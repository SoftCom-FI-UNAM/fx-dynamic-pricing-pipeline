# ADR 0002: AWS Lambda frente a AWS Glue para bronze → silver → gold

* **Estado:** Propuesto
* **Fecha:** 2026-11-12
* **Relacionado:** [ADR 0001](0001-arquitectura-serverless-medallon.md)

## Contexto

La transformación bronze → silver (validación, deduplicación, Parquet) y silver → gold (indicadores y estado vigente) puede implementarse con Lambda o con Glue. Los créditos de AWS alcanzarían para Glue, así que el costo cero no es el argumento: la decisión debe sostenerse con volumen, tiempo y costo.

## Volumen real por corrida

Fuentes: el código de `src/ingesta`, `infra/Lambdas.yaml` y el catálogo sintético del repositorio. **Las cifras marcadas como estimación son cálculos propios y deben medirse en la primera corrida real.**

| Dato | Volumen por corrida | Base |
|---|---|---|
| Ingesta diaria (FIX + inflación) | 1 a 2 observaciones por serie, menos de 5 KB de JSON | Estimación: el SIE devuelve el dato del día |
| Backfill histórico (FIX desde 1991) | Unos 8,000 registros, menos de 2 MB | Estimación: ~250 días hábiles por año |
| Catálogo | 100 SKU, 7 KB (70 bytes por fila) | Medido en `catalogo_sqlserver_sintetico.csv` |
| Catálogo real hipotético (1 millón de SKU) | Unos 70 MB | Extrapolación de los 70 bytes por fila |
| Corridas al mes | Unas 130 (2 series × 3 intentos diarios × ~22 días hábiles) | `ScheduleExpression` en `Lambdas.yaml` |

## Tiempo de ejecución y límites

| Concepto | Lambda | Glue (Spark) | Glue (Python shell) |
|---|---|---|---|
| Arranque | Menos de 1 s en frío (estimación) | 10 s a más de 30 s (estimación) | Alrededor de 10 s (estimación) |
| Tiempo por corrida esperado | 1 a 5 s (estimación) | Dominado por el arranque | Unos 10 a 20 s |
| Límite de ejecución | **15 minutos** | Horas | Horas |
| Memoria | Hasta 10,240 MB (hoy 512 MB configurados) | Mínimo 2 DPU, 16 GB | 1 DPU o 0.0625 DPU |
| Facturación mínima | 1 ms | 1 minuto | 1 minuto |

El requisito de alertar en menos de 5 minutos desde la publicación (N2 del SOW) deja poco margen para un arranque de Spark, sobre todo si se encadenan dos etapas.

## Costo comparado

Cálculo con precios de lista de us-east-1 (Lambda: USD 0.0000166667 por GB-s; Glue: USD 0.44 por DPU-hora). **Hay que validar precios y elegibilidad de la cuenta antes de usarlos como compromiso.**

| Opción | Cálculo | Costo mensual |
|---|---|---|
| Lambda, 512 MB, 5 s | 130 × 0.5 GB × 5 s = 325 GB-s | Menos de USD 0.01 (dentro de la capa gratuita) |
| Glue Python shell, 0.0625 DPU, mínimo 1 min | 130 × 0.0625 DPU × 1/60 h × 0.44 | Alrededor de USD 0.06 |
| Glue Spark, 2 DPU, mínimo 1 min | 130 × 2 DPU × 1/60 h × 0.44 | Alrededor de USD 1.90 |

La diferencia absoluta es mínima en las tres opciones. El costo no decide; deciden el arranque, la simplicidad operativa y la capacidad de crecimiento.

## Decisión

Usar **Lambda** para bronze → silver y silver → gold mientras se cumplan los umbrales de abajo. Cada capa debe ser su propia función, disparada por el objeto nuevo de la capa anterior, con prefijos distintos para evitar que una función se dispare a sí misma.

## Cuándo cambiaríamos a Glue

Se reevalúa si ocurre **cualquiera** de estas condiciones, medida en producción:

1. Una corrida procesa **más de 1 GB** de datos, o la memoria usada supera el **70%** de la configurada y ya no conviene subirla.
2. El tiempo p95 de una función supera **10 minutos**, es decir, dos tercios del límite de 15.
3. El catálogo real supera aproximadamente **5 millones de filas** (unos 350 MB) o requiere uniones contra históricos grandes.
4. Aparecen transformaciones que justifican Spark (particionado de varios años de datos, reprocesos masivos, uniones pesadas) o un catálogo de fuentes y esquemas que Glue Data Catalog gestione mejor.
5. El volumen crece unas 100 veces frente al actual y se confirma que se sostiene.

El reproceso histórico completo (backfill) también queda dentro de Lambda: unos 2 MB caben holgadamente. Si se reprocesara el catálogo completo de varios años, aplica la condición 3.

## Consecuencias

* Menor latencia y menor complejidad operativa; encaja con el objetivo de alerta en menos de 5 minutos.
* **Parquet en Lambda requiere una biblioteca.** El README propone "Python y biblioteca estándar", pero la biblioteca estándar no escribe Parquet. Habrá que añadir una capa (por ejemplo, AWS SDK for pandas / pyarrow) o aceptar otro formato para silver. Esto debe resolverse antes de implementar la Lambda de silver.
* Si se cruza algún umbral, la migración se limita a la capa afectada, porque cada una se dispara por archivos en S3 y no por llamadas directas.
* Las cifras de esta decisión son estimaciones hasta tener métricas de CloudWatch (duración, memoria, tamaño de los objetos). Conviene revisar este ADR tras el primer mes de operación.
