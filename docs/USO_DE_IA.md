# Nota de uso de IA

## En tiempo de ejecución: ninguna
El sistema no llama a ningún modelo. Clasificación, pre-calificación, borradores y
limpieza de datos son reglas y código determinista (ver DECISIONES.md, punto 1). Lo
decidí así porque en alivio de deudas un modelo generativo puede prometer ahorros o
inventar tarifas.

## Durante el desarrollo
Usé Claude (Anthropic) como asistente para:
- [Ej.: discutir el diseño de las reglas y el orden de decisión del clasificador]
- [Ej.: escribir borradores de código que luego revisé y adapté: indica qué módulos]
- Revisar mis documentos contra el código. Con DECISIONES.md y el README, comparó lo que
  yo afirmaba con los archivos reales.
- [Ej.: redactar y pulir textos, como el README y las notas]

## Qué decidí yo
- Qué construir y qué dejar fuera, y los candados de compliance: nada se envía ni se
  transfiere solo, y ante la duda se escala.
- [Ej.: la regla de no corregir teléfonos ni `creator_id` en la limpieza, porque
  movería comisiones]
- Los datos ficticios, las reglas de `rules.yaml` y la marca (Alivio Norte, Consejería
  Clara).

## Cómo verifiqué lo que salió de la IA
- [Ej.: ejecuté el flujo completo con los 40+ leads y revisé a mano las decisiones]
- [Ej.: probé mensajes de borde: emocional, legal, datos sensibles, monto alto, baja]
- Contrasté mis afirmaciones con el código y el schema. Esa revisión encontró
  inexactitudes en mis documentos, por ejemplo la falta de un reclamo atómico de
  mensajes (limita el sistema a un worker) y una función `enqueue` definida dos veces
  en `database.py`. Las corregí o las documenté como costo.

## Dónde la IA falló o la corregí
- [Ej.: una sugerencia que no coincidía con mi estructura de carpetas, un comando que
  no existía, un caso del clasificador que dio una decisión equivocada]

## Límites
Todo lo que está en el repo lo revisé y lo entiendo, y puedo explicarlo. La IA
no vio datos reales: los leads y el CSV son inventados.