# ADR 0002: AWS Lambda frente a AWS Glue para bronze → silver → gold

* **Estado:** Propuesto
* **Fecha:** 2026-11-12
* **Relacionado:** [ADR 0001](0001-arquitectura-serverless-medallon.md)

## Contexto

La transformación de bronze a silver (validación, deduplicación, Parquet) y de silver a gold (indicadores y estado vigente) puede implementarse con Lambda o con Glue. Los créditos de AWS alcanzarían para Glue, así que el costo cero no es el argumento. La decisión se basa en el tamaño del problema y en la complejidad que cada opción añade.

## Decisión

Usar **AWS Lambda** para las transformaciones de bronze → silver y silver → gold. Cada capa es su propia función, disparada por el objeto nuevo de la capa anterior, con prefijos distintos para que ninguna función se dispare a sí misma.

## Justificación

* **El volumen es muy pequeño.** El pipeline procesa una o dos observaciones diarias por serie (tipo de cambio e inflación) y un catálogo de productos de tamaño modesto. Es una carga que una función pequeña resuelve en segundos; un motor distribuido como Spark estaría muy sobredimensionado.
* **El costo es mínimo.** Lambda cobra solo por el tiempo de ejecución, que aquí es muy corto, y queda prácticamente dentro de la capa gratuita. Glue cobra por capacidad reservada con un tiempo mínimo de facturación por corrida, así que es más caro para una tarea tan pequeña, aunque la diferencia absoluta sea baja.
* **Arranque rápido.** El SOW exige alertar anomalías en menos de cinco minutos desde la publicación del dato. Lambda arranca casi de inmediato; un trabajo de Glue tarda bastante más en iniciar, lo que consume parte de ese margen, sobre todo al encadenar dos etapas.
* **Curva de aprendizaje más corta.** Lambda con Python se escribe y se prueba como código normal. Glue exige aprender su modelo de trabajos, el catálogo de datos, los conectores y, si se usa Spark, el propio Spark. Para un equipo pequeño y un plazo de pocas semanas, esa inversión no se justifica.
* **Menos piezas que operar.** Lambda ya es parte del diseño (ingesta, catálogo y consulta). Usarla también para las transformaciones mantiene una sola forma de empaquetar, desplegar con CloudFormation y monitorear con CloudWatch.
* **Encaja con la arquitectura por eventos.** Un objeto nuevo en S3 dispara la función de la siguiente capa de forma natural, sin orquestación adicional.

## Alternativas consideradas

* **Glue con Spark:** pensado para grandes volúmenes y transformaciones distribuidas. No hay ese problema aquí.
* **Glue con Python shell:** más ligero que Spark, pero sigue añadiendo arranque más lento, otro servicio que aprender y desplegar, y poca ventaja sobre Lambda para esta carga.

## Cuándo cambiaríamos a Glue

Se reevaluaría la decisión si:

* El volumen por corrida crece hasta acercarse a los límites de memoria o de tiempo de ejecución de Lambda, o la función empieza a tardar lo suficiente para poner en riesgo el límite de ejecución.
* El catálogo real resulta mucho mayor de lo supuesto o requiere uniones pesadas contra históricos grandes.
* Aparecen transformaciones que sí justifican Spark, como reprocesos masivos de varios años de datos.
* El equipo adopta Glue para otras cargas y conviene unificar herramientas.

Estos criterios se revisarán con las métricas reales de CloudWatch (duración, memoria y tamaño de los objetos) una vez que el pipeline esté en operación.

## Consecuencias

* Menor latencia, menor costo y menor complejidad operativa.
* Hay un techo de escala: si el volumen crece mucho, será necesario migrar la capa afectada. Como cada capa se dispara por archivos en S3 y no por llamadas directas, esa migración quedaría acotada.
* **Parquet en Lambda requiere una biblioteca.** El README propone "Python y biblioteca estándar", pero la biblioteca estándar no escribe Parquet. Habrá que añadir una capa de Lambda (por ejemplo, AWS SDK for pandas o pyarrow) o elegir otro formato para silver. Debe resolverse antes de implementar la función de silver.
