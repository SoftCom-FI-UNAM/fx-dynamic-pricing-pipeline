# RFP: Sistema de blindaje cambiario y precio dinámico

**Cliente:** ImportaTech Mexico  
**Contacto:** Dirección de Logística y Finanzas  
**Equipo redactor:** Comité de Transformación Digital y Control de Inventarios  
**Fecha de publicación:** 05/10/2026

\---

## Quiénes somos

Somos una empresa de comercio electrónico en Ciudad de México dedicada a la distribución minorista de refacciones, tecnología y equipo industrial ligero (sistemas de soldadura e inversores, compresores y herramientas neumáticas, generadores portátiles, maquinaria de banco y equipos para manejo de carga menor). Adquirimos el 100% de nuestro catálogo a fabricantes y mayoristas internacionales cotizados en dólares estadounidenses (USD) y vendemos a través de nuestros canales digitales cobrando en pesos mexicanos (MXN). Contamos con un equipo de 45 personas distribuidas entre compras internacionales, almacén central, atención al cliente y soporte técnico de la plataforma.

## El problema

Cada vez que el dólar experimenta un salto abrupto en el mercado, nuestro negocio queda descubierto. Al pagar inventario en USD y mantener precios fijos en MXN en la tienda online, la falta de actualización inmediata hace que vendamos mercancía por debajo del costo real de reposición. Hoy en día, las revisiones cambiarias se hacen de forma manual y desfasada por días, lo que provoca que en cada pico de volatilidad financiera absorbamos la pérdida directa en nuestros márgenes operativos, amenazando la rentabilidad y la caja de la empresa.

## Qué necesitamos lograr

|#|Necesidad|Cómo sabemos que se cumplió (medible)|
|-|-|-|
|**N1**|Monitoreo automatizado del tipo de cambio oficial e inflación sin captura manual.|Ingesta diaria verificada del tipo de cambio FIX del SIE de Banxico a las 12:30 PM (o inmediatamente al ser publicado por Banxico) sin fallos en el 99.5% de los días hábiles.|
|**N2**|Identificación inmediata de saltos críticos en la divisa.|Emisión de alertas de volatilidad/anomalía en menos de 5 minutos tras el cierre/publicación del indicador oficial.|
|**N3**|Consulta rápida del estatus de riesgo para el e-commerce.|Endpoint de consulta disponible con tiempo de respuesta inferior a 250 ms para evaluar si se deben actualizar precios o pausar promociones.|
|**N4**|Protección del margen comercial en eventos de alta volatilidad.|50% de ventas cerradas con margen negativo atribuible a desbalance cambiario durante picos de volatilidad a partir de la puesta en marcha.|

## Qué NO queremos en este proyecto

* No incluye el rediseño, desarrollo visual ni remaquetación de la página de nuestra tienda en línea.
* No contempla la renegociación contractual, automatización de pagos bancarios ni dispersión de transferencias a proveedores en el extranjero.
* No abarca modelos especulativos de compra/venta de divisas (hedging financiero, futuros o derivados cambiarios).
* No incluye la administración o integración de pasarelas de pago de la tienda (Stripe, Mercado Pago, PayPal).

## Datos que tenemos y datos que faltan

* **Datos que tenemos:** Catálogo de productos centralizado en una base de datos relacional transaccional (Microsoft SQL Server Standard Edition), operando bajo licenciamiento comercial corporativo con suscripción anual y renovación obligatoria al cierre de cada ejercicio fiscal. Contiene registros estructurados y altamente confiables integrados a la plataforma de comercio electrónico: SKU, costo base de compra en USD, precio de venta vigente en MXN, stock actual y reglas de margen objetivo por categoría. Datos estructurados, altamente confiables.
* **Datos externos identificados:** Servicio API del Sistema de Información Económica (SIE) de Banxico (requiere token y parametrización de series de tipo de cambio FIX e inflación). El cual es de acceso libre previo registro de token.
* **Datos que faltan / dudas:** Umbrales históricos formales de volatilidad para definir con precisión matemática qué porcentaje o desviación estándar constituye una "anomalía crítica" para nuestro mix de productos.

## Restricciones

* **Presupuesto máximo:** $380,000 MXN para el desarrollo e implementación de la solución completa.
* **Plazo:** Entrega final y puesta en producción en un máximo de 8 semanas naturales a partir de la firma del contrato.
* **Costo de operación mensual máximo:** $4,500 MXN mensuales para infraestructura de datos y hosting de la solución.
* **Seguridad y privacidad:** Las credenciales de acceso a catálogos, llaves de API institucionales y tokens de servicio deben viajar cifrados y gestionarse mediante variables de entorno seguras; ninguna métrica interna de márgenes o costos debe exponerse al público.
* **Quién lo va a usar:** El equipo de desarrollo interno del e-commerce (consumo vía API) y la Gerencia de Finanzas/Precios (revisión de logs, estado de alertas y umbrales de margen).

## Qué esperamos recibir

1. Pipeline de datos automatizado que capture, almacene en crudo y procese los indicadores del SIE de Banxico de forma desatendida.
2. Motor de detección de anomalías y cálculo de volatilidad parametrizable según reglas de negocio definidas.
3. Base de datos histórica optimizada con registros limpios de tipos de cambio, varianzas y banderas de riesgo.
4. Servicio de API desacoplado y documentado que permita a nuestro e-commerce consultar en tiempo real si el catálogo requiere ajuste de precio o congelamiento de descuentos.
5. Manual de operación técnica y sesión de transferencia de conocimiento para el equipo interno.

## Cómo evaluaremos las propuestas

|Criterio|Peso (suma 100)|
|-|-|
|Robustez de la arquitectura de datos y resiliencia ante caídas del proveedor de origen|30|
|Claridad del plan de trabajo, cronograma de entregas y viabilidad del plazo|25|
|Cumplimiento de restricciones presupuestarias y costo de operación en la nube|20|
|Experiencia demostrable en proyectos de ingeniería de datos e integración de APIs|15|
|Plan de mitigación de riesgos técnicos y soporte post-lanzamiento|10|

## Qué debe incluir su propuesta

* **Statement of Work (SOW):** Alcance detallado, entregables técnicos, supuestos y exclusiones explícitas.
* **Arquitectura de solución:** Diagrama conceptual de flujo de datos, tecnologías propuestas y justificación de componentes.
* **Cronograma:** Desglose semanal de hitos, revisiones y fechas de entrega.
* **Equipo de trabajo:** Perfiles y experiencia de los profesionales asignados al proyecto.
* **Matriz de riesgos:** Identificación de riesgos operativos/técnicos y planes de contingencia.
* **Propuesta económica:** Desglose de honorarios de desarrollo y estimación puntual de costos de infraestructura mensual.

## Calendario del proceso

* **Fecha límite para preguntas y aclaraciones:** 16 de octubre de 2026
* **Fecha límite para entrega de propuestas:** 23 de octubre de 2026 (hasta las 18:00 hrs CST)
* **Fecha de decisión y adjudicación:** 30 de octubre de 2026

