#!/usr/bin/env python3
"""Generador automático de horarios basado en reglas académicas.

Este script toma como base la estructura vista en la pizarra:
- Registro de docentes (con especialidades)
- Registro de aulas (por tipo: lab, taller, aula)
- Carga de clases desde CSV (nombre, especialidad, tipo de aula, créditos)
- Configuración de periodo y turnos (ej. 90 min por bloque, 2 créditos por bloque)

Salida:
- horario.csv: horario final por clase / docente / aula / bloque
- resumen_horario.txt: resumen legible
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


DAY_ORDER = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


@dataclass(frozen=True)
class Docente:
    nombre: str
    especialidades: Set[str]


@dataclass(frozen=True)
class Aula:
    nombre: str
    tipo: str


@dataclass(frozen=True)
class Clase:
    nombre: str
    especialidad: str
    tipo_aula: str
    creditos: float


@dataclass(frozen=True)
class ConfiguracionPeriodo:
    nombre: str
    fecha_inicio: str
    fecha_fin: str
    anio: int
    dias_habiles: List[str]
    hora_entrada: str
    hora_salida: str
    almuerzo_inicio: str
    almuerzo_fin: str
    minutos_bloque: int
    credito_por_bloque: float


@dataclass(frozen=True)
class Bloque:
    dia: str
    inicio: str
    fin: str


@dataclass(frozen=True)
class Asignacion:
    clase: str
    sesion: int
    docente: str
    aula: str
    dia: str
    inicio: str
    fin: str


def parse_time(hhmm: str) -> time:
    return datetime.strptime(hhmm, "%H:%M").time()


def format_time(t: time) -> str:
    return t.strftime("%H:%M")


def add_minutes(base: time, minutes: int) -> time:
    dt = datetime.combine(datetime.today(), base) + timedelta(minutes=minutes)
    return dt.time()


def make_blocks(config: ConfiguracionPeriodo) -> List[Bloque]:
    entrada = parse_time(config.hora_entrada)
    salida = parse_time(config.hora_salida)
    alm_ini = parse_time(config.almuerzo_inicio)
    alm_fin = parse_time(config.almuerzo_fin)

    blocks: List[Bloque] = []
    for dia in config.dias_habiles:
        cur = entrada
        while cur < salida:
            nxt = add_minutes(cur, config.minutos_bloque)
            if nxt > salida:
                break

            cruza_almuerzo = not (nxt <= alm_ini or cur >= alm_fin)
            if not cruza_almuerzo:
                blocks.append(Bloque(dia=dia, inicio=format_time(cur), fin=format_time(nxt)))
            cur = nxt

    return blocks


def load_clases_csv(path: Path) -> List[Clase]:
    clases: List[Clase] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"nombre", "especialidad", "tipo_aula", "creditos"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                "El CSV debe incluir columnas: nombre, especialidad, tipo_aula, creditos"
            )

        for row in reader:
            clases.append(
                Clase(
                    nombre=row["nombre"].strip(),
                    especialidad=row["especialidad"].strip().lower(),
                    tipo_aula=row["tipo_aula"].strip().lower(),
                    creditos=float(row["creditos"]),
                )
            )

    return clases


def normalize_docentes(raw: Iterable[dict]) -> List[Docente]:
    docentes: List[Docente] = []
    for d in raw:
        docentes.append(
            Docente(
                nombre=d["nombre"].strip(),
                especialidades={e.strip().lower() for e in d["especialidades"]},
            )
        )
    return docentes


def normalize_aulas(raw: Iterable[dict]) -> List[Aula]:
    return [Aula(nombre=a["nombre"].strip(), tipo=a["tipo"].strip().lower()) for a in raw]


def blocks_needed(clase: Clase, config: ConfiguracionPeriodo) -> int:
    return max(1, math.ceil(clase.creditos / config.credito_por_bloque))


def generate_schedule(
    clases: List[Clase], docentes: List[Docente], aulas: List[Aula], config: ConfiguracionPeriodo
) -> List[Asignacion]:
    bloques = make_blocks(config)

    docentes_por_esp: Dict[str, List[Docente]] = {}
    for d in docentes:
        for esp in d.especialidades:
            docentes_por_esp.setdefault(esp, []).append(d)

    aulas_por_tipo: Dict[str, List[Aula]] = {}
    for a in aulas:
        aulas_por_tipo.setdefault(a.tipo, []).append(a)

    # Ordenar por dificultad (menos opciones primero)
    clases_ordenadas = sorted(
        clases,
        key=lambda c: (
            len(docentes_por_esp.get(c.especialidad, [])) * len(aulas_por_tipo.get(c.tipo_aula, [])),
            -blocks_needed(c, config),
            c.nombre,
        ),
    )

    busy_doc: Set[Tuple[str, str, str]] = set()  # (docente, dia, inicio)
    busy_aula: Set[Tuple[str, str, str]] = set()  # (aula, dia, inicio)
    busy_clase_dia: Set[Tuple[str, str]] = set()  # (clase, dia)

    resultado: List[Asignacion] = []

    for clase in clases_ordenadas:
        docentes_posibles = docentes_por_esp.get(clase.especialidad, [])
        aulas_posibles = aulas_por_tipo.get(clase.tipo_aula, [])

        if not docentes_posibles:
            raise RuntimeError(
                f"No hay docentes para la especialidad '{clase.especialidad}' de la clase '{clase.nombre}'"
            )
        if not aulas_posibles:
            raise RuntimeError(
                f"No hay aulas del tipo '{clase.tipo_aula}' para la clase '{clase.nombre}'"
            )

        sesiones = blocks_needed(clase, config)
        asignadas = 0

        for bloque in sorted(bloques, key=lambda b: (DAY_ORDER.index(b.dia), b.inicio)):
            if asignadas >= sesiones:
                break

            if (clase.nombre, bloque.dia) in busy_clase_dia:
                continue

            asigno_esta_sesion = False
            for docente in docentes_posibles:
                if (docente.nombre, bloque.dia, bloque.inicio) in busy_doc:
                    continue

                for aula in aulas_posibles:
                    if (aula.nombre, bloque.dia, bloque.inicio) in busy_aula:
                        continue

                    resultado.append(
                        Asignacion(
                            clase=clase.nombre,
                            sesion=asignadas + 1,
                            docente=docente.nombre,
                            aula=aula.nombre,
                            dia=bloque.dia,
                            inicio=bloque.inicio,
                            fin=bloque.fin,
                        )
                    )
                    busy_doc.add((docente.nombre, bloque.dia, bloque.inicio))
                    busy_aula.add((aula.nombre, bloque.dia, bloque.inicio))
                    busy_clase_dia.add((clase.nombre, bloque.dia))
                    asignadas += 1
                    asigno_esta_sesion = True
                    break

                if asigno_esta_sesion:
                    break

        if asignadas < sesiones:
            raise RuntimeError(
                f"No se pudo completar '{clase.nombre}': requería {sesiones} bloques y solo se asignaron {asignadas}."
            )

    return sorted(resultado, key=lambda a: (DAY_ORDER.index(a.dia), a.inicio, a.aula, a.clase))


def write_outputs(asignaciones: List[Asignacion], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "horario.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["dia", "inicio", "fin", "clase", "sesion", "docente", "aula"])
        for a in asignaciones:
            writer.writerow([a.dia, a.inicio, a.fin, a.clase, a.sesion, a.docente, a.aula])

    txt_path = output_dir / "resumen_horario.txt"
    with txt_path.open("w", encoding="utf-8") as fh:
        dia_actual = None
        for a in asignaciones:
            if dia_actual != a.dia:
                dia_actual = a.dia
                fh.write(f"\n=== {dia_actual.upper()} ===\n")
            fh.write(
                f"{a.inicio}-{a.fin} | {a.clase} (sesión {a.sesion}) | Docente: {a.docente} | Aula: {a.aula}\n"
            )


def load_config(path: Path) -> tuple[ConfiguracionPeriodo, List[Docente], List[Aula]]:
    data = json.loads(path.read_text(encoding="utf-8"))

    config = ConfiguracionPeriodo(**data["periodo"])  # type: ignore[arg-type]
    docentes = normalize_docentes(data["docentes"])
    aulas = normalize_aulas(data["aulas"])
    return config, docentes, aulas


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador automático de horarios")
    parser.add_argument("--clases", required=True, help="Ruta del CSV de clases")
    parser.add_argument("--config", required=True, help="Ruta del JSON de configuración")
    parser.add_argument("--out", default="salida", help="Carpeta de salida")

    args = parser.parse_args()

    clases = load_clases_csv(Path(args.clases))
    config, docentes, aulas = load_config(Path(args.config))

    horario = generate_schedule(clases, docentes, aulas, config)
    write_outputs(horario, Path(args.out))

    print(f"Horario generado con {len(horario)} sesiones. Archivos en: {args.out}")


if __name__ == "__main__":
    main()
