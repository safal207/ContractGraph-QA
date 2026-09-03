# Interoperabilidad de ContractGraph-QA: guía de cinco minutos

[English](../en/GETTING_STARTED.md) · [简体中文](../zh-CN/GETTING_STARTED.md) · [हिन्दी](../hi/GETTING_STARTED.md) · Español · [العربية](../ar/GETTING_STARTED.md)

ContractGraph-QA, LiminalQA y PythiaLabs forman una pila de seguridad basada
en evidencia para flujos de agentes con estado y de alto riesgo. Cada proyecto
conserva la autoridad sobre su propio veredicto; los adaptadores intercambian
JSON estricto y nunca convierten un informe en permiso para actuar.

## Qué aporta cada proyecto

| Proyecto | Función | Lo que no afirma |
|---|---|---|
| ContractGraph-QA | Búsqueda acotada de estados/acciones, evidencia del sujeto exacto y entradas de replay | Corrección exhaustiva o autorización de acciones |
| LiminalQA | Contexto QA bitemporal y candidatos no autoritativos de replay/deuda | Un finding CGQA verificado o un veredicto de continuidad LTP |
| PythiaLabs | Nueva puerta determinista de autorización con evidencia externa como contexto consultivo | Que la evidencia externa por sí sola pueda devolver `ALLOW` |

## Ejecuta el contrato fijado

Desde un checkout de ContractGraph-QA:

```bash
python -m pip install .
cgqa liminalqa-conformance > report.json
```

Un informe válido contiene los 14 vectores golden y fail-closed:

```json
{"status":"PASS","counts":{"total":14,"passed":14,"failed":0},"authority":{"classification":"conformance_evidence_only","mayAuthorizeAction":false}}
```

El objeto completo también fija el SHA-256 de la suite, ambos contratos de
productor, cada ID y digest de entrada, `sideEffectExecuted=false` y el límite
de las afirmaciones.

## Valida desde tu lenguaje

El repositorio incluye adaptadores ligeros para TypeScript/JavaScript, Go,
Java/JVM y .NET. Validan la evidencia del runner nativo sin reimplementar la
lógica de veredictos de CGQA/LiminalQA.

```bash
node sdks/typescript/bin/cgqa-report-validate.js report.json

cd sdks/go && go run ./cmd/cgqa-report-validate ../../report.json

mvn -q -f sdks/java/pom.xml exec:java -Dexec.args=report.json

dotnet run --project sdks/dotnet/src/ContractGraphQA.Interop.Cli -- report.json
```

Las coordenadas de paquetes están en la [guía de publicación de SDK](../../SDK_RELEASE.md).
Python es el runner de referencia de ContractGraph-QA, Rust el runner nativo
de LiminalQA y Elixir el de PythiaLabs.

[SDK v0.1.0 se puede descargar públicamente desde GitHub](https://github.com/safal207/ContractGraph-QA/releases/tag/interop-sdk-v0.1.0),
y el módulo Go está disponible con
`go get github.com/safal207/ContractGraph-QA/sdks/go@v0.1.0`. Los archivos
`.tgz`, JAR/POM y `.nupkg` están en la release; las publicaciones en npm,
Maven Central y nuget.org todavía están pendientes.

## Límite fail-closed

Todos los consumidores rechazan claves JSON duplicadas, campos críticos
desconocidos, cambios de pins, casos ausentes o repetidos, `UNSAFE_ACCEPTED`,
`mayAuthorizeAction=true` y cualquier efecto secundario declarado. La entrada
se limita a 1 MiB. La validación no usa la red, no ejecuta candidatos, no
escribe en bases de datos y no actúa sobre el sistema objetivo.

Un informe válido solo demuestra conformidad para los vectores sintéticos
fijados. Antes de una acción real, repite la verificación sobre la evidencia
actual y ejecuta la puerta activa de Pythia o del operador. `PASS` nunca es un
permiso.

Protocolo completo: [interop ContractGraph-QA ↔ LiminalQA](../../LIMINALQA_INTEROP.md).
