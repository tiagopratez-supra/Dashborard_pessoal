import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client
from datetime import datetime
import time
import os

# ==========================================
# 1. CONFIGURAÇÃO E TEMA CSS AVANÇADO
# ==========================================
st.set_page_config(page_title="Sistema Financeiro", page_icon="💸", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 0rem; max-width: 98%; }
    
    .kpi-card { 
        background-color: #1e1e2e; padding: 20px; border-radius: 12px; 
        border-left: 6px solid; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .kpi-title { color: #a6adc8; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;}
    .kpi-value { color: #cdd6f4; font-size: 32px; font-weight: 800; margin-top: 8px;}
    
    /* Micro-cards modernos para o topo */
    .micro-kpi { background-color: #1e1e2e; padding: 15px 20px; border-radius: 10px; border-left: 5px solid; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.2);}
    .micro-title { color: #a6adc8; font-size: 14px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;}
    .micro-value { color: #cdd6f4; font-size: 22px; font-weight: 900;}
    
    [data-testid="stToolbar"] {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

meses_pt = {1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 
            7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'}

# ==========================================
# 2. BANCO DE DADOS E INTELIGÊNCIA
# ==========================================
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["connections"]["supabase"]["url"]
        key = st.secrets["connections"]["supabase"]["key"]
    except Exception:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
    return create_client(url, key)

supabase = init_connection()

def carregar_dados():
    desp = pd.DataFrame(supabase.table("despesas").select("*").execute().data)
    rec = pd.DataFrame(supabase.table("receitas").select("*").execute().data)
    if not desp.empty:
        desp['status_clean'] = desp['status'].apply(lambda x: 'Pago' if 'pago' in str(x).lower() else 'Aberto')
        
        def categorizar(nome):
            n = str(nome).lower()
            if any(x in n for x in ['cartao', 'cartão', 'nubank', 'mp', 'inter', 'will']): return '💳 Cartões'
            if any(x in n for x in ['emprestimo', 'empréstimo', 'picpay', 'jeito']): return '🏦 Empréstimos'
            if any(x in n for x in ['internet', 'seguro', 'zelo', 'odete', 'recarga', 'streming', 'spotify', 'tv']): return '🏠 Despesas Fixas'
            if any(x in n for x in ['shoppe', 'shopee', 'mercado livre']): return '📦 Compras Online'
            if any(x in n for x in ['faculdade', 'escola', 'curso']): return '📚 Educação'
            if any(x in n for x in ['carro', 'ipva', 'mecânico', 'gasolina']): return '🚗 Veículo'
            if any(x in n for x in ['laje', 'pedreiro', 'faxina', 'sitio']): return '🧱 Manutenção/Imóvel'
            return '🛒 Outros'
            
        desp['categoria'] = desp['nome'].apply(categorizar)
    return desp, rec

def format_rs(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

despesas_df, receitas_df = carregar_dados()

if despesas_df.empty:
    st.error("Banco de dados vazio ou falha na conexão.")
    st.stop()

# ==========================================
# 3. SIDEBAR FIXA (MENU E FILTROS)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=70)
    st.title("Menu Principal")
    
    # MUDEI O NOME AQUI PARA FICAR MAIS AMIGÁVEL
    pagina = st.radio("Navegação:", ["📊 Painel Executivo", "🔮 Fluxo de Caixa Futuro", "📱 Lançamentos do Mês"])
    st.markdown("---")
    st.markdown("### 🔍 Filtros Globais")
    
    ano_atual = datetime.now().year
    anos_disp = sorted(despesas_df['ano'].unique().tolist(), reverse=True)
    idx_ano = anos_disp.index(ano_atual) if ano_atual in anos_disp else 0
    ano_sel = st.selectbox("Ano Fiscal", anos_disp, index=idx_ano)
    
    meses_disp = sorted(despesas_df[despesas_df['ano'] == ano_sel]['mes'].unique().tolist())
    if not meses_disp:
        st.warning("Sem dados para este ano.")
        st.stop()
        
    mes_atual = datetime.now().month
    if mes_atual in meses_disp and ano_sel == ano_atual:
        idx_mes = meses_disp.index(mes_atual)
    else:
        idx_mes = len(meses_disp) - 1 
        
    mes_sel = st.selectbox("Mês de Referência", [meses_pt[m] for m in meses_disp], index=idx_mes)
    mes_num = [k for k, v in meses_pt.items() if v == mes_sel][0]
    
    st.markdown("---")
    st.info("💡 Role a tela sem perder os filtros de vista.")

# --- APLICAÇÃO DOS FILTROS ---
df_mes = despesas_df[(despesas_df['ano'] == ano_sel) & (despesas_df['mes'] == mes_num)].copy()
rec_mes = receitas_df[(receitas_df['ano'] == ano_sel) & (receitas_df['mes'] == mes_num)]

# --- CÁLCULOS GLOBAIS ---
rec_tot = (rec_mes['tiago'].sum() + rec_mes['analia'].sum() + rec_mes['extra'].sum()) if not rec_mes.empty else 0
desp_tot = df_mes['valor'].sum() if not df_mes.empty else 0
desp_aberto = df_mes[df_mes['status_clean'] == 'Aberto']['valor'].sum() if not df_mes.empty else 0
saldo = rec_tot - desp_tot


# ==========================================
# 4. PÁGINAS DO SISTEMA
# ==========================================

# --- PÁGINA 1: PAINEL EXECUTIVO ---
if pagina == "📊 Painel Executivo":
    st.header(f"Resumo Financeiro • {mes_sel}/{ano_sel}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="kpi-card" style="border-color: #89b4fa;"><div class="kpi-title">Receitas Globais</div><div class="kpi-value">{format_rs(rec_tot)}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="kpi-card" style="border-color: #f9e2af;"><div class="kpi-title">Total de Despesas</div><div class="kpi-value">{format_rs(desp_tot)}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="kpi-card" style="border-color: #f38ba8;"><div class="kpi-title">Falta Pagar</div><div class="kpi-value">{format_rs(desp_aberto)}</div></div>', unsafe_allow_html=True)
    cor_saldo = "#a6e3a1" if saldo >= 0 else "#f38ba8"
    c4.markdown(f'<div class="kpi-card" style="border-color: {cor_saldo};"><div class="kpi-title">Saldo Projetado</div><div class="kpi-value" style="color: {cor_saldo};">{format_rs(saldo)}</div></div>', unsafe_allow_html=True)

    g1, g2 = st.columns([1, 1.5])
    with g1:
        st.subheader("Concentração de Gastos")
        if not df_mes.empty:
            df_grp = df_mes.groupby('categoria')['valor'].sum().reset_index()
            fig_donut = px.pie(df_grp, values='valor', names='categoria', hole=0.55)
            fig_donut.update_traces(textposition='inside', textinfo='percent+label', textfont_size=12)
            fig_donut.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, margin=dict(t=20, b=0, l=0, r=0))
            st.plotly_chart(fig_donut, use_container_width=True)

    with g2:
        st.subheader("Despesas por Agrupamento")
        if not df_mes.empty:
            df_cat = df_mes.groupby(['categoria', 'status_clean'])['valor'].sum().reset_index()
            df_cat = df_cat.sort_values(by='valor', ascending=True)
            fig_bar = px.bar(df_cat, x='valor', y='categoria', color='status_clean', orientation='h', color_discrete_map={'Pago':'#a6e3a1', 'Aberto':'#f38ba8'}, text='valor')
            fig_bar.update_traces(texttemplate='R$ %{text:,.2f}', textposition='inside')
            fig_bar.update_layout(barmode='stack', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_title="", yaxis_title="", margin=dict(t=20, b=0, l=0, r=0), legend_title_text='Status', font=dict(color='#cdd6f4'))
            st.plotly_chart(fig_bar, use_container_width=True)

# --- PÁGINA 2: FLUXO DE CAIXA FUTURO ---
elif pagina == "🔮 Fluxo de Caixa Futuro":
    st.header("Projeção Financeira (Próximos 6 Meses)")
    
    dados_proj = []
    m_atual, a_atual = mes_num, ano_sel
    
    for i in range(6):
        mf, af = m_atual + i, a_atual
        if mf > 12: 
            mf -= 12
            af += 1
            
        rec_fut = receitas_df[(receitas_df['ano'] == af) & (receitas_df['mes'] == mf)]
        rf_tot = (rec_fut['tiago'].sum() + rec_fut['analia'].sum() + rec_fut['extra'].sum()) if not rec_fut.empty else rec_tot
        df_tot = despesas_df[(despesas_df['ano'] == af) & (despesas_df['mes'] == mf)]['valor'].sum()
        dados_proj.append({"Mês": f"{meses_pt[mf]}/{str(af)[-2:]}", "Receitas": rf_tot, "Despesas": df_tot, "Saldo": rf_tot - df_tot})
        
    df_proj = pd.DataFrame(dados_proj)
    fig_proj = go.Figure()
    fig_proj.add_trace(go.Bar(x=df_proj['Mês'], y=df_proj['Receitas'], name='Receitas', marker_color='#a6e3a1', text=df_proj['Receitas'], texttemplate='R$ %{text:,.0f}', textposition='inside'))
    fig_proj.add_trace(go.Bar(x=df_proj['Mês'], y=df_proj['Despesas'], name='Despesas', marker_color='#f38ba8', text=df_proj['Despesas'], texttemplate='R$ %{text:,.0f}', textposition='inside'))
    fig_proj.add_trace(go.Scatter(x=df_proj['Mês'], y=df_proj['Saldo'], name='Saldo', mode='lines+markers+text', line=dict(color='#89b4fa', width=3), text=df_proj['Saldo'], texttemplate='R$ %{text:,.0f}', textposition='top center'))
    fig_proj.update_layout(barmode='group', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#cdd6f4'), margin=dict(t=40, b=0, l=0, r=0))
    st.plotly_chart(fig_proj, use_container_width=True)


# --- PÁGINA 3: LAYOUT MODERNO DE GESTÃO ---
elif pagina == "📱 Lançamentos do Mês":
    
    st.header(f"Gestão do Mês • {mes_sel}/{ano_sel}")
    st.markdown("Bem-vindos! Aqui vocês controlam o dinheiro do mês de forma simples e rápida.")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 1. BARRA DE RESUMO (Ocupando toda a largura no topo)
    c_tot1, c_tot2, c_tot3 = st.columns(3)
    c_tot1.markdown(f'<div class="micro-kpi" style="border-color:#89b4fa;"><span class="micro-title">💰 Total de Receitas</span><span class="micro-value">{format_rs(rec_tot)}</span></div>', unsafe_allow_html=True)
    c_tot2.markdown(f'<div class="micro-kpi" style="border-color:#f9e2af;"><span class="micro-title">💸 Total de Despesas</span><span class="micro-value">{format_rs(desp_tot)}</span></div>', unsafe_allow_html=True)
    cor = "#a6e3a1" if saldo >= 0 else "#f38ba8"
    c_tot3.markdown(f'<div class="micro-kpi" style="border-color:{cor};"><span class="micro-title">⚖️ Sobra (Saldo)</span><span class="micro-value" style="color:{cor};">{format_rs(saldo)}</span></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 2. ABAS DE NAVEGAÇÃO (Interface de App)
    aba_despesas, aba_receitas, aba_ferramentas = st.tabs(["🛒 Lista de Contas", "💵 Atualizar Rendas", "⚙️ Ferramentas"])
    
    with aba_despesas:
        st.markdown("#### 🛒 Nossas Despesas")
        st.caption("Dica: Dê um duplo-clique no valor para alterar. Mude a situação para 'Pago' quando quitar a conta.")
        
        # Botão em destaque em cima da tabela
        placeholder_salvar = st.empty() 
        
        # TABELA DE DADOS OTIMIZADA PARA UX
        desp_edit = st.data_editor(
            df_mes[['id', 'nome', 'valor', 'parcela', 'status']], 
            hide_index=True, 
            use_container_width=True, 
            height=600,
            column_config={
                "id": None, # ESCONDE O ID TÉCNICO!
                "nome": st.column_config.TextColumn("Descrição da Conta", width="large"),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", step=10.0),
                "parcela": st.column_config.TextColumn("Parcela", width="small"),
                "status": st.column_config.SelectboxColumn("Situação", options=["Aberto", "Pago", "Pago Parcial"], width="medium")
            }
        )
        
        with placeholder_salvar:
            if st.button("💾 Salvar Situação das Contas", use_container_width=True, type="primary"):
                with st.spinner("Registrando alterações..."):
                    for index, row in desp_edit.iterrows():
                        id_linha = int(row['id'])
                        orig = df_mes[df_mes['id'] == id_linha].iloc[0]
                        if row['nome'] != orig['nome'] or row['valor'] != orig['valor'] or row['status'] != orig['status'] or row['parcela'] != orig['parcela']:
                            supabase.table("despesas").update({"nome": row['nome'], "valor": row['valor'], "status": row['status'], "parcela": row['parcela']}).eq("id", id_linha).execute()
                    st.success("Contas atualizadas com sucesso!"); time.sleep(1); st.rerun()

    with aba_receitas:
        st.markdown("#### 💵 Atualizar Entradas do Mês")
        if not rec_mes.empty:
            rec_id = int(rec_mes.iloc[0]['id'])
            val_tiago = float(rec_mes.iloc[0]['tiago'])
            val_analia = float(rec_mes.iloc[0]['analia'])
            val_extra = float(rec_mes.iloc[0]['extra'])
            
            # UX: Trocamos a tabela bizarra por um Formulário Bonito e familiar!
            with st.container(border=True):
                st.info("Preencha os valores abaixo para recalcular todo o sistema automaticamente.")
                c_tiago, c_analia, c_extra = st.columns(3)
                
                novo_tiago = c_tiago.number_input("Entrada Tiago (R$)", value=val_tiago, step=100.0, format="%.2f")
                novo_analia = c_analia.number_input("Entrada Analia (R$)", value=val_analia, step=100.0, format="%.2f")
                novo_extra = c_extra.number_input("Renda Extra (R$)", value=val_extra, step=50.0, format="%.2f")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("💾 Salvar Novos Valores", use_container_width=True, type="primary"):
                    with st.spinner("Atualizando salários..."):
                        supabase.table("receitas").update({"tiago": novo_tiago, "analia": novo_analia, "extra": novo_extra}).eq("id", rec_id).execute()
                        st.success("Rendas atualizadas!"); time.sleep(1); st.rerun()
        else:
            st.warning("Nenhuma receita cadastrada neste mês.")

    with aba_ferramentas:
        st.markdown("#### ⚙️ Ferramentas Administrativas")
        
        with st.expander("➕ Adicionar Nova Conta Avulsa", expanded=False):
            with st.form("form_nova_despesa", clear_on_submit=True):
                novo_nome = st.text_input("Descrição da Compra/Conta*")
                novo_valor = st.number_input("Valor (R$)*", min_value=0.01, format="%.2f")
                nova_parcela = st.text_input("Parcela (Opcional)", value="N/A")
                novo_status = st.selectbox("Situação Inicial", ["Aberto", "Pago"])
                if st.form_submit_button("Lançar no Sistema", use_container_width=True):
                    if not novo_nome.strip(): st.error("A descrição é obrigatória.")
                    else:
                        supabase.table("despesas").insert({"nome": novo_nome, "valor": novo_valor, "mes": mes_num, "ano": ano_sel, "parcela": nova_parcela, "status": novo_status, "origem": "Web"}).execute()
                        st.success("Lançamento efetuado!"); time.sleep(1); st.rerun() 

        with st.expander("🔄 Rotina de Faturamento (Clonar Mês)", expanded=False):
            with st.form("form_clonagem", clear_on_submit=True):
                pmes = mes_num + 1 if mes_num < 12 else 1
                pano = ano_sel if mes_num < 12 else ano_sel + 1
                st.info(f"O sistema copiará as contas de {mes_sel}/{ano_sel} calculando as novas parcelas automaticamente.")
                novo_mes_clon = st.selectbox("Mês Destino", list(meses_pt.values()), index=pmes-1)
                novo_ano_clon = st.number_input("Ano Destino", min_value=2020, max_value=2050, value=pano)
                
                if st.form_submit_button("🚀 Iniciar Processo de Clonagem", use_container_width=True):
                    with st.spinner("Calculando o futuro..."):
                        m_dest = [k for k, v in meses_pt.items() if v == novo_mes_clon][0]
                        origens = df_mes.to_dict('records')
                        novos = []
                        for d in origens:
                            nparc = d['parcela']
                            if str(nparc).strip().isdigit():
                                if int(nparc) <= 1: continue 
                                else: nparc = str(int(nparc) - 1)
                            novos.append({"nome": d['nome'], "valor": d['valor'], "mes": m_dest, "ano": novo_ano_clon, "parcela": nparc, "status": "Aberto", "origem": "Clonagem"})
                        if novos:
                            supabase.table("despesas").insert(novos).execute()
                            if not rec_mes.empty: supabase.table("receitas").insert({"mes": m_dest, "ano": novo_ano_clon, "tiago": rec_mes.iloc[0]['tiago'], "analia": rec_mes.iloc[0]['analia'], "extra": 0}).execute()
                            st.success(f"{len(novos)} contas geradas para {novo_mes_clon}/{novo_ano_clon}!"); time.sleep(2); st.rerun()