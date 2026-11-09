# Guía de presentación y demostración para tres personas

Esta guía reúne el guion, el reparto entre expositores, los pasos de la demostración y las evidencias del Ejercicio 4. Se puede leer y compartir desde cualquier computador o celular.

## Accesos del trabajo

- [Panel público y controles de demostración](https://aci606-cloud-fleet-sebit44s.onrender.com/dashboard).
- [Código y documentación del proyecto](https://github.com/goudetsebastian-cyber/aci606-cloud-fleet-challenge).
- [Reporte del modelo, EDA y figuras](../reports/MODEL_REPORT.md).
- [Resultados de la evaluación pública](../reports/remote_evaluation.json).
- [Comprobación pública del panel y del reinicio](../reports/browser_demo_checks.json).
- [Guía de preguntas para la defensa](DEFENSA.md).

Para editar esta guía desde otro computador, inicia sesión en GitHub con una cuenta que tenga permiso sobre el repositorio y utiliza el botón del lápiz de este archivo. Para compartirla con los compañeros, copia la dirección que aparece en el navegador.

## Reparto y orden sugerido

La exposición está organizada para aproximadamente 12-15 minutos, incluida la demostración. La duración del reinicio depende de Render.

| Persona | Explicación | Demostración |
|---|---|---|
| 1 | Problema, arquitectura, recorrido de una medición y almacenamiento | Flota, historial, preparación de las 125 muestras e inicio del reinicio |
| 2 | Dataset, EDA, separación por flotas y elección del modelo | Reporte del modelo y matriz de confusión mientras Render reinicia |
| 3 | Verificación del historial, contrato de la API, métricas, despliegue y Git | Resultado del reinicio, predicción, rechazo 422, métricas y evidencias en GitHub |

## Revisión contra la pauta del docente

Se revisaron los siete requisitos de las páginas 5-7 y las verificaciones y entregables de las páginas 15-17 de *Ejercicio 4: Cloud Fleet Challenge. Del prototipo local a un servicio desplegado en una plataforma PaaS*, facilitado por el estudiante. Los requisitos técnicos tienen implementación y evidencia en el repositorio. La evaluación con la flota específica del docente corresponde a la defensa.

| Requisito | Implementación y evidencia que se debe mostrar |
|---|---|
| Ingesta persistente e historial completo | PostgreSQL en Neon, transacciones y conservación de más de 100 muestras. Mostrar la comprobación de 125 muestras tras el reinicio. |
| Entrenamiento de ML | EDA, dos clasificadores, separación por `fleet_id`, matriz de confusión, F1 macro y pipeline en `models/model.joblib`. |
| Inferencia | `/predict` devuelve `robot_id`, `predicted_status`, `confidence`, `model_version` e `inference_ms`. |
| Panel | Robots, telemetría, condición, confianza, batería, posición, historial y estado del servicio. |
| Observabilidad | Solicitudes, errores, latencias y uptime. Hay una evaluación HTTP adicional de latencia desde el cliente. |
| Git | Commits, rama `feature/cloud-platform` y merge a `main`, documentado en el pull request 1. |
| PaaS | Render con URL HTTPS, Neon para los datos, variables de entorno, dependencias declaradas y despliegue automático desde GitHub. |

La pauta también pide el smoke test público, revisión de los registros de Render, apertura desde otro dispositivo y reinicio en vivo. La evidencia de estas comprobaciones se conserva en `reports/`. Durante la presentación se debe repetir la demostración en vivo y justificar las decisiones.

## Persona 1. Problema, arquitectura y persistencia

### Guion para decir en voz alta

Nuestro proyecto se llama Cloud Fleet Challenge. El objetivo fue transformar el servicio base del docente en una plataforma en la nube que reciba telemetría, conserve el historial, estime la condición de los robots y permita supervisarlos desde un panel.

El servicio inicial guardaba las mediciones en memoria y conservaba hasta cien registros por robot. Eso hacía que el historial dependiera del proceso que ejecutaba la aplicación.

La solución utiliza FastAPI en Render y una base PostgreSQL administrada en Neon. El simulador o el navegador actúan como clientes que envían mediciones. Render procesa las solicitudes y Neon conserva los datos.

El recorrido comienza cuando un cliente envía una muestra mediante POST /telemetry. La API valida los campos, sus tipos y los rangos permitidos. Después aplica el modelo entrenado y guarda la medición junto con su predicción dentro de una transacción.

La aplicación confirma la aceptación después de que la base confirma la escritura. Esto permite relacionar la respuesta del servicio con una operación de almacenamiento completada.

Cada fila guarda el identificador del robot, los tiempos de medición y recepción, su posición y las seis señales de los sensores. También conserva la condición predicha, la confianza, la versión del modelo y el tiempo de inferencia.

La tabla tiene una clave primaria y un índice por robot, tiempo e identificador, acorde con la consulta del historial. Los registros permanecen disponibles cuando un robot deja de enviar datos.

Esta arquitectura aplica la separación entre cómputo y almacenamiento que vimos en clases. La aplicación puede reiniciarse y volver a conectarse a la misma base.

Ahora vamos a guardar 125 mediciones de un robot de prueba. El navegador conservará una referencia con el conteo, la huella digital del historial y el identificador de arranque. Después del reinicio consultaremos nuevamente los registros para comprobar que se conservan.

### Qué mostrar y cómo hacerlo

1. Abre el panel y pulsa **Iniciar demostración**. Señala los seis robots enviando datos.
2. Selecciona un robot, cambia la variable del gráfico y abre **Historial completo**. Muestra los campos guardados.
3. En GitHub, abre [app/main.py](../app/main.py) y localiza `def ingest`. Explica que esa función valida, predice y solicita el guardado.
4. Abre [app/db.py](../app/db.py) y localiza `def save`. La inserción se ejecuta dentro de `engine.begin()`, que delimita la transacción.
5. Vuelve al panel y despliega **Pruebas para la presentación**.
6. Pulsa **Guardar 125 muestras** y espera la confirmación. Esta acción detiene la demostración de seis robots y prepara un robot de comprobación.
7. Pulsa **Abrir Render**, entra al servicio `aci606-cloud-fleet-sebit44s` y utiliza **Deploys > Manual Deploy > Restart service**.
8. Mientras termina el reinicio, interviene la persona 2.

### Qué guarda la base de datos

La tabla se llama `telemetry` y tiene 16 columnas. Su esquema fue contrastado con la tabla real de Neon.

| Contenido | Campos |
|---|---|
| Identificación | `id`, `robot_id` |
| Tiempos | `timestamp`, `received_at` |
| Posición | `x`, `y` |
| Sensores | `speed`, `battery`, `motor_temp`, `vibration`, `motor_current`, `obstacle_distance` |
| Resultado del modelo | `predicted_status`, `confidence`, `model_version`, `inference_ms` |

`timestamp` corresponde al tiempo enviado con la medición. `received_at` registra cuándo la recibió el servidor. La aplicación usa la recepción para determinar si el robot está conectado.

El código y el artefacto del modelo están versionados en GitHub. El historial operacional se conserva en PostgreSQL en Neon. El generador de entrenamiento permite reproducir el dataset a partir de semillas.

## Persona 2. Datos, entrenamiento y modelo

### Guion para decir en voz alta

Para construir el modelo generamos 32.768 muestras sintéticas de 64 flotas independientes, utilizando el simulador del proyecto.

El generador agrega un identificador de flota que permite separar los datos correctamente. Cada muestra tiene una etiqueta de condición generada por el simulador, que se utiliza durante el entrenamiento y la evaluación.

Primero realizamos un análisis exploratorio. Revisamos la distribución de NORMAL, WARNING y CRITICAL, los valores ausentes y las distribuciones de los sensores. Observamos que la temperatura y la vibración ayudaban a distinguir las condiciones, mientras que otras señales presentaban mayor solapamiento.

El modelo utiliza velocidad, batería, temperatura, vibración, corriente y distancia al obstáculo. Dejamos fuera los identificadores, el tiempo y la posición para reducir la posibilidad de aprender características particulares de una flota o trayectoria.

Separamos las flotas mediante GroupShuffleSplit. Usamos 48 para entrenamiento y validación, y reservamos 16 para la prueba final. Dentro del entrenamiento aplicamos validación por grupos con cuatro particiones.

La separación por flota es importante porque las mediciones de un mismo grupo están relacionadas. Reservar grupos completos permite evaluar el modelo con flotas que no participaron en su ajuste.

Comparamos regresión logística y Random Forest. Elegimos regresión logística por su mejor F1 macro de validación y por su tamaño y costo de inferencia reducidos.

En la prueba reservada obtuvo F1 macro de 0,9260. Random Forest obtuvo 0,9229 y la estrategia de clase mayoritaria obtuvo 0,1982.

F1 combina precisión y sensibilidad. El promedio macro da el mismo peso a las tres clases.

Guardamos el preprocesamiento y el clasificador dentro de models/model.joblib. La API carga ese pipeline al iniciar y aplica las mismas transformaciones a las nuevas mediciones. La versión del modelo también queda registrada en cada predicción guardada, lo que permite mantener trazabilidad sobre los resultados.

### Qué mostrar y cómo hacerlo

1. Abre el [reporte del modelo](../reports/MODEL_REPORT.md).
2. Señala la distribución de clases y los histogramas.
3. Explica el reparto de 48 flotas de entrenamiento y 16 de prueba.
4. Muestra la comparación entre los dos clasificadores.
5. Señala la matriz de confusión. La diagonal contiene los aciertos y las otras celdas muestran entre qué condiciones se producen errores.
6. Abre la [carpeta models](../models) y muestra `model.joblib` y `metadata.json`.

| Clasificador | F1 macro de validación | F1 macro de prueba |
|---|---:|---:|
| Regresión logística | 0,9249 | 0,9260 |
| Random Forest | 0,9202 | 0,9229 |
| Clase mayoritaria | - | 0,1982 |

Los conteos observados son 10.213 muestras NORMAL, 9.647 WARNING y 12.908 CRITICAL. La implementación y el reporte utilizan esa distribución real del dataset generado.

## Persona 3. Verificación, API, métricas y despliegue

### Guion para decir en voz alta

Vamos a comprobar el historial después del reinicio.

La referencia preparada contiene el identificador del robot, la cantidad de muestras, una huella digital del contenido y el identificador de arranque anterior. Al verificar, el navegador consulta nuevamente la API y compara esos datos.

**Decir el párrafo siguiente después de que aparezca Persistencia confirmada.**

La comprobación encontró un nuevo arranque del servicio y las 125 muestras con exactamente el mismo contenido. Esto demuestra que el historial se conserva de forma independiente del proceso de la aplicación.

La referencia que mantiene el navegador permite hacer la comparación. Las mediciones se recuperan desde PostgreSQL mediante la API.

El servicio también implementa las siete rutas exigidas por la pauta. Podemos comprobar su estado, enviar telemetría, consultar los robots y su historial, obtener predicciones, consultar métricas y abrir el panel.

La respuesta de POST /predict contiene el identificador del robot, la condición estimada, la confianza, la versión del modelo y el tiempo de inferencia. Vamos a mostrar esa respuesta con una solicitud válida.

También probaremos una batería fuera de rango. La API devuelve 422 y continúa atendiendo solicitudes. Las pruebas registradas cubren además campos ausentes y valores no finitos, como NaN.

Para observar la operación disponemos de solicitudes, errores, latencia y tiempo activo. Estos contadores pertenecen al proceso y se reinician al arrancar. El historial de telemetría permanece en la base.

La evaluación pública registrada utilizó cuatro flotas nuevas y obtuvo 512 respuestas válidas, con hasta ocho solicitudes en paralelo y cero fallos. El F1 macro fue aproximadamente 0,9267. Desde el cliente se midieron una latencia mediana cercana a 197 milisegundos y un percentil 95 de 275 milisegundos.

El despliegue utiliza Render para ejecutar la aplicación y Neon para PostgreSQL. Las dependencias están declaradas, el modelo está versionado y la conexión se configura mediante una variable privada.

GitHub conserva los commits, la rama de funcionalidad y su integración a main. También ejecuta las pruebas automatizadas, cuya última ejecución revisada está aprobada.

### Qué mostrar y cómo hacerlo

1. Comprueba que el nuevo reinicio terminó en Render y figura como **Live**. Debe corresponder a la operación que inició la persona 1.
2. Vuelve al panel usando el mismo navegador donde se guardaron las 125 muestras.
3. Pulsa **Verificar tras reinicio**.
4. Muestra el mensaje de **125/125 muestras idénticas y un nuevo arranque del servicio**.
5. Abre **Historial completo** para mostrar los registros consultables.
6. Pulsa **Obtener predicción** y señala HTTP **200** y los cinco campos de la respuesta.
7. Pulsa **Probar dato inválido** y señala HTTP **422**.
8. Despliega **Ver métricas completas del servicio**. Explica `requests_total`, `client_errors`, `uptime_seconds`, `stored_samples` y las latencias.
9. En Render, abre **Logs** y muestra las solicitudes atendidas.
10. En GitHub, muestra el [pull request integrado](https://github.com/goudetsebastian-cyber/aci606-cloud-fleet-challenge/pull/1) y una [ejecución aprobada de las pruebas](https://github.com/goudetsebastian-cyber/aci606-cloud-fleet-challenge/actions).
11. Regresa al panel y pulsa **Iniciar demostración** para dejar una flota activa durante las preguntas del profesor.

La demostración de seis robots dura dos minutos por ejecución. Se puede volver a iniciar desde el botón.

## Qué comprueba exactamente el reinicio

1. El navegador envía 125 muestras de un robot de comprobación a `/telemetry`.
2. La API valida, predice y confirma la escritura de cada muestra en PostgreSQL.
3. El navegador consulta el historial completo y calcula su SHA-256.
4. Conserva una referencia con el robot, el conteo, la huella y el identificador de arranque. Esa referencia se guarda en el mismo navegador para poder recargar la página.
5. Se reinicia la aplicación desde Render.
6. Al verificar, se exige un identificador de arranque distinto.
7. Se vuelve a consultar el historial mediante la API y se compara su conteo y su huella.
8. El resultado se confirma cuando las 125 muestras conservan el mismo contenido.

El historial operacional está en Neon. La referencia del navegador sirve para comprobarlo después del reinicio. Las muestras ya confirmadas permanecen disponibles cuando se detiene la demostración o se cierra la página.

Si el panel indica que el identificador de arranque sigue igual, espera a que finalice la operación de Render y vuelve a pulsar **Verificar tras reinicio**.

## Preparación antes de exponer

- Abrir [el estado del servicio](https://aci606-cloud-fleet-sebit44s.onrender.com/health) y esperar `status: ok`. Revisar `database: postgresql` y `model_loaded: true`.
- Tener iniciada la sesión de Render en el equipo que presentará.
- Abrir esta guía y el reporte del modelo.
- Mantener la referencia de las 125 muestras en el mismo navegador durante la comprobación.
- Abrir el panel desde otro dispositivo. Esa comprobación ya está registrada y puede repetirse con un celular.
- Mantener una flota activa al mostrar el panel y durante la evaluación que indique el docente.
- Compartir con el docente la URL pública y el repositorio.

## Cifras y evidencias de apoyo

| Comprobación | Resultado registrado | Evidencia |
|---|---|---|
| Pruebas del servicio | 41 aprobadas | [Resultado local](../reports/pytest-results.xml) y [GitHub Actions](https://github.com/goudetsebastian-cyber/aci606-cloud-fleet-challenge/actions) |
| Contrato público | Siete rutas, predicción y rechazo de entradas inválidas | [Smoke test público](../reports/public_smoke.json) |
| Evaluación HTTP | 512 respuestas válidas, ocho solicitudes en paralelo y cero fallos | [Evaluación pública](../reports/remote_evaluation.json) |
| Calidad en flotas nuevas por HTTP | F1 macro 0,9267 frente a línea base 0,1431 | [Evaluación pública](../reports/remote_evaluation.json) |
| Latencia desde el cliente | p50 197,19 ms y p95 275,32 ms | [Evaluación pública](../reports/remote_evaluation.json) |
| Historial después del reinicio | 125 muestras idénticas y nuevo identificador de arranque | [Controles del navegador](../reports/browser_demo_checks.json) |
| Despliegue automático | Actualización desde un cambio en `main` | [Comprobación registrada](../reports/autodeploy_check.json) |
| Acceso desde otro dispositivo | Confirmado por el estudiante | [Comprobación registrada](../reports/other_device_check.json) |

El F1 0,9260 corresponde a las 16 flotas reservadas durante el desarrollo. El F1 0,9267 corresponde a la evaluación HTTP adicional con otras cuatro flotas. Las latencias registradas corresponden al servicio activo durante ese experimento.

## Documentación para profundizar

- [Decisiones de arquitectura](ARCHITECTURE.md).
- [Publicación en Render y Neon](DEPLOYMENT.md).
- [Preguntas y respuestas para la defensa](DEFENSA.md).
- [Relación con las clases de persistencia](ALINEACION_CLASES.md).
- [Generación de datos](../ml/generate_fleets.py).
- [Entrenamiento y comparación de clasificadores](../ml/train_model.py).
- [Contratos y rutas de la API](API_CONTRACT.md).

Revisión técnica y guía actualizadas el 9 de noviembre de 2026.
