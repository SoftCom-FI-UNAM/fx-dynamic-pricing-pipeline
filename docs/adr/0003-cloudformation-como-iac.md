# ADR 0003: CloudFormation como única herramienta de infraestructura como código

* **Estado:** Propuesto
* **Fecha:** 2026-11-12
* **Relacionado:** [ADR 0001](0001-arquitectura-serverless-medallon.md)

## Contexto

El SOW establece CloudFormation como única herramienta de IaC, con cambios revisados en Git, y el entregable E1 es un stack de CloudFormation desplegable. La infraestructura incluye buckets S3, cinco Lambdas, roles IAM, EventBridge, SNS y alarmas de CloudWatch. El equipo es pequeño y el despliegue se hará desde la consola de AWS.

## Decisión

Toda la infraestructura se define en plantillas de CloudFormation dentro de `infra/`:

* `Buckets.yaml`: buckets bronze, silver, gold, catalog y artifacts, con versionado, ciclo de vida y políticas.
* `Lambdas.yaml`: funciones, roles, programación, reglas de EventBridge, SNS y alarmas.

Reglas de trabajo:

1. Se despliega primero `Buckets.yaml`. `Lambdas.yaml` importa sus nombres con `Fn::ImportValue`.
2. Cualquier recurso nuevo entra a una plantilla el mismo día. Si un recurso solo existe en la consola de AWS, se considera inexistente.
3. El código de las Lambdas se empaqueta con `scripts/build.sh` y se sube a `lambdas/` del bucket artifacts antes de crear o actualizar la pila de Lambdas.
4. Los cambios a las plantillas se revisan por Git, como pide el SOW.

## Alternativas consideradas

* **Terraform:** requiere instalar y mantener otra herramienta y su estado remoto; el SOW ya fija CloudFormation.
* **AWS CDK o SAM:** añaden una capa de abstracción y un paso de síntesis; para cuatro Lambdas no aportan lo suficiente.
* **Consola de AWS a mano:** no es reproducible ni auditable.

## Consecuencias

* Despliegues repetibles, versionados y revisables.
* Los nombres entre plantillas quedan acoplados por exportaciones; renombrar una exportación exige coordinar ambas pilas.
* Los parámetros (token en Parameter Store, serie de inflación, umbrales) quedan expuestos y documentados en la plantilla.
* Las plantillas aún no se han validado con `cfn-lint` ni `validate-template`; está pendiente.
