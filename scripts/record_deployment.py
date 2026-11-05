"""Record a real PostgreSQL-backed public endpoint, never a proposed URL."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    base = args.url.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query:
        parser.error("Se requiere URL HTTPS pública, sin credenciales ni consultas")
    repository = urlparse(args.repository)
    if repository.scheme != "https" or repository.netloc != "github.com" or len(repository.path.strip("/").split("/")) != 2:
        parser.error("Se requiere la URL HTTPS del repositorio GitHub propio")
    response = requests.get(base + "/health", timeout=90)
    response.raise_for_status()
    assert response.json()["database"] == "postgresql", "El servicio público debe utilizar PostgreSQL"
    smoke = ROOT / "reports/public_smoke.json"
    persistence = ROOT / "reports/persistence_snapshot.json"
    evaluation = ROOT / "reports/remote_evaluation.json"
    automatic = ROOT / "reports/autodeploy_check.json"
    other_device = ROOT / "reports/other_device_check.json"
    def verified(path, field):
        if not path.is_file():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("api_url", "").rstrip("/") == base and data.get(field) is True
    contract = verified(smoke, "passed")
    restart = verified(persistence, "restart_verified")
    quality = verified(evaluation, "passed")
    auto = verified(automatic, "passed")
    device_data = json.loads(other_device.read_text(encoding="utf-8")) if other_device.is_file() else {}
    device = device_data.get("verified") is True and device_data.get("public_url") == base + "/dashboard"
    complete = contract and restart and quality and auto and device
    status = {"status": "verified" if complete else "deployed_pending_verification", "public_url": base, "repository_url": args.repository, "platform": "Render", "data_location": "Neon PostgreSQL", "public_contract_verified": contract, "public_restart_verified": restart, "public_quality_verified": quality, "auto_deploy_verified": auto, "other_device_verified": device}
    (ROOT / "reports/deployment_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = ROOT / "README.md"
    content = readme.read_text(encoding="utf-8")
    start, end = "<!-- deployment:start -->", "<!-- deployment:end -->"
    block = f"{start}\nServicio: **[{base}]({base})** · [Panel]({base}/dashboard) · [API]({base}/docs)\n\nRepositorio: [{args.repository}]({args.repository})\n\nVerificación pública: {'completa' if complete else 'pendiente de completar pruebas; revisar reports/deployment_status.json'}.\n{end}"
    readme.write_text(content.split(start)[0] + block + content.split(end)[1], encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
