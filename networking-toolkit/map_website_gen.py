#!/usr/bin/env python3
"""
generate_map.py

Reads route_map.json (new schema) and outputs route_map.html using Leaflet.

Expected input schema (new):
{
  "target": "...",
  "timestamp_unix": 123,
  "hops": [
    {
      "hop": 1,
      "ip": "1.2.3.4",
      "hostname": "optional-rdns",
      "avg_ms": 12.3,
      "loss_pct": 0.0,
      "marker": { "lat": 30.8, "lon": -90.6, "label": "Chicago, United States", "isp": "...", "source": "ip-api|override" },
      "geo": { ... }   # optional, richer
    }
  ]
}

Usage:
  python3 generate_map.py route_map.json route_map.html
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_marker(hop: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Prefer hop['marker'] (new map schema). Fallback to hop['geo'] if it has lat/lon.
    """
    m = hop.get("marker")
    if isinstance(m, dict) and m.get("lat") is not None and m.get("lon") is not None:
        return m

    g = hop.get("geo")
    if isinstance(g, dict) and g.get("lat") is not None and g.get("lon") is not None:
        # normalize into marker-like shape
        label_parts = [p for p in [g.get("city"), g.get("region"), g.get("country")] if p]
        return {
            "lat": g.get("lat"),
            "lon": g.get("lon"),
            "label": g.get("label") or ", ".join(label_parts) or None,
            "isp": g.get("isp"),
            "org": g.get("org"),
            "as": g.get("as"),
            "source": g.get("source"),
        }

    return None


def first_last_labels(points: List[Dict[str, Any]], fallback_a: str, fallback_b: str) -> Tuple[str, str]:
    """
    Build title from first and last available labels.
    """
    if not points:
        return fallback_a, fallback_b

    a = points[0].get("label") or fallback_a
    b = points[-1].get("label") or fallback_b

    # Keep titles short-ish: if label is massive, trim.
    def trim(s: str, n: int = 48) -> str:
        s = str(s)
        return s if len(s) <= n else (s[: n - 1] + "…")

    return trim(a), trim(b)


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python3 generate_map.py <route_map.json> <output.html>")
        return 2

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = load_json(in_path)
    hops = data.get("hops")
    if not isinstance(hops, list):
        print("Input JSON does not look like new schema; expected top-level {hops:[...]} object.")
        return 2

    # Extract usable points (only hops with markers)
    points: List[Dict[str, Any]] = []
    enriched_hops: List[Dict[str, Any]] = []

    for hop in hops:
        if not isinstance(hop, dict):
            continue
        m = pick_marker(hop)
        if not m:
            continue

        enriched = dict(hop)
        enriched["_marker"] = m
        points.append(m)
        enriched_hops.append(enriched)

    target = data.get("target") or data.get("destination") or "target"
    fallback_from = "Source"
    fallback_to = str(target)

    title_from, title_to = first_last_labels(points, fallback_from, fallback_to)
    page_title = f"PathFinder; {title_from} → {title_to}"

    # Prepare JS arrays
    js_points = [
        {
            "hop": h.get("hop"),
            "ip": h.get("ip"),
            "hostname": h.get("hostname"),
            "avg_ms": h.get("avg_ms") or h.get("latency") or h.get("Avg"),
            "loss_pct": h.get("loss_pct"),
            "sent": h.get("sent"),
            "label": h["_marker"].get("label"),
            "isp": h["_marker"].get("isp"),
            "source": h["_marker"].get("source"),
            "lat": h["_marker"].get("lat"),
            "lon": h["_marker"].get("lon"),
        }
        for h in enriched_hops
    ]

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(page_title)}</title>

  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

  <style>
    html, body {{
      height: 100%;
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial;
    }}

    .app {{
      display: grid;
      grid-template-columns: 340px 1fr;
      height: 100%;
    }}

    .sidebar {{
      border-right: 1px solid #e6e6e6;
      padding: 14px 14px 10px 14px;
      overflow: auto;
      background: #fff;
    }}

    .title {{
      font-size: 16px;
      font-weight: 700;
      margin: 0 0 6px 0;
      line-height: 1.2;
    }}

    .subtitle {{
      margin: 0 0 12px 0;
      font-size: 12px;
      color: #666;
    }}

    .chiprow {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 12px;
    }}

    .chip {{
      font-size: 12px;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid #ddd;
      background: #fafafa;
      color: #222;
      user-select: none;
    }}

    .hoplist {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .hop {{
      border: 1px solid #eee;
      border-radius: 10px;
      padding: 10px;
      cursor: pointer;
      transition: transform 0.06s ease, box-shadow 0.06s ease;
    }}

    .hop:hover {{
      transform: translateY(-1px);
      box-shadow: 0 4px 14px rgba(0,0,0,0.06);
    }}

    .hopline1 {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 12px;
      font-weight: 650;
    }}

    .hopline2 {{
      margin-top: 6px;
      font-size: 12px;
      color: #555;
    }}

    .hopline3 {{
      margin-top: 6px;
      font-size: 11px;
      color: #777;
    }}

    #map {{
      height: 100%;
      width: 100%;
    }}

    /* Pulsing dashed path overlay */
    .path-pulse {{
      stroke-dasharray: 10 18;
      animation: flow 1.7s linear infinite;
    }}

    @keyframes flow {{
      from {{ stroke-dashoffset: 70; }}
      to   {{ stroke-dashoffset: 0; }}
    }}

    /* Make Leaflet SVG paths prettier */
    .leaflet-overlay-pane svg path {{
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
  </style>
</head>

<body>
  <div class="app">
    <div class="sidebar">
      <h1 class="title">{esc(title_from)} → {esc(title_to)}</h1>
      <p class="subtitle">PathFinder Visualizer; {esc(in_path.name)}</p>

      <div class="chiprow">
        <div class="chip">Hops with geo: {len(js_points)}</div>
        <div class="chip">Target: {esc(target)}</div>
      </div>

      <div class="hoplist" id="hoplist"></div>
    </div>

    <div id="map"></div>
  </div>

<script>
  const hops = {json.dumps(js_points, ensure_ascii=False)};

  const map = L.map('map', {{
    zoomControl: true,
    worldCopyJump: true
  }});

  // Base map tiles
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);

  // Build LatLngs
  const latlngs = hops.map(h => [h.lat, h.lon]);

  // Fit bounds if we have points, otherwise default view
  if (latlngs.length > 0) {{
    map.fitBounds(latlngs, {{ padding: [30, 30] }});
  }} else {{
    map.setView([20, 0], 2);
  }}

  // Add markers
  const markers = [];
  for (const h of hops) {{
    const popupHtml = `
      <div style="min-width: 240px">
        <div style="font-weight: 700; margin-bottom: 6px;">Hop ${'{'}h.hop{'}'}; ${'{'}(h.label || h.ip || '???'){'}'}</div>
        <div style="font-size: 12px; color:#444;">
          <div><b>IP:</b> ${'{'}(h.ip || '???'){'}'}</div>
          <div><b>rDNS:</b> ${'{'}(h.hostname || 'n/a'){'}'}</div>
          <div><b>Avg:</b> ${'{'}(h.avg_ms != null ? (Number(h.avg_ms).toFixed(2) + ' ms') : 'n/a'){'}'}</div>
          <div><b>Loss:</b> ${'{'}(h.loss_pct != null ? (Number(h.loss_pct).toFixed(1) + '%') : 'n/a'){'}'}</div>
          <div><b>ISP:</b> ${'{'}(h.isp || 'n/a'){'}'}</div>
          <div><b>Source:</b> ${'{'}(h.source || 'n/a'){'}'}</div>
        </div>
      </div>
    `;
    const m = L.marker([h.lat, h.lon]).addTo(map).bindPopup(popupHtml);
    markers.push(m);
  }}

  // Main path (solid)
  const basePath = L.polyline(latlngs, {{
    color: "#2563eb",
    weight: 4,
    opacity: 0.55
  }}).addTo(map);

  // Pulse overlay (dashed animated)
  const pulsePath = L.polyline(latlngs, {{
    color: "#111827",
    weight: 3,
    opacity: 0.9,
    className: "path-pulse"
  }}).addTo(map);

  // Sidebar list
  const hoplist = document.getElementById("hoplist");

  function fmtMs(x) {{
    if (x == null) return "n/a";
    const n = Number(x);
    if (!Number.isFinite(n)) return "n/a";
    return n.toFixed(2) + "ms";
  }}

  function hopTitle(h) {{
    // Prefer readable location label; else IP
    return (h.label || h.ip || "???");
  }}

  for (let i = 0; i < hops.length; i++) {{
    const h = hops[i];
    const el = document.createElement("div");
    el.className = "hop";
    el.innerHTML = `
      <div class="hopline1">
        <div>[${'{'}String(h.hop).padStart(2,'0'){'}'}] ${'{'}hopTitle(h){'}'}</div>
        <div>${'{'}fmtMs(h.avg_ms){'}'}</div>
      </div>
      <div class="hopline2">📍 ${'{'}(h.label || "unknown"){'}'}</div>
      <div class="hopline3">🏢 ${'{'}(h.isp || "n/a"){'}'} | IP ${'{'}(h.ip || "???"){'}'}</div>
    `;
    el.addEventListener("click", () => {{
      const m = markers[i];
      if (m) {{
        map.setView(m.getLatLng(), Math.max(map.getZoom(), 6), {{ animate: true }});
        m.openPopup();
      }}
    }});
    hoplist.appendChild(el);
  }}

  // If there are no points, warn in sidebar
  if (hops.length === 0) {{
    const w = document.createElement("div");
    w.className = "hop";
    w.innerHTML = `
      <div class="hopline1"><div>No geo points found</div><div></div></div>
      <div class="hopline2">Your JSON has no hops with marker.lat/lon.</div>
      <div class="hopline3">Make sure your tracer wrote marker fields, or add overrides.</div>
    `;
    hoplist.appendChild(w);
  }}
</script>
</body>
</html>
"""

    out_path.write_text(html_doc, encoding="utf-8")
    print(f"✅ Wrote: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
