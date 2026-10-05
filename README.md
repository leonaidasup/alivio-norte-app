# Alivio Norte — Pre-calificación de leads y reporting

Sistema en Python que recibe mensajes de leads de alivio de deudas, decide si responder, ignorar o escalar a un humano, deja borradores y resúmenes para revisión, aplica disposiciones tipo CRM y limpia el CSV de inscripciones del partner (Consejería Clara). Marca y partner son ficticios.

Nunca envía ni transfiere nada por su cuenta: todo pasa por una persona.

## Inicio rápido

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/leonaidasup/alivio-norte-app.git
cd alivio-norte-app
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Correr la demo

```bash
# 1. Cargar los leads a la cola
python -m app import-leads data/leads_chat.json

# 2. Clasificar: genera decisiones, borradores y resúmenes de handoff
python -m app once

# 3. Limpiar el CSV del partner (lo dudoso va a cuarentena)
python -m app clean data/partner_enrollments_dirty.csv

# 4. Métricas del funnel
python -m app metrics
```

Resultados:

| Qué | Dónde |
| :--- | :--- |
| Decisiones (log mínimo) | `runtime/decisions_log.csv` |
| Borradores para revisión | `runtime/drafts/*.md` |
| Reportes de limpieza, métricas y estancados | `reports/` |
| Base de datos | `runtime/alivio.db` |

Una carpeta `demo/` con una corrida ya generada está en el repo, por si prefieres revisar sin ejecutar.

## Cómo funciona

```text
leads_chat.json / webhook
        │  import-leads (redacta SSN y tarjetas antes de guardar)
        ▼
  cola de mensajes ──► classifier.py ◄── config/rules.yaml
                            │
        ┌───────────────────┼───────────────────┐
     responder           escalar_humano        ignorar
  pre-califica +        motivo + resumen      (baja → no
  borrador (.md)        para un agente        contactar)
        │                   │
        └──── decisions_log.csv + base SQLite ────┘
```

Las disposiciones (No Answer, Info Sent, Transferido, Call Back, No le interesa) mueven la etapa del lead, dejan audit trail y preparan un WhatsApp en el outbox. El envío es un paso aparte, con reintentos y cola de fallos.

## Reglas editables

Todo el criterio de negocio vive en `config/rules.yaml`, sin tocar código: umbrales de monto, palabras que disparan handoff, pesos de riesgo, lenguaje prohibido y disposiciones. Con el sistema corriendo, el siguiente mensaje usa la versión nueva. Si el archivo queda inválido, se conserva la última versión válida.

## Comandos

| Comando | Qué hace |
| :--- | :--- |
| `python -m app import-leads <archivo>` | Carga leads (JSON o CSV) a la cola de mensajes. |
| `python -m app once` | Procesa una vez la cola pendiente. |
| `python -m app queue` | Muestra la cola humana (borradores y handoffs). |
| `python -m app disposition <lead_id> "<disposición>"` | Aplica una disposición. |
| `python -m app send` | Envía los WhatsApp pendientes del outbox. |
| `python -m app clean <csv>` | Limpia inscripciones; los casos dudosos van a cuarentena. |
| `python -m app metrics` | Funnel y conversión por creador y canal. |
| `python -m app stalled` | Leads estancados con siguiente acción. |

## Estructura

```text
alivio-norte-app/
├── app/
│   ├── data/        # base de datos, limpieza del CSV
│   ├── engine/      # clasificador, reglas, borradores, handoff, CRM, WhatsApp
│   ├── commands.py  # comandos del CLI
│   └── __main__.py
├── config/rules.yaml
├── db/schema.sql
├── data/            # leads y CSV de prueba
├── docs/            # contenido y notas
├── reports/         # salidas de limpieza y métricas
├── runtime/         # base, borradores, logs (se genera al correr)
└── demo/            # corrida de ejemplo
```

## Entregables

* [Decisiones: qué NO construí](docs/DECISIONES.md)
* [Nota de escala (~200 leads/hora)](docs/ESCALA.md)
* [Nota de uso de IA](docs/USO_DE_IA.md)
* [Video de la demo (≤ 6 min)](ENLACE)

## Verificación rápida del motor

```python
from app.engine.rules import RulesStore
from app.engine.classifier import classify

rules = RulesStore("config/rules.yaml").get()
res = classify("Hola, tengo una deuda de 8000 con una tarjeta de crédito y necesito ayuda", rules)

print("Decisión:", res.decision)
print("Motivo:  ", res.reason)
print("Estado:  ", res.prequal and res.prequal["estado"])
```