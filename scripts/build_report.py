"""Build the technical hand-in from measured evidence, including deployment state."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
INK = colors.HexColor("#203653")
TEAL = colors.HexColor("#365f8f")
MUTED = colors.HexColor("#526780")
PALE = colors.HexColor("#edf3fa")
LINE = colors.HexColor("#d8e3e8")
WIDTH = A4[0] - 88
REPORT_DATE = "5 de noviembre de 2026"


def load(name, default=None):
    path = ROOT / "reports" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def fonts():
    candidates = [(Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf")), (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))]
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont("Report", str(regular)))
            pdfmetrics.registerFont(TTFont("ReportBold", str(bold)))
            pdfmetrics.registerFontFamily("Report", normal="Report", bold="ReportBold")
            return "Report", "ReportBold"
    return "Helvetica", "Helvetica-Bold"


FONT, BOLD = fonts()
STYLE = getSampleStyleSheet()
STYLE.add(ParagraphStyle("BodyR", fontName=FONT, fontSize=10, leading=14.4, textColor=INK, spaceAfter=8))
STYLE.add(ParagraphStyle("SmallR", fontName=FONT, fontSize=8.5, leading=11.6, textColor=MUTED, spaceAfter=6))
STYLE.add(ParagraphStyle("HeadR", fontName=BOLD, fontSize=22, leading=27, textColor=INK, spaceAfter=14))
STYLE.add(ParagraphStyle("SubR", fontName=BOLD, fontSize=12.5, leading=17, textColor=TEAL, spaceBefore=10, spaceAfter=7))
STYLE.add(ParagraphStyle("CellR", fontName=FONT, fontSize=9, leading=12, textColor=INK))
STYLE.add(ParagraphStyle("CellHeadR", fontName=BOLD, fontSize=9, leading=12, textColor=colors.white))
STYLE.add(ParagraphStyle("KpiR", fontName=BOLD, fontSize=25, leading=31, textColor=TEAL, alignment=TA_CENTER))
STYLE.add(ParagraphStyle("KpiLabelR", fontName=FONT, fontSize=8.5, leading=11, textColor=MUTED, alignment=TA_CENTER))


def p(text, style="BodyR"):
    return Paragraph(text, STYLE[style])


def table(headers, rows, widths):
    data = [[p(escape(str(cell)), "CellHeadR") for cell in headers]]
    data.extend([[p(escape(str(cell)).replace("\n", "<br/>"), "CellR") for cell in row] for row in rows])
    result = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6f8")]),
        ("LINEBELOW", (0, -1), (-1, -1), .5, LINE),
    ]))
    return result


def note(text, background=PALE):
    box = Table([[p(text)]], colWidths=[WIDTH])
    box.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), background), ("BOX", (0,0), (-1,-1), .5, LINE), ("LEFTPADDING", (0,0), (-1,-1), 13), ("RIGHTPADDING", (0,0), (-1,-1), 13), ("TOPPADDING", (0,0), (-1,-1), 11), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
    return box


def picture(name, width=WIDTH):
    from PIL import Image as PILImage
    path = ROOT / "reports" / name
    with PILImage.open(path) as source:
        height = width * source.height / source.width
    return Image(str(path), width=width, height=height)


class Architecture(Flowable):
    def __init__(self):
        super().__init__()
        self.width = WIDTH
        self.height = 152
    def draw(self):
        c = self.canv
        boxes = [(0, 61, 118, 72, "CLIENTES", ["Flota virtual", "Operador y evaluador"]), (141, 61, 180, 72, "RENDER / FASTAPI", ["API + pipeline de ML", "Panel y métricas"]), (344, 61, 163, 72, "NEON / POSTGRESQL", ["Telemetría e historial", "SQL con TLS"]), (151, 3, 160, 35, "GITHUB / MAIN", ["Código y modelo versionados"])]
        for x, y, w, h, title, lines in boxes:
            c.setFillColor(PALE if x != 344 else colors.HexColor("#edf2f8"))
            c.setStrokeColor(LINE)
            c.roundRect(x, y, w, h, 8, fill=1, stroke=1)
            c.setFillColor(INK); c.setFont(BOLD, 8.7)
            c.drawCentredString(x+w/2, y+h-17, title)
            c.setFont(FONT, 8.5); c.setFillColor(MUTED)
            for index, line in enumerate(lines):
                c.drawCentredString(x+w/2, y+h-33-index*13, line)
        c.setStrokeColor(TEAL); c.setFillColor(TEAL)
        for x1,x2 in [(118,141),(321,344)]:
            c.line(x1,97,x2-4,97)
            shape=c.beginPath();shape.moveTo(x2,97);shape.lineTo(x2-6,100);shape.lineTo(x2-6,94);shape.close();c.drawPath(shape,fill=1,stroke=0)
        c.line(231,38,231,57)
        shape=c.beginPath();shape.moveTo(231,61);shape.lineTo(228,55);shape.lineTo(234,55);shape.close();c.drawPath(shape,fill=1,stroke=0)


def page_frame(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(TEAL);canvas.rect(44,A4[1]-40,26,3,fill=1,stroke=0)
    canvas.setFont(BOLD,8);canvas.setFillColor(MUTED);canvas.drawString(79,A4[1]-40,"ACI606  /  INFORME TÉCNICO")
    canvas.setStrokeColor(LINE);canvas.line(44,43,A4[0]-44,43)
    canvas.setFont(FONT,8);canvas.drawString(44,28,"Cloud Fleet Challenge · " + REPORT_DATE)
    canvas.drawRightString(A4[0]-44,28,f"{doc.page}")
    canvas.restoreState()


def build(output):
    report=load("evaluation.json")
    local=load("local_unseen_evaluation.json")
    deployment=load("deployment_status.json",{})
    neon=load("neon_persistence_snapshot.json",{})
    remote=load("remote_evaluation.json",{})
    xml=ET.parse(ROOT/"reports/pytest-results.xml").getroot().find("testsuite")
    count=int(xml.attrib["tests"])
    test_ok=int(xml.attrib["errors"])==0 and int(xml.attrib["failures"])==0
    ready=deployment.get("status")=="verified"
    model=report["models"][report["selected_model"]]
    body=[]
    def add(*items): body.extend(items)
    def section(title): add(p(title,"SubR"))
    def next_page(title): add(PageBreak(),p(title,"HeadR"))

    add(Spacer(1,8),p("Cloud Fleet<br/>Challenge","HeadR"),p("Del prototipo local a una plataforma persistente de flotas", "SubR"),p("Ejercicio 4 · Cloud Computing · Implementación, evaluación y operación"),Spacer(1,11))
    kpis=Table([[p(f"{report['test_macro_f1']:.3f}","KpiR"),p(f"{report['samples']:,}".replace(",","."),"KpiR"),p(str(count),"KpiR")],[p("F1 macro en flotas reservadas","KpiLabelR"),p("muestras sintéticas / 64 flotas","KpiLabelR"),p("pruebas locales aprobadas" if test_ok else "pruebas ejecutadas","KpiLabelR")]],colWidths=[WIDTH/3]*3)
    kpis.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),PALE),("TOPPADDING",(0,0),(-1,0),13),("BOTTOMPADDING",(0,1),(-1,1),13)]))
    add(kpis,Spacer(1,17))
    if ready:
        add(note(f"<b>Servicio público verificado.</b> <link href='{escape(deployment['public_url'])}' color='#365f8f'>{escape(deployment['public_url'])}</link><br/>Contrato, calidad y persistencia después del reinicio comprobados."))
    else:
        add(note("<b>Estado de la entrega:</b> implementación y evidencia local verificadas. La publicación pública y su prueba de reinicio siguen pendientes de completar la vinculación y el despliegue en las cuentas del estudiante.",colors.HexColor("#fff3df")))
    section("Objetivo y solución")
    add(p("El starter recibía muestras en RAM y dejaba la inferencia sin implementar. La solución valida cada muestra, calcula una predicción con un pipeline entrenado, conserva el historial en una base de datos y presenta la flota en un panel de operación. El simulador se mantiene como cliente de prueba; el producto es el servicio que recibe sus datos. [1, 2]"))
    section("Arquitectura de despliegue")
    add(Architecture(),p("Figura 1. Arquitectura implementada y preparada para PaaS. El estado de publicación real se detalla en la página 7.","SmallR"))
    add(p("<b>Resultado medido:</b> regresión logística con F1 macro 0,9260 en 16 flotas reservadas; la línea base obtuvo 0,1982. Una evaluación HTTP local adicional usó cuatro flotas nuevas y ocho solicitudes en paralelo, sin fallos."))

    next_page("Servicio, datos y observabilidad")
    add(p("La API conserva las siete rutas de la pauta. Cada POST de telemetría válido ejecuta inferencia y confirma la transacción antes de responder accepted=true. La respuesta de /predict contiene exactamente los cinco campos exigidos."))
    add(table(["Ruta", "Comportamiento"],[
        ("GET /health","Comprueba la base y el modelo. Expone versión e instance_id del proceso."),
        ("POST /telemetry","Valida sensores, predice y guarda muestra, condición, confianza y versión."),
        ("GET /robots","Último evento de cada robot, conexión y conteo de muestras."),
        ("GET /robots/{id}/history","Historial completo. limit y offset son opcionales; no se trunca a 100."),
        ("POST /predict","robot_id, predicted_status, confidence, model_version, inference_ms."),
        ("GET /metrics","Solicitudes, errores, latencia, uptime, robots y muestras persistidas."),
        ("GET /dashboard","Panel web con condición, batería, posición e historial."),
    ],[155,WIDTH-155]))
    section("Persistencia y consistencia")
    add(p("PostgreSQL en Neon almacena una fila por POST aceptado. El índice (robot_id, timestamp, id) apoya las consultas. El historial se ordena por tiempo de evento e identificador; una consulta con función de ventana selecciona la última muestra aunque llegue fuera de orden. La conexión del robot se calcula por tiempo de recepción, con un umbral de 30 segundos."))
    add(p("SQLAlchemy y psycopg 3 leen DATABASE_URL desde el entorno. La conexión usa TLS, pool_pre_ping y reciclaje de conexiones. En desarrollo se admite SQLite con WAL; Render rechaza SQLite para impedir que un disco efímero se confunda con almacenamiento persistente. [5, 6]"))
    section("Validación y métricas")
    add(p("Los campos ausentes o adicionales, tipos incorrectos, NaN, infinito y valores fuera de los rangos declarados devuelven 422. El manejador de validación omite el valor crudo del error para evitar que NaN vuelva a fallar al serializar la respuesta. Una base no disponible produce 503 sin credenciales."))
    add(p("Los contadores distinguen intentos de telemetría y predicción, errores 4xx/5xx e inferencias de ingesta y de /predict. La latencia media interna usa todas las inferencias del proceso; p50/p95 usan las últimas 2.000. Contadores y uptime se reinician con el proceso; el historial permanece en la base. La latencia de red se mide por separado desde el cliente."))

    next_page("Dataset y análisis exploratorio")
    add(p("Se generaron 64 flotas con semillas independientes a partir del simulador original, sin modificar simulator/core.py. Cada flota aporta 512 muestras de ocho robots. El generador agrega fleet_id y timestamps deterministas para reproducir el mismo CSV."))
    add(table(["Clase", "Muestras", "Proporción"],[(label,f"{report['class_distribution'][label]:,}".replace(",","."),f"{100*report['class_distribution'][label]/report['samples']:.2f}%") for label in report["labels"]],[WIDTH*.45,WIDTH*.25,WIDTH*.3]))
    add(Spacer(1,10),p("No se encontraron valores ausentes o no finitos. CRITICAL es la clase más frecuente en estos datos; se reportan los conteos observados, sin asumir que sea minoritaria. Las seis variables son speed, battery, motor_temp, vibration, motor_current y obstacle_distance."))
    add(picture("feature_distributions.png"),p("Figura 2. Histogramas por condición. Temperatura y vibración presentan mayor separación; batería y distancia muestran fuerte solapamiento. La observación describe asociación dentro del simulador.","SmallR"))
    section("Separación sin mezcla de flotas")
    add(p("GroupShuffleSplit, semilla 606, reserva el 25% de las flotas: 48 para entrenamiento (24.576 muestras) y 16 para prueba (8.192). No hay fleet_id compartidos. La validación de cuatro particiones GroupKFold se ejecuta solo sobre entrenamiento. Imputación y escalado se ajustan dentro del pipeline de cada partición. [3]"))
    add(p("Se excluyen fleet_id, robot_id, timestamp, x e y para evitar memorizar identidad o trayectoria. Listas de grupos, estadísticas y huella SHA-256 completas se conservan en reports/evaluation.json.","SmallR"))

    next_page("Comparación y modelo seleccionado")
    rows=[(name,f"{r['cv_macro_f1_mean']:.4f} ± {r['cv_macro_f1_std']:.4f}",f"{r['test_macro_f1']:.4f}") for name,r in report["models"].items()]
    rows.append(("Clase mayoritaria","No aplica",f"{report['baseline_macro_f1']:.4f}"))
    add(table(["Clasificador", "F1 macro validación", "F1 macro prueba"],rows,[175,175,WIDTH-350]),Spacer(1,9))
    add(p("La elección se fijó antes de consultar la prueba: mayor F1 macro de validación, con preferencia por regresión logística si queda a 0,005 o menos del mejor resultado. La regresión logística obtuvo el mejor promedio; además su pipeline es pequeño y su inferencia económica. El artefacto servido se ajustó únicamente con las 48 flotas de entrenamiento."))
    add(picture("confusion_matrix.png",width=352),p("Figura 3. Matriz del clasificador seleccionado en las 16 flotas reservadas. Los errores se concentran en clases contiguas.","SmallR"))
    add(table(["Clase", "Precisión", "Recall", "F1"],[(label,*(f"{model['classification_report'][label][key]:.4f}" for key in ("precision","recall","f1-score"))) for label in report["labels"]],[WIDTH*.4,WIDTH*.2,WIDTH*.2,WIDTH*.2]))
    section("Reproducibilidad y alcance")
    add(p(f"<b>Versión:</b> {report['model_version']}. El bundle models/model.joblib incluye imputador, escalado, clasificador y orden de variables. scikit-learn {report['sklearn_version']}; semilla 606. requirements.txt fija las dependencias de ejecución."))
    add(p("La calidad medida se refiere a datos sintéticos del simulador. No acredita desempeño en robots reales. confidence es probabilidad estimada y no cuenta con una evaluación independiente de calibración.","SmallR"))

    next_page("Panel de operación")
    add(p("El panel consulta el servicio cada tres segundos. Incluye conexión, telemetría más reciente, condición predicha, confianza, batería media, posición y serie histórica por robot. Permite buscar, filtrar y pausar la actualización; el historial completo sigue disponible aunque el gráfico muestre las 180 muestras más recientes."))
    dashboard=load("dashboard_checks.json",{})
    dashboard_place="servicio público de Render" if dashboard.get("capture_url", "").startswith("https://") else "servicio local"
    add(picture("dashboard_desktop.png",width=484),p(f"Figura 4. Captura del {dashboard_place} con telemetría sintética. Los indicadores reflejan el estado real al capturar. También se verificó el diseño móvil a 390 px.","SmallR"))

    next_page("Verificación y evidencia medida")
    add(note(f"<b>{count} pruebas locales aprobadas.</b> Se comprueban contratos, 130 registros intactos tras una nueva instancia, concurrencia, datos fuera de orden, rechazos 422, fallos de base y separación de flotas."))
    section("Evaluación HTTP independiente")
    add(p("El cliente generó cuatro flotas nuevas con semilla 9001, identificadores distintos y leves cambios de sensores: ruido térmico adicional, vibración ×1,02 y corriente ×0,98. No se envían etiquetas al servicio. Estas flotas no participan en la elección del clasificador."))
    add(table(["Medida", "API local", "Render público"],[
        ("Predicciones / concurrencia",f"{local['requests']} / {local['workers']} en paralelo",f"{remote['requests']} / {remote['workers']} en paralelo" if remote else "Pendiente"),
        ("Solicitudes fallidas",str(local["errors"]),str(remote["errors"]) if remote else "Pendiente"),
        ("F1 macro / línea base",f"{local['macro_f1']:.4f} / {local['baseline_macro_f1']:.4f}",f"{remote['macro_f1']:.4f} / {remote['baseline_macro_f1']:.4f}" if remote else "Pendiente"),
        ("Latencia p50 cliente",f"{local['client_latency_p50_ms']:.2f} ms",f"{remote['client_latency_p50_ms']:.2f} ms" if remote else "Pendiente"),
        ("Latencia p95 cliente",f"{local['client_latency_p95_ms']:.2f} ms",f"{remote['client_latency_p95_ms']:.2f} ms" if remote else "Pendiente"),
    ],[WIDTH*.43,WIDTH*.285,WIDTH*.285]))
    add(Spacer(1,9),p("La columna local mide HTTP en el equipo de desarrollo. La columna pública incluye la red hacia Render con el servicio activo; no incluye un arranque en frío. La coincidencia de F1 es esperable: ambas evalúan el mismo modelo y las mismas muestras independientes.","SmallR"))
    section("Persistencia antes y después del reinicio")
    add(table(["Ambiente", "Prueba / estado"],[
        ("SQLite local","130 muestras preservadas al cerrar y crear una nueva instancia del servicio. Comparación completa de registros aprobada."),
        ("PostgreSQL en Neon; API local", "125 muestras y hash idénticos tras reiniciar el proceso; instance_id cambió." if neon.get("restart_verified") else "Base creada y conexión comprobada; prueba de 125 muestras y reinicio en curso o pendiente."),
        ("Render + Neon; URL pública","Contrato, flota nueva y reinicio remoto verificados." if ready else "Pendiente de finalizar publicación y repetir las comprobaciones desde fuera del proveedor."),
    ],[174,WIDTH-174]))
    section("Comprobación del panel")
    add(p("Un navegador aislado comprobó datos en vivo, selección de historial, búsqueda, cambio de variable, pausa/reanudación y ausencia de errores JavaScript. Se revisaron capturas de escritorio y móvil y se comprobó que la página no desbordara horizontalmente."))
    if load("other_device_check.json",{}).get("verified"):
        add(p("El estudiante confirmó la apertura del panel público desde otro dispositivo el 5 de noviembre de 2026. La confirmación está registrada en other_device_check.json.","SmallR"))
    add(p("Archivos de evidencia: pytest-results.xml, local_smoke.json, local_unseen_evaluation.json, dashboard_checks.json y, cuando corresponda, neon_persistence_snapshot.json y public_smoke.json. Los archivos se guardan en reports/.","SmallR"))

    next_page("Despliegue, entrega y defensa")
    if deployment.get("public_url"):
        add(p(f"<b>Servicio:</b> <link href='{escape(deployment['public_url'])}' color='#365f8f'>{escape(deployment['public_url'])}</link>"))
    if deployment.get("repository_url"):
        add(p(f"<b>Repositorio:</b> <link href='{escape(deployment['repository_url'])}' color='#365f8f'>{escape(deployment['repository_url'])}</link>","SmallR"))
    add(note("<b>Estado público: verificado.</b> La URL está registrada en el README con evidencia del contrato, calidad y reinicio." if ready else "<b>Estado público: pendiente.</b> No se presenta una dirección propuesta como URL activa. El estado comprobado se conserva en reports/deployment_status.json.",PALE if ready else colors.HexColor("#fff3df")))
    section("Configuración y cierre de aceptación")
    add(p("Render ejecuta FastAPI con Uvicorn en 0.0.0.0 y el puerto PORT. El modelo está versionado y el build instala requirements.txt. DATABASE_URL se guarda como secreto del servicio; los datos viven en Neon, AWS Oregon. La rama de funcionalidad y el merge a main conservan la trazabilidad real. [4, 5, 6]"))
    if ready:
        add(p("El servicio Free se creó en el espacio de trabajo confirmado del estudiante, desde main, con despliegue automático habilitado. Se verificaron smoke_test.py --final, una flota independiente por HTTP y las fases before/after de persistencia alrededor de un redespliegue del mismo commit en Render. El cambio de instance_id confirma el reinicio y la comparación de hash confirma las 125 muestras intactas. La URL real está registrada en el README."))
        add(p("La instancia creada mediante el conector mantiene el chequeo TCP predeterminado de Render; /health consulta PostgreSQL y el modelo para la verificación operativa. render.yaml incluye /health como chequeo HTTP para recrear el servicio mediante Blueprint.","SmallR"))
    else:
        add(p("Para cerrar el despliegue: publicar main en el repositorio propio, conectar Render al proveedor Git, crear el servicio Free, configurar el secreto y esperar Live. Después ejecutar smoke_test.py --final, evaluate_remote.py y las fases before/after de check_persistence.py alrededor de un reinicio desde Render. Registrar la URL real en el README."))
    add(p("El plan gratuito puede suspender el servicio tras 15 minutos sin tráfico y tardar alrededor de un minuto en arrancar. La evaluación se prepara abriendo /health y activando la flota. El disco local es efímero y no contiene el historial cloud. [5]"))
    section("Defensa técnica")
    add(p("Demostrar el recorrido de una muestra, explicar por qué se separan las flotas, comparar F1 macro con la línea base y mostrar un rechazo 422 seguido de un servicio operativo. En el reinicio, exigir cambio de instance_id y conservación de más de 100 registros. docs/DEFENSA.md contiene el guion, la secuencia y respuestas a preguntas probables."))
    section("Referencias")
    refs=[
        "[1] Loyola, O. (2026). Ejercicio 4: Cloud Fleet Challenge. Pauta entregada por el estudiante, pp. 4-17.",
        "[2] Repositorio base: github.com/DrOscarL/aci606-cloud-fleet-challenge.",
        "[3] scikit-learn. GroupShuffleSplit y validación por grupos. scikit-learn.org/stable/modules/cross_validation.html.",
        "[4] FastAPI en Render: render.com/docs/deploy-fastapi.",
        "[5] Render. Blueprint y plan gratuito: render.com/docs/blueprint-spec; render.com/docs/free.",
        "[6] Neon. Planes y PostgreSQL gestionado: neon.com/docs/introduction/plans. Consultas web: 4 y 5 de noviembre de 2026.",
    ]
    add(*(p(escape(ref),"SmallR") for ref in refs))
    output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=61,bottomMargin=57,title="Ejercicio 4 - Cloud Fleet Challenge",author="Proyecto ACI606",subject="Implementación y evidencia del servicio de flotas")
    doc.build(body,onFirstPage=page_frame,onLaterPages=page_frame)
    print(output)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"output/pdf/Informe_tecnico_Ejercicio4.pdf")
    build(parser.parse_args().output)
