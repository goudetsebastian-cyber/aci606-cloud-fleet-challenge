# Publicación en Render y Neon

Servicio publicado: [panel Cloud Fleet](https://aci606-cloud-fleet-sebit44s.onrender.com/dashboard). Repositorio: [solución del estudiante](https://github.com/goudetsebastian-cyber/aci606-cloud-fleet-challenge). Los resultados comprobados están en `reports/deployment_status.json`.

La instancia actual fue creada directamente en Render con el plan Free y los mismos comandos y variables declarados en `render.yaml`. Usa el chequeo TCP predeterminado de Render; `/health` comprueba la disponibilidad de PostgreSQL y el modelo. Al recrear el servicio mediante Blueprint, `healthCheckPath: /health` activa la comprobación HTTP. Los pasos siguientes permiten reproducir la publicación.

## 1. GitHub

Crear un repositorio propio `aci606-cloud-fleet-challenge` y publicar **main y feature/cloud-platform** conservando el historial Git. No usar el repositorio del docente como destino de escritura. El paquete de entrega incluye `repositorio.bundle`, que conserva ambas ramas y el merge; subir archivos sueltos por la web no conserva ese historial.

Si se parte del bundle en otro equipo:

```powershell
git clone repositorio.bundle aci606-cloud-fleet-challenge
cd aci606-cloud-fleet-challenge
git remote rename origin entrega-local
git remote add origin URL_DEL_REPOSITORIO_PROPIO
git push -u origin main
git push origin feature/cloud-platform
```

La cadena en mayúsculas es un argumento que se reemplaza con la URL real del repositorio creado. No es una URL de entrega.

## 2. Neon: proyecto y base de datos

1. Abrir [la consola de Neon](https://console.neon.tech/) y crear la cuenta gratuita si hace falta.
2. Crear el proyecto `aci606-cloud-fleet`, plan **Free**, PostgreSQL, proveedor AWS y región Oregon si está disponible (cercana a Render Oregon).
3. Abrir **Connect**, seleccionar la base y el rol de la aplicación, y activar la conexión con pool.
4. Copiar la cadena PostgreSQL con `sslmode=require`. Es una credencial: ingresarla únicamente en la variable privada `DATABASE_URL` de Render. No ponerla en el README, capturas, Git ni en mensajes del chat.

La aplicación adapta automáticamente `postgresql://` a `postgresql+psycopg://`. Crea la tabla `telemetry` y su índice al primer arranque. No requiere importar el dataset de entrenamiento a la base.

## 3. Render: servicio web

1. Abrir [Render](https://dashboard.render.com/) y crear la cuenta si hace falta.
2. Conectar el repositorio propio de GitHub. Si se instala la integración, restringirla al repositorio del ejercicio.
3. Elegir **New > Blueprint**, seleccionar el repositorio y la rama `main`. Render detecta `render.yaml`.
4. Revisar que el único recurso sea un Web Service con plan **Free**. La base está en Neon; no crear otra en Render.
5. Ingresar la cadena de Neon en el campo privado `DATABASE_URL`. Crear el Blueprint.
6. Esperar el estado **Live**. Guardar la dirección HTTPS real `onrender.com` en el README.

Alternativa por **New > Web Service**, con estos valores:

| Campo | Valor |
|---|---|
| Runtime | Python |
| Branch | main |
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` |
| Health check | `/health` |
| Instance | Free |
| Auto-deploy | On commit |
| PYTHON_VERSION | 3.12.10 |
| DATABASE_URL | Cadena privada de Neon con TLS |
| MODEL_PATH | models/model.joblib |
| OPENBLAS_NUM_THREADS / OMP_NUM_THREADS | 1 / 1 |

El artefacto entrenado está versionado: el build no entrena de nuevo ni requiere matplotlib. `pool_pre_ping=True`, reciclaje de 240 s y tiempo de conexión de 15 s ayudan a recuperar conexiones suspendidas. La aplicación rechaza SQLite cuando detecta Render.

## 4. Verificación desde fuera de Render

En los comandos siguientes reemplazar la dirección ilustrativa por la URL pública real. En Windows puede usarse `.venv\Scripts\python.exe` en lugar de `python`.

```powershell
python tests/smoke_test.py --api https://SERVICIO.onrender.com --final --output reports/public_smoke.json
python tests/evaluate_remote.py --api https://SERVICIO.onrender.com --output reports/remote_evaluation.json
python tests/check_persistence.py --api https://SERVICIO.onrender.com --phase before
```

En Render elegir **Manual Deploy > Restart service**. Esperar que el servicio vuelva a Live y ejecutar:

```powershell
python tests/check_persistence.py --api https://SERVICIO.onrender.com --phase after
```

La comprobación exige que cambie `instance_id` y que las 125 muestras mantengan exactamente el mismo hash. No basta con repetir una consulta sin reiniciar.

Ejecutar el simulador hacia la URL pública y abrir `/dashboard` desde otro equipo o teléfono:

```powershell
python simulator/fleet_simulator.py --api https://SERVICIO.onrender.com --robots 6
```

Comprobar también que un nuevo commit a `main` genere un deploy sin pulsar Manual Deploy. Render necesita las credenciales Git de la cuenta y permiso sobre el repositorio. Guardar esa comprobación en `reports/autodeploy_check.json` y la confirmación del acceso desde otro dispositivo en `reports/other_device_check.json`.

Registrar la URL y plataforma con `scripts/record_deployment.py` después de ejecutar las pruebas. Ese comando comprueba `/health`, exige PostgreSQL y reúne los estados de contrato, calidad, reinicio, actualización automática y otro dispositivo; **no sustituye** esas verificaciones.

## Límites de la modalidad gratuita

Render suspende el servicio tras 15 minutos sin tráfico; su siguiente arranque puede tardar aproximadamente un minuto. El disco es efímero, por eso los datos viven en Neon. Antes de la defensa, abrir `/health`, esperar respuesta y activar el simulador. No usar tráfico artificial para evitar los límites del plan.

Neon Free suspende el cómputo tras inactividad y tiene cuotas. Revisar los valores actuales en las páginas oficiales al crear la cuenta. Este proyecto no necesita contratar planes de pago.

Fuentes consultadas el 4 y 5 de noviembre de 2026:

- [Render: FastAPI](https://render.com/docs/deploy-fastapi)
- [Render: Blueprint](https://render.com/docs/blueprint-spec)
- [Render: modalidad gratuita](https://render.com/docs/free)
- [Neon: planes](https://neon.com/docs/introduction/plans)
- [SQLAlchemy: reconexión con pre-ping](https://docs.sqlalchemy.org/en/20/core/pooling.html#disconnect-handling-pessimistic)
