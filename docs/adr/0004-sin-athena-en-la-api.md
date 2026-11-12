# ADR 0004: La API no consulta Athena; lee un objeto JSON con el estado vigente

* **Estado:** Propuesto
* **Fecha:** 2026-11-12
* **Relacionado:** [ADR 0001](0001-arquitectura-serverless-medallon.md)

## Contexto

El requisito N3 pide consultar el estado de riesgo con un objetivo de latencia p99 inferior a 250 ms. El histórico limpio se guarda en Parquet en S3 (silver) y se podría consultar con Athena, pero Athena está pensado para consultas analíticas, no para respuestas síncronas de una API.

## Decisión

El pipeline calcula el estado vigente y lo escribe como un objeto JSON pequeño en `gold`. La Lambda de consulta (`GET /v1/risk/current`, `/v1/health`) solo lee ese objeto y lo devuelve. La API no ejecuta consultas analíticas síncronas. Athena puede usarse fuera de la API, para análisis ad hoc del histórico.

## Alternativas consideradas

* **Athena desde la API:** la consulta se planifica y ejecuta de forma asíncrona y su duración se mide en segundos, no en milisegundos; no es adecuada para un p99 de 250 ms. Además cobra por datos escaneados.
* **DynamoDB u otra base de baja latencia:** cumpliría la latencia, pero añade un servicio y costo para un dato que cabe en un solo objeto por serie diaria. El SOW lo deja como cambio controlado si S3 no cumple.

## Consecuencias

* Latencia determinada por una lectura de S3 y una invocación de Lambda; hay que medirla (p95 y p99) con una carga acordada, como pide el SOW.
* La API solo devuelve el último estado publicado; no hay consultas históricas por la API.
* Si las pruebas muestran que S3 no cumple el p99 de 250 ms, se evaluará una capa de estado de baja latencia (por ejemplo DynamoDB o caché) como cambio controlado y con estimación de costo.
* La Lambda de consulta existe, pero Amazon API Gateway aún no está en las plantillas.
