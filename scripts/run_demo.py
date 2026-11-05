"""Open a local or cloud demo; stop only children started by this invocation."""
import argparse
from pathlib import Path
import os
import subprocess
import sys
import time
import webbrowser
import requests

ROOT = Path(__file__).resolve().parents[1]
LOCAL_BASE = "http://127.0.0.1:8000"


def ready(base, timeout=2):
    try:
        response = requests.get(base + "/health", timeout=timeout)
        return response.ok and response.json().get("service") == "aci606-cloud-fleet"
    except (requests.RequestException, ValueError):
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=LOCAL_BASE)
    args = parser.parse_args()
    base = args.api.rstrip("/")
    processes = []
    (ROOT / "tmp").mkdir(exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (ROOT / "tmp/demo.log").open("a", encoding="utf-8") as log:
        try:
            if base != LOCAL_BASE:
                print("Conectando con el servicio en la nube; el arranque puede tardar un minuto...")
                deadline = time.monotonic() + 120
                while not ready(base, timeout=10):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("El servicio no responde. Revisar su URL pública y volver a intentar.")
                    time.sleep(2)
            elif not ready(base):
                environment = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
                processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT, env=environment, stdout=log, stderr=log, creationflags=flags))
                for _ in range(60):
                    if ready(base):
                        break
                    time.sleep(.5)
                else:
                    raise RuntimeError("No fue posible iniciar el servicio. Revisar tmp/demo.log")
            processes.append(subprocess.Popen([sys.executable, "simulator/fleet_simulator.py", "--api", base, "--robots", "6"], cwd=ROOT, stdout=log, stderr=log, creationflags=flags))
            webbrowser.open(base + "/dashboard")
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
