# Decisiones de arquitectura

## Recorrido de una muestra

El cliente envía un JSON a `/telemetry`. Pydantic valida tipos, magnitudes y valores finitos. El pipeline transforma las seis variables y estima la clase. Una transacción almacena sensores, fecha de recepción, clase, confianza, versión y latencia. Solo después del commit se devuelve `accepted: true`. Si falla la escritura se responde 503; no se confirma una muestra que no quedó guardada.

`/predict` usa el mismo pipeline y responde el contrato exigido, pero no inserta telemetría. Esto permite evaluar el modelo sin modificar el historial de operación. Los endpoints síncronos se ejecutan en el pool de hilos de FastAPI; el bucle de eventos no se ocupa con consultas o inferencia síncronas.

## Persistencia

SQLAlchemy Core y psycopg 3 conectan con PostgreSQL gestionado en Neon por TLS, con configuración externa. El pool tiene cinco conexiones y hasta cinco adicionales; `pool_pre_ping=True`, reciclaje de 240 s y conexión de hasta 15 s. El esquema se inicializa al arranque con `create_all`; no hay borrado automático ni truncamiento por robot.

La tabla `telemetry` guarda todas las solicitudes aceptadas. El índice compuesto `(robot_id, timestamp, id)` ayuda a consultar por robot y tiempo. El historial se devuelve en orden ascendente; el `id` resuelve empates. Una función de ventana selecciona el evento más nuevo por robot. La conectividad usa el máximo tiempo de recepción y no el timestamp del sensor, que puede llegar desordenado.

En local se admite SQLite con WAL y timeout de 30 s para desarrollar sin una cuenta cloud. Esta modalidad **no se usa en Render**: si `RENDER` está definido y la URL no es PostgreSQL, el arranque falla explícitamente. La persistencia local y la remota se verifican por separado.

La ingesta tiene semántica de una fila por POST aceptado. Reenviar una misma muestra puede generar otra fila: el contrato no incluye un identificador idempotente. No se elimina historia al desconectar robots. El endpoint público no tiene límite fijo; el panel solicita hasta 180 muestras recientes usando paginación.

## Cliente de demostración en el navegador

El panel permite iniciar una ejecución de seis robots, limitada a dos minutos. `GET /demo/scenario` genera 40 rondas con el simulador original de `simulator/core.py`, sin escribir en la base. El navegador asigna identificadores propios y timestamps actuales, y envía cada muestra mediante `POST /telemetry`. La validación, la inferencia y la transacción son las mismas de los clientes externos. El cliente detiene sus envíos al finalizar, al pulsar Detener o al cerrar la página. El historial ya confirmado permanece en PostgreSQL.

## Inferencia

El artefacto de confianza se carga una vez en el ciclo de vida del servicio. Nunca se aceptan modelos subidos por clientes. El bundle incluye pipeline, orden de las variables, versión y métricas. El entrenamiento usa GroupShuffleSplit y GroupKFold; el modelo final servido solo ha visto las 48 flotas de entrenamiento. Identificadores, tiempos y posiciones no son variables predictoras.

Se usa un proceso Uvicorn por servicio y se limita el paralelismo de BLAS/OpenMP en Render. El pipeline es pequeño y se comparte para lectura. Cambiar el modelo implica entrenar, actualizar artefacto y metadatos, comprobar las pruebas y desplegar un nuevo commit.

## Métricas y recuperación

Los contadores protegidos por un lock incluyen solicitudes totales, intentos por ruta POST, códigos HTTP, errores 4xx y 5xx e inferencias terminadas. Se distinguen las inferencias de ingesta y las de `/predict`. La latencia media usa suma y conteo de todo el proceso; los percentiles usan una ventana de 2.000 inferencias. `inference_ms` excluye red, cola HTTP y serialización; el evaluador HTTP mide latencia desde el cliente.

Los contadores se reinician al reiniciar el proceso. El identificador `instance_id` cambia en cada arranque y permite exigir un reinicio real en la prueba de persistencia. Las muestras y las predicciones están en la base y no dependen de esos contadores.

Los errores de validación excluyen el valor crudo del mensaje para que NaN e infinito tampoco rompan la serialización del error. Los fallos de base producen una respuesta genérica 503. Los fallos inesperados generan 500 y un registro del servicio para diagnóstico.

## Despliegue y alcance

El Blueprint configura Python 3.12.10, dependencias fijadas, puerto asignado por la plataforma, health check y despliegue desde `main`. El modelo está en Git para que un disco nuevo lo recupere. El secreto `DATABASE_URL` se ingresa en Render y no aparece en el Blueprint.

El plan gratuito de Render suspende el proceso por inactividad; una URL estable no equivale a una instancia siempre encendida. Neon también puede suspender el cómputo. Para la defensa se despierta el servicio antes de evaluar y se mide su estado operativo. No se afirma disponibilidad con SLA.

El alcance es un ejercicio público con telemetría sintética. Un entorno real requeriría identidad de clientes, autorización, cuotas, migraciones de esquema, retención y monitoreo externo. Las pruebas ejecutadas y las pendientes están identificadas en los informes; una configuración preparada no se considera un despliegue verificado.
