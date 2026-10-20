# RFP: Sistema de blindaje cambiario y precio dinámico

**Cliente:** ImportaTech Mexico  
**Contacto:** finance@importech.com *(confirmar que el dominio corresponde al cliente antes de publicar)*  
**Equipo redactor:** Comité de Transformación Digital y Control de Inventarios  
**Fecha de publicación:** 05/10/2026

---

## Quiénes somos

Somos una empresa de comercio electrónico en Venustiano Carranza, Ciudad de México, dedicada a la distribución minorista de refacciones, tecnología y equipo industrial ligero (sistemas de soldadura e inversores, compresores y herramientas neumáticas, generadores portátiles, maquinaria de banco y equipos para manejo de carga menor). Adquirimos el 100% de nuestro catálogo a fabricantes y mayoristas internacionales cotizados en dólares estadounidenses (USD) y vendemos a través de nuestros canales digitales cobrando en pesos mexicanos (MXN). Contamos con un equipo de 45 personas distribuidas entre compras internacionales, almacén central, atención al cliente y soporte técnico de la plataforma.

## El problema

Cuando el dólar experimenta un salto abrupto, el negocio queda expuesto. Al pagar inventario en USD y mantener precios fijos en MXN, la falta de actualización oportuna puede hacer que se venda mercancía por debajo del costo de reposición. Las revisiones cambiarias manuales y desfasadas pueden reducir los márgenes operativos y afectar la caja.

## Qué necesitamos lograr

| # | Necesidad | Cómo sabemos que se cumplió (medible) |
|---|---|---|
| **N1** | Monitoreo automatizado del tipo de cambio oficial y la inflación sin captura manual. | Ingesta diaria verificada del tipo de cambio FIX del SIE de Banxico a las 12:30 PM, o tan pronto como esté publicado y disponible, con éxito en al menos 99.5% de los días hábiles del periodo de medición acordado. La serie de inflación se ingiere según su periodicidad oficial y se conserva la fecha de observación. |
| **N2** | Identificación inmediata de saltos críticos en la divisa. | Emisión de alertas de volatilidad/anomalía en menos de 5 minutos desde que el indicador oficial está disponible para el pipeline. |
| **N3** | Consulta rápida del estado de riesgo para el e-commerce. | Endpoint con tiempo de respuesta p99 inferior a 250 ms bajo una carga de prueba acordada. La API devuelve el último estado calculado con la publicación oficial disponible; no representa una cotización intradía. |
| **N4** | Protección del margen comercial durante eventos de alta volatilidad. | Reducir en 50% las ventas cerradas con margen negativo atribuible al desbalance cambiario frente al trimestre anterior, usando una definición y línea base aprobadas por Finanzas. El resultado depende también de la adopción de recomendaciones por el e-commerce. |

## Qué NO queremos en este proyecto

- No incluye el rediseño, desarrollo visual ni remaquetación de la página de nuestra tienda en línea.
- No contempla la renegociación contractual, automatización de pagos bancarios ni dispersión de transferencias a proveedores en el extranjero.
- No abarca modelos especulativos de compra/venta de divisas (hedging financiero, futuros o derivados cambiarios).
- No incluye la administración o integración de pasarelas de pago de la tienda (Stripe, Mercado Pago, PayPal).

## Datos que tenemos y datos que faltan

- **Datos que tenemos:** Catálogo de productos centralizado en una base de datos relacional transaccional (Microsoft SQL Server Standard Edition), operando bajo licenciamiento comercial corporativo con suscripción anual y renovación obligatoria al cierre de cada ejercicio fiscal. Contiene SKU, costo base de compra en USD, precio de venta vigente en MXN, stock actual y reglas de margen objetivo por categoría.
- **Datos externos identificados:** API del Sistema de Información Económica (SIE) de Banxico, con token y series de tipo de cambio FIX e inflación.
- **Datos que faltan / dudas:** Umbrales históricos formales de volatilidad para definir qué porcentaje o desviación constituye una anomalía crítica. También deben acordarse la línea base y el método de cálculo de N4, así como la frecuencia/formato de extracción del catálogo.

## Restricciones

- **Presupuesto máximo:** $380,000 MXN para desarrollo e implementación.
- **Plazo:** Entrega final y puesta en producción en un máximo de 8 semanas naturales a partir de la firma del contrato.
- **Costo de operación mensual máximo:** $4,500 MXN para infraestructura de datos y hosting.
- **Seguridad y privacidad:** Credenciales, llaves de API y tokens deben viajar cifrados y gestionarse mediante mecanismos seguros; las métricas internas de márgenes o costos no deben exponerse al público.
- **Quién lo va a usar:** Equipo de desarrollo interno del e-commerce (consumo vía API) y Gerencia de Finanzas/Precios (revisión de logs, estado de alertas y umbrales).

## Qué esperamos recibir

1. Pipeline de datos automatizado que capture, almacene en crudo y procese los indicadores del SIE de Banxico.
2. Motor de detección de anomalías y cálculo de volatilidad parametrizable según reglas de negocio aprobadas.
3. Histórico de tipos de cambio, inflación, variaciones y banderas de riesgo con validaciones de calidad.
4. Servicio API desacoplado y documentado para consultar si el catálogo requiere ajuste de precio o congelamiento de descuentos.
5. Alertas de anomalías y fallos de ingesta, manual de operación y sesión de transferencia de conocimiento.
6. Diagrama de arquitectura con seguridad, gobierno y auditoría.

## Cómo evaluaremos las propuestas

| Criterio | Peso |
|---|---:|
| Robustez de arquitectura de datos y resiliencia ante caídas del proveedor de origen | 30 |
| Claridad del plan de trabajo, cronograma y viabilidad del plazo | 25 |
| Cumplimiento de restricciones presupuestarias y costo mensual en la nube | 20 |
| Experiencia demostrable en ingeniería de datos e integración de APIs | 15 |
| Mitigación de riesgos técnicos y soporte post-lanzamiento | 10 |
| **Total** | **100** |

## Qué debe incluir su propuesta

- **Statement of Work (SOW):** alcance, entregables, supuestos y exclusiones.
- **Arquitectura de solución:** diagrama conceptual, tecnologías propuestas y justificación.
- **Cronograma:** desglose semanal de hitos, revisiones y fechas de entrega.
- **Equipo de trabajo:** perfiles y experiencia verificable.
- **Matriz de riesgos:** riesgos operativos/técnicos y contingencias.
- **Propuesta económica:** honorarios de desarrollo y estimación mensual de infraestructura.

## Calendario del proceso

- **Fecha límite para preguntas y aclaraciones:** 16 de octubre de 2026.
- **Fecha límite para entrega de propuestas:** 23 de octubre de 2026, hasta las 18:00 CST.
- **Fecha de decisión y adjudicación:** 30 de octubre de 2026.
