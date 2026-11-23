# Resumen de experimentos

## Experimento A: top_k

| Indicador | K=1 | K=3 | K=5 |
|---|---|---|---|
| Tiempo RAG medio (s) | 0.078 | 0.050 | 0.040 |
| Tokens entrada medios | 331 | 670 | 1008 |
| Tokens salida medios | 27 | 55 | 92 |
| Generación media (s) | 0.72 | 1.59 | 2.76 |
| Duración total media (s) | 3.88 | 5.73 | 6.77 |
| Similitud máxima media | 0.736 | 0.740 | 0.740 |
| Con dato clave (heurística) | 1/8 | 3/9 | 6/9 |
| Rechazos correctos sin evidencia | 3/3 | 3/3 | 3/3 |
| Rechazos indebidos (con evidencia) | 6 | 3 | 1 |

### Detalle por pregunta (✔ = contiene el dato clave; R = rechazó)

| id | K=1 | K=3 | K=5 | fuentes K=3 |
|---|---|---|---|---|
| G2 | ✘ | ✘ | ✘ | convenio_2017, estudios_previos_2017, informe_supervision_2017 |
| N01 | R | ✘ | ✘ | convenio_2017, informe_actividades_2017, informe_supervision_2017 |
| N02 | error | ✔ | ✔ | convenio_2017, informe_actividades_2017, informe_supervision_2017 |
| N03 | ✔ | ✔ | ✔ | convenio_2017, estudios_previos_2017, informe_actividades_2017 |
| G4 | R | ✔ | ✔ | acta_inicio_convenio_2017, convenio_2017 |
| G1 | R | ✘ | ✔ | convenio_2017, estudios_previos_2017 |
| I1 | R | R | ✔ | informe_actividades_2017, informe_supervision_2017 |
| N04 | R | R | ✔ | convenio_2017, informe_actividades_2017, informe_supervision_2017 |
| I2 | R | R | R | acta_inicio_convenio_2017, convenio_2017, estudios_previos_2017 |
| F5 | R | R | R | estudios_previos_2017, informe_actividades_2017, matriz_riesgo_2017 |
| F4 | R | R | R | informe_actividades_2017, informe_supervision_2017 |
| F2 | R | R | R | informe_supervision_2017 |

## Experimento B: temperatura

| Temperatura | Respuestas distintas de 9 (3 preguntas × 3 rep.) | Tokens salida medios |
|---|---|---|
| 0.0 | 5 | 56 |
| 0.5 | 9 | 62 |
| 1.0 | 9 | 73 |

## Experimento C: preguntas sin evidencia

| Pregunta | ¿Rechazó? | Similitud máx. | Respuesta (inicio) |
|---|---|---|---|
| ¿Cuál es el salario del director de INCIVA? | sí | 0.672 | No existe información suficiente en los documentos proporcionados para responder esta pregunta. |
| ¿Cuál fue la facturación de INCIVA en 2017? | sí | 0.713 | No existe información suficiente en los documentos proporcionados para responder esta pregunta. |
| ¿Cuántos empleados tiene INCIVA? | sí | 0.708 | No existe información suficiente en los documentos proporcionados para responder esta pregunta. |
| ¿Cuántos visitantes recibió el Museo Arqueológico La Merced en 2024? | sí | 0.671 | No existe información suficiente en los documentos proporcionados para responder esta pregunta. |
| ¿Quién ganó el mundial de fútbol de 2022? | sí | 0.594 | No existe información suficiente en los documentos proporcionados para responder esta pregunta sobre el ganador del mundial de fútbol de 202 |

## Experimento D: rendimiento (cada tanda inicia con el modelo descargado)

| N consultas | Total (s) | 1ª consulta (s) | Carga modelo 1ª (s) | Media resto (s) | Carga media resto (s) |
|---|---|---|---|---|---|
| 1 | 11.88 | 11.88 | 1.58 | - | - |
| 5 | 37.93 | 12.51 | 1.58 | 6.35 | 0.005 |
| 10 | 87.36 | 11.90 | 1.32 | 8.38 | 0.005 |
