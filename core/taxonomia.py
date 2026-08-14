"""
Taxonomía oficial de categorías/materiales para la declaración RESIMPLE
de envases y embalajes (Ley REP, Chile).

Esta estructura fue extraída fila por fila de una declaración real
presentada ("Declaracion marzo 2026.xlsx", hoja "LB"), que replica el
formato exigido por RESIMPLE: dos bloques (CATEGORIA DOMICILIARIA /
CATEGORIA NO DOMICILIARIA), cada uno con Subcategoría > (Flexible/Rígido,
solo en Plásticos) > Material, y dos columnas de toneladas (No peligroso /
Peligroso).

No inventar ni reordenar filas: es una tabla regulatoria fija.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FilaTaxonomia:
    subcategoria: str
    subcategoria2: str | None  # "Flexible" / "Rígido" / None
    material: str


# --- Materiales plásticos que requieren distinguir Flexible / Rígido ---
MATERIALES_CON_RIGIDEZ = [
    "Envases de PEAD que NO contienen sustancias con grasa (2)",
    "Envases de PEAD que contienen sustancias con grasa (2)",
    "PVC (3)",
    "Envases de PEBD que NO contienen sustancias con grasa (4)",
    "Envases de PEBD que contienen sustancias con grasa (4)",
    "Envases de PP que NO contienen sustancias con grasa (5)",
    "Envases de PP que contienen sustancias con grasa (5)",
    "Envases de PS que NO contienen sustancias con grasa (6)",
    "Envases de PS que contienen sustancias con grasa (6) y envases de EPS",
    "Otros (7)",
]

_RIGIDEZ_SET = set(MATERIALES_CON_RIGIDEZ)


def material_requiere_rigidez(material_normalizado: str) -> bool:
    return material_normalizado in _RIGIDEZ_SET


def normalizar_material(texto: str) -> str:
    """Normaliza texto libre de 'Materiales' (Base Maestra) al texto
    canónico de la taxonomía RESIMPLE: colapsa espacios repetidos y
    corrige la coma suelta antes del paréntesis ("grasa,  (5)" -> "grasa (5)")."""
    if texto is None:
        return ""
    t = str(texto).strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*,\s*\(", " (", t)
    return t.strip()


def normalizar_categoria(texto: str) -> str:
    t = normalizar_material(texto)
    if t.lower().startswith("no domic"):
        return "No Domiciliario"
    return "Domiciliario"


def normalizar_peligrosidad(texto) -> str:
    if texto is None or (isinstance(texto, float) and texto != texto):  # NaN
        return "No Peligroso"
    t = normalizar_material(texto)
    if "no peligroso" in t.lower():
        return "No Peligroso"
    if "peligroso" in t.lower():
        return "Peligroso"
    return "No Peligroso"


# ---------------------------------------------------------------------
# CATEGORIA DOMICILIARIA — 49 filas (filas 7-55 del template oficial)
# ---------------------------------------------------------------------
DOMICILIARIO: list[FilaTaxonomia] = [
    FilaTaxonomia("METALES", None, "Aluminio (latas)"),
    FilaTaxonomia("METALES", None, "Hojalata"),
    FilaTaxonomia("METALES", None, "Metal con aire comprimido"),
    FilaTaxonomia("METALES", None, "Otros envases de metal"),
    FilaTaxonomia("METALES", None, "Metales Reutilizables Nuevos"),
    FilaTaxonomia("METALES", None, "Metales Reutilizables Recuperados"),
    FilaTaxonomia("METALES", None, "Metales Reutilizables convertidos en Residuos"),
    FilaTaxonomia("PLÁSTICOS", None, "Plástico compostable"),
    FilaTaxonomia("PLÁSTICOS", None, "Botellas PET (1)"),
    FilaTaxonomia("PLÁSTICOS", None, "Otros envases PET (1)"),
    FilaTaxonomia("PLÁSTICOS", None, "Plásticos Reutilizables Nuevos"),
    FilaTaxonomia("PLÁSTICOS", None, "Plásticos Reutilizables Recuperados"),
    FilaTaxonomia("PLÁSTICOS", None, "Plásticos Reutilizables convertidos en Residuos"),
]
DOMICILIARIO += [
    FilaTaxonomia("PLÁSTICOS", "Flexible", m) for m in MATERIALES_CON_RIGIDEZ
]
DOMICILIARIO += [
    FilaTaxonomia("PLÁSTICOS", "Rígido", m) for m in MATERIALES_CON_RIGIDEZ
]
DOMICILIARIO += [
    FilaTaxonomia("PAPELES Y CARTONES", None, "Cartón"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Papel"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Otro papel compuesto"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Papeles y Cartones Reutilizables Nuevos"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Papeles y Cartones Reutilizables Recuperados"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Papeles y Cartones Reutilizables convertidos en Residuos"),
    FilaTaxonomia("CARTÓN PARA BEBIDAS", None, "Cartón para bebidas (Tetrapack)"),
    FilaTaxonomia("VIDRIO", None, "Vidrio"),
    FilaTaxonomia("VIDRIO", None, "Vidrio Reutilizables Nuevos"),
    FilaTaxonomia("VIDRIO", None, "Vidrio Reutilizables Recuperados"),
    FilaTaxonomia("VIDRIO", None, "Vidrio Reutilizables convertidos en Residuos"),
    FilaTaxonomia("OTROS", None, "Madera"),
    FilaTaxonomia("OTROS", None, "Otros Reutilizables Nuevos"),
    FilaTaxonomia("OTROS", None, "Otros Reutilizables Recuperados"),
    FilaTaxonomia("OTROS", None, "Otros Reutilizables convertidos en Residuos"),
    FilaTaxonomia("OTROS", None, "Otros no Madera"),
]

assert len(DOMICILIARIO) == 49, f"Domiciliario debería tener 49 filas, tiene {len(DOMICILIARIO)}"

# ---------------------------------------------------------------------
# CATEGORIA NO DOMICILIARIA — 43 filas (filas 7-49 del template oficial)
# ---------------------------------------------------------------------
NO_DOMICILIARIO: list[FilaTaxonomia] = [
    FilaTaxonomia("METALES", None, "Envases de Aluminio"),
    FilaTaxonomia("METALES", None, "Hojalata"),
    FilaTaxonomia("METALES", None, "Metal con aire comprimido"),
    FilaTaxonomia("METALES", None, "Envases metálicos de otros metales"),
    FilaTaxonomia("METALES", None, "Metales Reutilizables Nuevos"),
    FilaTaxonomia("METALES", None, "Metales Reutilizables Recuperados"),
    FilaTaxonomia("METALES", None, "Metales Reutilizables convertidos en Residuos"),
    FilaTaxonomia("PLÁSTICOS", None, "Plástico compostable"),
    FilaTaxonomia("PLÁSTICOS", None, "Envases PET"),
    FilaTaxonomia("PLÁSTICOS", None, "Plásticos Reutilizables Nuevos"),
    FilaTaxonomia("PLÁSTICOS", None, "Plásticos Reutilizables Recuperados"),
    FilaTaxonomia("PLÁSTICOS", None, "Plásticos Reutilizables convertidos en Residuos"),
]
NO_DOMICILIARIO += [
    FilaTaxonomia("PLÁSTICOS", "Flexible", m) for m in MATERIALES_CON_RIGIDEZ
]
NO_DOMICILIARIO += [
    FilaTaxonomia("PLÁSTICOS", "Rígido", m) for m in MATERIALES_CON_RIGIDEZ
]
NO_DOMICILIARIO += [
    FilaTaxonomia("PAPELES Y CARTONES", None, "Cartón"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Papel"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Otro papel compuesto"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Papeles y Cartone Reutilizables Nuevos"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Papeles y Cartone Reutilizables Recuperados"),
    FilaTaxonomia("PAPELES Y CARTONES", None, "Papeles y Cartone Reutilizables convertidos en Residuos"),
    FilaTaxonomia("OTROS", None, "Madera"),
    FilaTaxonomia("OTROS", None, "Otros Reutilizables Nuevos"),
    FilaTaxonomia("OTROS", None, "Otros Reutilizables Recuperados"),
    FilaTaxonomia("OTROS", None, "Otros Reutilizables convertidos en Residuos"),
    FilaTaxonomia("OTROS", None, "Otros no Madera"),
]

assert len(NO_DOMICILIARIO) == 43, f"No Domiciliario debería tener 43 filas, tiene {len(NO_DOMICILIARIO)}"

BLOQUES = {
    "Domiciliario": DOMICILIARIO,
    "No Domiciliario": NO_DOMICILIARIO,
}

# Orden fijo de subcategorías principales (para gráficos: color por identidad, nunca por rango)
SUBCATEGORIAS_ORDEN = [
    "METALES",
    "PLÁSTICOS",
    "PAPELES Y CARTONES",
    "CARTÓN PARA BEBIDAS",
    "VIDRIO",
    "OTROS",
]


def indice_taxonomia(categoria: str) -> dict[tuple[str | None, str], int]:
    """Devuelve {(subcategoria2, material): posición_en_la_lista} para el bloque dado."""
    filas = BLOQUES[categoria]
    return {(f.subcategoria2, f.material): i for i, f in enumerate(filas)}
