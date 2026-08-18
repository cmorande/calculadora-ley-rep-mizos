from __future__ import annotations

import hashlib
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import calculo, carga, comparacion, exportar, taxonomia

st.set_page_config(page_title="Calculadora Ley REP · Mizos", page_icon="♻️", layout="wide")
st.logo("assets/logo_ley_rep_mizos.png", size="large")


def _credenciales_validas(usuario: str, password: str) -> bool:
    try:
        auth = st.secrets["auth"]
    except Exception:
        st.error(
            "No hay credenciales configuradas (falta .streamlit/secrets.toml). "
            "Contacta a quien administra la app."
        )
        return False
    return usuario == auth["usuario"] and hashlib.sha256(password.encode()).hexdigest() == auth["password_hash"]


if not st.session_state.get("autenticado", False):
    col_izq, col_centro, col_der = st.columns([1, 1, 1])
    with col_centro:
        st.image("assets/logo_ley_rep_mizos.png", width=220)
        st.subheader("Iniciar sesión")
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            enviado = st.form_submit_button("Ingresar", type="primary")
        if enviado:
            if _credenciales_validas(usuario, password):
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()


# --- Paleta fija (identidad, no ranking) para las 6 subcategorías principales ---
PALETA_SUBCAT = {
    "METALES": "#2a78d6",
    "PLÁSTICOS": "#eb6834",
    "PAPELES Y CARTONES": "#1baf7a",
    "CARTÓN PARA BEBIDAS": "#eda100",
    "VIDRIO": "#e87ba4",
    "OTROS": "#008300",
}
COLOR_DOMICILIARIO = "#2a78d6"
COLOR_NO_DOMICILIARIO = "#4a3aa7"

PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color="#0b0b0b"),
    plot_bgcolor="#fcfcfb",
    paper_bgcolor="#fcfcfb",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(t=40, l=10, r=10, b=10),
)

DATA_DEFAULT = {
    "homologacion": "data/tabla_homologaciones.xlsx",
    "base_maestra": "data/base_maestra_envases.xlsx",
}


def fuente_homologacion():
    if st.session_state.homolog_override is not None:
        return st.session_state.homolog_override
    return DATA_DEFAULT["homologacion"] if os.path.exists(DATA_DEFAULT["homologacion"]) else None


def fuente_base_maestra():
    if st.session_state.base_maestra_override is not None:
        return st.session_state.base_maestra_override
    return DATA_DEFAULT["base_maestra"] if os.path.exists(DATA_DEFAULT["base_maestra"]) else None


for key in ("homolog_override", "base_maestra_override", "empresa_info"):
    if key not in st.session_state:
        st.session_state[key] = None


# ---------------------------------------------------------------------
# Sidebar: datos de la empresa (van en el encabezado de la declaración)
# ---------------------------------------------------------------------
with st.sidebar:
    if st.button("Cerrar sesión"):
        st.session_state.autenticado = False
        st.rerun()

    st.header("Datos de la empresa")
    razon_social = st.text_input("Nombre productor / Razón social", value="COMERCIAL VIVE SANO SPA")
    responsable = st.text_input("Responsable", value="")
    rut_empresa = st.text_input("RUT empresa", value="")
    id_rut_reporta = st.text_input("ID RUT de empresa que reporta", value=rut_empresa)
    representante_legal = st.text_input("Representante legal", value="")
    st.session_state.empresa_info = exportar.InfoEmpresa(
        razon_social=razon_social,
        responsable=responsable,
        id_rut_reporta=id_rut_reporta,
        rut_empresa=rut_empresa,
        representante_legal=representante_legal,
    )

st.title("♻️ Calculadora Ley REP — Envases y Embalajes")
st.caption("Genera la declaración RESIMPLE a partir del Informe de Ventas, y compara toneladas entre periodos.")

tab_calc, tab_datos, tab_comp = st.tabs(
    ["📋 Calcular declaración", "⚙️ Datos maestros", "📈 Comparar periodos"]
)


# =======================================================================
# TAB: Calcular declaración
# =======================================================================
with tab_calc:
    st.subheader("1. Nombre del periodo")
    periodo_label = st.text_input(
        "Nombre del periodo (para el archivo de descarga)", value="", key="periodo_label"
    )

    st.subheader("2. Verifica los datos maestros")
    st.info(
        "Antes de calcular, revisa en la pestaña '⚙️ Datos maestros' que la Tabla de "
        "Homologación y la Base Maestra de Envases estén con la última versión."
    )

    st.subheader("3. Sube el Informe de Ventas del periodo")
    archivo_ventas = st.file_uploader(
        "Informe de Ventas Consolidado (.xlsx)", type=["xlsx"], key="up_ventas"
    )

    homolog_fuente, base_fuente = fuente_homologacion(), fuente_base_maestra()
    if archivo_ventas is not None and not (homolog_fuente and base_fuente):
        st.error(
            "Falta la Homologación y/o la Base Maestra de Envases. Súbelas en la pestaña "
            "'⚙️ Datos maestros' antes de calcular."
        )
        st.stop()

    if archivo_ventas is not None:
        try:
            ventas_df, ventas_descartadas = carga.cargar_ventas(archivo_ventas)
            homolog_df, dup = carga.cargar_homologacion(homolog_fuente)
            base_df = carga.cargar_base_maestra(base_fuente)
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")
            st.stop()

        st.success(f"{len(ventas_df)} líneas de venta leídas.")

        componentes = carga.componentes_que_requieren_rigidez(base_df)
        rigidez_map = calculo.rigidez_por_defecto(componentes)

        st.subheader("4. Calcular")

        if st.button("Calcular declaración", type="primary"):
            resultado = calculo.calcular(
                ventas_df, homolog_df, base_df, rigidez_map,
                ventas_descartadas=ventas_descartadas, homologaciones_duplicadas=dup,
            )
            st.session_state["ultimo_resultado"] = resultado
            st.session_state["ultimo_periodo"] = periodo_label

        resultado = st.session_state.get("ultimo_resultado")
        if resultado is not None:
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Total declarado", f"{resultado.total_toneladas:.3f} t")
            c2.metric("Domiciliario", f"{resultado.total_por_categoria['Domiciliario']:.3f} t")
            c3.metric("No Domiciliario", f"{resultado.total_por_categoria['No Domiciliario']:.3f} t")

            if resultado.hay_advertencias:
                with st.expander("⚠️ Advertencias — revisar antes de declarar", expanded=True):
                    if resultado.ventas_descartadas:
                        st.warning(f"{resultado.ventas_descartadas} filas de venta sin cantidad válida, descartadas.")
                    if resultado.homologaciones_duplicadas:
                        st.warning(f"{resultado.homologaciones_duplicadas} códigos duplicados en Homologación (se usó la primera fila).")
                    if len(resultado.ventas_no_homologadas):
                        st.warning(f"{len(resultado.ventas_no_homologadas)} artículos vendidos no están en la Tabla de Homologación (excluidos del cálculo):")
                        st.dataframe(resultado.ventas_no_homologadas, use_container_width=True)
                    if len(resultado.skus_sin_bom):
                        st.warning(f"{len(resultado.skus_sin_bom)} combinaciones SKU/Canal no tienen ficha de envase en Base Maestra (excluidas):")
                        st.dataframe(resultado.skus_sin_bom, use_container_width=True)
                    if len(resultado.materiales_no_clasificados):
                        st.error("Materiales que no calzan con la taxonomía RESIMPLE (no se incluyeron en el total):")
                        st.dataframe(resultado.materiales_no_clasificados, use_container_width=True)

            comp_df = calculo.composicion_por_subcategoria(resultado)
            fig = go.Figure()
            for cat, color in [("Domiciliario", COLOR_DOMICILIARIO), ("No Domiciliario", COLOR_NO_DOMICILIARIO)]:
                sub = comp_df[comp_df["Categoría"] == cat]
                fig.add_bar(
                    x=sub["Subcategoría"], y=sub["toneladas"], name=cat,
                    marker_color=color, marker_line_width=0,
                )
            fig.update_layout(
                **PLOTLY_LAYOUT, barmode="group", title="Composición por material",
                yaxis_title="Toneladas", xaxis_title=None,
            )
            fig.update_yaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7")
            fig.update_xaxes(categoryorder="array", categoryarray=taxonomia.SUBCATEGORIAS_ORDEN)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("**Detalle agregado**")
            columnas_visibles = ["Categoría", "Materiales", "toneladas"]
            st.dataframe(resultado.agregado[columnas_visibles], use_container_width=True)

            nombre_archivo = f"Declaracion_{(st.session_state.get('ultimo_periodo') or 'REP').replace(' ', '_')}.xlsx"
            datos_xlsx = exportar.generar_bytes(resultado, st.session_state.empresa_info)
            st.download_button(
                "⬇️ Descargar declaración RESIMPLE (.xlsx)",
                data=datos_xlsx,
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
    else:
        st.info("Sube un Informe de Ventas para comenzar.")


# =======================================================================
# TAB: Datos maestros (Homologación / Base Maestra) — con override opcional
# =======================================================================
with tab_datos:
    st.subheader("Tabla de Homologación y Base Maestra de Envases")
    st.write(
        "La app trae cargadas las tablas actuales de Mizos. Si agregaste productos nuevos "
        "o cambió alguna ficha de envase, sube aquí la versión actualizada — se usará solo "
        "en esta sesión, no reemplaza el archivo original del proyecto."
    )
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Tabla de Homologación**")
        nuevo_h = st.file_uploader("Subir / reemplazar Homologación (.xlsx)", type=["xlsx"], key="up_homolog")
        if nuevo_h is not None:
            st.session_state.homolog_override = nuevo_h
        if os.path.exists(DATA_DEFAULT["homologacion"]):
            with open(DATA_DEFAULT["homologacion"], "rb") as f:
                st.download_button("Descargar la actual", f.read(), file_name="tabla_homologaciones.xlsx")
        elif st.session_state.homolog_override is None:
            st.warning("No hay una Homologación por defecto cargada en esta app — sube una para continuar.")

    with col2:
        st.markdown("**Base Maestra de Envases**")
        nuevo_b = st.file_uploader("Subir / reemplazar Base Maestra (.xlsx)", type=["xlsx"], key="up_base")
        if nuevo_b is not None:
            st.session_state.base_maestra_override = nuevo_b
        if os.path.exists(DATA_DEFAULT["base_maestra"]):
            with open(DATA_DEFAULT["base_maestra"], "rb") as f:
                st.download_button("Descargar la actual", f.read(), file_name="base_maestra_envases.xlsx")
        elif st.session_state.base_maestra_override is None:
            st.warning("No hay una Base Maestra por defecto cargada en esta app — sube una para continuar.")

    homolog_fuente, base_fuente = fuente_homologacion(), fuente_base_maestra()
    if homolog_fuente and base_fuente:
        try:
            homolog_df, dup = carga.cargar_homologacion(homolog_fuente)
            base_df = carga.cargar_base_maestra(base_fuente)
            st.success(f"Homologación: {len(homolog_df)} SKUs · Base Maestra: {base_df['Código producto'].nunique()} productos")
            with st.expander("Ver Tabla de Homologación"):
                st.dataframe(homolog_df, use_container_width=True)
            with st.expander("Ver Base Maestra de Envases"):
                st.dataframe(base_df, use_container_width=True)
        except Exception as e:
            st.error(f"No se pudo leer una de las tablas maestras: {e}")


# =======================================================================
# TAB: Comparar periodos
# =======================================================================
with tab_comp:
    st.subheader("Compara toneladas declaradas entre varios periodos")
    st.write(
        "Sube 2 o más archivos de declaración ya calculados (los que descargas en la primera "
        "pestaña, o declaraciones oficiales anteriores como 'Declaracion marzo 2026.xlsx') "
        "para ver la variación entre periodos."
    )
    archivos = st.file_uploader(
        "Declaraciones a comparar (.xlsx)", type=["xlsx"], accept_multiple_files=True, key="up_comparar"
    )

    if archivos:
        etiquetas = []
        st.write("Etiqueta cada archivo con su periodo (se usa para ordenar la comparación):")
        cols = st.columns(len(archivos))
        for i, (col, f) in enumerate(zip(cols, archivos)):
            with col:
                etiqueta = st.text_input(
                    f.name, value=comparacion.sugerir_periodo(f.name), key=f"etiqueta_{i}_{f.name}"
                )
                etiquetas.append(etiqueta)

        if st.button("Comparar", type="primary"):
            dfs = []
            errores = []
            for f, etiqueta in zip(archivos, etiquetas):
                try:
                    dfs.append(comparacion.leer_declaracion(f, etiqueta))
                except comparacion.ErrorDeclaracion as e:
                    errores.append(f"{f.name}: {e}")

            for err in errores:
                st.error(err)

            if len(dfs) >= 2:
                st.session_state["comparacion_df"] = comparacion.combinar(dfs)
                st.session_state["comparacion_orden"] = etiquetas
            elif dfs:
                st.warning("Sube al menos 2 archivos válidos para comparar.")

        combinado = st.session_state.get("comparacion_df")
        orden = st.session_state.get("comparacion_orden")
        if combinado is not None:
            st.divider()

            resumen = comparacion.resumen_por_periodo(combinado)
            resumen["Periodo"] = pd.Categorical(resumen["Periodo"], categories=orden, ordered=True)
            resumen = resumen.sort_values("Periodo")

            fig_total = go.Figure()
            for cat, color in [("Domiciliario", COLOR_DOMICILIARIO), ("No Domiciliario", COLOR_NO_DOMICILIARIO)]:
                sub = resumen[resumen["Categoría"] == cat]
                fig_total.add_bar(x=sub["Periodo"], y=sub["Toneladas"], name=cat, marker_color=color)
            fig_total.update_layout(
                **PLOTLY_LAYOUT, barmode="stack", title="Toneladas totales por periodo",
                yaxis_title="Toneladas",
            )
            fig_total.update_yaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7")
            st.plotly_chart(fig_total, use_container_width=True)

            comp = comparacion.composicion_por_periodo(combinado)
            comp["Periodo"] = pd.Categorical(comp["Periodo"], categories=orden, ordered=True)
            comp = comp.sort_values("Periodo")

            fig_comp = go.Figure()
            for subcat in taxonomia.SUBCATEGORIAS_ORDEN:
                sub = comp[comp["Subcategoría"] == subcat]
                fig_comp.add_bar(
                    x=sub["Periodo"], y=sub["Toneladas"], name=subcat,
                    marker_color=PALETA_SUBCAT[subcat],
                )
            fig_comp.update_layout(
                **PLOTLY_LAYOUT, barmode="stack", title="Composición por material y periodo",
                yaxis_title="Toneladas",
            )
            fig_comp.update_yaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7")
            st.plotly_chart(fig_comp, use_container_width=True)

            st.markdown("**Tabla de variación (toneladas y % entre periodos consecutivos)**")
            tabla_var = comparacion.tabla_variacion(combinado, orden)
            st.dataframe(tabla_var, use_container_width=True)

            st.download_button(
                "⬇️ Descargar tabla de variación (.csv)",
                data=tabla_var.to_csv().encode("utf-8-sig"),
                file_name="variacion_ley_rep.csv",
                mime="text/csv",
            )
    else:
        st.info("Sube al menos 2 declaraciones para comparar.")
