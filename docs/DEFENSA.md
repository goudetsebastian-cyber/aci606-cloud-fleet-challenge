# Guía de defensa del Ejercicio 4

## Explicación inicial (aproximadamente 90 segundos)

"El proyecto convierte el starter del docente en una plataforma para recibir y consultar telemetría de una flota virtual. Cada muestra se valida, se clasifica mediante un pipeline entrenado y se guarda junto con la predicción. El operador puede ver los robots, su batería, condición, posición e historial en el panel.

La arquitectura de despliegue usa Render para ejecutar FastAPI y Neon para PostgreSQL. Esta separación es importante porque el disco del servicio gratuito es efímero; los datos no pueden depender de la memoria o del archivo local del proceso.

Para el modelo generamos 64 flotas independientes, con 32.768 muestras. Reservamos 16 flotas completas para prueba y usamos validación por grupos en las otras 48. Comparamos regresión logística y Random Forest. Elegimos la regresión logística por su F1 de validación y su bajo coste de inferencia. En la prueba reservada obtuvo F1 macro de 0,926, frente a 0,198 de la clase mayoritaria.

Las pruebas locales comprueban datos inválidos, concurrencia y conservación de más de 100 registros después de reiniciar. La demostración pública debe mostrar esas mismas capacidades en la URL de Render."

Solo afirmar que la publicación y su reinicio están verificados después de completar las pruebas públicas y guardar su evidencia.

## Demostración sugerida (5 a 7 minutos)

1. Abrir `/health`: mostrar PostgreSQL, modelo y `instance_id`.
2. Enviar telemetría desde el simulador y abrir `/dashboard`; mostrar robots conectados, condiciones y batería.
3. Seleccionar un robot, cambiar la variable del gráfico y abrir el historial completo.
4. En `/docs`, ejecutar `/predict` con una muestra y explicar los cinco campos obligatorios. `confidence` es probabilidad estimada, no una garantía de calibración.
5. Enviar una batería fuera de rango: mostrar 422 y confirmar que `/health` sigue respondiendo.
6. Ejecutar la fase `before` de persistencia: guarda 125 muestras y su huella. Reiniciar el servicio desde Render y ejecutar `after`: deben cambiar el identificador del proceso y conservarse los datos.
7. Abrir `/metrics` y explicar solicitudes, errores, latencia y tiempo activo. Los contadores se reinician con el proceso; el historial permanece en PostgreSQL.

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
