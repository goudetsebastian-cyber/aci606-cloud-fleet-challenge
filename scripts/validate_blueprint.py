"""Check render.yaml against Render's current official JSON schema."""
import json
from pathlib import Path
import requests
import yaml
import jsonschema

ROOT=Path(__file__).resolve().parents[1]
SCHEMA_URL="https://render.com/schema/render.yaml.json"

if __name__ == "__main__":
    response=requests.get(SCHEMA_URL,timeout=30)
    response.raise_for_status()
    config=yaml.safe_load((ROOT/"render.yaml").read_text(encoding="utf-8"))
    jsonschema.validate(config,response.json())
    result={"valid":True,"schema_url":SCHEMA_URL,"services":len(config["services"]),"plan":config["services"][0]["plan"]}
    (ROOT/"reports/render_blueprint_validation.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result))
