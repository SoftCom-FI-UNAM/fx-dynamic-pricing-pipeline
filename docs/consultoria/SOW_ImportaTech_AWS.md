# SOW: Sistema de blindaje cambiario y precio dinámico

**Consultora:** SOFTCOM DATA ENGINEERING SOLUTIONS
**Cliente:** ImportaTech Mexico
**Respuesta al RFP del:** 05/10/2026
**Versión:** 2.0 (Arquitectura Cloud Native en AWS)
**Equipo:** 
* Ing. Victoria Monserrat Muñoz San Agustin, Project Manager & Data Architect (Líder)
* Ing. Santiago Velasco Garcia, Data Engineer (Ingesta - Bronze Zone)
* Ing. Mauricio Acosta Díaz, Data Engineer (Procesamiento - ETL & Analytics)
* Ing. José Rodrigo López López, Data Engineer (DBA - Gold Zone)
* Ing. Héctor Guerrero Gutiérrez, Desarrollador Backend (Backend API Developer)

## 1. Resumen ejecutivo
Entendemos la criticidad del riesgo cambiario y el impacto directo de la latencia de datos en su margen operativo. Diseñaremos e implementaremos un pipeline de datos *end-to-end* automatizado y resiliente sobre Amazon Web Services (AWS). El sistema extraerá la data de Banxico, procesará umbrales de volatilidad mediante contenedores efímeros y expondrá el riesgo en tiempo real a su e-commerce vía una API de baja latencia. Todo esto bajo un esquema de infraestructura como código (IaC), garantizando el cumplimiento de las 8 semanas de entrega, con un TCO (Total Cost of Ownership) en la nube estrictamente inferior a $4,500 MXN mensuales y un Capex de $345,000 MXN.

## 2. Alcance
**Dentro de alcance:**
* Despliegue de infraestructura base en AWS (VPC, IAM, Security Groups, Secrets Manager).
* Pipeline de ingesta serverless (Amazon EventBridge + AWS Lambda) conectada a la API del SIE de Banxico.
* Almacenamiento crudo (Bronze) en una base de datos documental (MongoDB / Amazon DocumentDB) garantizando inmutabilidad.
* Desarrollo de un contenedor dedicado (AWS ECS Fargate) para ejecutar scripts en Python (Pandas/NumPy) que limpiarán los datos y detectarán anomalías de volatilidad.
* Almacenamiento estructurado (Gold) en Amazon RDS for PostgreSQL.
* Capa de servicio API REST (Flask) orquestada en AWS y expuesta mediante Amazon API Gateway para consumo del e-commerce.

**Fuera de alcance:**
* Modificaciones al frontend del e-commerce (El RFP excluye desarrollo visual).
* Mecanismos de hedging financiero o derivados cambiarios (Restricción explícita).
* Integración con pasarelas de pago (Stripe, PayPal, etc.).

## 3. Entregables y criterios de aceptación
| # | Entregable | Criterio de aceptación | Hito |
|---|---|---|---|
| E1 | Infraestructura como Código (IaC) | Scripts de Terraform/CloudFormation para el despliegue replicable en AWS. | 1 |
| E2 | Pipeline de Ingesta (Bronze) | Ejecución idempotente diaria que guarda el *payload* crudo en MongoDB sin pérdida de datos. Monitoreo en AWS CloudWatch evidenciando >99.5% de éxito. | 2 |
| E3 | Motor ETL y Detección (Gold) | Contenedor Python procesando y escribiendo en PostgreSQL en < 5 minutos tras la ingesta. | 3 |
| E4 | API REST (Flask sobre AWS) | Endpoint en Amazon API Gateway respondiendo con latencia p99 < 250 ms. | 4 |
| E5 | Documentación y Handoff | Repositorio Git documentado, diagramas de arquitectura AWS y sesión técnica al equipo. | 5 |

## 4. Trazabilidad con el RFP
| Necesidad del RFP | Entregable(s) que la cubre(n) | Estado |
|---|---|---|
| N1 (Monitoreo automatizado Banxico) | E2 | Cubierta |
| N2 (Identificación inmediata de saltos) | E3 | Cubierta |
| N3 (Consulta rápida del estatus) | E4 | Cubierta |
| N4 (Protección del margen comercial) | E3, E4 | Cubierta |

## 5. Enfoque técnico (alto nivel)
Como ingenieros de datos, priorizamos la resiliencia y la inmutabilidad. La arquitectura *end-to-end* iniciará con Amazon EventBridge disparando una AWS Lambda que extraerá los datos del SIE y hará un volcado crudo (Bronze) en MongoDB. Esto dispara un evento hacia AWS ECS (Fargate), donde levantaremos un contenedor efímero con Python, Pandas y NumPy. Este motor calculará varianzas y medias móviles para detectar anomalías, escribiendo los resultados (Gold) en Amazon RDS (PostgreSQL). Finalmente, un backend en Flask, expuesto a través de Amazon API Gateway y balanceadores de carga, servirá la data al e-commerce con tiempos de respuesta de milisegundos. Las credenciales y tokens se gestionarán estrictamente en AWS Secrets Manager.

## 6. Plan por hitos
| Hito | Qué se entrega | Evidencia | Fecha | Horas |
|---|---|---|---|---|
| 0 Setup | Definición de umbrales, diseño de VPC y repositorios | Arquitectura AWS final aprobada | Sem 1 | 25 |
| 1 Infra e Ingesta | IaC desplegada, ingesta a MongoDB | Logs de CloudWatch de extracción exitosa | Sem 3 | 60 |
| 2 Motor ETL | Contenedor Python (Pandas/NumPy) y RDS PostgreSQL | Ejecución exitosa del cálculo de varianza | Sem 5 | 80 |
| 3 Capa API | API Flask y Amazon API Gateway | Pruebas de carga (Locust) con latencia <250ms | Sem 7 | 70 |
| 4 Producción | CI/CD final, Manuales y Handoff | Firma de paso a producción (Go-Live) | Sem 8 | 25 |

## 7. Equipo y responsabilidades
* **Ing. Victoria Monserrat Muñoz San Agustin (Project Manager & Data Architect):** Diseño de la canalización de datos, gobierno de datos, configuración de IAM/Networking en AWS y aseguramiento de idempotencia. Reporta directamente a Logística y Finanzas de ImportaTech.
* **Ing. Santiago Velasco Garcia (Data Engineer - Ingesta):** Desarrollo del script de ingesta a MongoDB y orquestación del pipeline serverless para la zona Bronze.
* **Ing. Mauricio Acosta Díaz (Data Engineer - Procesamiento):** Modelado analítico en Pandas/NumPy dentro de contenedores efímeros para la detección de picos y cálculo de varianzas.
* **Ing. José Rodrigo López López (Data Engineer - DBA):** Diseño del modelo relacional en PostgreSQL, estructuración de la base de datos histórica y optimización de consultas.
* **Ing. Héctor Guerrero Gutiérrez (Desarrollador Backend API):** Desarrollo del microservicio Flask y optimización de latencia en API Gateway para exposición al e-commerce.

## 8. Supuestos y dependencias del cliente
* **Supuestos:** El esquema de red del cliente permite conexiones entrantes desde direcciones IP elásticas de AWS o se configurará un API Gateway con WAF (Web Application Firewall) público restringido por API Keys.
* **Dependencias:** El equipo de Logística y Finanzas deberá definir matemáticamente la "anomalía crítica" (ej. > 2 desviaciones estándar en promedio móvil de 7 días) durante la Semana 1. El cliente proporcionará el token de Banxico, el cual rotaremos e inyectaremos en AWS Secrets Manager.

## 9. Riesgos
| Riesgo | Probabilidad | Impacto | Qué haremos (Mitigación) |
|---|---|---|---|
| Cambios en la estructura del *payload* de Banxico. | Media | Alto | El enfoque *Medallion* guarda el dato crudo en MongoDB (sin esquema estricto). El ETL fallará seguro, enviará alerta SNS y nos permitirá reprocesar la historia sin perder datos originales. |
| Exceder latencia de 250ms en la API por arranques en frío (*Cold Starts*). | Media | Medio | Usaremos *Provisioned Concurrency* o mantendremos contenedores base activos en ECS para garantizar respuesta inmediata. |
| Superar el presupuesto mensual de AWS ($4,500 MXN). | Baja | Alto | Diseño Serverless agresivo (Lambdas, Fargate SPOT para ETL, y RDS en capa t4g/Burstable). |

## 10. Presupuesto
| Concepto | Horas | Tarifa MXN/h | Subtotal MXN |
|---|---|---|---|
| Arquitectura Cloud y Gestión (AWS Setup) | 40 | $1,500 | $60,000 |
| Data Engineering (Ingesta Bronze y Motor ETL) | 120 | $1,300 | $156,000 |
| Backend & API Integration (Gold y Servicio) | 90 | $1,300 | $117,000 |
| Colchón de imprevistos / Aseguramiento QA | | | $12,000 |
| **Total del Proyecto de Desarrollo** | 250 | | **$345,000** |

**Costo Operativo Nube (Estimación mensual AWS):**
* Amazon RDS (PostgreSQL db.t4g.micro Multi-AZ): ~$1,100 MXN
* MongoDB (Atlas Serverless / DocumentDB mínimo): ~$500 MXN
* AWS ECS Fargate (Cálculo efímero) + Lambdas + API Gateway: ~$1,000 MXN
* Networking, Secrets Manager y CloudWatch: ~$600 MXN
* **Total estimado AWS: ~$3,200 MXN/mes** *(Cumpliendo la restricción de $4,500 MXN).*

## 11. Control de cambios y comunicación
Implementaremos metodologías ágiles con sprints de 2 semanas. Al final de cada hito habrá un *Sprint Review* con demostración del software funcionando en un entorno de *Staging* en AWS. Cualquier alteración de alcance se documentará en Jira y requerirá aprobación formal si altera el *baseline* de presupuesto o tiempo.

## 12. Aceptación y pagos
Los entregables de cada hito se validarán contra los Criterios de Aceptación usando pruebas automatizadas.
* 20% al firmar y validar la arquitectura en AWS (Hito 0).
* 40% al liberar el procesamiento ETL escribiendo exitosamente en PostgreSQL (Hito 2).
* 40% al estabilizar la API en producción y finalizar la transferencia de conocimiento (Hito 4).
