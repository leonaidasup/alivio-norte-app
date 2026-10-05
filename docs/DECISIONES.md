# Decisiones: qué NO construí a propósito

1. **Sin LLM en tiempo de ejecución.** Las decisiones salen de reglas en `config/rules.yaml`
   y código determinista. En alivio de deudas, un modelo puede prometer ahorros o inventar
   tarifas; con reglas, la misma entrada da siempre la misma decisión y queda explicada.
   *Costo:* lo que las reglas no cubren va a un humano, y la coincidencia aproximada de
   términos puede dar falsos positivos (que terminan en escalar, el lado seguro).

2. **Sin framework web.** El webhook usa `http.server` de la librería estándar. Cero
   dependencias para levantarlo en 15 minutos. *Costo:* sin TLS y con auth mínima (token
   opcional). En producción iría detrás de un proxy o sobre FastAPI.

3. **Sin base de datos servidor.** SQLite en modo WAL; para ~200 leads/hora alcanza.
   *Costo:* un solo worker (no hay reclamo atómico de mensajes, dos workers procesarían el
   mismo) y sin migraciones: el schema usa `CREATE TABLE IF NOT EXISTS`, así que cambiar una
   tabla existente exige recrear la base.

4. **Sin envíos ni transferencias automáticas.** Borradores y WhatsApp quedan en cola y solo
   salen al ejecutar `send` (gateway simulado). "Transferido" mueve la etapa y deja el audit
   trail; la transferencia la hace una persona. Si `auto_enviar` o `auto_transferir` pasan a
   `true`, `rules.yaml` se rechaza al cargar. *Costo:* el envío es "al menos una vez": si el
   proceso cae justo después de enviar, el reintento puede duplicar el mensaje. Prefiero un
   duplicado a un mensaje perdido.

5. **Sin auto-corrección de datos que mueven dinero.** Un teléfono o `creator_id` que no
   coincide va a cuarentena, no se "arregla": corregir un dígito atribuiría la comisión a
   otro creador. *Costo:* más trabajo manual con el partner.

6. **Sin interfaz gráfica.** La cola se ve con `python -m app queue` y los `.md`; métricas y
   estancados salen en texto y CSV. *Costo:* un equipo no técnico necesitaría una pantalla.

7. **Sin ORM.** 9 tablas con SQL parametrizado. *Costo:* más SQL a mano.

8. **Reportes desacoplados de la base viva.** `metrics` y `stalled` leen archivos y
   reclasifican en memoria. *Costo:* no reflejan las disposiciones aplicadas desde el CRM.

9. **Sin NLP para montos ni soporte de otros idiomas.** Los montos salen de regex con filtro
   por contexto, y todo está en español. *Costo:* frases raras pueden dar un monto
   equivocado y un mensaje en inglés cae en "ambiguo"; ambos terminan con un humano.

**Con más tiempo haría primero:** reclamo atómico de mensajes, idempotencia en el envío y
pruebas de las reglas con mensajes reales.