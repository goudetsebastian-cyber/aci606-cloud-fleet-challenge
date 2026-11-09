# Guía de defensa del Ejercicio 4

## Explicación inicial (aproximadamente 90 segundos)

"El proyecto convierte el starter del docente en una plataforma para recibir y consultar telemetría de una flota virtual. Cada muestra se valida, se clasifica mediante un pipeline entrenado y se guarda junto con la predicción. El operador puede ver los robots, su batería, condición, posición e historial en el panel.

La arquitectura de despliegue usa Render para ejecutar FastAPI y Neon para PostgreSQL. Esta separación es importante porque el disco del servicio gratuito es efímero; los datos no pueden depender de la memoria o del archivo local del proceso.

Para el modelo generamos 64 flotas independientes, con 32.768 muestras. Reservamos 16 flotas completas para prueba y usamos validación por grupos en las otras 48. Comparamos regresión logística y Random Forest. Elegimos la regresión logística por su F1 de validación y su bajo coste de inferencia. En la prueba reservada obtuvo F1 macro de 0,926, frente a 0,198 de la clase mayoritaria.

Las pruebas locales comprueban datos inválidos, concurrencia y conservación de más de 100 registros después de reiniciar. La demostración pública debe mostrar esas mismas capacidades en la URL de Render."

Solo afirmar que la publicación y su reinicio están verificados después de completar las pruebas públicas y guardar su evidencia.

## Demostración sugerida (5 a 7 minutos)

1. Abrir `/health`: mostrar PostgreSQL, modelo y `instance_id`.
2. Abrir `/dashboard` y pulsar **Iniciar demostración**. Se activan seis robots durante dos minutos desde el navegador. Mostrar condiciones, batería e historial. El botón **Detener demostración** y el cierre de la pestaña detienen ese cliente. El lanzador del simulador de consola sigue disponible para las pruebas de carga y clientes externos.
3. Seleccionar un robot, cambiar la variable del gráfico y abrir el historial completo.
4. Abrir **Pruebas para la presentación** en el panel y pulsar **Obtener predicción**. Mostrar HTTP 200 y los cinco campos obligatorios. `confidence` es probabilidad estimada, no una garantía de calibración.
5. Pulsar **Probar dato inválido** para enviar una batería fuera de rango y mostrar HTTP 422.
6. Pulsar **Guardar 125 muestras** y esperar la confirmación. Abrir Render desde el enlace del panel y usar **Manual Deploy > Restart service**. Cuando ese reinicio termine en Live, volver al panel y pulsar **Verificar tras reinicio**. La verificación exige un identificador de arranque nuevo y el mismo hash de las 125 muestras. La referencia se conserva en PostgreSQL. Desde otro navegador, pulsa **Recuperar pruebas**, selecciona la prueba guardada y verifica; también se puede abrir **Enlace de esta prueba**. El programa `tests/check_persistence.py` mantiene la alternativa por consola.
7. Desplegar **Ver métricas completas del servicio** y explicar solicitudes, errores, latencia y tiempo activo. Los contadores se reinician con el proceso; el historial permanece en PostgreSQL.

## Preguntas probables y respuestas

**¿Por qué separar por fleet_id?** Las muestras de una misma flota comparten robots y dinámica temporal. Repartir filas al azar puede colocar observaciones relacionadas a ambos lados de la prueba y producir una estimación optimista. Aquí ningún fleet_id aparece en entrenamiento y prueba.

**¿Por qué F1 macro?** Promedia el F1 de NORMAL, WARNING y CRITICAL con el mismo peso; una clase frecuente no domina la métrica como puede ocurrir con accuracy. En este dataset CRITICAL es la más frecuente; los conteos se reportan como se observaron.

**¿Por qué regresión logística?** Su media de validación por grupos fue 0,9249 frente a 0,9202 de Random Forest. Además, el pipeline es pequeño y la inferencia barata. La decisión se fijó antes de evaluar las flotas reservadas.

**¿Es una regla manual de temperatura?** No. Los límites de salud del simulador generan las etiquetas para entrenamiento; el servicio no conoce esa salud oculta. Recibe seis sensores y calcula probabilidades con un clasificador aprendido.

**¿Qué evita la pérdida de historial?** Una transacción por muestra en PostgreSQL gestionado. No hay `deque(maxlen=100)` ni borrado al desconectarse un robot. El endpoint devuelve todo el historial; `limit` y `offset` son opcionales para el panel.

**¿Qué ocurre con muestras desordenadas?** El historial se ordena por timestamp e identificador; `/robots` elige el timestamp más nuevo y no el último POST recibido. La conexión se calcula por tiempo de recepción.

**¿Por qué PaaS?** El grupo administra código, modelo y datos; el proveedor opera el entorno, sistema y servidores. Render aporta proceso web y HTTPS; Neon administra PostgreSQL.

**¿Cómo se recupera la conexión a Neon?** SQLAlchemy comprueba las conexiones antes de usarlas (`pool_pre_ping`) y recicla conexiones antiguas. Los fallos de base devuelven 503 sin exponer credenciales.

**¿Qué mide inference_ms?** El trabajo interno del pipeline; no incluye la red ni el arranque en frío. El evaluador de flotas también mide p50 y p95 desde el cliente, que sí reflejan el recorrido de la solicitud.

**¿Qué falta para producción real?** Datos y validación reales, autenticación y límites de uso, políticas de retención, migraciones, copias de seguridad y monitoreo externo. El alcance actual es el ejercicio con telemetría sintética y acceso evaluable por el docente.

## Relación con las clases de persistencia

La [revisión de los materiales](ALINEACION_CLASES.md) relaciona cada concepto con el código y la evidencia. La práctica de sensores en Colab enseña un patrón; las rutas y entregables de este trabajo siguen siendo los del Ejercicio 4.

**¿Qué estado es volátil y cuál persiste?** Los contadores, el uptime y la ventana de latencias viven en RAM y se reinician. La telemetría y su predicción viven en PostgreSQL. El modelo se reconstruye en memoria a partir del artefacto versionado. Perder los contadores no significa perder el historial.

**¿Qué significa separar cómputo y datos aquí?** Render puede reemplazar el proceso de la API y volver a conectarlo a la misma base de Neon. El historial no está ligado al disco de esa instancia. La API sí mantiene métricas locales; con varias réplicas habría que reunirlas mediante un sistema externo de observabilidad.

**¿Cómo se aplica ACID?** Cada muestra y su predicción se guardan juntas dentro de `engine.begin()`: se confirma todo o se revierte ante un error. La API valida la entrada; el esquema exige clave primaria y columnas no nulas. PostgreSQL gestiona las transacciones concurrentes. Solo se responde `accepted=true` después del commit. Las pruebas de concurrencia y reinicio cubren esos escenarios; no demuestran aislamiento serializable ni recuperación de un desastre.

**¿Para qué sirve el índice?** `(robot_id, timestamp, id)` ofrece una ruta de acceso acorde con buscar y ordenar el historial de un robot. Ocupa espacio y debe actualizarse al insertar. El motor elige si usarlo; no medimos su mejora con un análisis del plan de ejecución.

**¿Por qué consultar y agregar en la base?** `COUNT`, `MAX` y la consulta de último evento trabajan cerca de los datos. `/robots` devuelve una fila por robot y evita enviar el historial completo para calcular su resumen. El promedio de batería del panel se calcula sobre ese resumen pequeño.

**¿Por qué SQLite en la clase y PostgreSQL aquí?** SQLite permite observar persistencia manteniendo un archivo local. Ese archivo puede sobrevivir al proceso, pero no a la eliminación de su disco efímero. El Ejercicio 4 despliega la API en Render y separa el almacenamiento en Neon. SQLite se conserva como opción de desarrollo.

**¿Qué sigue siendo responsabilidad del grupo con DBaaS?** El esquema, consultas, índices, credenciales, permisos, calidad y políticas de uso. Las capacidades de respaldo y recuperación dependen del servicio contratado y hay que comprobarlas. Nuestra prueba confirma datos intactos tras reiniciar Render; no se ha hecho una restauración desde un respaldo.

**¿Qué ocurriría con cien veces más clientes?** Habría que medir conexiones, costo de consultas históricas, escrituras y CPU de inferencia. El pool tiene cinco conexiones y cinco adicionales; las consultas de resumen del panel recorren información histórica. La evaluación de 512 solicitudes, con ocho en paralelo, corresponde a predicción, no a un ensayo de volumen de almacenamiento.
