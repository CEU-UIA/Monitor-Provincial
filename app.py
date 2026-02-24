import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import base64
import json


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Fichas Provinciales – CEU UIA",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# CSS GLOBAL
# ─────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=DM+Mono:wght@400;500&display=swap');
  html, body, [class*="css"], [data-testid] { font-family: 'Sora', sans-serif !important; }
  [data-testid="stSidebar"]    { display: none !important; }
  [data-testid="stSidebarNav"] { display: none !important; }
  .block-container {
    max-width: 900px;
    padding-top: 0rem !important;
    padding-bottom: 4rem;
    padding-left: 2rem;
    padding-right: 2rem;
  }
  [data-testid="stHeader"] { background: transparent !important; }
  div[data-testid="stTabs"] { margin-top: -8px; }
  button[data-baseweb="tab"] {
    font-family: 'Sora', sans-serif !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
  }
  label[data-testid="stWidgetLabel"] p {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6b7a99 !important;
  }
  div[data-baseweb="select"] > div {
    font-family: 'Sora', sans-serif !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    border-radius: 10px !important;
    border: 1.5px solid #e2e8f4 !important;
  }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────
VS_CODE_PATH      = "data/vs_code.xlsx"
SHEET_ANUAL       = "anual"
SHEET_TRIM        = "trim"
SHEET_ART         = "art"
SHEET_VAB_SECTOR  = "vabporsector"
SHEET_VAB_RAMAS   = "vabporramas"
SECTOR_INDUSTRIA  = "Industria manufacturera"
LABEL_ART         = "Alícuota promedio ART"


MAPA_IND_PERMITIDAS = [
    "VAB por 1000 habitantes",
    "Empleo formal cada 1.000 habitantes",
    "Empleo industrial cada 1.000 habitantes",
    "Industria / VAB Total",
    "MOA+MOI / Expo",
    "Empresas industriales cada 1.000 habitantes",
    "Empresas cada 1.000 habitantes",
    LABEL_ART,
]

MAPA_IND_KIND = {
    "Industria / VAB Total": "pct",
    "MOA+MOI / Expo": "pct",
    LABEL_ART: "pct",
    # el resto son niveles
    "VAB por 1000 habitantes": "int",
    "Empleo formal cada 1.000 habitantes": "int",
    "Empleo industrial cada 1.000 habitantes": "int",
    "Empresas industriales cada 1.000 habitantes": "int",
    "Empresas cada 1.000 habitantes": "int",
}

# Nombres exactos de variables en el Excel para las 4 KPI cards
KPI_VAR_EMP     = "Cantidad de empresas industriales"        # empresas industriales  → anual
KPI_VAR_EXPO    = "Expo MOA+MOI (M u$s)"                     # exportaciones          → anual
# Empleo: se busca por coincidencia parcial case-insensitive en VARS_TRIM
_KPI_PUESTOS_KEYWORD = "empleo industrial"   # substring para encontrar la variable trim

def _is_pct_var(var: str) -> bool:
    return MAPA_IND_KIND.get(var) == "pct"

def _pctize(v):
    """Si viene como ratio (0.75) lo pasa a % (75). Si ya viene 75 lo deja."""
    if v is None or pd.isna(v):
        return None
    vv = float(v)
    return vv * 100 if abs(vv) <= 1.5 else vv

PALETTE = [
    "#1B2D6B","#D4860A","#127070","#C0392B","#7B2D8B",
    "#1A7A4A","#0077B6","#E67E22","#8E44AD","#16A085",
    "#2C3E50","#E74C3C","#27AE60","#2980B9","#F39C12",
    "#6C3483","#117A65","#784212","#1F618D","#922B21",
    "#0B5345","#6E2F8C","#1A5276","#7D6608","#4A235A",
]
COLORES_SECT = ["#1B2D6B","#D4860A","#127070","#C0392B","#7B2D8B","#aab0c0"]

# Secuencia fija de meses para ART: nov-20 → oct-25
def _generar_periodos_art():
    meses = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    result = []
    for yr in range(2020, 2026):
        for i, m in enumerate(meses, 1):
            label = f"{m}-{str(yr)[2:]}"
            order = yr * 100 + i
            result.append((label, order))
    # filtrar nov-20 en adelante hasta oct-25
    result = [(l, o) for l, o in result if o >= 202011 and o <= 202510]
    return result

PERIODOS_ART = _generar_periodos_art()  # lista de (label, order_int)
PERIODOS_ART_LABELS  = [p[0] for p in PERIODOS_ART]
PERIODOS_ART_ORDERS  = [p[1] for p in PERIODOS_ART]
N_PERIODOS_ART       = len(PERIODOS_ART_LABELS)   # debería ser 60

# ─────────────────────────────────────────────
# Helpers generales
# ─────────────────────────────────────────────
def hex_to_rgba(hex_color: str, alpha: float = 0.1) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"

def fmt_int_es(x):
    if x is None or pd.isna(x): return "—"
    return f"{float(x):,.0f}".replace(",","X").replace(".",",").replace("X",".")

def fmt_pct_es(x, digits=1):
    if x is None or pd.isna(x): return "—"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.{digits}f}%".replace(".",",")

def fmt_pct_plain(x, digits=1):
    if x is None or pd.isna(x): return "—"
    return f"{x:.{digits}f}%".replace(".",",")

def truncate_label(text, max_len=26):
    return text if len(text) <= max_len else text[:max_len].rstrip() + "…"

def img_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# ─────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_anual(file_path, sheet_name):
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    col_prov, col_var = df.columns[0], df.columns[1]
    per_cols = df.columns[2:]
    df[col_prov] = df[col_prov].astype(str).str.strip()
    df[col_var]  = df[col_var].astype(str).str.strip()
    df_long = df.melt(id_vars=[col_prov,col_var], value_vars=per_cols,
                      var_name="period", value_name="value")
    df_long.columns = ["provincia","variable","period","value"]
    df_long["period_num"] = pd.to_numeric(df_long["period"], errors="coerce")
    df_long["value"]      = pd.to_numeric(df_long["value"],  errors="coerce")
    df_long = df_long.dropna(subset=["period_num"])
    df_long["period_num"] = df_long["period_num"].astype(int)
    df_long = df_long[~df_long["provincia"].str.lower().isin(["nan","none",""])]
    df_long = df_long[~df_long["variable"].str.lower().isin(["nan","none",""])]
    return df_long


@st.cache_data(show_spinner=False)
def load_trim(file_path, sheet_name):
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    col_prov, col_var = df.columns[0], df.columns[1]
    per_cols = df.columns[2:]
    df[col_prov] = df[col_prov].astype(str).str.strip()
    df[col_var]  = df[col_var].astype(str).str.strip()
    df_long = df.melt(id_vars=[col_prov,col_var], value_vars=per_cols,
                      var_name="period", value_name="value")
    df_long.columns = ["provincia","variable","period","value"]
    df_long["value"] = pd.to_numeric(df_long["value"], errors="coerce")
    df_long = df_long[~df_long["provincia"].str.lower().isin(["nan","none",""])]
    df_long = df_long[~df_long["variable"].str.lower().isin(["nan","none",""])]

    def trim_order(s):
        try:
            p = str(s).split("-")
            num = {"I":1,"II":2,"III":3,"IV":4}.get(p[0].strip(), 0)
            yr  = int(p[1].strip())
            yr  = yr+2000 if yr<50 else yr+1900
            return yr*10 + num
        except:
            return 0

    df_long["period_num"] = df_long["period"].apply(trim_order)
    df_long = df_long[df_long["period_num"] > 0]
    return df_long


@st.cache_data(show_spinner=False)
def load_art(file_path, sheet_name, label):
    """
    Lee la hoja ART ignorando completamente los encabezados de columna.
    Col 0 = provincia, col 1..N = valores mensuales en orden (nov-20 → oct-25).
    Los valores pueden ser float 0.034 (= 3,4%) o string "3,4%" — los normaliza a %.
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl", header=None)

    df_data = df.iloc[1:].copy().reset_index(drop=True)

    col_prov = 0
    df_data[col_prov] = df_data[col_prov].astype(str).str.strip()
    df_data = df_data[~df_data[col_prov].str.lower().isin(["nan","none",""])]

    rows = []
    for _, row in df_data.iterrows():
        prov = row[col_prov]
        for i, (period_label, period_num) in enumerate(PERIODOS_ART):
            col_idx = i + 1
            if col_idx >= len(row):
                break
            raw = row[col_idx]
            try:
                s = str(raw).replace("%","").replace(",",".").strip()
                val = float(s)
                if val < 1:
                    val = val * 100
            except:
                val = float("nan")
            rows.append({
                "provincia":  prov,
                "variable":   label,
                "period":     period_label,
                "period_num": period_num,
                "value":      val,
            })

    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def load_vab_tabla(file_path, sheet_name):
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    df.columns = ["provincia","sector"] + list(df.columns[2:])
    df["provincia"] = df["provincia"].astype(str).str.strip()
    df["sector"]    = df["sector"].astype(str).str.strip()
    return df


import unicodedata as _ud

def _norm(s):
    s = str(s).strip().lower()
    s = _ud.normalize("NFKD", s)
    return "".join(c for c in s if not _ud.combining(c))

_ALIAS_GEO = {
    "caba":              "ciudad autonoma de buenos aires",
    "tierra del fuego":  "tierra del fuego, antartida e islas del atlantico sur",
}

@st.cache_data(show_spinner=False)
def load_argentina_geojson():
    """Carga provincias_ign.geojson desde data/. Fallback: intenta descarga."""
    import os, urllib.request
    for path in ["data/provincias_ign.geojson", "data/argentina.geojson", "provincias_ign.geojson"]:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    # Intentar descarga desde IGN
    urls = [
        "https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/public/data/argentina.geojson",
        "https://servicios.ign.gob.ar/geoserver/IGN/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=IGN%3Aprovincias&outputFormat=application%2Fjson&srsName=EPSG%3A4326",
    ]
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            os.makedirs("data", exist_ok=True)
            with open("data/provincias_ign.geojson", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            return data
        except Exception:
            continue
    return None

# ─────────────────────────────────────────────
# Cargar datos
# ─────────────────────────────────────────────
try:
    DF_ANUAL = load_anual(VS_CODE_PATH, SHEET_ANUAL); ANUAL_OK = True
except Exception as e:
    DF_ANUAL = pd.DataFrame(); ANUAL_OK = False; ANUAL_ERR = str(e)

try:
    DF_TRIM = load_trim(VS_CODE_PATH, SHEET_TRIM); TRIM_OK = True
except Exception as e:
    DF_TRIM = pd.DataFrame(); TRIM_OK = False

try:
    DF_ART = load_art(VS_CODE_PATH, SHEET_ART, LABEL_ART); ART_OK = True
except Exception as e:
    DF_ART = pd.DataFrame(); ART_OK = False

try:
    DF_VAB_SECTOR = load_vab_tabla(VS_CODE_PATH, SHEET_VAB_SECTOR); VAB_SECT_OK = True
except Exception as e:
    DF_VAB_SECTOR = pd.DataFrame(); VAB_SECT_OK = False

try:
    DF_VAB_RAMAS = load_vab_tabla(VS_CODE_PATH, SHEET_VAB_RAMAS); VAB_RAMAS_OK = True
except Exception as e:
    DF_VAB_RAMAS = pd.DataFrame(); VAB_RAMAS_OK = False

# ─────────────────────────────────────────────
# Catálogos
# ─────────────────────────────────────────────
if ANUAL_OK and not DF_ANUAL.empty:
    PROVINCIAS_LIST = sorted(DF_ANUAL["provincia"].unique().tolist())
    PROVINCIAS = {n:{"nombre":n,"color":PALETTE[i%len(PALETTE)]} for i,n in enumerate(PROVINCIAS_LIST)}
else:
    PROVINCIAS_LIST = []; PROVINCIAS = {}

VARS_ANUAL = sorted(DF_ANUAL["variable"].unique().tolist()) if ANUAL_OK and not DF_ANUAL.empty else []
VARS_TRIM  = sorted(DF_TRIM["variable"].unique().tolist())  if TRIM_OK  and not DF_TRIM.empty  else []
VARS_ART   = [LABEL_ART] if ART_OK and not DF_ART.empty else []
VARIABLES_LIST = VARS_ANUAL + VARS_TRIM + VARS_ART

# ─────────────────────────────────────────────
# Variables para TAB Evolución (excluir las de 1 solo dato)
# - fuera: Población
# - fuera: indicadores "cada 1.000" / "por 1000" / "por 1.000"
# ─────────────────────────────────────────────
def _is_excluded_for_evol(v: str) -> bool:
    s = str(v).strip().lower()
    if "poblacion" in s or "población" in s:
        return True
    if "cada 1.000" in s or "cada 1000" in s or "por 1000" in s or "por 1.000" in s:
        return True
    return False

VARIABLES_EVO = [v for v in VARIABLES_LIST if not _is_excluded_for_evol(v)]

# Resolver nombre real de "Empleo industrial" en VARS_TRIM (match parcial case-insensitive)
KPI_VAR_PUESTOS = next(
    (v for v in VARS_TRIM if _KPI_PUESTOS_KEYWORD in v.lower()),
    None
)

def _source(v):
    if v in VARS_ANUAL: return "anual"
    if v in VARS_TRIM:  return "trim"
    return "art"

# ─────────────────────────────────────────────
# Helpers de series
# ─────────────────────────────────────────────
def get_serie(prov, variable):
    src = _source(variable)
    if src == "anual":
        if DF_ANUAL.empty: return [],[],[]
        sub = DF_ANUAL[(DF_ANUAL["provincia"]==prov)&(DF_ANUAL["variable"]==variable)]\
              .sort_values("period_num").dropna(subset=["value"])
        return sub["period"].tolist(), sub["value"].tolist(), sub["period_num"].tolist()
    elif src == "trim":
        if DF_TRIM.empty: return [],[],[]
        sub = DF_TRIM[(DF_TRIM["provincia"]==prov)&(DF_TRIM["variable"]==variable)]\
              .sort_values("period_num").dropna(subset=["value"])
        return sub["period"].tolist(), sub["value"].tolist(), sub["period_num"].tolist()
    else:
        if DF_ART.empty: return [],[],[]
        sub = DF_ART[(DF_ART["provincia"]==prov)]\
              .sort_values("period_num").dropna(subset=["value"])
        return sub["period"].tolist(), sub["value"].tolist(), sub["period_num"].tolist()

def kpi_last(periods, values):
    """Devuelve (last_period, last_value)."""
    if not periods: return None, None
    return periods[-1], values[-1]

# ─────────────────────────────────────────────
# VAB industria desde vabporsector
# ─────────────────────────────────────────────
def get_vab_industria(prov):
    """Devuelve (pct_str, año_str) del peso de industria manufacturera en el VAB."""
    if not VAB_SECT_OK or DF_VAB_SECTOR.empty:
        return "—", "—"
    df_p = DF_VAB_SECTOR[DF_VAB_SECTOR["provincia"]==prov].copy()
    if df_p.empty: return "—","—"
    col_last = df_p.columns[-1]
    df_p["vab"] = pd.to_numeric(df_p[col_last], errors="coerce")
    total = df_p["vab"].sum()
    if total == 0: return "—","—"
    ind = df_p[df_p["sector"].str.lower() == SECTOR_INDUSTRIA.lower()]
    if ind.empty: return "—","—"
    pct = ind["vab"].values[0] / total * 100
    return fmt_pct_plain(pct), str(col_last)

# ─────────────────────────────────────────────
# Insight dinámico
# ─────────────────────────────────────────────
def _top_vab(df_tabla, prov, n=10):
    df_p = df_tabla[df_tabla["provincia"]==prov].copy()
    if df_p.empty: return pd.DataFrame()
    col_last = df_p.columns[-1]
    df_p["vab"] = pd.to_numeric(df_p[col_last], errors="coerce")
    df_p = df_p.dropna(subset=["vab"])
    total = df_p["vab"].sum()
    if total==0: return pd.DataFrame()
    df_p["pct"] = (df_p["vab"]/total*100).round(1)
    return df_p.sort_values("pct",ascending=False).reset_index(drop=True).head(n)

def get_insight_y_vab(prov_name):
    top_sect  = _top_vab(DF_VAB_SECTOR, prov_name, 10) if VAB_SECT_OK  else pd.DataFrame()
    top_ramas = _top_vab(DF_VAB_RAMAS,  prov_name, 10) if VAB_RAMAS_OK else pd.DataFrame()
    if top_sect.empty:
        return None, None, top_ramas if not top_ramas.empty else None

    def fmt(x):
        return f"{x:.1f}%".replace(".", ",")

    s1 = top_sect.iloc[0]
    s2 = top_sect.iloc[1] if len(top_sect) > 1 else None

    texto = f"Sus principales sectores son <strong>{s1['sector']}</strong> ({fmt(s1['pct'])} del VAB)"
    if s2 is not None:
        texto += f" y <strong>{s2['sector']}</strong> ({fmt(s2['pct'])})."
    else:
        texto += "."

    ind_row = DF_VAB_SECTOR[
        (DF_VAB_SECTOR["provincia"] == prov_name) &
        (DF_VAB_SECTOR["sector"].str.lower() == SECTOR_INDUSTRIA.lower())
    ]

    top2_lower = [s1["sector"].lower()] + ([s2["sector"].lower()] if s2 is not None else [])

    if (not ind_row.empty) and (SECTOR_INDUSTRIA.lower() not in top2_lower):
        col_last = ind_row.columns[-1]
        ind_vab  = pd.to_numeric(ind_row.iloc[0][col_last], errors="coerce")
        df_p     = DF_VAB_SECTOR[DF_VAB_SECTOR["provincia"] == prov_name].copy()
        total    = pd.to_numeric(df_p.iloc[:, -1], errors="coerce").sum()
        if total > 0 and not pd.isna(ind_vab):
            texto += f" La industria manufacturera pesa <strong>{fmt(ind_vab/total*100)}</strong>."

    if not top_ramas.empty:
        r1 = top_ramas.iloc[0]
        r2 = top_ramas.iloc[1] if len(top_ramas) > 1 else None

        texto += f" Las principales ramas industriales son <strong>{r1['sector']}</strong> ({fmt(r1['pct'])} del VAB industrial)"
        if r2 is not None:
            texto += f" y <strong>{r2['sector']}</strong> ({fmt(r2['pct'])})."
        else:
            texto += "."

    return (
        texto,
        top_sect[["sector", "pct"]].head(10),
        top_ramas[["sector", "pct"]].head(10) if not top_ramas.empty else None,
    )

# ─────────────────────────────────────────────
# 4 KPI cards — blanco + acento azul (label / valor / período)
# ─────────────────────────────────────────────
STYLE_GRID_4 = (
    "display:grid;"
    "grid-template-columns:repeat(4,1fr);"
    "gap:0.65rem;"
    "margin-bottom:1.5rem;"
)

CARD_STYLE = (
    "background:white;"
    "border:1.5px solid #e2e8f4;"
    "border-radius:14px;"
    "padding:0.9rem 0.8rem;"
    "border-top:4px solid #1B2D6B;"
    "box-shadow:0 2px 6px rgba(0,0,0,0.04);"
)

LABEL_STYLE = (
    "font-family:'DM Mono',monospace;"
    "font-size:0.6rem;"
    "font-weight:600;"
    "text-transform:uppercase;"
    "letter-spacing:0.07em;"
    "color:#6b7a99;"
    "margin-bottom:0.35rem;"
    "white-space:nowrap;"
    "overflow:hidden;"
    "text-overflow:ellipsis;"
)

VALUE_STYLE = (
    "font-family:'Sora',sans-serif;"
    "font-size:1.15rem;"
    "font-weight:800;"
    "color:#1B2D6B;"
    "letter-spacing:-0.02em;"
    "margin-bottom:0.2rem;"
    "line-height:1.2;"
)

VALUE_STYLE_SM = (
    "font-family:'Sora',sans-serif;"
    "font-size:0.95rem;"
    "font-weight:800;"
    "color:#1B2D6B;"
    "letter-spacing:-0.02em;"
    "margin-bottom:0.2rem;"
    "line-height:1.2;"
)

PERIOD_STYLE = (
    "font-family:'DM Mono',monospace;"
    "font-size:0.6rem;"
    "color:#9aa3b2;"
)

def _kpi_card(label, value, period):
    vs = VALUE_STYLE_SM if len(str(value)) > 9 else VALUE_STYLE
    return (
        f'<div style="{CARD_STYLE}">'
        f'<div style="{LABEL_STYLE}">{label}</div>'
        f'<div style="{vs}">{value}</div>'
        f'<div style="{PERIOD_STYLE}">{period}</div>'
        f'</div>'
    )

def render_4_kpis(prov):
    cards = []

    # 1) VAB industria — desde vabporsector
    vab_pct, vab_yr = get_vab_industria(prov)
    cards.append(_kpi_card("Industria en el VAB", vab_pct, vab_yr))

    # 2) Empresas industriales — desde anual
    p, v, _ = get_serie(prov, KPI_VAR_EMP)
    lp, lv  = kpi_last(p, v)
    cards.append(_kpi_card(
        "Empresas industriales",
        fmt_int_es(lv) if lv is not None else "—",
        str(lp) if lp else "—",
    ))

    # 3) Empleo industrial — desde trim (nombre resuelto dinámicamente)
    if KPI_VAR_PUESTOS:
        p, v, _ = get_serie(prov, KPI_VAR_PUESTOS)
        lp, lv  = kpi_last(p, v)
        cards.append(_kpi_card(
            "Empleo industrial",
            fmt_int_es(lv) if lv is not None else "—",
            str(lp) if lp else "—",
        ))
    else:
        cards.append(_kpi_card("Empleo industrial", "—", "—"))

    # 4) Exportaciones — desde anual
    p, v, _ = get_serie(prov, KPI_VAR_EXPO)
    lp, lv  = kpi_last(p, v)
    cards.append(_kpi_card(
        "Expo MOA+MOI (M u$s)",
        fmt_int_es(lv) if lv is not None else "—",
        str(lp) if lp else "—",
    ))

    return f'<div style="{STYLE_GRID_4}">{"".join(cards)}</div>'

# ─────────────────────────────────────────────
# Plotly helpers
# ─────────────────────────────────────────────
def fig_serie(prov_name, variable, periods, values, color="#1B2D6B"):
    hover = "<b>%{x}</b><br>%{y:.1f}%<extra></extra>" if variable==LABEL_ART \
            else "<b>%{x}</b><br>%{y:,.2f}<extra></extra>"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=periods, y=values,
        mode="lines+markers",
        line=dict(color=color, width=2.5),
        marker=dict(color=color, size=5),
        fill="tozeroy",
        fillcolor=hex_to_rgba(color, 0.08),
        hovertemplate=hover,
    ))
    fig.update_layout(
        title=dict(
            text=f"<span style='font-family:Sora,sans-serif;font-size:13px;'>{variable} · {prov_name}</span>",
            x=0.01,
        ),
        height=280,
        margin=dict(t=40, b=50, l=80, r=40),
        xaxis=dict(gridcolor="#F0F2F6", tickfont=dict(size=9, family="DM Mono, monospace"),
                   tickangle=-45, nticks=14),
        yaxis=dict(gridcolor="#F0F2F6", tickfont=dict(size=10, family="DM Mono, monospace"),
                   rangemode="tozero"),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Sora, sans-serif", color="#31333F"),
        showlegend=False,
    )
    return fig

def fig_barras_h_azul(title, sectores, vals, n=10):
    """Barras horizontales con gradiente de azul oscuro a azul claro."""
    pares = sorted(
        [(s,v) for s,v in zip(sectores,vals) if v is not None],
        key=lambda x: x[1],
    )
    nombres_completos = [p[0] for p in pares]
    sect_truncados    = [truncate_label(p[0],30) for p in pares]
    vals_ord          = [float(p[1]) for p in pares]
    maxv = max(vals_ord) if vals_ord else 1.0

    n_bars = len(vals_ord)
    azul_oscuro = (27, 45, 107)   # #1B2D6B
    azul_claro  = (173, 198, 230) # #ADC6E6
    colores = []
    for i in range(n_bars):
        t = i / max(n_bars - 1, 1)  # 0 = más bajo (claro), 1 = más alto (oscuro)
        r = int(azul_claro[0] + t * (azul_oscuro[0] - azul_claro[0]))
        g = int(azul_claro[1] + t * (azul_oscuro[1] - azul_claro[1]))
        b = int(azul_claro[2] + t * (azul_oscuro[2] - azul_claro[2]))
        colores.append(f"rgb({r},{g},{b})")

    fig = go.Figure(go.Bar(
        x=vals_ord, y=sect_truncados,
        orientation="h",
        marker_color=colores,
        text=[f"{v:.1f}%".replace(".",",") for v in vals_ord],
        textposition="outside",
        textfont=dict(size=11),
        cliponaxis=False,
        customdata=nombres_completos,
        hovertemplate="<b>%{customdata}</b><br>%{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13), x=0.01),
        margin=dict(t=40, b=30, l=120, r=40),
        xaxis=dict(range=[0, maxv*1.06], showgrid=False, showticklabels=False,
                   showline=False, zeroline=False, fixedrange=True),
        yaxis=dict(tickfont=dict(size=10), automargin=True,
                   ticklabelposition="outside left"),
        plot_bgcolor="white", paper_bgcolor="white",
        height=max(300, n_bars * 38 + 80),
        font=dict(family="Sora, sans-serif", color="#31333F"),
        showlegend=False, bargap=0.3,
    )
    return fig

def fig_comp_linea(seleccionadas, variable):
    is_pct = _is_pct_var(variable)

    fig = go.Figure()
    for pname in seleccionadas:
        color = PROVINCIAS[pname]["color"]
        periods, values, _ = get_serie(pname, variable)
        if periods:
            y_plot = [_pctize(v) for v in values] if is_pct else values

            hover = (
                f"<b>{pname}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>"
                if is_pct
                else f"<b>{pname}</b><br>%{{x}}: %{{y:,.2f}}<extra></extra>"
            )

            fig.add_trace(go.Scatter(
                x=periods, y=y_plot,
                mode="lines+markers", name=pname,
                line=dict(color=color, width=2.5),
                marker=dict(color=color, size=4),
                hovertemplate=hover,
            ))

    fig.update_layout(
        title=dict(
            text=f"<span style='font-family:Sora,sans-serif;font-size:13px;'>{variable}</span>",
            x=0.01,
        ),
        height=320, margin=dict(t=70,b=80,l=80,r=20),
        xaxis=dict(gridcolor="#F0F2F6", tickfont=dict(size=9,family="DM Mono, monospace"),
                   tickangle=-45, nticks=12),
        yaxis=dict(
            gridcolor="#F0F2F6",
            tickfont=dict(size=10,family="DM Mono, monospace"),
            rangemode="tozero",
            ticksuffix="%" if is_pct else "",
        ),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Sora, sans-serif", color="#31333F"),
        legend=dict(orientation="h", x=0.99, xanchor="right", y=1.18, yanchor="top",
                    font=dict(size=11), bgcolor="rgba(255,255,255,0)"),
        showlegend=True,
    )
    return fig

def fig_comp_barra(seleccionadas, variable):
    xs,ys,cs = [],[],[]
    for pname in seleccionadas:
        periods, values, _ = get_serie(pname, variable)
        if periods and values:
            xs.append(pname); ys.append(values[-1]); cs.append(PROVINCIAS[pname]["color"])
    if not xs: return go.Figure()
    ultimo = get_serie(seleccionadas[0], variable)[0]
    ultimo = ultimo[-1] if ultimo else ""
    fig = go.Figure(go.Bar(
        x=xs, y=ys, marker_color=cs,
        text=[f"{v:,.2f}" for v in ys], textposition="outside",
        textfont=dict(family="DM Mono, monospace", size=10),
        hovertemplate="<b>%{x}</b><br>%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text=f"<span style='font-family:Sora,sans-serif;font-size:13px;'>Último dato ({ultimo})</span>",
            x=0.01,
        ),
        height=280, margin=dict(t=40,b=60,l=44,r=20),
        xaxis=dict(tickfont=dict(size=10), tickangle=-30),
        yaxis=dict(gridcolor="#F0F2F6", tickfont=dict(size=10,family="DM Mono, monospace"),
                   rangemode="tozero"),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Sora, sans-serif", color="#31333F"),
        showlegend=False,
    )
    return fig

def fig_comp_scatter(seleccionadas, variable):
    xs,ys,nombres,cols = [],[],[],[]
    for pname in seleccionadas:
        periods, values, _ = get_serie(pname, variable)
        if periods and len(values)>=2:
            last_v = values[-1]
            prev_v = values[-2]
            yoy = (last_v/prev_v-1)*100 if prev_v and not pd.isna(prev_v) else None
            if last_v is not None and yoy is not None:
                xs.append(last_v); ys.append(yoy)
                nombres.append(pname); cols.append(PROVINCIAS[pname]["color"])
    if not xs: return go.Figure()
    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="markers+text",
        text=nombres, textposition="top center",
        marker=dict(color=cols, size=12),
        hovertemplate="<b>%{text}</b><br>Valor: %{x:,.2f}<br>Var: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text=f"<span style='font-family:Sora,sans-serif;font-size:13px;'>{variable} vs var. i.a. (%)</span>",
            x=0.01,
        ),
        height=280, margin=dict(t=40,b=44,l=64,r=20),
        xaxis=dict(title="Valor", gridcolor="#F0F2F6",
                   tickfont=dict(size=10,family="DM Mono, monospace")),
        yaxis=dict(title="Var. % i.a.", gridcolor="#F0F2F6",
                   tickfont=dict(size=10,family="DM Mono, monospace")),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Sora, sans-serif", color="#31333F"),
        showlegend=False,
    )
    return fig

# ─────────────────────────────────────────────
# Mapa helper (reutilizable)
# ─────────────────────────────────────────────

def build_map_and_rank(
    df_map_in,
    geo,
    title_text,
    color_scale="Reds",
    kind="auto",          # "pct" | "int" | "auto"
    hover_simple=False,   # True => solo Provincia + Valor formateado
):
    """
    df_map_in: columns ["provincia","value","periodo"]
    kind:
      - "pct": muestra % con 1 decimal
      - "int": muestra entero (miles)
      - "auto": intenta decidir (si value <= 1.5 y >=0 => pct, sino int)
    hover_simple:
      - True: hover = "Provincia" + "valor_formateado" (2 líneas)
    """
    if df_map_in is None or df_map_in.empty or geo is None:
        return go.Figure(), pd.DataFrame()

    def _fmt_value(v):
        if v is None or pd.isna(v):
            return "—"

        # normalizar strings tipo "70%" o "70,5%"
        if isinstance(v, str):
            s = v.strip().replace("%", "").replace(",", ".")
            try:
                v = float(s)
            except:
                return "—"

        vv = float(v)

        if kind == "pct":
            # ✅ si viene como ratio (0.70) => 70.0%
            # ✅ si viene como porcentaje (70) => 70.0%
            pct = vv * 100 if abs(vv) <= 1.5 else vv
            return fmt_pct_plain(pct, 1)

        if kind == "int":
            return fmt_int_es(vv)

        # auto (si cae acá)
        return fmt_int_es(vv)

    geo_features = geo["features"]
    geo_df = pd.DataFrame({
        "id":        [f["properties"].get("id",    f["properties"].get("ID",
                       f["properties"].get("fid",  f["properties"].get("FID",
                       f["properties"].get("nombre", i))))) for i, f in enumerate(geo_features)],
        "nombre_geo":[f["properties"].get("nombre",f["properties"].get("name",
                       f["properties"].get("NAME_1","?"))) for f in geo_features],
    })
    geo_df["nombre_norm"] = geo_df["nombre_geo"].apply(_norm)

    sample = geo_features[0]["properties"] if geo_features else {}
    feat_key = "properties.id" if "id" in sample else (
               "properties.nombre" if "nombre" in sample else "properties.name")

    df_map = df_map_in.copy()
    df_map["nombre_norm"] = df_map["provincia"].apply(_norm)
    df_map["nombre_norm"] = df_map["nombre_norm"].replace(_ALIAS_GEO)
    df_map = df_map.merge(geo_df[["id", "nombre_norm"]], on="nombre_norm", how="left")

    # ✅ columna formateada para hover
    df_map["value_fmt"] = df_map["value"].apply(_fmt_value)

    # ✅ IMPORTANTE: usar SOLO filas ploteables (id válido) para que customdata no se corra
    df_plot = df_map.dropna(subset=["id"]).copy()
    
    # Si querés, opcional: avisar cuántas quedaron afuera
    # dropped = len(df_map) - len(df_plot)
    
    # ✅ Pasar custom_data desde px para que quede alineado con el trace
    fig = px.choropleth(
        df_plot,
        geojson=geo,
        locations="id",
        featureidkey=feat_key,
        color="value",
        hover_name="provincia",
        custom_data=["value_fmt", "periodo"],
        color_continuous_scale=color_scale,
        labels={"value": "Valor"},
        projection="mercator",
    )
    
    # ✅ Hover (mismo formato que tu tabla, ej: 0,9%)
    if hover_simple:
        fig.update_traces(
            hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]}<extra></extra>"
        )
    else:
        fig.update_traces(
            hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>"
        )

    fig.update_geos(
        visible=False,
        lataxis_range=[-56, -20],
        lonaxis_range=[-75, -52],
    )
    fig.update_layout(
        title=dict(text=title_text, x=0.01),
        margin=dict(t=50, b=10, l=10, r=10),
        height=700,
        coloraxis_colorbar=dict(
            title=dict(text="Valor", font=dict(size=10, family="DM Mono, monospace")),
            tickfont=dict(size=9, family="DM Mono, monospace"),
            len=0.6,
        ),
        paper_bgcolor="white",
        font=dict(family="Sora, sans-serif", color="#31333F"),
    )

    # Ranking
    df_rank = df_map_in.copy().sort_values("value", ascending=False).reset_index(drop=True)
    df_rank.index = df_rank.index + 1
    df_rank = df_rank.rename(columns={"provincia": "Provincia", "value": "Valor", "periodo": "Período"})

    if kind == "pct":
        df_rank["Valor"] = df_rank["Valor"].apply(lambda x: fmt_pct_plain(x, 1) if pd.notna(x) else "—")
    elif kind == "int":
        df_rank["Valor"] = df_rank["Valor"].apply(lambda x: fmt_int_es(x) if pd.notna(x) else "—")
    else:
        df_rank["Valor"] = df_rank["Valor"].apply(lambda x: _fmt_value(x) if pd.notna(x) else "—")

    return fig, df_rank

# ─────────────────────────────────────────────
# VAB: utilitarios para mapas de sectores/ramas
# ─────────────────────────────────────────────
def _vab_last_col(df_tabla):
    if df_tabla is None or df_tabla.empty:
        return None
    return df_tabla.columns[-1]

def build_df_map_sector_share(sector_name: str):
    """
    Devuelve df con ["provincia","value","periodo"] donde value es % del sector / VAB total provincial
    usando DF_VAB_SECTOR última columna.
    """
    if not VAB_SECT_OK or DF_VAB_SECTOR.empty:
        return pd.DataFrame()

    col_last = _vab_last_col(DF_VAB_SECTOR)
    if col_last is None:
        return pd.DataFrame()

    rows = []
    for prov in PROVINCIAS_LIST:
        df_p = DF_VAB_SECTOR[DF_VAB_SECTOR["provincia"] == prov].copy()
        if df_p.empty:
            continue
        df_p["vab"] = pd.to_numeric(df_p[col_last], errors="coerce")
        total = df_p["vab"].sum()
        if not total or pd.isna(total) or total == 0:
            rows.append({"provincia": prov, "value": None, "periodo": str(col_last)})
            continue
        sel = df_p[df_p["sector"].str.lower() == str(sector_name).strip().lower()]
        if sel.empty:
            rows.append({"provincia": prov, "value": None, "periodo": str(col_last)})
            continue
        val = pd.to_numeric(sel["vab"].values[0], errors="coerce")
        pct = (val / total * 100) if (pd.notna(val) and total > 0) else None
        rows.append({"provincia": prov, "value": pct, "periodo": str(col_last)})

    return pd.DataFrame(rows)

def build_df_map_industria_share_total():
    """
    Mapa de: Industria manufacturera / VAB total provincial (%) usando DF_VAB_SECTOR.
    """
    return build_df_map_sector_share(SECTOR_INDUSTRIA)

def build_df_map_rama_share_industrial(rama_name: str):
    """
    Devuelve df con ["provincia","value","periodo"] donde value es:
    rama / VAB industrial provincial (%), usando DF_VAB_RAMAS última columna.
    """
    if not VAB_RAMAS_OK or DF_VAB_RAMAS.empty:
        return pd.DataFrame()

    col_last = _vab_last_col(DF_VAB_RAMAS)
    if col_last is None:
        return pd.DataFrame()

    rows = []
    for prov in PROVINCIAS_LIST:
        df_p = DF_VAB_RAMAS[DF_VAB_RAMAS["provincia"] == prov].copy()
        if df_p.empty:
            continue
        df_p["vab"] = pd.to_numeric(df_p[col_last], errors="coerce")
        total_ind = df_p["vab"].sum()
        if not total_ind or pd.isna(total_ind) or total_ind == 0:
            rows.append({"provincia": prov, "value": None, "periodo": str(col_last)})
            continue
        sel = df_p[df_p["sector"].str.lower() == str(rama_name).strip().lower()]
        if sel.empty:
            rows.append({"provincia": prov, "value": None, "periodo": str(col_last)})
            continue
        val = pd.to_numeric(sel["vab"].values[0], errors="coerce")
        pct = (val / total_ind * 100) if (pd.notna(val) and total_ind > 0) else None
        rows.append({"provincia": prov, "value": pct, "periodo": str(col_last)})

    return pd.DataFrame(rows)

# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
try:
    logo_b64  = img_to_base64("images/okok2.png")
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:48px;width:auto;">'
except Exception:
    logo_html = ('<span style="font-family:\'Sora\',sans-serif;font-size:26px;'
                 'font-weight:700;color:white;letter-spacing:-1px;">ceu</span>')

st.markdown(f"""
<div style="background:#1B2D6B;margin:30px -2rem 0 -2rem;padding:18px 2rem;
display:flex;align-items:center;justify-content:space-between;gap:20px;">
  <span style="font-family:'Sora',sans-serif;font-size:1.5rem;font-weight:700;color:white;">
    Monitor Provincial
  </span>
  {logo_html}
</div>
<div style="background:#F0F3FA;margin:0 -2rem 1.5rem -2rem;padding:10px 2rem;
font-size:12px;color:#6b6f7e;border-bottom:1px solid #E6E9EF;font-family:'Sora',sans-serif;">
  Unión Industrial Argentina
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Guard
# ─────────────────────────────────────────────
if not ANUAL_OK:
    st.error(f"⚠️ No se pudo cargar el Excel.\n\n`{ANUAL_ERR}`")
    st.stop()
if not PROVINCIAS:
    st.warning("No se encontraron provincias en el Excel.")
    st.stop()

# ─────────────────────────────────────────────
# Tabs — nuevo orden + renombre
# 1) Ficha provincial
# 2) Mapa por sectores (nuevo)
# 3) Mapa por indicadores (antes mapa)
# 4) Evolución de variables (antes evol)
# ─────────────────────────────────────────────
tab_ficha, tab_mapa_sect, tab_mapa_ind, tab_evol = st.tabs([
    "📋 Fichas",
    "🧩 Mapa por sectores",
    "🧭 Mapa por indicadores",
    "📈 Evolución de variables",
])

# ══════════════════════════════════════════════
# TAB 1 — FICHA PROVINCIAL
# ══════════════════════════════════════════════
with tab_ficha:

    prov = st.selectbox("Provincia", options=PROVINCIAS_LIST, key="sel_prov")
    prov_name = prov

    st.markdown(
        f'<div style="font-family:\'Sora\',sans-serif;font-size:2.4rem;font-weight:700;'
        f'color:#1B2D6B;letter-spacing:-0.03em;line-height:1;margin:0.5rem 0 1.2rem 0;">'
        f'{prov_name}'
        f'</div>',
        unsafe_allow_html=True,
    )

    resultado       = get_insight_y_vab(prov_name)
    txt_insight     = resultado[0]
    vab_top10_sect  = resultado[1]
    vab_top10_ramas = resultado[2]


    st.markdown(render_4_kpis(prov_name), unsafe_allow_html=True)

    # ─────────────────────────────────────────────
    # Estructura económica (VAB por sector / ramas)
    # ─────────────────────────────────────────────
    st.markdown(
        '<div style="font-family:\'Sora\',sans-serif;font-size:1.2rem;font-weight:700;'
        'color:#1B2D6B;letter-spacing:-0.02em;margin-bottom:1rem;">Estructura económica</div>',
        unsafe_allow_html=True,
    )

    if txt_insight:
        st.markdown(
            f'<div style="background:#f8fafc;'
            f'border:1px solid #e2e8f4;'
            f'border-left:4px solid #1B2D6B;'
            f'border-radius:10px;'
            f'padding:0.85rem 1.1rem;'
            f'font-size:0.875rem;'
            f'color:#334155;'
            f'line-height:1.6;'
            f'display:flex;gap:0.75rem;align-items:flex-start;'
            f'margin:0.5rem 0 1.2rem 0;">'
            f'<span style="font-size:1rem;flex-shrink:0;margin-top:1px">💡</span>'
            f'<span style="font-family:\'Sora\',sans-serif;">{txt_insight}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Gráfico VAB por sector — fila completa
    with st.container(border=True):
        if vab_top10_sect is not None and not vab_top10_sect.empty:
            st.plotly_chart(
                fig_barras_h_azul(
                    "Composición VAB por sector (%)",
                    vab_top10_sect["sector"].tolist(),
                    vab_top10_sect["pct"].tolist(),
                    n=10,
                ),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        else:
            st.info("Sin datos de VAB sectorial.")

    # Gráfico VAB por ramas — fila completa
    with st.container(border=True):
        if vab_top10_ramas is not None and not vab_top10_ramas.empty:
            st.plotly_chart(
                fig_barras_h_azul(
                    "Principales ramas industriales (%)",
                    vab_top10_ramas["sector"].tolist(),
                    vab_top10_ramas["pct"].tolist(),
                    n=10,
                ),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        else:
            st.info("Sin datos de ramas industriales.")

    st.markdown(
        '<div style="text-align:center;font-family:\'DM Mono\',monospace;font-size:0.7rem;'
        'color:#aab0c0;letter-spacing:0.05em;margin-top:2rem;">'
        'CEU – Centro de Estudios UIA · Unión Industrial Argentina · 2026</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════
# TAB 2 — MAPA ARGENTINO POR SECTORES (NUEVO)
# ══════════════════════════════════════════════
with tab_mapa_sect:

    if not VAB_SECT_OK or DF_VAB_SECTOR.empty:
        st.info("No hay datos disponibles de VAB por sector (`vabporsector`).")
    else:
        # Cargar geo una vez por tab
        with st.spinner("Cargando mapa..."):
            GEO = load_argentina_geojson()

        if GEO is None:
            st.error(
                "⚠️ No se encontró el archivo `data/provincias_ign.geojson`. "
                "Descargalo del IGN o de la URL que te pasé y ponelo en la carpeta `data/`."
            )
        else:
            # Selector de sector y (condicional) de rama en la MISMA fila
            sectores_disponibles = sorted(
                DF_VAB_SECTOR["sector"].dropna().astype(str).str.strip().unique().tolist()
            )

            ramas_disponibles = []
            if VAB_RAMAS_OK and not DF_VAB_RAMAS.empty:
                ramas_disponibles = sorted(
                    DF_VAB_RAMAS["sector"].dropna().astype(str).str.strip().unique().tolist()
                )

            c1, c2 = st.columns([1.2, 1.0], gap="medium")
            with c1:
                sector_sel = st.selectbox(
                    "Seleccioná un sector",
                    options=sectores_disponibles,
                    index=sectores_disponibles.index(SECTOR_INDUSTRIA) if SECTOR_INDUSTRIA in sectores_disponibles else 0,
                    key="map_sect_sector",
                )

            is_industria = (str(sector_sel).strip().lower() == SECTOR_INDUSTRIA.lower())

            with c2:
                # Siempre visible; gris (disabled) salvo industria
                rama_options = ["Total industria"] + ramas_disponibles if ramas_disponibles else ["Total industria"]
                rama_sel = st.selectbox(
                    "Seleccioná una rama industrial",
                    options=rama_options,
                    key="map_sect_rama",
                    disabled=not is_industria,
                )

            # Construir df para mapa (siempre en %)
            if not is_industria:
                df_map = build_df_map_sector_share(sector_sel)
                periodo_label = df_map["periodo"].iloc[0] if (df_map is not None and not df_map.empty) else ""
                titulo = f"<span style='font-family:Sora,sans-serif;font-size:13px;'>{sector_sel} · % del VAB ({periodo_label})</span>"
            else:
                if rama_sel == "Total industria":
                    df_map = build_df_map_industria_share_total()
                    periodo_label = df_map["periodo"].iloc[0] if (df_map is not None and not df_map.empty) else ""
                    titulo = f"<span style='font-family:Sora,sans-serif;font-size:13px;'>{SECTOR_INDUSTRIA} · % del VAB ({periodo_label})</span>"
                else:
                    df_map = build_df_map_rama_share_industrial(rama_sel)
                    periodo_label = df_map["periodo"].iloc[0] if (df_map is not None and not df_map.empty) else ""
                    titulo = f"<span style='font-family:Sora,sans-serif;font-size:13px;'>{rama_sel} · % del VAB industrial de cada pcia ({periodo_label})</span>"

            if df_map is None or df_map.empty or df_map["value"].dropna().empty:
                st.info("No hay datos suficientes para mostrar el mapa con esta selección.")
            else:
                fig, df_rank = build_map_and_rank(
                    df_map,
                    GEO,
                    title_text=titulo,
                    color_scale="Blues",
                    kind="pct",
                    hover_simple=True,   # ✅ Provincia + "10,2%"
                )

                with st.container(border=True):
                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False},
                    )

                st.markdown(
                    '<div style="font-family:\'Sora\',sans-serif;font-size:0.9rem;font-weight:600;'
                    'color:#1B2D6B;margin:1.2rem 0 0.5rem 0;">Ranking por provincia</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(df_rank, use_container_width=True, hide_index=False)

    st.markdown(
        '<div style="text-align:center;font-family:\'DM Mono\',monospace;font-size:0.7rem;'
        'color:#aab0c0;letter-spacing:0.05em;margin-top:2rem;">'
        'CEU – Centro de Estudios UIA · Unión Industrial Argentina · 2026</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════
# TAB 3 — MAPA ARGENTINO POR INDICADORES (RENOMBRADO)
# ══════════════════════════════════════════════
with tab_mapa_ind:

    opciones_ind = [v for v in MAPA_IND_PERMITIDAS if v in VARIABLES_LIST]
    
    DEFAULT_VAR_MAPA_IND = "Empleo industrial cada 1.000 habitantes"
    _idx_map = opciones_ind.index(DEFAULT_VAR_MAPA_IND) if DEFAULT_VAR_MAPA_IND in opciones_ind else 0
    
    var_mapa = st.selectbox(
        "Variable",
        options=opciones_ind,
        index=_idx_map,
        key="sel_var_mapa",
    )

    rows_mapa = []
    for prov in PROVINCIAS_LIST:
        periods, values, _ = get_serie(prov, var_mapa)
        if periods and values:
            rows_mapa.append({"provincia": prov, "value": values[-1], "periodo": periods[-1]})

    if not rows_mapa:
        st.info(f"No hay datos disponibles para **{var_mapa}**.")
    else:
        df_mapa = pd.DataFrame(rows_mapa)
        periodo_label = df_mapa["periodo"].iloc[0] if not df_mapa.empty else ""

        with st.spinner("Cargando mapa..."):
            GEO = load_argentina_geojson()

        if GEO is None:
            st.error(
                "⚠️ No se encontró el archivo `data/provincias_ign.geojson`. "
                "Descargalo del IGN o de la URL que te pasé y ponelo en la carpeta `data/`."
            )
        else:
            title = f"<span style='font-family:Sora,sans-serif;font-size:13px;'>{var_mapa} · Mapa provincial ({periodo_label})</span>"

            kind = MAPA_IND_KIND.get(var_mapa, "int")

            fig, df_rank = build_map_and_rank(
                df_mapa[["provincia","value","periodo"]],
                GEO,
                title_text=title,
                color_scale="Blues",     # ✅ mismo look
                kind=kind,               # ✅ % solo cuando corresponde
                hover_simple=True,       # ✅ Provincia + valor (unidad correcta)
            )

            with st.container(border=True):
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False},
                )

            st.markdown(
                '<div style="font-family:\'Sora\',sans-serif;font-size:0.9rem;font-weight:600;'
                'color:#1B2D6B;margin:1.2rem 0 0.5rem 0;">Ranking por provincia</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(df_rank, use_container_width=True, hide_index=False)

    st.markdown(
        '<div style="text-align:center;font-family:\'DM Mono\',monospace;font-size:0.7rem;'
        'color:#aab0c0;letter-spacing:0.05em;margin-top:2rem;">'
        'CEU – Centro de Estudios UIA · Unión Industrial Argentina · 2026</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════
# TAB 4 — EVOLUCIÓN DE VARIABLES (AL FINAL)
# ══════════════════════════════════════════════
with tab_evol:

    col_var_comp, col_provs_comp = st.columns([1, 2], gap="medium")

    # =========================
    # DEFAULTS DEL TAB EVOL
    # =========================
    DEFAULT_VAR_EVOL = "Cantidad de empresas"   # 👈 AJUSTÁ si en tu Excel se llama distinto
    DEFAULT_PROVS_EVOL = ["Córdoba", "Santa Fe"]

    # -------- Variable (selectbox)
    with col_var_comp:
        # si existe la variable default, la usamos; si no, caemos a la primera
        _idx_var = VARIABLES_EVO.index(DEFAULT_VAR_EVOL) if DEFAULT_VAR_EVOL in VARIABLES_EVO else 0

        var_comp = st.selectbox(
            "Variable",
            options=VARIABLES_EVO,
            index=_idx_var,
            key="sel_var_comp",
        )

    # -------- Provincias (multiselect)
    with col_provs_comp:
        # armamos defaults solo con las que existan en el Excel
        _default_provs = [p for p in DEFAULT_PROVS_EVOL if p in PROVINCIAS_LIST]
        if not _default_provs:
            _default_provs = PROVINCIAS_LIST[:1] if PROVINCIAS_LIST else []

        seleccionadas = st.multiselect(
            "Provincias (hasta 4)",
            options=PROVINCIAS_LIST,
            default=_default_provs,
            key="sel_provs_comp",
        )

    # Guards
    if len(seleccionadas) < 1:
        st.info("Seleccioná al menos 1 provincia.")
        st.stop()
    if len(seleccionadas) > 4:
        st.warning("Máximo 4 provincias. Sacá alguna de la selección.")
        st.stop()

    # 1) Gráfico principal (línea)
    with st.container(border=True):
        st.plotly_chart(
            fig_comp_linea(seleccionadas, var_comp),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    # ... (desde acá seguí con tu código actual de tabla, etc.)
    # 2) Tabla con los datos que alimentan el gráfico
    #    (filas = período, columnas = provincias)
    rows = []
    for pname in seleccionadas:
        periods, values, _ = get_serie(pname, var_comp)
        if periods and values:
            for p, v in zip(periods, values):
                rows.append({"Período": p, "Provincia": pname, "Valor": v})

    if not rows:
        st.info("No hay datos para mostrar en la tabla con esta selección.")
    else:
        df_long = pd.DataFrame(rows)

        # Intento de ordenamiento temporal (si existe period_num)
        # (en anual/trim/art ya viene ordenado en get_serie, pero esto evita mezclas)
        # Pivot a formato ancho
        df_wide = df_long.pivot_table(
            index="Período",
            columns="Provincia",
            values="Valor",
            aggfunc="first"
        ).reset_index()

        # Formateo “suave” para visual (no rompe el dato)
        # - ART suele ser % ya (ej 3.4). Si querés otro formato, lo ajustamos.
        def _fmt_cell(x):
            if x is None or pd.isna(x):
                return "—"
            # si parece entero grande, lo muestro como entero
            try:
                xf = float(x)
            except:
                return str(x)
            if abs(xf) >= 1000:
                return fmt_int_es(xf)
            # si es decimal “normal”
            return f"{xf:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        df_show = df_wide.copy()
        for c in df_show.columns:
            if c != "Período":
                df_show[c] = df_show[c].apply(_fmt_cell)

        st.markdown(
            '<div style="font-family:\'Sora\',sans-serif;font-size:0.95rem;font-weight:700;'
            'color:#1B2D6B;margin:1.0rem 0 0.5rem 0;">Tabla de datos</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(df_show, use_container_width=True, hide_index=True)

    st.markdown(
        '<div style="text-align:center;font-family:\'DM Mono\',monospace;font-size:0.7rem;'
        'color:#aab0c0;letter-spacing:0.05em;margin-top:2rem;">'
        'CEU – Centro de Estudios UIA · Unión Industrial Argentina · 2026</div>',
        unsafe_allow_html=True,
    )
