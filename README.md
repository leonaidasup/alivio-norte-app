# Alivio Norte — Pre-calificación de Leads & Pipeline ETL

Sistema en Python para ingesta y clasificación determinista de chats financieros, actualización de CRM y limpieza de datos (ETL) sobre SQLite en modo WAL.

## Requisitos

* Python 3.10 o superior

## Instalación

```bash
# Clonar repositorio
git clone https://github.com/leonaidasup/alivio-norte-app.git
cd alivio-norte-app

# Crear y activar entorno virtual
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Flujo de Ejecución (Demo)

```powershell
# 1. Ingestar leads desde el JSON
python -m app import-leads data/leads_chat.json

# 2. Clasificar pendientes y generar borradores en outbox
python -m app once

# 3. Limpiar CSV del partner (envía inconsistencias a cuarentena)
python -m app clean data/partner_enrollments_dirty.csv

# 4. Generar reporte con métricas del funnel
python -m app metrics
```

## Arquitectura

```text
┌──────────────────┐
│ leads_chat.json  │
└────────┬─────────┘
         │ import-leads
         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ config/          │────►│ app/engine/      │────►│ Base de Datos    │
│ rules.yaml       │     │ classifier.py    │     │ SQLite (outbox)  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
  (Reglas de              (Evaluador               (Persistencia WAL /
   negocio)                determinista)            Audit Trail)
```

## Comandos CLI

| Comando | Descripción | Entradas / Salidas |
| :--- | :--- | :--- |
| `python -m app import-leads <path>` | Ingesta mensajes de chat a la tabla staging. | `data/leads_chat.json` |
| `python -m app once` | Procesa la cola pendiente con `classifier.py`. | `config/rules.yaml` → DB |
| `python -m app clean <path>` | Filtra inscripciones y aísla registros erróneos en cuarentena. | `data/partner_enrollments_dirty.csv` |
| `python -m app metrics` | Genera y exporta la analítica del funnel a CSV. | `reports/funnel_metrics.csv` |


## Estructura del Proyecto

```text
alivio-norte-app/
├── app/
│   ├── data/          # Esquema SQLite, migraciones y conexión WAL
│   ├── engine/        # Clasificación determinista y reglas
│   ├── etl/           # Limpieza de CSVs y cuarentena
│   ├── reports/       # Generación de métricas
│   ├── commands.py    # Lógica de comandos CLI
│   └── __main__.py    # Entrada principal del CLI
├── config/
│   └── rules.yaml     # Reglas de negocio
├── data/              # Datasets de prueba
├── docs/              # Estrategia de contenido
├── reports/           # Archivos exportados
├── requirements.txt   # Dependencias
└── README.md
```

## Verificación Rápida del Motor

Script de prueba rápida para validar la clasificación de un mensaje:

```python
from app.engine.rules import RulesStore
from app.engine.classifier import classify

rules = RulesStore('config/rules.yaml').get()
msg = "Hola, tengo una deuda de 20000 con 2 tarjetas y necesito ayuda"
res = classify(msg, rules)

print(f"Decisión: {res.decision}")
print(f"Motivo:   {res.reason}")
print(f"Estado:   {res.prequal['estado']}")
```

## Nota sobre el uso de IA

Se utilizó Inteligencia Artificial generativa como herramienta de soporte exclusivamente para:
* Generación de código base para la CLI y migración de SQLite.
* Creación de datasets sintéticos de prueba (`leads_chat.json` y `partner_enrollments_dirty.csv`).
* Estructuración de la documentación en Markdown.

*Nota:* El motor de clasificación (`classifier.py`) es **100% determinista** y no realiza llamad
