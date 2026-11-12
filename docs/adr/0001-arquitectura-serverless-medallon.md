# ADR 0001: Arquitectura serverless con data lake en S3 (medallón) e IaC con CloudFormation

* **Estado:** Propuesto
* **Fecha:** 2026-11-12
* **Contexto del proyecto:** Sistema de blindaje cambiario y precio dinámico (ImportaTech Mexico)

## Contexto

El sistema ingiere diariamente el tipo de cambio FIX y la inflación del SIE de Banxico, conserva el dato original, calcula indicadores de riesgo, alerta anomalías en menos de 5 minutos y expone el estado vigente al e-commerce con latencia objetivo inferior a 250 ms. El volumen es muy pequeño (series diarias), el presupuesto operativo objetivo es de hasta $4,500 MXN mensuales y el catálogo vive en SQL Server, que no se debe migrar ni modificar.

## Decisión

1. **Cómputo con AWS Lambda (Python 3.13)** para ingesta, validación/cálculo, evaluación de catálogo y consulta. No se usa ECS/Fargate.
2. **Orquestación por eventos:** EventBridge Scheduler dispara la ingesta (días hábiles, tres intentos idempotentes); reglas de EventBridge disparan la validación al crearse un objeto en bronze y la evaluación de catálogo al llegar un export nuevo.
3. **Data lake en S3 con arquitectura medallón y versionado**, un bucket por capa:
   * `bronze`: payload original de Banxico, para reprocesar la historia.
   * `silver`: histórico limpio y validado (Parquet).
   * `gold`: estado vigente (JSON pequeño) y resultados de evaluación.
   * `catalog`: export periódico del catálogo de SQL Server.
   * `artifacts`: paquetes `.zip` de las Lambdas.
4. **La API solo lee el estado vigente** (objeto JSON en gold) mediante la Lambda de consulta (`GET /v1/risk/current`, `/v1/health`); no ejecuta consultas analíticas síncronas.
5. **Alertas** con SNS cuando la validación detecta una anomalía; **observabilidad** con CloudWatch (logs y alarmas de errores por Lambda).
6. **Secretos y permisos:** token de Banxico en Parameter Store (`SecureString`); un rol IAM por función con mínimo privilegio; CloudTrail para auditoría.
7. **CloudFormation como única herramienta de IaC**, en dos plantillas con despliegue ordenado: `infra/Buckets.yaml` (almacenamiento) y `infra/Lambdas.yaml` (funciones, programación, disparadores, alertas y alarmas), que importa los nombres de la primera.
8. **Umbrales de anomalía parametrizados** (`AnomalyWindow`=7, `AnomalySigma`=2) como propuesta inicial, sujetos a aprobación de Finanzas/Precios.

## Alternativas consideradas

* **ECS/Fargate o instancias EC2:** innecesario para una serie diaria pequeña y más costoso de operar.
* **Base de datos (documental o relacional) activa para el histórico:** agrega costo y administración; S3 con versionado cubre reprocesamiento y consulta del estado vigente.
* **Consultas analíticas (p. ej. Athena) desde la API:** no cumplen de forma fiable el objetivo de 250 ms.
* **Terraform/CDK:** se descartan para mantener una sola herramienta de IaC nativa de AWS.
* **Migrar o conectar directamente SQL Server:** fuera de alcance; se usa exportación periódica acordada con el cliente.

## Consecuencias

**Positivas**
* Costo bajo y proporcional al uso; sin servidores que administrar.
* Dato crudo inmutable y versionado: reprocesable y auditable.
* Despliegues reproducibles y revisables.

**Negativas / riesgos**
* El FIX es diario: la API devuelve el último estado publicado, no una cotización intradía.
* Dependencia de la disponibilidad de la API del SIE y de la frescura del export del catálogo.
* El costo cero no está garantizado; hay que validar cuotas, precios y elegibilidad del Free Tier.
* Los umbrales de anomalía y la serie de inflación aún requieren validación del cliente.

## Pendientes

* `Lambdas.yaml` define la Lambda de consulta pero no incluye el recurso de Amazon API Gateway que la expone; debe añadirse o desplegarse aparte.
* Las plantillas hacen referencia a `01-storage.yaml`; el nombre del archivo en el repositorio es `Buckets.yaml`. Alinear nombres o la descripción.
* README y diagrama mencionan "raw/curated/current"; las plantillas usan bronze/silver/gold. Unificar la terminología.
