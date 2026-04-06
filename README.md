# BuenPlan - Generador automático de horarios

Este repositorio ahora incluye un programa que construye el horario de forma **automática**, tomando como base la estructura de tu foto (pizarra):

1. Registrar docentes + especialidad.
2. Registrar aulas por tipo (lab, taller, aula).
3. Registrar período y turno (horas, minutos por bloque, almuerzo, días hábiles).
4. Cargar clases por CSV con: `nombre`, `especialidad`, `tipo_aula`, `creditos`.
5. Asignar en cada clase: **docente + aula + bloque horario** sin choques.

## Archivos

- `scheduler.py`: motor principal de generación de horario.
- `examples/config.json`: ejemplo de configuración (incluye 90 min/bloque y 2 créditos por bloque).
- `examples/clases.csv`: ejemplo de clases a programar.

## Cómo usar

```bash
python3 scheduler.py --clases examples/clases.csv --config examples/config.json --out salida
```

Salida esperada:

- `salida/horario.csv`: horario detallado.
- `salida/resumen_horario.txt`: resumen por día.

## Reglas que aplica

- Una clase necesita `ceil(creditos / credito_por_bloque)` sesiones.
- Solo se asignan docentes con la especialidad correcta.
- Solo se asignan aulas del tipo requerido por la clase.
- Evita choque de docente, aula y clase en un mismo bloque.
- Evita asignar dos sesiones de la misma clase el mismo día.
- Respeta entrada/salida y excluye almuerzo.

## Personalización

Edita `examples/config.json` para tu realidad:

- Cambia días hábiles (por ejemplo, incluir sábado).
- Cambia turno (hora entrada/salida).
- Ajusta duración de bloque (`minutos_bloque`).
- Ajusta equivalencia crédito-bloque (`credito_por_bloque`).
- Agrega tus docentes y aulas reales.

Luego carga tu propio CSV de clases y vuelve a ejecutar.
