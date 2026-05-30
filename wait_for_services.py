import socket
import time
import sys

def wait_for_port(port, name, timeout=120):
    start_time = time.time()
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect(('127.0.0.1', port))
                print(f"[Wait] {name} is ready on port {port}!", flush=True)
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            if time.time() - start_time > timeout:
                print(f"[Wait] Timeout waiting for {name} on port {port}", file=sys.stderr, flush=True)
                sys.exit(1)
            time.sleep(0.5)

if __name__ == '__main__':
    print("[Wait] Waiting for backend (8000) and frontend (3000)...", flush=True)
    wait_for_port(8000, "Backend (FastAPI)")
    wait_for_port(3000, "Frontend (Next.js)")
    print("[Wait] All services ready. Starting Nginx.", flush=True)
