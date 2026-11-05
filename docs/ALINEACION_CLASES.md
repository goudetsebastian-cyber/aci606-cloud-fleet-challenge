# Revisión del Ejercicio 4 frente a las clases de persistencia

Revisión realizada el 5 de noviembre de 2026 sobre la implementación publicada. Los dos materiales de clases son compatibles con la solución: FastAPI en Render, PostgreSQL gestionado en Neon y SQLite para desarrollo local. No se detectó un requisito funcional pendiente del Ejercicio 4 a partir de estos archivos. Se amplía la explicación técnica en este documento, en la guía de defensa y en el informe.

## Material y alcance

| Fuente del docente | Contenido revisado | Aplicación al trabajo |
|---|---|---|
| *Persistencia y servicios de datos en Cloud* (`Cloud_Computing_Clase_DB.pdf`, 19 páginas) | Estado, persistencia, separación de cómputo y datos, modelo relacional, ACID, almacenamiento y DBaaS | Fundamento de las decisiones de arquitectura |
| *Laboratorio: servicio persistente de datos de sensores* (`Cloud_Computing_Clase_DB-2.pdf`, 11 páginas) | Práctica FastAPI + SQLite en Colab, consultas, índices, reinicio y volumen | Patrón que se transfiere al servicio de robots |
| *Ejercicio 4: Cloud Fleet Challenge*, páginas 4-17 | Contrato, ML, persistencia, panel, métricas, Git y PaaS | Requisitos de la entrega evaluada |

La guía de laboratorio declara en su página 1 que no constituye la solución de una evaluación específica. Sus rutas `/measurements` y `/stats/{sensor_id}`, las celdas de Colab y el experimento de 100/1.000/5.000 mediciones pertenecen a esa práctica. El Ejercicio 4 conserva sus siete rutas, su simulador y la arquitectura de referencia Render + Neon. No se agregan rutas de sensores ni resultados de experimentos que no se ejecutaron.

## Correspondencia con la implementación

| Concepto y fuente | Aplicación existente | Evidencia o límite |
|---|---|---|
| Estado volátil y durable: clase pp. 3-5; laboratorio pp. 6-8 | Telemetría y predicción en PostgreSQL; contadores y uptime en el proceso | [Persistencia pública](../reports/persistence_snapshot.json): 125 registros con el mismo hash tras un redespliegue y cambio de `instance_id` |
| Separación de cómputo y almacenamiento: clase pp. 6-7; laboratorio pp. 10-11 | Render ejecuta la API; Neon conserva los datos fuera del disco del servicio | [Arquitectura](ARCHITECTURE.md); el arranque en Render rechaza una configuración SQLite |
| Esquema relacional: clase pp. 8-10 | Tabla `telemetry`, clave primaria `id`, columnas obligatorias y consultas SQL parametrizadas mediante SQLAlchemy | [Persistencia](../app/db.py); [validación de sensores](../app/schemas.py) |
| Transacciones ACID: clase p. 11 | Una transacción guarda sensores y predicción; la API confirma la aceptación después del commit | `Storage.save()` y `ingest()`; el reinicio comprobado no es una certificación de todas las situaciones de fallo |
| Índice por entidad y tiempo: laboratorio p. 7 | Índice `(robot_id, timestamp, id)` para consultas históricas por robot | Tiene costo de espacio y mantenimiento en cada escritura; no se midió su mejora con `EXPLAIN` |
| Consultas y agregación en la base: laboratorio pp. 8-9 | `COUNT`, `MAX`, agrupación y función de ventana obtienen conteos, última recepción y último evento | `/metrics` cuenta en SQL; `/robots` devuelve una fila por robot, sin transferir todo el historial al panel |
| Selección de almacenamiento: clase pp. 12-13 y 18 | PostgreSQL para telemetría estructurada; SQLite para desarrollo; modelo pequeño versionado en Git | No se requiere NoSQL ni un servicio de objetos adicional para cumplir esta pauta |
| DBaaS y responsabilidades: clase pp. 14-16 | Neon administra el servicio PostgreSQL; el proyecto define esquema, consultas, credenciales y uso | No se ha probado restauración desde una copia de seguridad ni alta disponibilidad |

## Cómo explicar las decisiones

### Estado y reemplazo de instancias

El dato de negocio es la telemetría junto con su predicción. Se guarda fuera del proceso. Los contadores y la ventana de latencias son estado operativo temporal: pueden reiniciarse sin borrar el historial. El modelo se carga en memoria desde un artefacto versionado que se recupera al desplegar.

La API puede reemplazarse sin trasladar una lista local de muestras. Esto no equivale a afirmar que todo su estado es inexistente: las métricas actuales pertenecen a un solo proceso. Si se desplegaran varias réplicas, habría que reunirlas con observabilidad externa; la solución actual utiliza un proceso.

### Transacción y corrección

`engine.begin()` confirma la inserción al terminar correctamente o revierte la transacción si ocurre un error. Los sensores y la predicción forman una misma fila. La clave primaria y las columnas no nulas aportan integridad estructural; Pydantic valida las reglas de entrada. PostgreSQL gestiona la concurrencia de las transacciones, sin que la aplicación solicite un nivel de aislamiento especial.

La prueba local de escrituras concurrentes verifica que no se pierdan las muestras de ese experimento. La prueba pública verifica conservación después de un reinicio del cómputo. Ninguna demuestra aislamiento serializable, recuperación de un desastre o restauración de respaldos. Un reenvío puede crear una segunda fila porque el contrato no define una clave de idempotencia.

### Índices, agregaciones y crecimiento

El índice comienza por `robot_id` y continúa por tiempo e identificador, acorde con la consulta del historial. Su beneficio depende del plan elegido por el motor y del volumen; mantenerlo también consume trabajo al insertar. Los conteos y la última recepción se calculan en SQL, cerca de los datos. El navegador calcula la batería media sobre el resumen de robots recibido, no sobre miles de muestras históricas.

Con cien veces más clientes, habría que medir escrituras, consultas sobre todo el historial, conexiones y CPU de inferencia. El pool local permite cinco conexiones y cinco adicionales; aumentar réplicas también aumenta la demanda de conexiones. Las consultas de resumen, solicitadas periódicamente por el panel, merecen especial atención. La evaluación pública de 512 solicitudes mide `/predict`, no el rendimiento de 512 escrituras persistentes ni el experimento de volumen del laboratorio.

### PostgreSQL, SQLite y DBaaS

SQLite resuelve la persistencia frente al reinicio del proceso mientras se conserva su archivo. En un disco efímero, perder la instancia puede implicar perder ese archivo. La elección de PostgreSQL externo responde al despliegue del Ejercicio 4 y no a que SQLite sea una herramienta inadecuada en general.

Una base relacional encaja con filas de sensores con estructura conocida, historial por robot y escrituras transaccionales. No hace falta introducir documentos o caché para este alcance. Un modelo o dataset grande podría justificar almacenamiento de objetos; el modelo actual cabe en el repositorio y debe recuperarse en cada despliegue.

DBaaS reduce la operación del motor y su infraestructura, pero no elimina las responsabilidades sobre acceso, esquema, consultas, calidad, retención o recuperación. Antes de un uso real habría que definir respaldos y probar su restauración, además de identidad de clientes, cuotas y monitoreo. Conservar datos y atender continuamente son propiedades distintas: la modalidad gratuita puede suspender el cómputo.

## Resultado de la revisión

Se conserva la implementación y el panel blanco con azul marino. El ajuste es documental: se hace explícita la relación con la materia y el alcance de las pruebas. La prueba de reinicio ya realizada cubre el objetivo de persistencia; no corresponde presentarla como prueba de alta disponibilidad o de recuperación desde un respaldo. La guía de defensa incorpora preguntas sobre estos conceptos.

Identificación de los materiales recibidos, SHA-256:

- Clase: `7d5428ebfb6f2f81f940233ccc45d1e5e0423d992505d84112929580a3165a76`.
- Laboratorio: `4a0e7e3d8725ccf759b32dd19b122bf4663ab8dc609ed89feaba92ecd92af28f`.
