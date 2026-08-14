"""Carga y limpieza de los tres archivos de entrada:
Informe de Ventas, Tabla de Homologación y Base Maestra de Envases.

Cada loader es tolerante a filas de encabezado corridas (busca la fila que
contiene los nombres de columna esperados) y devuelve columnas ya limpias
y tipadas, listas para el motor de cálculo.
"""

from __future__ import annotations

import pandas as pd

from . import taxonomia


class ErrorCarga(Exception):
    pass


def _detectar_fila_encabezado(fuente, sheet_name, columnas_esperadas: set[str], max_scan: int = 10) -> int:
    raw = pd.read_excel(fuente, sheet_name=sheet_name, header=None, nrows=max_scan)
    for i in range(len(raw)):
        valores = {str(v).strip() for v in raw.iloc[i].tolist() if pd.notna(v)}
        if columnas_esperadas.issubset(valores):
            return i
    raise ErrorCarga(
        f"No se encontraron las columnas esperadas {sorted(columnas_esperadas)} "
        f"en las primeras {max_scan} filas de la hoja '{sheet_name}'."
    )


def _primera_hoja(fuente) -> str:
    return pd.ExcelFile(fuente).sheet_names[0]


# ---------------------------------------------------------------------
# Informe de Ventas
# ---------------------------------------------------------------------
COLS_VENTAS = {"ID Artículo", "Cantidad"}


def cargar_ventas(fuente, sheet_name: str | None = None) -> pd.DataFrame:
    sheet = sheet_name or _primera_hoja(fuente)
    header_row = _detectar_fila_encabezado(fuente, sheet, COLS_VENTAS)
    df = pd.read_excel(fuente, sheet_name=sheet, header=header_row)
    df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]

    df["ID Artículo"] = df["ID Artículo"].astype(str).str.strip()
    df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce")

    descripcion_col = next((c for c in df.columns if "Descripci" in str(c)), None)
    cols = ["ID Artículo", "Cantidad"] + ([descripcion_col] if descripcion_col else [])
    df = df[cols].rename(columns={descripcion_col: "Descripción"} if descripcion_col else {})

    antes = len(df)
    df = df.dropna(subset=["Cantidad"])
    df = df[df["ID Artículo"].notna() & (df["ID Artículo"] != "") & (df["ID Artículo"] != "nan")]
    descartadas = antes - len(df)

    return df.reset_index(drop=True), descartadas


# ---------------------------------------------------------------------
# Tabla de Homologación
# ---------------------------------------------------------------------
COLS_HOMOLOGACION = {"Codigo_erp", "sku_rep", "Factor_conversion", "Canal"}


def cargar_homologacion(fuente, sheet_name: str | None = None) -> pd.DataFrame:
    sheet = sheet_name or _primera_hoja(fuente)
    header_row = _detectar_fila_encabezado(fuente, sheet, COLS_HOMOLOGACION)
    df = pd.read_excel(fuente, sheet_name=sheet, header=header_row)
    df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]

    df["Codigo_erp"] = df["Codigo_erp"].astype(str).str.strip()
    df["sku_rep"] = df["sku_rep"].astype(str).str.strip()
    df["Canal"] = df["Canal"].astype(str).str.strip()
    df["Factor_conversion"] = pd.to_numeric(df["Factor_conversion"], errors="coerce")

    df = df.dropna(subset=["Codigo_erp", "sku_rep", "Factor_conversion"])
    df = df[df["Codigo_erp"] != ""]

    duplicados = df["Codigo_erp"].duplicated().sum()
    if duplicados:
        df = df.drop_duplicates(subset=["Codigo_erp"], keep="first")

    cols = ["Codigo_erp", "sku_rep", "Canal", "Factor_conversion"]
    if "Descripción Artículo" in df.columns:
        cols.append("Descripción Artículo")
    return df[cols].reset_index(drop=True), int(duplicados)


# ---------------------------------------------------------------------
# Base Maestra de Envases
# ---------------------------------------------------------------------
COLS_BASE_MAESTRA = {"Código producto", "Canal", "Componentes", "Peso caja", "Materiales", "Categoría"}


def cargar_base_maestra(fuente, sheet_name: str | None = None) -> pd.DataFrame:
    sheet = sheet_name or _primera_hoja(fuente)
    header_row = _detectar_fila_encabezado(fuente, sheet, COLS_BASE_MAESTRA)
    df = pd.read_excel(fuente, sheet_name=sheet, header=header_row)
    df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]

    df["Código producto"] = df["Código producto"].astype(str).str.strip()
    df["Canal"] = df["Canal"].astype(str).str.strip()
    df["Componentes"] = df["Componentes"].astype(str).str.strip()
    df["Peso caja"] = pd.to_numeric(df["Peso caja"], errors="coerce")
    df["Materiales"] = df["Materiales"].apply(taxonomia.normalizar_material)
    df["Categoría"] = df["Categoría"].apply(taxonomia.normalizar_categoria)

    peligrosidad_col = "Peligrosidad" if "Peligrosidad" in df.columns else None
    df["Peligrosidad"] = (
        df[peligrosidad_col].apply(taxonomia.normalizar_peligrosidad)
        if peligrosidad_col
        else "No Peligroso"
    )

    df = df.dropna(subset=["Código producto", "Canal", "Peso caja"])
    df = df[df["Código producto"] != ""]

    cols = ["Código producto", "Canal", "Componentes", "Peso caja", "Materiales", "Categoría", "Peligrosidad"]
    return df[cols].reset_index(drop=True)


def componentes_que_requieren_rigidez(base_maestra: pd.DataFrame) -> list[str]:
    """Componentes cuyo material cae en alguna de las 10 familias plásticas
    que la taxonomía RESIMPLE exige clasificar como Flexible o Rígido."""
    mask = base_maestra["Materiales"].apply(taxonomia.material_requiere_rigidez)
    return sorted(base_maestra.loc[mask, "Componentes"].unique().tolist())
