import subprocess
import time
import requests
import signal
import sys
import os

print("Step 1: Finding server process on port 8000...")
try:
    # Find process using port 8000
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True
    )

    pid = None
    for line in result.stdout.split('\n'):
        if ':8000' in line and 'LISTENING' in line:
            parts = line.split()
            if len(parts) >= 5:
                pid = parts[-1]
                break

    if pid:
        print(f"Found process PID: {pid}")

        # Kill it
        try:
            subprocess.run(["taskkill", "/F", "/PID", pid],
                          capture_output=True, check=True)
            print(f"Killed process {pid}")
        except:
            # Try alternative method
            os.kill(int(pid), signal.SIGTERM)
            print(f"Terminated process {pid}")
    else:
        print("No process found on port 8000")

except Exception as e:
    print(f"Error finding/killing process: {e}")

print("\nStep 2: Waiting for port to be released...")
time.sleep(2)

print("\nStep 3: Starting new server...")
# Start new server
server_proc = subprocess.Popen(
    [sys.executable, "Main.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

print(f"Server started with PID: {server_proc.pid}")

print("\nStep 4: Waiting for server to be ready...")
for i in range(10):
    try:
        resp = requests.get("http://127.0.0.1:8000/", timeout=2)
        if resp.status_code == 200:
            print("Server is ready!")
            break
    except:
        time.sleep(1)
        print(f"Waiting... ({i+1}/10)")
else:
    print("Server didn't start properly")

print("\nServer restarted successfully!")
print(f"Process ID: {server_proc.pid}")
print("\nYou can now test dynamic personas again.")
