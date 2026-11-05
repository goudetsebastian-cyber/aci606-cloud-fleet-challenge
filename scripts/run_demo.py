"""Open a local demo; terminate only children started by this invocation."""
from pathlib import Path
import os
import subprocess
import sys
import time
import webbrowser
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"


def ready():
    try:
        response = requests.get(BASE + "/health", timeout=2)
        return response.ok and response.json().get("service") == "aci606-cloud-fleet"
    except (requests.RequestException, ValueError):
        return False


if __name__ == "__main__":
    processes = []
    (ROOT / "tmp").mkdir(exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (ROOT / "tmp/demo.log").open("a", encoding="utf-8") as log:
        try:
            if not ready():
                environment = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
                processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT, env=environment, stdout=log, stderr=log, creationflags=flags))
                for _ in range(60):
                    if ready():
                        break
                    time.sleep(.5)
                else:
                    raise RuntimeError("No fue posible iniciar el servicio. Revisar tmp/demo.log")
            processes.append(subprocess.Popen([sys.executable, "simulator/fleet_simulator.py", "--api", BASE, "--robots", "6"], cwd=ROOT, stdout=log, stderr=log, creationflags=flags))
            webbrowser.open(BASE + "/dashboard")
            print("Panel abierto. Hay seis robots enviando datos.")
            input("Presiona Enter para detener esta demostración... ")
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
