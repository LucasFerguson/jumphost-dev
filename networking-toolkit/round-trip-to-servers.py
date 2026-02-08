import subprocess
import socket
import time
import platform

def get_ping(host):
	param = '-n' if platform.system().lower() == 'windows' else '-c'
	try:
		output = subprocess.check_output(['ping', param, '1', host], stderr=subprocess.STDOUT).decode('utf-8')
		if platform.system().lower() == 'windows':
			# Extract time from Windows output format
			return float(output.split('time=')[1].split('ms')[0])
		else:
			# Extract time from Linux/Mac output format
			return float(output.split('time=')[1].split(' ')[0])
	except:
		return None

def get_tcp(host, port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.settimeout(1.0)
	start = time.perf_counter()
	try:
		s.connect((host, port))
		duration = (time.perf_counter() - start) * 1000
		s.close()
		return duration
	except:
		return None

servers = [
	{"name": "TOR1 (Jump)", "ip": "...", "mc_port": 22},
	{"name": "TOR1 (Jump)", "ip": "...", "mc_port": 25565},
	{"name": "SFO3 (Jump)", "ip": "...", "mc_port": 22},
	{"name": "SFO3 (Jump)", "ip": "...", "mc_port": 25565}
]

print(f"{'Server Name':<15} | {'ICMP Ping':<12} | {'TCP Port Test':<15}")
print("-" * 50)

for srv in servers:
	p_times = []
	t_times = []
	for i in range(10):
		p_times.append(get_ping(srv['ip']))
		t_times.append(get_tcp(srv['ip'], srv['mc_port']))
  
	total = 0.0
	for t in p_times:
		total += t
	p_avg = total / len(p_times)
 
	total = 0.0
	for t in t_times:
		total += t
	t_avg = total / len(t_times)
	
	p_str = f"{p_avg:.2f}ms" if p_avg else "FAIL"
	t_str = f"{t_avg:.2f}ms" if t_avg else "CLOSED"
	
	print(f"{srv['name']:<15} | {p_str:<12} | {t_str:<15}")