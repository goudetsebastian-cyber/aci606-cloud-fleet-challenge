"""Package source, measured evidence, dataset and real Git history; exclude secrets."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DELIVERY=ROOT.parent/"Entrega_Ejercicio4"
ARCHIVE=ROOT.parent/"Entrega_Ejercicio4.zip"


def checked_destination(relative):
    destination=(DELIVERY/relative).resolve()
    if not destination.is_relative_to(DELIVERY.resolve()):
        raise ValueError("Destino fuera de la entrega")
    return destination


if __name__ == "__main__":
    deployment=json.loads((ROOT/"reports/deployment_status.json").read_text(encoding="utf-8"))
    if deployment.get("status")!="verified":
        raise SystemExit("Completar las verificaciones públicas antes de empaquetar")
    DELIVERY.mkdir(exist_ok=True)
    files=subprocess.check_output(["git","ls-files"],cwd=ROOT,text=True).splitlines()
    packaged=[]
    for name in files:
        if name==".env" or (name.startswith(".env.") and name!=".env.example"):
            raise ValueError("Archivo de credenciales en Git")
        source=(ROOT/name).resolve()
        if not source.is_relative_to(ROOT):
            raise ValueError("Origen fuera del proyecto")
        relative=Path("codigo")/name
        destination=checked_destination(relative)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
        packaged.append(relative)
    dataset=checked_destination(Path("codigo/data/training.csv"))
    dataset.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/"data/training.csv",dataset)
    packaged.append(Path("codigo/data/training.csv"))
    pdf=checked_destination(Path("Informe_tecnico_Ejercicio4.pdf"))
    shutil.copy2(ROOT/"output/pdf/Informe_tecnico_Ejercicio4.pdf",pdf)
    packaged.append(pdf.relative_to(DELIVERY))
    bundle=checked_destination(Path("repositorio.bundle"))
    subprocess.run(["git","bundle","create",str(bundle),"main","feature/cloud-platform"],cwd=ROOT,check=True)
    subprocess.run(["git","bundle","verify",str(bundle)],cwd=ROOT,check=True,capture_output=True)
    packaged.append(bundle.relative_to(DELIVERY))
    evaluation=json.loads((ROOT/"reports/remote_evaluation.json").read_text(encoding="utf-8"))
    guide=f"""# Entrega del Ejercicio 4 - Cloud Fleet Challenge

Servicio: {deployment['public_url']}
Panel: {deployment['public_url']}/dashboard
API interactiva: {deployment['public_url']}/docs
Repositorio: {deployment['repository_url']}

## Contenido

- Informe_tecnico_Ejercicio4.pdf: arquitectura, EDA, comparación de modelos y evidencia local/pública.
- codigo/: implementación completa, modelo entrenado, datos y documentación.
- codigo/docs/DEFENSA.md: guion y respuestas para la defensa.
- codigo/docs/ALINEACION_CLASES.md: revisión de la solución frente a los materiales de persistencia del curso.
- codigo/VER_DEMO_NUBE.cmd: abre el panel público y conecta seis robots, una vez preparado el entorno.
- repositorio.bundle: historial Git real, rama de funcionalidad y merge a main. No basta con subir archivos sueltos para conservar la trazabilidad.

## Resultados comprobados

41 pruebas de servicio aprobadas, también verificadas en GitHub sobre Linux.
Evaluación pública: {evaluation['successful']}/{evaluation['requests']} respuestas válidas, {evaluation['errors']} solicitudes fallidas, F1 macro {evaluation['macro_f1']:.4f}, p95 {evaluation['client_latency_p95_ms']:.2f} ms desde el cliente.
125 muestras intactas después de reiniciar Render, comprobadas por hash e identificador de proceso.
Acceso desde otro dispositivo confirmado por el estudiante.

## Antes de defender

Abrir /health y esperar el arranque del servicio gratuito. Iniciar el simulador hacia la URL pública con el lanzador o el comando indicado en el README. La API y la base no dependen de mantener este computador encendido; el simulador es solo el cliente que genera datos.

El historial y las predicciones están en PostgreSQL gestionado en Neon. Las credenciales no están en este paquete. Para ejecutar o recrear el servicio, seguir codigo/README.md y codigo/docs/DEPLOYMENT.md.
"""
    intro=checked_destination(Path("LEEME_ENTREGA.md"))
    intro.write_text(guide,encoding="utf-8")
    packaged.append(intro.relative_to(DELIVERY))
    manifest={str(relative).replace("\\","/"):hashlib.sha256((DELIVERY/relative).read_bytes()).hexdigest() for relative in packaged}
    manifest_path=checked_destination(Path("SHA256.json"))
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    packaged.append(manifest_path.relative_to(DELIVERY))
    with zipfile.ZipFile(ARCHIVE,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=8) as target:
        for relative in sorted(packaged):
            target.write(DELIVERY/relative,Path("Entrega_Ejercicio4")/relative)
    with zipfile.ZipFile(ARCHIVE) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archivo ZIP dañado")
        names=archive.namelist()
        assert not any(name.endswith((".env", ".env.neon")) for name in names)
        assert any(name.endswith("models/model.joblib") for name in names)
        assert any(name.endswith("repositorio.bundle") for name in names)
    print(json.dumps({"archive":str(ARCHIVE),"bytes":ARCHIVE.stat().st_size,"files":len(packaged),"pdf":str(pdf)},ensure_ascii=False,indent=2))
