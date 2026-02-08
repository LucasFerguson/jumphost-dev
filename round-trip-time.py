import subprocess
import platform

# Using known IP gateways for DO Regions
targets = {
    "Toronto (TOR1)": "159.203.0.1",
    "New York (NYC1)": "159.203.160.1",
    "New York (NYC3)": "159.65.240.1",
    "San Francisco (SFO3)": "143.110.224.1",
}

def run_diagnostics(name, ip):
    print(f"\n--- Testing {name} ({ip}) ---")
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    
    # Simple Ping
    try:
        ping = subprocess.check_output(['ping', param, '3', ip]).decode('utf-8')
        print("Ping: Success")
    except:
        print("Ping: Failed")

    # Quick Traceroute (limited to 10 hops for speed)
    trace_cmd = 'tracert' if platform.system().lower() == 'windows' else 'traceroute'
    try:
        # We only take the first few lines to see the initial Chicago exit points
        trace = subprocess.check_output([trace_cmd, '-m', '10', ip]).decode('utf-8')
        print("Traceroute (First 10 hops):")
        print("\n".join(trace.splitlines()[:10]))
    except:
        print("Traceroute: Failed")

for name, ip in targets.items():
    run_diagnostics(name, ip)

# Data From 2026-02-07
# Destination,Latency (ms),Route Taken
# Toronto (TOR1),~18ms,Chicago → Cleveland → Toronto
# New York (NYC1/3),~17ms,Chicago → Cleveland → Toronto*
# San Francisco (SFO3),~35ms,Chicago → Omaha → Denver → SLC