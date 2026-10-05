# Ejercicio D: 3 guiones de contenido (30–45 s)

Cada guion sale de una fuente de `content_sources.json`, y el orden sale de los datos del propio sistema (leads, inscripciones limpias y estancados), no de la intuición. Los personajes son ficticios y cada video lleva la leyenda "historia ilustrativa".

## Cómo se priorizó

Cada lead se asignó a un tema por palabras clave (`python scripts/content_priorities.py` reproduce la tabla). Con solo 40 leads sirve para ordenar el primer experimento, no para concluir.

| # | Tema (fuente) | Leads que lo mencionan | Inscripciones completadas | Riesgo de compliance |
|---|---|---|---|---|
| 1 | Pago mínimo que no baja la deuda (SRC-003) | 4 | 3 | Bajo, quitando las cifras de la fuente |
| 2 | Gastos médicos que terminan en la tarjeta (SRC-009) | 2 | 1 (y 1 en proceso) | Bajo |
| 3 | Cartas y llamadas de cobranza (SRC-004) | 6 | 0 | Alto: roza lo legal |

**Por qué este orden.** El 1 es lo que ya convierte, con riesgo bajo. El 2 tiene muestra pequeña, pero ambos leads avanzaron, y la fuente es limpia. El 3 es el de **mayor volumen y se publica al final a propósito**: sus 6 leads se escalan a una persona y hoy están los 6 sin seguimiento (todos en prioridad alta de la vista de estancados). Publicarlo primero solo alargaría esa cola; antes hay que resolver el seguimiento y pasarlo por revisión legal.

**Hueco detectado:** 2 leads preguntan si esto es una estafa o si es seguro (LEAD-1013 y LEAD-1027) y ninguna fuente lo cubre. Conviene sumar una fuente para ese tema.

---

## Guion 1: el pago mínimo que no baja la deuda

**Prioridad:** 1 · **Fuente:** SRC-003 (tendencia: el pago mínimo en tarjetas)
**Estructura:** gancho → historia → giro → cierre
**Duración estimada:** 35–40 s

> ¿Pagas el mínimo cada mes y tu deuda casi no se mueve?
> Carlos pagó su tarjeta puntual durante mucho tiempo. Cada mes miraba el saldo y pensaba: ya falta menos. Pero el saldo apenas cambiaba.
> Un día entendió algo que nadie le había explicado: en muchos casos, buena parte del pago mínimo se va en intereses. No era falta de disciplina. Así funciona la tarjeta.
> Carlos habló con un Consejero, que revisó su situación completa y le explicó qué opciones podría tener.
> Si esto te suena familiar, escríbenos por WhatsApp. Un Consejero revisa tu caso.

**Texto en pantalla:** Historia ilustrativa. Cada caso es distinto y los resultados varían.

**De la fuente tomé** la idea del pago mínimo que se va en intereses. **Descarté** el 90 %, el "$8,000 que se convierte en $25,000" y los "15 años": son cifras inventadas, y la guardia de compliance marca la palabra "tasas" en esa fuente.

## Guion 2: la emergencia médica que terminó en la tarjeta

**Prioridad:** 2 · **Fuente:** SRC-009 (tendencia: gastos médicos como causa de endeudamiento)
**Estructura:** gancho → historia → giro → cierre
**Duración estimada:** 35–40 s

> Una emergencia médica no avisa. Y la tarjeta fue lo único que tenías a la mano.
> Lucía llegó a urgencias un martes cualquiera. Para cubrir lo que el seguro no pagó, usó su tarjeta de crédito. Pensó que sería solo por unos meses.
> Pero las cuentas médicas se sumaron a todo lo demás, y el saldo se volvió un círculo difícil de ver desde adentro.
> Si te pasó algo parecido, no eres la única persona. Un Consejero podría revisar tu situación y explicarte qué opciones existen en tu caso.
> Escríbenos por WhatsApp y cuéntanos con calma.

**Texto en pantalla:** Historia ilustrativa. Cada caso es distinto y los resultados varían.

**De la fuente tomé** el tono de acompañamiento. **Dejé fuera** la afirmación de que son la "causa #1" de endeudamiento: es una estadística sin respaldo en los datos.

## Guion 3: la carta de cobranza que suena a demanda

**Prioridad:** 3 · **Fuente:** SRC-004 (pregunta frecuente: embargos y cobranza)
**Estructura:** gancho → historia → giro → cierre
**Duración estimada:** 35–40 s

> Una carta de cobranza que suena a demanda. Y esa noche, nadie duerme.
> Marta abrió el sobre y sintió que se le iba el piso. Leyó palabras que no entendía y se imaginó lo peor.
> Cuando el miedo manda, es fácil decidir mal. Antes de responderle a nadie por impulso, vale la pena entender qué dice ese papel y cuáles son tus opciones.
> Un Consejero no reemplaza a un abogado, pero en muchos casos puede ayudarte a ordenar tu situación y a ver el panorama.
> Si recibiste una carta así, escríbenos. Una persona real revisa tu caso.

**Texto en pantalla:** Historia ilustrativa. Contenido informativo; no constituye consejo legal.

**De la fuente tomé** el tema y el tono calmado. **No afirmo** cuándo procede un embargo ni cómo distinguir una carta de una orden judicial: eso es opinión legal y el sistema escala esos casos a una persona.

---

## Qué NO usé de las fuentes, y por qué

- **SRC-010** ("24 a 48 meses", "$10,000 en 18 años"): promete una duración y compara cifras inventadas.
- **SRC-006** ("recupera la tranquilidad en 30 días"): es una promesa de resultado en un plazo.
- **SRC-001** (impacto temporal sobre el crédito): afirma algo sobre el crédito de una persona; además, ningún lead lo menciona.
- **SRC-007** compara con un "asesor financiero": las reglas de lenguaje piden no usar esa palabra cerca del Consejero.
- **SRC-002, 005 y 008** afirman reglas del programa (no hay quitas, no es un préstamo, hay que congelar tarjetas). Podrían ser ciertas, pero esas reglas las define el partner y no están verificadas aquí.

**Cómo medirlo sin inventar nada:** cada video con su `creator_id` y el canal CTWA, y luego comparar, con la misma limpieza del Ejercicio C, cuántos leads llegan por tema y cuántos terminan en inscripciones completadas.