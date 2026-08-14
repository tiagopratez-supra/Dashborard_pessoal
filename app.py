# =============================================================================
# Análise Gerencial — GRUPO PRESERVAR
# Stack: Streamlit · pyodbc · pandas · plotly
# Banco: COLEFAR  |  Views: vw_DRE_Gerencial, vw_PlanoContas_DRE
# =============================================================================

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import pyodbc
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import base64, os, warnings

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONFIG DA PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Análise Gerencial · Grupo Preservar",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Paleta Colefar ───────────────────────────
VERDE_ESCURO  = "#1A3A1A"
VERDE_MEDIO   = "#2E6B10"
VERDE_LIMA    = "#7AB830"
VERDE_CLARO   = "#B8D98A"
VERDE_BG      = "#F2F7EC"
BRANCO        = "#FFFFFF"
CINZA_TEXT    = "#4A5568"
CINZA_BORDA   = "#D4E0C8"
DARK          = "#1A2A1A"
VERMELHO      = "#C0392B"
LARANJA       = "#E67E22"
AZUL_INFO     = "#2471A3"

CORES_GRAF = [VERDE_ESCURO, VERDE_LIMA, VERDE_MEDIO, LARANJA, AZUL_INFO,
              "#8E44AD", "#16A085", "#F39C12", VERMELHO, "#1ABC9C"]

EMPRESA_TEMAS = {
    "colefar": {"sb_top": "#1A3A1A", "sb_bot": "#0D220D", "accent": "#7AB830", "accent_l": "#B8D98A", "bg": "#F2F7EC", "logo": "logo_colefar.png", "grad": "#1A3A1A,#7AB830,#B8D98A"},
    "ambientec": {"sb_top": "#0A3D2E", "sb_bot": "#051F17", "accent": "#1BAA80", "accent_l": "#80D4B8", "bg": "#EEF8F4", "logo": "logo_ambientec.png", "grad": "#0A3D2E,#1BAA80,#80D4B8"},
    "biocoletas": {"sb_top": "#2D5016", "sb_bot": "#162808", "accent": "#80BA30", "accent_l": "#C0DFA0", "bg": "#F3F8EC", "logo": "logo_biocoletas.png", "grad": "#2D5016,#80BA30,#C0DFA0"},
    "colemax": {"sb_top": "#0D2B5E", "sb_bot": "#061527", "accent": "#3A7EC8", "accent_l": "#A0C8E8", "bg": "#EDF3FB", "logo": "logo_colemax.png", "grad": "#0D2B5E,#3A7EC8,#A0C8E8"},
    "colenorte": {"sb_top": "#5E3A0D", "sb_bot": "#2E1C06", "accent": "#D4891A", "accent_l": "#F0C878", "bg": "#FBF5EC", "logo": "logo_colenorte.png", "grad": "#5E3A0D,#D4891A,#F0C878"},
}
TEMA_MULTI = {"sb_top": "#1A2535", "sb_bot": "#0D1520", "accent": "#4A9DB5", "accent_l": "#A0CDD8", "bg": "#F2F5F9", "logo": "logo_colefar.png", "grad": "#1A2535,#4A9DB5,#A0CDD8"}

def get_tema(empresas_sel: list) -> dict:
    if len(empresas_sel) == 1:
        return EMPRESA_TEMAS.get(empresas_sel[0].lower(), TEMA_MULTI)
    return TEMA_MULTI

def inject_tema_css(tema: dict):
    a, al = tema["accent"], tema["accent_l"]
    st.markdown(f"""
    <style>
    section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {tema['sb_top']} 0%, {tema['sb_bot']} 100%) !important; }}
    section[data-testid="stSidebar"] [data-baseweb="tag"] {{ background: {a}88 !important; border: 1px solid {a}CC !important; }}
    section[data-testid="stSidebar"] .stButton button {{ background: {a}99 !important; }}
    section[data-testid="stSidebar"] .stButton button:hover {{ background: {a} !important; }}
    .stApp {{ background: {tema['bg']} !important; }}
    .sec-label {{ color: {a} !important; border-left-color: {al} !important; }}
    .chart-title {{ border-bottom-color: {al} !important; }}
    .dre-cat td {{ background: {al}55 !important; color: {tema['sb_top']} !important; border-top-color: {a} !important; }}
    .dre-total td {{ background: {tema['sb_top']} !important; }}
    </style>
    """, unsafe_allow_html=True)

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
  * {{ font-family: 'Inter', sans-serif !important; }}
  .stApp {{ background: {VERDE_BG} !important; }}
  .block-container {{ padding: 0.5rem 1.6rem 2rem !important; max-width: 100% !important; }}
  header[data-testid="stHeader"] {{ background: transparent !important; }}
  section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {VERDE_ESCURO} 0%, #0D220D 100%) !important; border-right: none !important; }}
  section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span {{ color: {BRANCO} !important; }}
  
  .kpi-card {{ background: {BRANCO}; border-radius: 14px; padding: 12px 10px 12px; box-shadow: 0 2px 12px rgba(26,58,26,0.08); border: 1px solid {CINZA_BORDA}; position: relative; overflow: hidden; min-height: 110px; }}
  .kpi-top-bar {{ position: absolute; top: 0; left: 0; right: 0; height: 3px; border-radius: 14px 14px 0 0; }}
  .kpi-icon {{ position: absolute; right: 10px; top: 10px; font-size: 1.4rem; opacity: 0.08; }}
  .kpi-label {{ font-size: 0.62rem; font-weight: 700; letter-spacing: 0.7px; text-transform: uppercase; color: {CINZA_TEXT}; margin-bottom: 6px; }}
  .kpi-val {{ font-size: clamp(1.1rem, 1.3vw, 1.45rem); font-weight: 800; color: {DARK}; line-height: 1; white-space: nowrap; letter-spacing: -0.5px; }}
  .kpi-badge {{ display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 0.62rem; font-weight: 700; margin-top: 5px; }}
  .b-green  {{ background: #D6EEC0; color: #2E6B10; }}
  .b-red    {{ background: #FDECEA; color: #C0392B; }}
  .b-blue   {{ background: #D6EAF8; color: #1A5276; }}
  .b-gray   {{ background: #EAECEE; color: #616A6B; }}
  .b-lime   {{ background: #E9F7D5; color: #4A7C1A; }}

  .chart-card {{ background: {BRANCO}; border-radius: 14px; padding: 16px 16px 8px; border: 1px solid {CINZA_BORDA}; box-shadow: 0 2px 10px rgba(26,58,26,0.06); margin-bottom: 14px; }}
  .chart-title {{ font-size: 0.69rem; font-weight: 700; color: {CINZA_TEXT}; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid {CINZA_BORDA}; padding-bottom: 8px; margin-bottom: 10px; }}
  .sec-label {{ font-size: 0.67rem; font-weight: 700; color: {VERDE_MEDIO}; text-transform: uppercase; letter-spacing: 0.8px; border-left: 3px solid {VERDE_LIMA}; padding-left: 9px; margin: 18px 0 12px; display: block; }}

  .dre-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  .dre-table th {{ background: {VERDE_ESCURO}; color: white; padding: 8px 12px; text-align: right; font-weight: 600; white-space: nowrap; }}
  .dre-table th:first-child {{ text-align: left; }}
  .dre-table td {{ padding: 6px 12px; border-bottom: 1px solid {CINZA_BORDA}; text-align: right; }}
  .dre-table td:first-child {{ text-align: left; color: {DARK}; font-weight: 500; }}
  .dre-cat td {{ background: #E8F3DA; font-weight: 700; color: {VERDE_ESCURO}; border-top: 2px solid {VERDE_LIMA}; }}
  .dre-total td {{ background: {VERDE_ESCURO}; color: white !important; font-weight: 800; font-size: 13px; }}
  .dre-sub td {{ padding-left: 28px !important; color: {CINZA_TEXT}; font-size: 12px; }}
  .pos {{ color: {VERDE_MEDIO}; font-weight: 600; }}
  .neg {{ color: {VERMELHO}; font-weight: 600; }}
</style>
""", unsafe_allow_html=True)

DB_CONFIG = {
    "server":             "colefar.defenseti.com.br,1433",
    "database":           "sgc",
    "trusted_connection": False,
    "username":           "ops",
    "password":           "Suporte2022=Mais",
}

def _detect_odbc_driver() -> str:
    drivers = pyodbc.drivers()
    for d in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0", "SQL Server"]:
        if d in drivers:
            return d
    return "ODBC Driver 17 for SQL Server"

def _build_conn_str():
    c = DB_CONFIG
    driver = _detect_odbc_driver()
    extras = "TrustServerCertificate=yes;Encrypt=yes;Connect Timeout=15;"
    return f"DRIVER={{{driver}}};SERVER={c['server']};DATABASE={c['database']};UID={c['username']};PWD={c['password']};{extras}"

def _pick(cols, candidates):
    low = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in low:
            return low[cand.lower()]
    return None

@st.cache_data(ttl=300, show_spinner="Carregando dados do banco…")
def carregar_dre(regime: str):
    if regime == "Competência":
        view_name = "vw_DRE_Consolidado_Competencia"
    else:
        view_name = "vw_DRE_Consolidado"

    conn = pyodbc.connect(_build_conn_str(), timeout=30)
    df_g = pd.read_sql(f"SELECT * FROM {view_name}", conn)
    cols_g = list(df_g.columns)

    c_data = _pick(cols_g, ["Data","DataLancamento","DataMovimento","DataEmissao","Competencia","DT_LANCAMENTO","dt_data"])
    df_g = df_g.rename(columns={c_data: "Data"})
    df_g["Data"] = pd.to_datetime(df_g["Data"], errors="coerce", dayfirst=True)
    df_g = df_g[df_g["Data"].dt.year >= 2020]

    c_val = _pick(cols_g, ["Valor","VlLancamento","ValorLancamento","Vlr","VlMovimento","VALOR","vl_valor","Vl_Total"])
    df_g = df_g.rename(columns={c_val: "Valor"})
    df_g["Valor"] = pd.to_numeric(df_g["Valor"], errors="coerce").fillna(0)

    # Captura a origem da consulta se existir na view
    c_origem = _pick(cols_g, ["OrigemConsulta", "origem_consulta", "Consulta"])
    if c_origem:
        df_g = df_g.rename(columns={c_origem: "OrigemConsulta"})
    else:
        df_g["OrigemConsulta"] = "Não Informada"

    cols_apos_rename = list(df_g.columns)
    c_cat_g = _pick(cols_apos_rename, ["CategoriaDRE","Categoria","GrupoDRE","Grupo","CAT_DRE","Tipo","ClassificacaoDRE"])
    c_sub_g = _pick(cols_apos_rename, ["SubcategoriaDRE","Subcategoria","SubGrupo","SUB_CATEGORIA","SubTipo"])
    c_nom_g = _pick(cols_apos_rename, ["NomeConta","Nome","Descricao","DescricaoConta","Conta","NOME_CONTA","DS_CONTA","nm_conta"])

    precisa_join = (c_cat_g is None)

    if precisa_join:
        df_p = pd.read_sql("SELECT * FROM vw_PlanoContas_DRE", conn)
        cols_p = list(df_p.columns)
        c_cod_g = _pick(cols_apos_rename, ["CodContaDRE","CodigoConta","Codigo","CodConta","COD_CONTA","cd_conta"])
        c_cod_p = _pick(cols_p, ["codigo","Codigo","CodConta","CodigoConta","COD_CONTA","ID","cd_conta"])
        c_cat_p = _pick(cols_p, ["CategoriaDRE","Categoria","GrupoDRE","Grupo","CAT_DRE","Tipo","ClassificacaoDRE"])
        c_sub_p = _pick(cols_p, ["SubcategoriaDRE","Subcategoria","SubGrupo","SUB_CATEGORIA","SubTipo"])
        c_nom_p = _pick(cols_p, ["NomeConta","Nome","Descricao","DescricaoConta","Conta","NOME_CONTA","DS_CONTA","nm_conta"])
        c_ord_p = _pick(cols_p, ["OrdemDRE","Ordem","Sequencia","Seq","ORD_DRE"])

        rp = {}
        if c_cod_p: rp[c_cod_p] = "CodContaDRE"
        if c_nom_p: rp[c_nom_p] = "NomeConta"
        if c_cat_p: rp[c_cat_p] = "CategoriaDRE"
        if c_sub_p: rp[c_sub_p] = "SubcategoriaDRE"
        if c_ord_p: rp[c_ord_p] = "OrdemDRE"
        df_p = df_p.rename(columns=rp)
        for col in ["NomeConta","CategoriaDRE","SubcategoriaDRE","OrdemDRE"]:
            if col not in df_p.columns: df_p[col] = ""

        if c_cod_g: df_g = df_g.rename(columns={c_cod_g: "CodContaDRE"})

        if "CodContaDRE" in df_g.columns and "CodContaDRE" in df_p.columns:
            merge_cols = ["CodContaDRE","NomeConta","CategoriaDRE","SubcategoriaDRE","OrdemDRE"]
            df = df_g.merge(df_p[merge_cols].drop_duplicates("CodContaDRE"), on="CodContaDRE", how="left")
        else:
            df = df_g.copy()
            for col in ["NomeConta","CategoriaDRE","SubcategoriaDRE","OrdemDRE"]: df[col] = ""
    else:
        conn.close()
        rg = {}
        if c_cat_g and c_cat_g != "CategoriaDRE": rg[c_cat_g] = "CategoriaDRE"
        if c_sub_g and c_sub_g != "SubcategoriaDRE": rg[c_sub_g] = "SubcategoriaDRE"
        if c_nom_g and c_nom_g != "NomeConta": rg[c_nom_g] = "NomeConta"
        df = df_g.rename(columns=rg)
        for col in ["NomeConta","CategoriaDRE","SubcategoriaDRE","OrdemDRE"]:
            if col not in df.columns: df[col] = ""

    try:
        conn.close()
    except Exception:
        pass

    cols_final = list(df.columns)
    c_emp = _pick(cols_final, ["Empresa","empresa","NomeEmpresa","Company"])
    if c_emp and c_emp != "Empresa": df = df.rename(columns={c_emp: "Empresa"})
    if "Empresa" not in df.columns: df["Empresa"] = "Colefar"

    df["Ano"] = df["Data"].dt.year.astype("Int64")
    df["Mes"] = df["Data"].dt.month.astype("Int64")

    ano_atual = datetime.now().year
    df = df[(df["Ano"] >= 2000) & (df["Ano"] <= ano_atual)].copy()

    df["ValorAbsoluto"] = df["Valor"].abs()
    df["MesAno"] = df["Data"].dt.strftime("%m/%Y")
    df["MesAnoSort"] = df["Ano"].astype(int) * 100 + df["Mes"].astype(int)
    df["CategoriaDRE"] = df["CategoriaDRE"].fillna("").str.strip().str.upper()
    df["SubcategoriaDRE"] = df["SubcategoriaDRE"].fillna("").str.strip()
    df["NomeConta"] = df["NomeConta"].fillna("").str.strip()
    df["OrigemConsulta"] = df["OrigemConsulta"].fillna("").str.strip()

    return df

def fmt_brl(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    neg = v < 0
    s = f"R$ {abs(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    return f"-{s}" if neg else s

def pct_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    return f"{v:+.1f}%"

def calcular_indicadores(df: pd.DataFrame) -> dict:
    if "CategoriaDRE" not in df.columns or df.empty:
        return {"rec_bruta":0,"deducoes":0,"rec_liq":0,"csp":0,"luc_bruto":0,
                "desp_op":0,"ebitda":0,"res_fin":0,"lair":0,"impostos":0,
                "luc_liq":0,"mg_bruta":0,"mg_ebitda":0,"mg_liq":0}

    cat = df["CategoriaDRE"].str.upper()
    def soma(keyword):
        mask = cat.str.contains(keyword, na=False)
        return df.loc[mask, "Valor"].sum()

    rec_bruta = soma("RECEITA BRUTA")
    deducoes  = soma("DEDU")
    csp       = soma("CUSTO|CMV")
    desp_op   = soma("DESPESAS OPERACION|DESPESAS NÃO OPERACION")
    res_fin   = soma("FINANC|OUTRAS RECEITAS")
    impostos  = soma("IR E CSL|IMPOSTO")

    rec_liq   = rec_bruta + deducoes
    luc_bruto = rec_liq + csp
    ebitda    = luc_bruto + desp_op
    lair      = ebitda + res_fin
    luc_liq   = lair + impostos

    def marg(n, d): return (n / d * 100) if d != 0 else 0.0

    return {
        "rec_bruta": rec_bruta, "deducoes": deducoes, "rec_liq": rec_liq,
        "csp": csp, "luc_bruto": luc_bruto, "desp_op": desp_op,
        "ebitda": ebitda, "res_fin": res_fin, "lair": lair,
        "impostos": impostos, "luc_liq": luc_liq,
        "mg_bruta":  marg(luc_bruto, rec_bruta),
        "mg_ebitda": marg(ebitda,    rec_bruta),
        "mg_liq":    marg(luc_liq,   rec_bruta),
    }

def kpi_card(label, valor, badge="", badge_cls="b-gray", icon="📌", cor=None):
    cor = cor or VERDE_ESCURO
    b = f'<span class="kpi-badge {badge_cls}">{badge}</span>' if badge else ""
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-top-bar" style="background:{cor}"></div>
      <div class="kpi-icon">{icon}</div>
      <div class="kpi-label">{label}</div>
      <div class="kpi-val">{valor}</div>
      {b}
    </div>""", unsafe_allow_html=True)

def lp(h=320):
    return dict(height=h, margin=dict(t=10,b=0,l=5,r=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", size=11))

def img_base64(path):
    try:
        with open(path, "rb") as f: return base64.b64encode(f.read()).decode()
    except Exception: return None

def _render_header(tema: dict, empresas_sel: list, regime: str):
    logos_dir = os.path.join(os.path.dirname(__file__), "logos")
    if len(empresas_sel) == 1:
        logo_file = EMPRESA_TEMAS.get(empresas_sel[0].lower(), TEMA_MULTI)["logo"]
        b64 = img_base64(os.path.join(logos_dir, logo_file))
        logos_html = f'<img src="data:image/png;base64,{b64}" style="height:52px;object-fit:contain;">' if b64 else f'<span style="font-size:1.5rem;font-weight:900;color:{tema["sb_top"]}">{empresas_sel[0]}</span>'
        subtitulo = empresas_sel[0]
    else:
        imgs = []
        for emp in empresas_sel:
            t = EMPRESA_TEMAS.get(emp.lower(), TEMA_MULTI)
            b64 = img_base64(os.path.join(logos_dir, t["logo"]))
            if b64: imgs.append(f'<img src="data:image/png;base64,{b64}" style="height:38px;object-fit:contain;margin:0 4px;">')
            else: imgs.append(f'<span style="font-size:0.9rem;font-weight:700;color:{t["sb_top"]};margin:0 4px;">{emp}</span>')
        logos_html = f'<div style="display:flex;align-items:center;gap:2px;flex-wrap:wrap;">' + "".join(imgs) + "</div>"
        subtitulo = "Consolidado · " + " · ".join(empresas_sel)

    cor_badge = AZUL_INFO if regime == "Competência" else LARANJA
    badge_html = f"<span style='background:{cor_badge}; color:white; padding: 3px 10px; border-radius: 12px; font-size: 0.65rem; font-weight: 700; margin-left: 12px; vertical-align: middle; letter-spacing: 0.5px;'>REGIME DE {regime.upper()}</span>"
    grad = tema["grad"]

    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0 6px;">
      <div style="display:flex;align-items:center;gap:16px;">
        {logos_html}
        <div style="border-left:2px solid {CINZA_BORDA};padding-left:16px;">
          <div style="font-size:1.25rem;font-weight:800;color:{tema['sb_top']};line-height:1.1; display: flex; align-items: center;">Análise Gerencial {badge_html}</div>
          <div style="font-size:0.74rem;color:{CINZA_TEXT};margin-top:2px;">{subtitulo}</div>
        </div>
      </div>
      <div style="font-size:0.72rem;color:{CINZA_TEXT};text-align:right;">🕒 Atualizado em<br><strong>{datetime.now().strftime('%d/%m/%Y %H:%M')}</strong></div>
    </div>
    <div style="height:3px;background:linear-gradient(90deg,{grad});border-radius:2px;margin-bottom:14px;"></div>
    """, unsafe_allow_html=True)

def _render_sidebar_logo(_, tema: dict, empresas_sel: list, logos_dir: str = ""):
    if not logos_dir: logos_dir = os.path.join(os.path.dirname(__file__), "logos")
    st.markdown(f"""
    <style>
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div, section[data-testid="stSidebar"] > div > div, section[data-testid="stSidebar"] > div > div > div {{
        background: linear-gradient(180deg, {tema['sb_top']} 0%, {tema['sb_bot']} 100%) !important;
    }}
    </style>
    """, unsafe_allow_html=True)
    st.sidebar.markdown(
        "<div style='text-align:center;padding:18px 0 4px;'><span style='font-size:1.1rem;font-weight:900;letter-spacing:0.5px;color:white;'>GRUPO PRESERVAR</span></div>"
        "<div style='text-align:center;font-size:0.65rem;color:rgba(255,255,255,0.45);padding:2px 0 10px;'>Análise Gerencial</div>"
        "<hr style='border-color:rgba(255,255,255,0.1);margin:0 0 14px;'>",
        unsafe_allow_html=True,
    )

def main():
    empresas_prev = st.session_state.get("empresas_sel", [])
    tema_prev = get_tema(empresas_prev)
    _render_sidebar_logo(None, tema_prev, empresas_prev)

    st.sidebar.markdown("<div style='font-size:0.65rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:rgba(255,255,255,0.45);padding:4px 0 6px;'>NAVEGAÇÃO</div>", unsafe_allow_html=True)
    
    pagina = st.sidebar.radio(
        "Página",
        ["📊 Visão Geral", "📋 DRE Completa", "💰 Análise de Custos", "📅 Comparativo Anual", "🔍 Auditoria"],
        label_visibility="collapsed",
    )
    st.sidebar.markdown("<hr style='border-color:rgba(255,255,255,0.1);margin:14px 0;'>", unsafe_allow_html=True)

    st.sidebar.markdown("<div style='font-size:0.65rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:rgba(255,255,255,0.45);padding:4px 0 6px;'>FILTROS</div>", unsafe_allow_html=True)
    regime_sel = st.sidebar.radio("Regime Contábil", ["Competência", "Caixa"], index=0, horizontal=True)

    try:
        df_raw = carregar_dre(regime_sel)
    except Exception as e:
        st.error(f"❌ **Erro ao carregar dados.** Detalhe: `{e}`")
        st.stop()

    if df_raw.empty:
        st.warning("⚠️ O banco não retornou registros.")
        st.stop()

    empresas_disp = sorted(df_raw["Empresa"].dropna().unique().tolist())
    empresas_sel = st.sidebar.multiselect("Empresa(s)", empresas_disp, default=empresas_prev if empresas_prev else empresas_disp, placeholder="Todas as empresas")
    if not empresas_sel: empresas_sel = empresas_disp
    st.session_state["empresas_sel"] = empresas_sel
    df_raw = df_raw[df_raw["Empresa"].isin(empresas_sel)]

    tema = get_tema(empresas_sel)
    inject_tema_css(tema)
    _render_header(tema, empresas_sel, regime_sel)

    anos_disp = sorted(df_raw["Ano"].dropna().unique().astype(int), reverse=True)
    anos_sel  = st.sidebar.multiselect("Ano(s) — máx. 3", anos_disp, default=[anos_disp[0]], placeholder="Selecione até 3 anos")
    if not anos_sel: anos_sel = [anos_disp[0]]
    if len(anos_sel) > 3: anos_sel = anos_sel[:3]
    anos_sel = sorted(anos_sel, reverse=True)
    ano_principal = anos_sel[0]

    nomes_mes  = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}
    meses_disp = sorted(df_raw[df_raw["Ano"].astype(int) == ano_principal]["Mes"].dropna().astype(int).unique())
    opts_mes = [f"{m:02d} – {nomes_mes[m]}" for m in meses_disp]

    hoje = date.today()
    mes_str = f"{hoje.month:02d} – {nomes_mes[hoje.month]}"
    default = [mes_str] if mes_str in opts_mes else (opts_mes[-1:] if opts_mes else [])
    sel_str = st.sidebar.multiselect("Mês(es)", opts_mes, default=default, placeholder="Todos os meses")
    sel_num = [int(m[:2]) for m in sel_str] if sel_str else meses_disp

    df = df_raw[(df_raw["Ano"].astype(int).isin(anos_sel)) & (df_raw["Mes"].astype(int).isin(sel_num))].copy()
    df_principal = df[df["Ano"].astype(int) == ano_principal].copy()

    m_ref = min(sel_num) if sel_num else 1
    ano_m_ant = ano_principal if m_ref > 1 else ano_principal - 1
    mes_m_ant = m_ref - 1 if m_ref > 1 else 12
    df_mant = df_raw[(df_raw["Ano"].astype(int) == ano_m_ant) & (df_raw["Mes"].astype(int) == mes_m_ant)]
    df_ant = df_raw[(df_raw["Ano"].astype(int) == ano_principal - 1) & (df_raw["Mes"].astype(int).isin(sel_num))].copy()

    if st.sidebar.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    ind_por_ano = {a: calcular_indicadores(df_raw[(df_raw["Ano"].astype(int) == a) & (df_raw["Mes"].astype(int).isin(sel_num))]) for a in anos_sel}
    ind = ind_por_ano[ano_principal]
    ind_ant = calcular_indicadores(df_mant)
    ind_total = calcular_indicadores(df)

    def mom(key):
        c, p = ind[key], ind_ant.get(key, 0)
        if p == 0: return None, "b-gray"
        pct = (c - p) / abs(p) * 100
        return pct, "b-green" if pct >= 0 else "b-red"

    # ══════════════════════════════════════════
    # PÁGINAS PRINCIPAIS (Visão Geral, DRE Completa, Custos, Comparativo)
    # ══════════════════════════════════════════
    if pagina == "📊 Visão Geral":
        if len(anos_sel) == 1:
            st.markdown('<span class="sec-label">Indicadores do Período</span>', unsafe_allow_html=True)
            c1,c2,c3,c4,c5,c6 = st.columns(6)
            with c1:
                p,cls = mom("rec_bruta")
                kpi_card("Receita Bruta", fmt_brl(ind["rec_bruta"]), pct_str(p)+" MoM" if p else "", cls, "💰", VERDE_ESCURO)
            with c2:
                p,cls = mom("rec_liq")
                kpi_card("Receita Líquida", fmt_brl(ind["rec_liq"]), pct_str(p)+" MoM" if p else "", cls, "📉", VERDE_MEDIO)
            with c3:
                p,cls = mom("luc_bruto")
                kpi_card("Lucro Bruto", fmt_brl(ind["luc_bruto"]), pct_str(p)+" MoM" if p else "", cls, "📈", VERDE_LIMA if ind["luc_bruto"] >= 0 else VERMELHO)
            with c4:
                kpi_card("EBITDA", fmt_brl(ind["ebitda"]), f"{ind['mg_ebitda']:.1f}% Margem", "b-lime", "⚡", VERDE_LIMA if ind["ebitda"] >= 0 else VERMELHO)
            with c5:
                kpi_card("Lucro Líquido", fmt_brl(ind["luc_liq"]), f"{ind['mg_liq']:.1f}% Margem", "b-green" if ind["luc_liq"] >= 0 else "b-red", "🏆", VERDE_MEDIO if ind["luc_liq"] >= 0 else VERMELHO)
            with c6:
                kpi_card("Margem Bruta", f"{ind['mg_bruta']:.1f}%", "% s/ Rec. Bruta", "b-blue", "🎯", AZUL_INFO)

        # ── Evolução / Composição / Receita vs Despesas ──
        col_l, col_r = st.columns([3, 2])
        with col_l:
            if len(anos_sel) == 1:
                titulo_evo = "📈 Evolução Mensal — Receita · EBITDA · Lucro"
                df_evo = df_raw[df_raw["Ano"].astype(int) == ano_principal].copy()
                mesano_map = df_evo.drop_duplicates("MesAnoSort").sort_values("MesAnoSort").set_index("MesAnoSort")["MesAno"].to_dict()
                ordem_sort = sorted(mesano_map)
                rows_evo = []
                for sk in ordem_sort:
                    sub = df_evo[df_evo["MesAnoSort"] == sk]
                    i = calcular_indicadores(sub)
                    rows_evo.append({"MesAno": mesano_map[sk], "Receita Bruta": i["rec_bruta"], "EBITDA": i["ebitda"], "Lucro Líquido": i["luc_liq"]})
                df_ep = pd.DataFrame(rows_evo)
                st.markdown(f'<div class="chart-card"><div class="chart-title">{titulo_evo}</div>', unsafe_allow_html=True)
                if not df_ep.empty:
                    fig = go.Figure()
                    for name, cor, dash in [("Receita Bruta", VERDE_ESCURO, "solid"), ("EBITDA", VERDE_LIMA, "dot"), ("Lucro Líquido", LARANJA, "dash")]:
                        fig.add_trace(go.Scatter(x=df_ep["MesAno"], y=df_ep[name], name=name, mode="lines+markers", line=dict(color=cor, width=2.5, dash=dash), marker=dict(size=6), hovertemplate="%{x}<br><b>%{customdata}</b><extra></extra>", customdata=[fmt_brl(v) for v in df_ep[name]]))
                    fig.update_layout(**lp(300), xaxis=dict(type="category", categoryorder="array", categoryarray=[mesano_map[s] for s in ordem_sort]), yaxis=dict(tickformat=",.0f"), legend=dict(orientation="h", y=1.05, x=1, xanchor="right"), hovermode="x unified")
                    st.plotly_chart(fig, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

        with col_r:
            ind_comp = ind_total if len(anos_sel) > 1 else ind
            st.markdown('<div class="chart-card"><div class="chart-title">🥧 Composição</div>', unsafe_allow_html=True)
            comp = {"Categoria": ["Rec. Bruta","Deduções","CSP","Desp. Op.","Res. Fin.","Impostos"], "Valor": [abs(ind_comp["rec_bruta"]), abs(ind_comp["deducoes"]), abs(ind_comp["csp"]), abs(ind_comp["desp_op"]), abs(ind_comp["res_fin"]), abs(ind_comp["impostos"])]}
            df_c = pd.DataFrame(comp)
            if df_c["Valor"].sum() > 0:
                fig = px.pie(df_c, names="Categoria", values="Valor", hole=0.52, color_discrete_sequence=CORES_GRAF)
                fig.update_traces(textposition="inside", textinfo="percent", textfont_size=11)
                fig.update_layout(**lp(270), legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center", font=dict(size=10)))
                st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # PÁG 5 — AUDITORIA (CONFERÊNCIA DIA A DIA COM ORIGEM DA CONSULTA)
    # ══════════════════════════════════════════
    elif pagina == "🔍 Auditoria":
        st.markdown('<span class="sec-label">Lançamentos Individuais — Auditoria & Comparação Dia a Dia</span>', unsafe_allow_html=True)

        if df.empty:
            st.info("Sem lançamentos para o período selecionado.")
        else:
            col_f1, col_f2, col_f3 = st.columns(3)
            cats_aud = ["Todas"] + sorted(df["CategoriaDRE"].dropna().unique().tolist())
            with col_f1:
                cat_aud = st.selectbox("Categoria DRE", cats_aud)
            subs_base = df if cat_aud == "Todas" else df[df["CategoriaDRE"] == cat_aud]
            subs_aud = ["Todas"] + sorted(subs_base["SubcategoriaDRE"].dropna().replace("", pd.NA).dropna().unique().tolist())
            with col_f2:
                sub_aud = st.selectbox("Subcategoria", subs_aud)
            with col_f3:
                busca = st.text_input("Filtrar por Consulta / Conta / Doc", placeholder="ex: 2.2.2 ou NFSe")

            df_aud = df.copy()
            if cat_aud != "Todas": df_aud = df_aud[df_aud["CategoriaDRE"] == cat_aud]
            if sub_aud != "Todas": df_aud = df_aud[df_aud["SubcategoriaDRE"] == sub_aud]
            if busca.strip():
                mask = df_aud["NomeConta"].str.contains(busca.strip(), case=False, na=False) | df_aud["OrigemConsulta"].str.contains(busca.strip(), case=False, na=False)
                df_aud = df_aud[mask]

            st.markdown("<br>", unsafe_allow_html=True)
            ind_aud = calcular_indicadores(df_aud)

            k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
            with k1: kpi_card("Receita Bruta", fmt_brl(ind_aud["rec_bruta"]), f"{len(df_aud):,} reg.", "b-lime", "💰", VERDE_ESCURO)
            with k2: kpi_card("Deduções", fmt_brl(ind_aud["deducoes"]), "", "b-gray", "📉", CINZA_TEXT)
            with k3: kpi_card("Receita Líquida", fmt_brl(ind_aud["rec_liq"]), "", "b-lime", "📊", VERDE_MEDIO)
            with k4: kpi_card("CSP", fmt_brl(ind_aud["csp"]), "", "b-red", "🔩", VERMELHO)
            with k5: kpi_card("Desp. Op.", fmt_brl(ind_aud["desp_op"]), "", "b-red", "🏢", LARANJA)
            with k6: kpi_card("EBITDA", fmt_brl(ind_aud["ebitda"]), f"{ind_aud['mg_ebitda']:.1f}%", "b-green" if ind_aud["ebitda"] >= 0 else "b-red", "⚡", VERDE_MEDIO)
            with k7: kpi_card("Lucro Líquido", fmt_brl(ind_aud["luc_liq"]), f"{ind_aud['mg_liq']:.1f}%", "b-green" if ind_aud["luc_liq"] >= 0 else "b-red", "🏆", VERDE_MEDIO if ind_aud["luc_liq"] >= 0 else VERMELHO)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="chart-card"><div class="chart-title">📄 Lançamentos Detalhados (Dia a Dia & Consulta no Banco)</div>', unsafe_allow_html=True)

            # Preparação da tabela de auditoria com coluna de Dia e Origem da Consulta
            df_show = df_aud[["Data", "OrigemConsulta", "CategoriaDRE", "SubcategoriaDRE", "NomeConta", "Valor"]].copy()
            df_show = df_show.sort_values("Data").reset_index(drop=True)
            
            # Criando explicitamente a coluna de Dia
            df_show["Dia"] = df_show["Data"].dt.day.astype(str).str.zfill(2)
            df_show["DataFmt"] = df_show["Data"].dt.strftime("%d/%m/%Y")
            df_show["ValorFmt"] = df_show["Valor"].apply(fmt_brl)

            # Reorganizando colunas para visualização ideal
            df_exib = df_show[["Dia", "DataFmt", "OrigemConsulta", "CategoriaDRE", "SubcategoriaDRE", "NomeConta", "ValorFmt"]].copy()
            df_exib.columns = ["Dia", "Data", "Consulta no Banco", "Categoria", "Subcategoria", "Conta / Documento", "Valor"]

            # Linha de total
            df_total = pd.DataFrame([{
                "Dia": "—",
                "Data": "TOTAL",
                "Consulta no Banco": "—",
                "Categoria": "",
                "Subcategoria": "",
                "Conta / Documento": f"{len(df_aud):,} registros",
                "Valor": fmt_brl(df_aud["Valor"].sum()),
            }])
            df_exib = pd.concat([df_exib, df_total], ignore_index=True)

            st.dataframe(df_exib, use_container_width=True, hide_index=True)

            # Botão de Exportação CSV
            csv = df_aud[["Data", "OrigemConsulta", "CategoriaDRE", "SubcategoriaDRE", "NomeConta", "Valor"]].copy()
            csv["Data"] = csv["Data"].dt.strftime("%d/%m/%Y")
            st.download_button(
                label="⬇️ Exportar Auditoria CSV",
                data=csv.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                file_name=f"auditoria_{regime_sel.lower()}_{ano_principal}.csv",
                mime="text/csv",
            )
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()