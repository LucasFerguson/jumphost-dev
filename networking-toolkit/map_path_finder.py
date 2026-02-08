#!/usr/bin/env python3
"""
pathfinder.py
mtr route mapping (no DNS) + GeoIP enrichment + optional reverse DNS.

Usage:
  python3 pathfinder.py <target>
  python3 pathfinder.py <target> -c 5 --rdns
  python3 pathfinder.py <target> --out route_map.json --rdns --rdns-timeout 1.0
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import random
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

import requests


# ----------------------------
# User maintained local overrides
# Put your private IP knowledge here.
# Supports exact IP keys and CIDR keys.
# ----------------------------

LOCAL_IP_OVERRIDES: Dict[str, Dict[str, Any]] = {
    # Exact IP example:
    # "10.0.0.1": {"label": "Core Router, Chicago, US", "lat": 41.8781, "lon": -87.6298, "isp": "HomeLab"},
    #
    # CIDR example:
    # "10.0.0.0/24": {"label": "VLAN10, Chicago, US", "lat": 41.8781, "lon": -87.6298, "isp": "HomeLab"},
}


# ----------------------------
# Regex helpers
# ----------------------------

IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def looks_like_ipv4(s: Optional[str]) -> bool:
    if not s:
        return False
    if not IPV4_RE.match(s):
        return False
    # Basic octet sanity check
    try:
        parts = [int(x) for x in s.split(".")]
        return all(0 <= p <= 255 for p in parts)
    except Exception:
        return False


# ----------------------------
# Geo lookup (free, no token)
# ----------------------------

IP_API_BASE = "http://ip-api.com/json/{q}"
IP_API_FIELDS = "status,message,country,regionName,city,lat,lon,isp,org,as,query"


def geo_from_ip_api(
    session: requests.Session,
    ip: str,
    timeout_s: float,
    retries: int,
    backoff_s: float,
) -> Optional[Dict[str, Any]]:
    """
    Uses ip-api.com free JSON endpoint.
    If private/reserved IP: often returns status=fail; we handle it and return None.
    """
    if not ip or ip == "???":
        return None

    url = IP_API_BASE.format(q=ip)
    params = {"fields": IP_API_FIELDS}

    for attempt in range(retries + 1):
        try:
            r = session.get(url, params=params, timeout=timeout_s)
            if r.status_code == 429:
                # rate limited; exponential backoff + jitter
                sleep_s = backoff_s * (2**attempt) + random.uniform(0, 0.25)
                time.sleep(min(sleep_s, 8.0))
                continue

            r.raise_for_status()
            data = r.json()
            if data.get("status") != "success":
                return None

            return {
                "ip": data.get("query"),
                "city": data.get("city"),
                "region": data.get("regionName"),
                "country": data.get("country"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "isp": data.get("isp"),
                "org": data.get("org"),
                "as": data.get("as"),
                "source": "ip-api",
            }
        except requests.RequestException:
            if attempt < retries:
                sleep_s = backoff_s * (2**attempt) + random.uniform(0, 0.25)
                time.sleep(min(sleep_s, 8.0))
                continue
            return None
        except ValueError:
            return None

    return None


def geo_from_overrides(ip: str) -> Optional[Dict[str, Any]]:
    """
    Match exact IP first; then any CIDR keys.
    """
    if not ip:
        return None

    # Exact match
    if ip in LOCAL_IP_OVERRIDES:
        g = dict(LOCAL_IP_OVERRIDES[ip])
        g["ip"] = ip
        g["source"] = "override"
        return g

    # CIDR match
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return None

    for k, v in LOCAL_IP_OVERRIDES.items():
        if "/" not in k:
            continue
        try:
            net = ipaddress.ip_network(k, strict=False)
        except ValueError:
            continue
        if ip_obj in net:
            g = dict(v)
            g["ip"] = ip
            g["source"] = "override"
            g["matched_cidr"] = k
            return g

    return None


def geo_lookup(
    session: requests.Session,
    ip: str,
    timeout_s: float,
    retries: int,
    backoff_s: float,
) -> Optional[Dict[str, Any]]:
    """
    Override first; then free API.
    Includes private IPs by design.
    """
    g = geo_from_overrides(ip)
    if g:
        return g
    return geo_from_ip_api(session, ip, timeout_s, retries, backoff_s)


def marker_from_geo(geo: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not geo:
        return None
    if geo.get("lat") is None or geo.get("lon") is None:
        return None

    label_parts = [p for p in [geo.get("city"), geo.get("region"), geo.get("country")] if p]
    label = geo.get("label") or ", ".join(label_parts) or None

    return {
        "lat": geo["lat"],
        "lon": geo["lon"],
        "label": label,
        "isp": geo.get("isp"),
        "org": geo.get("org"),
        "as": geo.get("as"),
        "source": geo.get("source"),
    }


# ----------------------------
# Reverse DNS
# ----------------------------

def rdns_lookup(ip: str, timeout_s: float) -> Optional[str]:
    """
    Reverse DNS lookup; returns hostname or None.
    """
    if not looks_like_ipv4(ip):
        return None

    # socket.gethostbyaddr uses system resolver; set default timeout
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout_s)
    try:
        name, _aliases, _addrs = socket.gethostbyaddr(ip)
        return name
    except Exception:
        return None
    finally:
        socket.setdefaulttimeout(old_timeout)


# ----------------------------
# mtr execution + parsing
# ----------------------------

def run_mtr_json(target: str, cycles: int, interval: float) -> Dict[str, Any]:
    """
    Force --no-dns; we want hop identity to be IP-like and consistent.
    Tries --json then -j for compatibility.
    """
    base = [
        "mtr",
        "--report",
        "--no-dns",
        "--report-wide",
        "--report-cycles",
        str(cycles),
        "--interval",
        str(interval),
    ]

    for json_flag in (["--json"], ["-j"]):
        cmd = base + json_flag + [target]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            # If --json unsupported, try -j
            if json_flag == ["--json"] and ("unknown option" in stderr.lower() or "unrecognized option" in stderr.lower()):
                continue
            raise RuntimeError(f"mtr failed (code {proc.returncode}): {stderr}")

        out = (proc.stdout or "").strip()
        if not out:
            continue

        try:
            return json.loads(out)
        except json.JSONDecodeError as e:
            snippet = out[:400].replace("\n", "\\n")
            raise RuntimeError(f"Failed to parse mtr JSON: {e}; output starts: {snippet}")

    raise RuntimeError("Could not run mtr with JSON output; tried --json and -j.")


def get_hops(raw_mtr: Dict[str, Any]) -> List[Dict[str, Any]]:
    report = raw_mtr.get("report") or {}
    hubs = report.get("hubs") or []
    return hubs


def pick_ip_from_hub(hub: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    In --no-dns mode, many builds put the numeric hop identity in hub['host'].
    Some builds also have ipaddr, but it is not guaranteed.
    We want:
      ip = best guess at numeric IP
      host_field = original hub['host'] value for debugging
    """
    host_field = hub.get("host")
    ip = hub.get("ipaddr") or hub.get("ip") or hub.get("address")

    # In no-dns mode, host is often the IP
    if not ip and isinstance(host_field, str) and looks_like_ipv4(host_field):
        ip = host_field

    # Sometimes weird data; keep ip as None if we cannot confirm it is an IP
    if ip and not looks_like_ipv4(ip):
        ip = None

    return ip, host_field if isinstance(host_field, str) else None


def fnum(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def inum(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(x)
    except Exception:
        return None


# ----------------------------
# Main
# ----------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="mtr (no-dns) + GeoIP + optional reverse DNS, outputs JSON + pretty lines.")
    p.add_argument("target", help="Target hostname or IP.")
    p.add_argument("-c", "--cycles", type=int, default=2, help="Report cycles per hop.")
    p.add_argument("-i", "--interval", type=float, default=1.0, help="Interval seconds.")
    p.add_argument("--out", default="route_map.json", help="Output JSON file path.")

    p.add_argument("--geo-timeout", type=float, default=5.0)
    p.add_argument("--geo-retries", type=int, default=2)
    p.add_argument("--geo-backoff", type=float, default=0.5)

    p.add_argument("--rdns", action="store_true", help="Do reverse DNS on hop IPs.")
    p.add_argument("--rdns-timeout", type=float, default=1.0)

    p.add_argument("--include-raw-mtr", action="store_true", help="Embed raw mtr JSON in output.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    print(f"📡 SCANNING ROUTE TO: {args.target}")
    print("=" * 88)

    try:
        raw = run_mtr_json(args.target, args.cycles, args.interval)
    except FileNotFoundError:
        print("mtr not found; install it first.", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Failed to run mtr: {e}", file=sys.stderr)
        return 2

    hubs = get_hops(raw)
    session = requests.Session()

    hops_out: List[Dict[str, Any]] = []

    for hub in hubs:
        hop_num = inum(hub.get("count")) or -1

        ip, host_field = pick_ip_from_hub(hub)

        loss_pct = fnum(hub.get("Loss%")) or fnum(hub.get("Loss")) or fnum(hub.get("loss"))
        sent = inum(hub.get("Snt")) or inum(hub.get("Sent")) or inum(hub.get("snt"))
        last_ms = fnum(hub.get("Last"))
        avg_ms = fnum(hub.get("Avg"))
        best_ms = fnum(hub.get("Best"))
        worst_ms = fnum(hub.get("Wrst")) or fnum(hub.get("Worst"))
        stdev_ms = fnum(hub.get("StDev")) or fnum(hub.get("Stdev"))

        # If 100% loss and no IP, skip lookups
        geo = None
        marker = None
        rdns = None

        if ip:
            geo = geo_lookup(session, ip, args.geo_timeout, args.geo_retries, args.geo_backoff)
            marker = marker_from_geo(geo)
            if args.rdns:
                rdns = rdns_lookup(ip, args.rdns_timeout)

        # Pretty print like your desired format
        ms_str = f"{avg_ms:.2f}ms" if avg_ms is not None else "n/a"
        ip_print = ip or "???"
        hop_label = f"{hop_num:02}" if hop_num >= 0 else "??"

        print(f"[{hop_label}] {ip_print:<34} | {ms_str:>8}")

        if marker:
            loc = marker.get("label") or "(unknown location)"
            isp = marker.get("isp") or "Unknown ISP"
            print(f"     📍 {loc} | 🏢 {isp}")
        else:
            print("     📍 (no geo)")

        if rdns:
            print(f"     🔎 rDNS: {rdns}")

        # Include host_field for debugging if mtr gives something odd
        if host_field and host_field != ip:
            print(f"     🧩 mtr_host_field: {host_field}")

        print("-" * 88)

        hops_out.append({
            "hop": hop_num,
            "ip": ip,
            "hostname": rdns,            # we define hostname as our rDNS result
            "mtr_host_field": host_field, # what mtr gave us in hub['host']
            "loss_pct": loss_pct,
            "sent": sent,
            "last_ms": last_ms,
            "avg_ms": avg_ms,
            "best_ms": best_ms,
            "worst_ms": worst_ms,
            "stdev_ms": stdev_ms,
            "geo": geo,
            "marker": marker,
        })

    out_obj: Dict[str, Any] = {
        "target": args.target,
        "timestamp_unix": int(time.time()),
        "hops": hops_out,
    }

    if args.include_raw_mtr:
        out_obj["raw_mtr"] = raw

    out_path = Path(args.out)
    out_path.write_text(json.dumps(out_obj, indent=2), encoding="utf-8")

    print(f"\n✅ Success! JSON saved to: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
