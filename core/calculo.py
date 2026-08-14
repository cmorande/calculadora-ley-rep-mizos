"""Motor de cálculo: Informe de Ventas x Homologación x Base Maestra de
Envases -> toneladas por Categoría / Subcategoría / Material / Peligrosidad,
listas para volcar en la grilla oficial RESIMPLE (ver core.taxonomia).

Lógica:
  1. cada fila de ventas se homologa por "ID Artículo" -> Codigo_erp, lo que
     entrega el sku_rep (código de producto en Base Maestra), el Canal y el
     Factor_conversion que lleva la cantidad vendida a "cajas equivalentes"
     (la unidad sobre la que está expresado el peso de cada componente de
     envase en Base Maestra).
  2. cada (sku_rep, Canal) trae su lista de componentes de envase (caja,
     film, cinta, etc.) con el peso total (gramos) por caja.
  3. peso_g = cajas_equivalentes * peso_por_caja(componente)
  4. se agrega por Categoría (Domiciliario/No Domiciliario) x Material x
     Peligrosidad, y para los materiales plásticos que la taxonomía separa
     en Flexible/Rígido, se resuelve con el mapa de rigidez entregado por
     el llamador (ver core.carga.componentes_que_requieren_rigidez).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import taxonomia

DEFAULT_FLEXIBLE = {"film", "cinta embalaje", "bolsa", "doypack", "bolsita", "pouch", "sachet", "envoltorio"}


def rigidez_por_defecto(componentes: list[str]) -> dict[str, str]:
    """Clasificación Flexible/Rígido por defecto según el tipo físico habitual
    del componente. Es un supuesto editable: revisar antes de declarar."""
    return {
        c: ("Flexible" if c.strip().lower() in DEFAULT_FLEXIBLE else "Rígido")
        for c in componentes
    }


@dataclass
class ResultadoCalculo:
    valores: dict[str, list[list[float]]]  # {categoria: [[no_peligroso, peligroso], ...]} alineado con taxonomia.BLOQUES
    total_toneladas: float
    total_por_categoria: dict[str, float]
    detalle: pd.DataFrame  # una fila por venta x componente, para auditoría
    agregado: pd.DataFrame  # agregado final por categoria/subcat2/material/peligrosidad
    ventas_no_homologadas: pd.DataFrame
    skus_sin_bom: pd.DataFrame
    materiales_no_clasificados: pd.DataFrame
    ventas_descartadas: int = 0
    homologaciones_duplicadas: int = 0

    @property
    def hay_advertencias(self) -> bool:
        return (
            len(self.ventas_no_homologadas) > 0
            or len(self.skus_sin_bom) > 0
            or len(self.materiales_no_clasificados) > 0
            or self.ventas_descartadas > 0
            or self.homologaciones_duplicadas > 0
        )


def calcular(
    ventas: pd.DataFrame,
    homologacion: pd.DataFrame,
    base_maestra: pd.DataFrame,
    rigidez_map: dict[str, str] | None = None,
    ventas_descartadas: int = 0,
    homologaciones_duplicadas: int = 0,
) -> ResultadoCalculo:
    rigidez_map = rigidez_map or {}

    # 1) Homologar ventas -> sku_rep / Canal / factor
    merged = ventas.merge(
        homologacion, left_on="ID Artículo", right_on="Codigo_erp", how="left", indicator=True
    )
    ventas_no_homologadas = merged.loc[
        merged["_merge"] == "left_only", ["ID Artículo"] + (["Descripción"] if "Descripción" in merged.columns else [])
    ].drop_duplicates().reset_index(drop=True)

    matched = merged.loc[merged["_merge"] == "both"].drop(columns=["_merge"]).copy()
    matched["cajas_equivalentes"] = matched["Cantidad"] * matched["Factor_conversion"]

    # 2) Traer componentes de envase desde Base Maestra
    detalle = matched.merge(
        base_maestra,
        left_on=["sku_rep", "Canal"],
        right_on=["Código producto", "Canal"],
        how="left",
        indicator=True,
    )
    skus_sin_bom = (
        detalle.loc[detalle["_merge"] == "left_only", ["ID Artículo", "sku_rep", "Canal"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    detalle = detalle.loc[detalle["_merge"] == "both"].drop(columns=["_merge"]).copy()

    # 3) Peso por fila (venta x componente)
    detalle["peso_g"] = detalle["cajas_equivalentes"] * detalle["Peso caja"]

    def _subcategoria2(row) -> str | None:
        if taxonomia.material_requiere_rigidez(row["Materiales"]):
            return rigidez_map.get(row["Componentes"], "Rígido")
        return None

    detalle["Subcategoria2"] = detalle.apply(_subcategoria2, axis=1)

    # 4) Agregar
    agregado = (
        detalle.groupby(["Categoría", "Subcategoria2", "Materiales", "Peligrosidad"], dropna=False)["peso_g"]
        .sum()
        .reset_index()
    )
    agregado["toneladas"] = agregado["peso_g"] / 1_000_000.0

    # 5) Volcar a la grilla de la taxonomía oficial
    valores = {cat: [[0.0, 0.0] for _ in filas] for cat, filas in taxonomia.BLOQUES.items()}
    filas_no_clasificadas = []

    for _, row in agregado.iterrows():
        categoria = row["Categoría"]
        if categoria not in taxonomia.BLOQUES:
            filas_no_clasificadas.append(row)
            continue
        subcat2 = row["Subcategoria2"] if isinstance(row["Subcategoria2"], str) else None
        idx_map = taxonomia.indice_taxonomia(categoria)
        key = (subcat2, row["Materiales"])
        if key not in idx_map:
            filas_no_clasificadas.append(row)
            continue
        i = idx_map[key]
        col = 1 if row["Peligrosidad"] == "Peligroso" else 0
        valores[categoria][i][col] += row["toneladas"]

    materiales_no_clasificados = pd.DataFrame(filas_no_clasificadas) if filas_no_clasificadas else pd.DataFrame(
        columns=["Categoría", "Subcategoria2", "Materiales", "Peligrosidad", "toneladas"]
    )

    total_por_categoria = {
        cat: sum(v[0] + v[1] for v in filas) for cat, filas in valores.items()
    }
    total_toneladas = sum(total_por_categoria.values())

    return ResultadoCalculo(
        valores=valores,
        total_toneladas=total_toneladas,
        total_por_categoria=total_por_categoria,
        detalle=detalle,
        agregado=agregado,
        ventas_no_homologadas=ventas_no_homologadas,
        skus_sin_bom=skus_sin_bom,
        materiales_no_clasificados=materiales_no_clasificados,
        ventas_descartadas=ventas_descartadas,
        homologaciones_duplicadas=homologaciones_duplicadas,
    )


def composicion_por_subcategoria(resultado: ResultadoCalculo) -> pd.DataFrame:
    """Toneladas por (Categoría, Subcategoría principal) — para el gráfico de composición."""
    filas = []
    for categoria, bloque in taxonomia.BLOQUES.items():
        valores = resultado.valores[categoria]
        for fila_tax, (no_pel, pel) in zip(bloque, valores):
            filas.append(
                {
                    "Categoría": categoria,
                    "Subcategoría": fila_tax.subcategoria,
                    "toneladas": no_pel + pel,
                }
            )
    df = pd.DataFrame(filas)
    return df.groupby(["Categoría", "Subcategoría"], as_index=False)["toneladas"].sum()
