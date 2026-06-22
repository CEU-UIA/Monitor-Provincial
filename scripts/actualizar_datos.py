# ============================================================
# Base provincial integrada para dashboard
#
# Salida:
# base_provincias_dashboard.xlsx
#
# Hojas:
# - anual:
#     provincia | variable | 1993 | ... | 2025
#
# - trim:
#     provincia | variable | I-96 | II-96 | ...
#
# - vabporsector:
#     provincia | variable | 2004 | ... | 2024
#
# - vabporramas:
#     provincia | variable | 2004 | ... | 2024
#
# Variables hoja anual:
# - empresas
# - empresas_indus
# - expo
# - expo_moa_moi
# - vab
# - vab_indus
# ============================================================

from __future__ import annotations

import re
import unicodedata
import warnings
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


# ============================================================
# URLs
# ============================================================
# ============================================================
# URLs dinámicas
# ============================================================

URL_BASE_ARGENTINA = "https://www.argentina.gob.ar/sites/default/files"

PATRON_EMPLEO = URL_BASE_ARGENTINA + "/provinciales_serie_empleo_trimestral_2dig_{version}.xlsx"
PATRON_EMPRESAS = URL_BASE_ARGENTINA + "/provinciales_serie_empresas1_{version}.xlsx"
URL_VAB = "https://repositorio.cepal.org/server/api/core/bitstreams/539fcce5-8977-4061-a222-fbfd7358a35f/content"
URL_EXPO = "https://www.indec.gob.ar/ftp/cuadros/economia/sh_opex_regiones_economicas_grubros_1993_2025.xls"

def url_existe(url: str) -> bool:
    """
    Verifica si una URL existe.
    Primero intenta HEAD; si el servidor no lo permite, intenta GET liviano.
    """
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.head(url, headers=headers, timeout=20, allow_redirects=True)

        if r.status_code == 200:
            return True

        # Algunos servidores no aceptan HEAD correctamente
        if r.status_code in [403, 405]:
            r = requests.get(url, headers=headers, timeout=30, stream=True)
            return r.status_code == 200

        return False

    except requests.RequestException:
        return False


def encontrar_ultima_url(
    patron_url: str,
    version_min: int = 1,
    version_max: int = 30,
) -> str:
    """
    Busca la última versión disponible de una URL con patrón.

    Ejemplo:
        patron_url = ".../provinciales_serie_empresas1_{version}.xlsx"

    Devuelve:
        URL de la versión más alta que existe.
    """
    ultima_url_valida = None
    ultima_version_valida = None

    for version in range(version_min, version_max + 1):
        url = patron_url.format(version=version)

        if url_existe(url):
            ultima_url_valida = url
            ultima_version_valida = version
            print(f"Detectada versión disponible: {version} -> {url}")

    if ultima_url_valida is None:
        raise ValueError(f"No encontré ninguna URL válida para el patrón: {patron_url}")

    print(f"Última versión detectada: {ultima_version_valida}")
    return ultima_url_valida

URL_EMPLEO = encontrar_ultima_url(
    PATRON_EMPLEO,
    version_min=1,
    version_max=30,
)

URL_EMPRESAS = encontrar_ultima_url(
    PATRON_EMPRESAS,
    version_min=1,
    version_max=30,
)
# ============================================================
# ARCHIVOS
# ============================================================

DIR_DATA = Path("data_fuentes")
DIR_DATA.mkdir(exist_ok=True)

ARCHIVO_EMPLEO = DIR_DATA / "empleo_trimestral_latest.xlsx"
ARCHIVO_EMPRESAS = DIR_DATA / "empresas_anual_latest.xlsx"
ARCHIVO_VAB = DIR_DATA / "vab_cepal_provincias.xlsx"
ARCHIVO_EXPO = DIR_DATA / "sh_opex_regiones_economicas_grubros_1993_2025.xls"

ARCHIVO_SALIDA = Path("data") / "base_provincias_dashboard.xlsx"

warnings.filterwarnings("ignore", category=UserWarning)


# ============================================================
# PROVINCIAS
# ============================================================

ORDEN_PROVINCIAS = [
    "Buenos Aires",
    "CABA",
    "Catamarca",
    "Chaco",
    "Chubut",
    "Córdoba",
    "Corrientes",
    "Entre Ríos",
    "Formosa",
    "Jujuy",
    "La Pampa",
    "La Rioja",
    "Mendoza",
    "Misiones",
    "Neuquén",
    "Río Negro",
    "Salta",
    "San Juan",
    "San Luis",
    "Santa Cruz",
    "Santa Fe",
    "Santiago del Estero",
    "Tierra del Fuego",
    "Tucumán",
]

MAPA_PROVINCIAS = {
    "ciudad autonoma de buenos aires": "CABA",
    "ciudad de buenos aires": "CABA",
    "ciudad_de_buenos_aires": "CABA",
    "caba": "CABA",
    "capital federal": "CABA",

    "buenos aires": "Buenos Aires",
    "buenos_aires": "Buenos Aires",
    "provincia de buenos aires": "Buenos Aires",

    "cordoba": "Córdoba",
    "entre rios": "Entre Ríos",
    "entre_rios": "Entre Ríos",
    "rio negro": "Río Negro",
    "rio_negro": "Río Negro",
    "neuquen": "Neuquén",
    "tucuman": "Tucumán",
    "tierra del fuego": "Tierra del Fuego",
    "tierra_del_fuego": "Tierra del Fuego",
    "tierra del fuego antartida e islas del atlantico sur": "Tierra del Fuego",
    "tierra del fuego, antartida e islas del atlantico sur": "Tierra del Fuego",
    "santiago del estero": "Santiago del Estero",
    "santiago_del_estero": "Santiago del Estero",
    "la pampa": "La Pampa",
    "la_pampa": "La Pampa",
    "la rioja": "La Rioja",
    "la_rioja": "La Rioja",
    "san juan": "San Juan",
    "san_juan": "San Juan",
    "san luis": "San Luis",
    "san_luis": "San Luis",
    "santa cruz": "Santa Cruz",
    "santa_cruz": "Santa Cruz",
    "santa fe": "Santa Fe",
    "santa_fe": "Santa Fe",
}


# ============================================================
# VAB SECTORIAL
# ============================================================

SECTORES_FILAS = {
    "Agricultura, ganadería, caza y silvicultura": list(range(7, 9)),
    "Pesca y servicios conexos": [9],
    "Explotación de minas y canteras": list(range(10, 12)),
    "Industria manufacturera": list(range(12, 36)),
    "Electricidad, gas y agua": list(range(36, 39)),
    "Construcción": [39],
    "Comercio al por mayor y al por menor": [40],
    "Hotelería y restaurantes": list(range(41, 43)),
    "Transporte, de almacenamiento y de comunicaciones": list(range(43, 45)),
    "Intermediación financiera y otros servicios financieros": list(range(45, 48)),
    "Servicios inmobiliarios, empresariales y de alquiler": list(range(48, 50)),
    "Administración pública": [50],
    "Enseñanza": list(range(51, 53)),
    "Servicios sociales y de salud": list(range(53, 55)),
    "Servicios comunitarios, sociales y personales n.c.p.": list(range(55, 59)),
}


# ============================================================
# FUNCIONES GENERALES
# ============================================================

def normalizar_txt(x: object) -> str:
    if x is None or pd.isna(x):
        return ""

    s = str(x).strip().lower()
    s = s.replace("_", " ")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace(".", "")
    s = s.replace("(", "")
    s = s.replace(")", "")
    s = re.sub(r"\s+", " ", s)

    return s


def limpiar_provincia(valor: object) -> Optional[str]:
    if valor is None or pd.isna(valor):
        return None

    s = str(valor).strip()
    if s == "":
        return None

    s_norm = normalizar_txt(s)

    if s_norm in MAPA_PROVINCIAS:
        return MAPA_PROVINCIAS[s_norm]

    for prov in ORDEN_PROVINCIAS:
        if normalizar_txt(prov) == s_norm:
            return prov

    return None


def provincia_desde_hoja(sheet_name: str) -> Optional[str]:
    s = normalizar_txt(sheet_name)

    # Caso empleo / empresas: Buenos Aires viene partido
    if "gba" in s or "gran buenos aires" in s or "partidos" in s:
        return "Buenos Aires"

    if "resto" in s and "buenos" in s:
        return "Buenos Aires"

    return limpiar_provincia(sheet_name)


def descargar(url: str, destino: Path, forzar: bool = False) -> None:
    """
    Descarga un archivo.

    Si forzar=False y el archivo ya existe, usa el archivo local.
    Si forzar=True, lo vuelve a descargar aunque exista.
    """
    if destino.exists() and not forzar:
        print(f"Uso archivo local: {destino}")
        return

    print(f"Descargando: {url}")

    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=120)
    r.raise_for_status()

    destino.write_bytes(r.content)

    print(f"Archivo descargado: {destino}")


def extraer_anio(valor: object, anio_min: int, anio_max: int) -> Optional[int]:
    if valor is None or pd.isna(valor):
        return None

    if isinstance(valor, pd.Timestamp):
        anio = valor.year
        return anio if anio_min <= anio <= anio_max else None

    if isinstance(valor, (int, float)):
        anio = int(valor)
        return anio if anio_min <= anio <= anio_max else None

    s = str(valor).strip()
    m = re.search(r"(19\d{2}|20\d{2})", s)

    if m:
        anio = int(m.group(1))
        return anio if anio_min <= anio <= anio_max else None

    return None


def pivotear_anual(base_larga: pd.DataFrame, variables_orden: list[str]) -> pd.DataFrame:
    out = (
        base_larga
        .pivot_table(
            index=["provincia", "variable"],
            columns="periodo",
            values="valor",
            aggfunc="sum",
        )
        .reset_index()
    )

    out.columns.name = None

    columnas_periodos = sorted(
        [c for c in out.columns if c not in ["provincia", "variable"]],
        key=lambda x: int(x),
    )

    out = out[["provincia", "variable"] + columnas_periodos]

    orden_prov = {p: i for i, p in enumerate(ORDEN_PROVINCIAS)}
    orden_var = {v: i for i, v in enumerate(variables_orden)}

    out["_orden_prov"] = out["provincia"].map(orden_prov)
    out["_orden_var"] = out["variable"].map(orden_var)

    out = (
        out.sort_values(["_orden_prov", "_orden_var", "provincia", "variable"])
        .drop(columns=["_orden_prov", "_orden_var"])
        .reset_index(drop=True)
    )

    return out


def ordenar_trimestres(cols: list[str]) -> list[str]:
    orden_q = {"I": 1, "II": 2, "III": 3, "IV": 4}

    def key(c: str):
        m = re.match(r"^(I|II|III|IV)-(\d{2})$", str(c))
        if not m:
            return (9999, 9)

        yy = int(m.group(2))
        year = 1900 + yy if yy >= 90 else 2000 + yy

        return (year, orden_q[m.group(1)])

    return sorted(cols, key=key)


def pivotear_trim(base_larga: pd.DataFrame) -> pd.DataFrame:
    out = (
        base_larga
        .pivot_table(
            index=["provincia", "variable"],
            columns="periodo",
            values="valor",
            aggfunc="sum",
        )
        .reset_index()
    )

    out.columns.name = None

    columnas_periodos = ordenar_trimestres(
        [c for c in out.columns if c not in ["provincia", "variable"]]
    )

    out = out[["provincia", "variable"] + columnas_periodos]

    orden_prov = {p: i for i, p in enumerate(ORDEN_PROVINCIAS)}
    orden_var = {"empleo_indus": 0, "empleo": 1}

    out["_orden_prov"] = out["provincia"].map(orden_prov)
    out["_orden_var"] = out["variable"].map(orden_var)

    out = (
        out.sort_values(["_orden_var", "_orden_prov", "provincia"])
        .drop(columns=["_orden_prov", "_orden_var"])
        .reset_index(drop=True)
    )

    return out


# ============================================================
# EMPLEO TRIMESTRAL
# ============================================================

ROMANOS = {"1": "I", "2": "II", "3": "III", "4": "IV"}


def etiqueta_trimestre(valor: object) -> Optional[str]:
    if valor is None or pd.isna(valor):
        return None

    if isinstance(valor, pd.Timestamp):
        q = (valor.month - 1) // 3 + 1
        return f"{ROMANOS[str(q)]}-{str(valor.year)[-2:]}"

    s = str(valor).strip().upper()
    s = s.replace("º", "°")
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s)

    # 1°TRIM 1996 / 2 TRIM 1996 / 3 TRIMESTRE 1996
    m = re.search(r"\b([1-4])\s*°?\s*(?:TRIM|TRIMESTRE)\s*(19\d{2}|20\d{2})\b", s)
    if m:
        return f"{ROMANOS[m.group(1)]}-{m.group(2)[-2:]}"

    # I-96 / II-1996
    m = re.match(r"^(I|II|III|IV)[-_/ ]?(\d{2}|\d{4})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)[-2:]}"

    return None


def detectar_columnas_trimestres(df: pd.DataFrame) -> dict[int, str]:
    mejor = {}

    for fila_idx in range(min(20, len(df))):
        candidatos = {}

        for col_idx, valor in enumerate(df.iloc[fila_idx].tolist()):
            etiqueta = etiqueta_trimestre(valor)
            if etiqueta is not None:
                candidatos[col_idx] = etiqueta

        if len(candidatos) > len(mejor):
            mejor = candidatos

    if not mejor:
        raise ValueError("No pude detectar trimestres.")

    return mejor


def procesar_empleo_trim() -> pd.DataFrame:
    descargar(URL_EMPLEO, ARCHIVO_EMPLEO)

    filas_variables = {
        "empleo_indus": 15,
        "empleo": 76,
    }

    xls = pd.ExcelFile(ARCHIVO_EMPLEO)
    filas = []

    for sheet in xls.sheet_names:
        provincia = provincia_desde_hoja(sheet)

        if provincia is None:
            print(f"Salteo hoja empleo no provincial: {sheet}")
            continue

        print(f"Procesando empleo: {sheet} -> {provincia}")

        df = pd.read_excel(ARCHIVO_EMPLEO, sheet_name=sheet, header=None)
        columnas = detectar_columnas_trimestres(df)

        for variable, fila_excel in filas_variables.items():
            fila_idx = fila_excel - 1

            for col_idx, periodo in columnas.items():
                valor = pd.to_numeric(df.iat[fila_idx, col_idx], errors="coerce")

                filas.append({
                    "provincia": provincia,
                    "variable": variable,
                    "periodo": periodo,
                    "valor": valor,
                })

    base = pd.DataFrame(filas)

    # Buenos Aires suma Partidos de GBA + Resto de Buenos Aires
    base = (
        base.groupby(["provincia", "variable", "periodo"], as_index=False)["valor"]
        .sum(min_count=1)
    )

    return base


# ============================================================
# EMPRESAS ANUAL
# ============================================================

def detectar_columnas_anios_generico(
    df: pd.DataFrame,
    anio_min: int,
    anio_max: int,
    fila_fija_excel: Optional[int] = None,
) -> dict[int, int]:

    if fila_fija_excel is not None:
        fila_idx = fila_fija_excel - 1
        columnas = {}

        for col_idx, valor in enumerate(df.iloc[fila_idx].tolist()):
            anio = extraer_anio(valor, anio_min, anio_max)
            if anio is not None:
                columnas[col_idx] = anio

        if columnas:
            return columnas

    mejor = {}

    for fila_idx in range(min(25, len(df))):
        candidatos = {}

        for col_idx, valor in enumerate(df.iloc[fila_idx].tolist()):
            anio = extraer_anio(valor, anio_min, anio_max)
            if anio is not None:
                candidatos[col_idx] = anio

        if len(candidatos) > len(mejor):
            mejor = candidatos

    if not mejor:
        raise ValueError("No pude detectar años.")

    return mejor


def procesar_empresas_anual() -> pd.DataFrame:
    descargar(URL_EMPRESAS, ARCHIVO_EMPRESAS)

    filas_variables = {
        "empresas_indus": 15,
        "empresas": 76,
    }

    xls = pd.ExcelFile(ARCHIVO_EMPRESAS)
    filas = []

    for sheet in xls.sheet_names:
        provincia = provincia_desde_hoja(sheet)

        if provincia is None:
            print(f"Salteo hoja empresas no provincial: {sheet}")
            continue

        print(f"Procesando empresas: {sheet} -> {provincia}")

        df = pd.read_excel(ARCHIVO_EMPRESAS, sheet_name=sheet, header=None)
        columnas = detectar_columnas_anios_generico(df, 1996, 2024)

        for variable, fila_excel in filas_variables.items():
            fila_idx = fila_excel - 1

            for col_idx, anio in columnas.items():
                valor = pd.to_numeric(df.iat[fila_idx, col_idx], errors="coerce")

                filas.append({
                    "provincia": provincia,
                    "variable": variable,
                    "periodo": anio,
                    "valor": valor,
                })

    base = pd.DataFrame(filas)

    base = (
        base.groupby(["provincia", "variable", "periodo"], as_index=False)["valor"]
        .sum(min_count=1)
    )

    return base


# ============================================================
# VAB TOTAL, VAB SECTORIAL Y RAMAS INDUSTRIALES
# ============================================================

def procesar_vab_total() -> pd.DataFrame:
    descargar(URL_VAB, ARCHIVO_VAB)

    df = pd.read_excel(ARCHIVO_VAB, sheet_name="VABpb", header=None)

    columnas = detectar_columnas_anios_generico(
        df,
        anio_min=2004,
        anio_max=2024,
        fila_fija_excel=6,
    )

    filas = []

    # Columna B = provincia; desde fila 7
    for fila_idx in range(6, len(df)):
        provincia = limpiar_provincia(df.iat[fila_idx, 1])

        if provincia not in ORDEN_PROVINCIAS:
            continue

        for col_idx, anio in columnas.items():
            valor = pd.to_numeric(df.iat[fila_idx, col_idx], errors="coerce")

            filas.append({
                "provincia": provincia,
                "variable": "vab",
                "periodo": anio,
                "valor": valor,
            })

    return pd.DataFrame(filas)


def procesar_vab_sectorial_y_ramas() -> tuple[pd.DataFrame, pd.DataFrame]:
    descargar(URL_VAB, ARCHIVO_VAB)

    xls = pd.ExcelFile(ARCHIVO_VAB)

    filas_sector = []
    filas_ramas_industria = []

    for sheet in xls.sheet_names:
        provincia = provincia_desde_hoja(sheet)

        if provincia is None:
            print(f"Salteo hoja VAB no provincial: {sheet}")
            continue

        print(f"Procesando VAB sectorial: {sheet} -> {provincia}")

        df = pd.read_excel(ARCHIVO_VAB, sheet_name=sheet, header=None)

        columnas = detectar_columnas_anios_generico(
            df,
            anio_min=2004,
            anio_max=2024,
            fila_fija_excel=6,
        )

        # Sectores agregados
        for sector, filas_excel in SECTORES_FILAS.items():
            filas_idx = [f - 1 for f in filas_excel]

            for col_idx, anio in columnas.items():
                valores = pd.to_numeric(df.iloc[filas_idx, col_idx], errors="coerce")
                valor = valores.sum(skipna=True)

                filas_sector.append({
                    "provincia": provincia,
                    "variable": sector,
                    "periodo": anio,
                    "valor": valor,
                })

        # Ramas industriales: filas 12 a 35
        for fila_excel in range(12, 36):
            fila_idx = fila_excel - 1

            rama_raw = df.iat[fila_idx, 1]
            if rama_raw is None or pd.isna(rama_raw):
                continue

            rama = str(rama_raw).strip()
            if rama == "":
                continue

            for col_idx, anio in columnas.items():
                valor = pd.to_numeric(df.iat[fila_idx, col_idx], errors="coerce")

                filas_ramas_industria.append({
                    "provincia": provincia,
                    "variable": rama,
                    "periodo": anio,
                    "valor": valor,
                })

    base_sector = pd.DataFrame(filas_sector)
    base_ramas = pd.DataFrame(filas_ramas_industria)

    return base_sector, base_ramas


def procesar_vab_indus_para_anual(base_sectorial_larga: pd.DataFrame) -> pd.DataFrame:
    out = base_sectorial_larga[
        base_sectorial_larga["variable"] == "Industria manufacturera"
    ].copy()

    out["variable"] = "vab_indus"

    return out


# ============================================================
# EXPORTACIONES
# ============================================================

MAPA_EXPO_VARIABLES = {
    "total": "expo",
    "productos primarios": "expo_productos_primarios",
    "manufacturas de origen agropecuario": "expo_moa",
    "manufacturas de origen industrial": "expo_moi",
    "combustibles y energia": "expo_combustibles",
}


def limpiar_variable_expo(valor: object) -> Optional[str]:
    if valor is None or pd.isna(valor):
        return None

    s = normalizar_txt(valor)

    for clave, variable in MAPA_EXPO_VARIABLES.items():
        if clave in s:
            return variable

    return None


def limpiar_valor_expo(valor: object) -> Optional[float]:
    if valor is None or pd.isna(valor):
        return None

    if isinstance(valor, str):
        s = valor.strip()

        if s in ["-", "–", "—", ""]:
            return 0.0

        s = s.replace(",", ".")

        try:
            return float(s)
        except ValueError:
            return None

    return pd.to_numeric(valor, errors="coerce")


def detectar_columna_provincia_expo(df: pd.DataFrame) -> int:
    for fila_idx in range(min(10, len(df))):
        for col_idx, valor in enumerate(df.iloc[fila_idx].tolist()):
            if normalizar_txt(valor) == "provincias":
                return col_idx

    raise ValueError("No pude detectar columna de provincias en expo.")


def armar_mapa_columnas_expo(df: pd.DataFrame) -> pd.DataFrame:
    # Según estructura observada:
    # fila 3 = grupos
    # fila 5 = años
    fila_grupos_idx = 2
    fila_anios_idx = 4

    grupos = pd.Series(df.iloc[fila_grupos_idx].tolist()).ffill()
    anios = df.iloc[fila_anios_idx].tolist()

    registros = []

    for col_idx, valor_anio in enumerate(anios):
        anio = extraer_anio(valor_anio, 1993, 2025)

        if anio is None:
            continue

        variable = limpiar_variable_expo(grupos.iloc[col_idx])

        if variable is None:
            continue

        registros.append({
            "col_idx": col_idx,
            "variable": variable,
            "periodo": anio,
        })

    mapa = pd.DataFrame(registros)

    if mapa.empty:
        raise ValueError("No pude armar mapa de columnas de expo.")

    return mapa


def procesar_expo_anual() -> pd.DataFrame:
    descargar(URL_EXPO, ARCHIVO_EXPO)

    xls = pd.ExcelFile(ARCHIVO_EXPO, engine="xlrd")
    bases = []

    for sheet in xls.sheet_names:
        print(f"Procesando expo: {sheet}")

        df = pd.read_excel(
            ARCHIVO_EXPO,
            sheet_name=sheet,
            header=None,
            engine="xlrd",
        )

        col_prov = detectar_columna_provincia_expo(df)
        mapa = armar_mapa_columnas_expo(df)

        datos = df.iloc[6:].copy()
        datos["provincia"] = datos.iloc[:, col_prov].apply(limpiar_provincia)
        datos = datos[datos["provincia"].isin(ORDEN_PROVINCIAS)].copy()

        if datos.empty:
            continue

        value_cols = mapa["col_idx"].tolist()
        base = datos[["provincia"] + value_cols].copy()

        rename_cols = {
            row.col_idx: f"c_{i}"
            for i, row in mapa.reset_index(drop=True).iterrows()
        }

        base = base.rename(columns=rename_cols)

        mapa = mapa.reset_index(drop=True)
        mapa["col_tmp"] = [f"c_{i}" for i in range(len(mapa))]

        largo = base.melt(
            id_vars=["provincia"],
            value_vars=mapa["col_tmp"].tolist(),
            var_name="col_tmp",
            value_name="valor",
        )

        largo = largo.merge(
            mapa[["col_tmp", "variable", "periodo"]],
            on="col_tmp",
            how="left",
        )

        largo["valor"] = largo["valor"].apply(limpiar_valor_expo)

        bases.append(largo[["provincia", "variable", "periodo", "valor"]])

    base = pd.concat(bases, ignore_index=True)

    base = (
        base.groupby(["provincia", "variable", "periodo"], as_index=False)["valor"]
        .sum(min_count=1)
    )

    # Variable solicitada: expo = total
    expo_total = base[base["variable"] == "expo"].copy()

    # Variable solicitada: expo_moa_moi = MOA + MOI
    expo_moa_moi = (
        base[base["variable"].isin(["expo_moa", "expo_moi"])]
        .groupby(["provincia", "periodo"], as_index=False)["valor"]
        .sum(min_count=1)
    )
    expo_moa_moi["variable"] = "expo_moa_moi"
    expo_moa_moi = expo_moa_moi[["provincia", "variable", "periodo", "valor"]]

    return pd.concat([expo_total, expo_moa_moi], ignore_index=True)


# ============================================================
# EXPORTACIÓN FINAL
# ============================================================

def escribir_hoja_ancha(
    writer: pd.ExcelWriter,
    df: pd.DataFrame,
    sheet_name: str,
    width_variable: int = 34,
) -> None:
    df.to_excel(writer, sheet_name=sheet_name, index=False)

    ws = writer.book[sheet_name]

    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = width_variable

    for col in range(3, ws.max_column + 1):
        letra = ws.cell(1, col).column_letter
        ws.column_dimensions[letra].width = 12

        celda = ws.cell(row=1, column=col)

        # En hojas anuales, los encabezados deben quedar numéricos.
        if isinstance(celda.value, str) and celda.value.isdigit():
            celda.value = int(celda.value)

        if isinstance(celda.value, int):
            celda.number_format = "0"

    for row in range(2, ws.max_row + 1):
        for col in range(3, ws.max_column + 1):
            ws.cell(row=row, column=col).number_format = "#,##0.0"


def exportar_excel(
    base_anual: pd.DataFrame,
    base_trim: pd.DataFrame,
    vab_sector: pd.DataFrame,
    vab_ramas: pd.DataFrame,
) -> None:

    with pd.ExcelWriter(ARCHIVO_SALIDA, engine="openpyxl") as writer:
        escribir_hoja_ancha(writer, base_anual, "anual", width_variable=24)
        escribir_hoja_ancha(writer, base_trim, "trim", width_variable=18)
        escribir_hoja_ancha(writer, vab_sector, "vabporsector", width_variable=58)
        escribir_hoja_ancha(writer, vab_ramas, "vabporramas", width_variable=70)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=== Procesando empleo trimestral ===")
    empleo_trim_largo = procesar_empleo_trim()
    base_trim = pivotear_trim(empleo_trim_largo)

    print("")
    print("=== Procesando empresas anuales ===")
    empresas_largo = procesar_empresas_anual()

    print("")
    print("=== Procesando VAB total ===")
    vab_total_largo = procesar_vab_total()

    print("")
    print("=== Procesando VAB sectorial y ramas industriales ===")
    vab_sector_largo, vab_ramas_largo = procesar_vab_sectorial_y_ramas()

    print("")
    print("=== Procesando exportaciones ===")
    expo_largo = procesar_expo_anual()

    print("")
    print("=== Armando hoja anual ===")
    vab_indus_largo = procesar_vab_indus_para_anual(vab_sector_largo)

    anual_largo = pd.concat(
        [
            empresas_largo,
            expo_largo,
            vab_total_largo,
            vab_indus_largo,
        ],
        ignore_index=True,
    )

    variables_anual = [
        "empresas",
        "empresas_indus",
        "expo",
        "expo_moa_moi",
        "vab",
        "vab_indus",
    ]

    base_anual = pivotear_anual(anual_largo, variables_anual)

    # Forzamos columnas anuales desde 1993 hasta 2025.
    # Donde una fuente no tiene dato, queda vacío.
    columnas_base = ["provincia", "variable"]
    columnas_anios = list(range(1993, 2026))

    for anio in columnas_anios:
        if anio not in base_anual.columns:
            base_anual[anio] = pd.NA

    base_anual = base_anual[columnas_base + columnas_anios]

    print("")
    print("=== Armando hojas VAB detalle ===")
    vab_sector = pivotear_anual(
        vab_sector_largo,
        variables_orden=list(SECTORES_FILAS.keys()),
    )

    # Forzamos 2004-2024 en detalle VAB
    for df in [vab_sector]:
        for anio in range(2004, 2025):
            if anio not in df.columns:
                df[anio] = pd.NA

    vab_sector = vab_sector[["provincia", "variable"] + list(range(2004, 2025))]

    vab_ramas = pivotear_anual(
        vab_ramas_largo,
        variables_orden=sorted(vab_ramas_largo["variable"].dropna().unique().tolist()),
    )

    for anio in range(2004, 2025):
        if anio not in vab_ramas.columns:
            vab_ramas[anio] = pd.NA

    vab_ramas = vab_ramas[["provincia", "variable"] + list(range(2004, 2025))]

    print("")
    print("=== Exportando Excel final ===")
    exportar_excel(
        base_anual=base_anual,
        base_trim=base_trim,
        vab_sector=vab_sector,
        vab_ramas=vab_ramas,
    )

    print("")
    print(f"Listo. Archivo creado: {ARCHIVO_SALIDA.resolve()}")

    print("")
    print("Resumen:")
    print(f"- Hoja anual: {base_anual.shape[0]} filas x {base_anual.shape[1]} columnas")
    print(f"- Hoja trim: {base_trim.shape[0]} filas x {base_trim.shape[1]} columnas")
    print(f"- Hoja vabporsector: {vab_sector.shape[0]} filas x {vab_sector.shape[1]} columnas")
    print(f"- Hoja vabporramas: {vab_ramas.shape[0]} filas x {vab_ramas.shape[1]} columnas")

    print("")
    print("Variables hoja anual:")
    print(base_anual["variable"].unique())

    print("")
    print("Primeras filas hoja anual:")
    print(base_anual.head())


if __name__ == "__main__":
    main()
