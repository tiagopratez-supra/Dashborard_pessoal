import streamlit as st
import pandas as pd
import gspread
import altair as alt
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import os

st.set_page_config(page_title="Dashboard Financeiro", layout="wide", initial_sidebar_state="expanded")

# Cabeçalho com estilo
st.markdown("## 💸 Meu Dashboard Financeiro")
st.markdown("Acompanhamento e projeção do fluxo de caixa familiar")
st.divider()

# Conexão principal
conn = st.connection("gsheets", type=GSheetsConnection)
url_planilha = "https://docs.google.com/spreadsheets/d/1ppZq8QeUAmHfdziGiTwgvzpxPCezEE0FvIsPm19uAR4/edit?gid=892610265#gid=892610265" 

def formata_moeda(valor):
    try:
        valor_float = float(valor)
        return f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def exibir_card_kpi(titulo, valor, cor_borda):
    st.markdown(f"""
    <div style="border: 1px solid rgba(128,128,128,0.2); padding: 15px; border-radius: 8px; border-left: 6px solid {cor_borda}; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
        <p style="margin:0; font-size: 14px; font-weight: bold; color: gray;">{titulo}</p>
        <h3 style="margin: 5px 0 0 0; font-size: 24px;">{valor}</h3>
    </div>
    """, unsafe_allow_html=True)

meses_pt = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}
meses_para_num = {v: k for k, v in meses_pt.items()}

def extrair_data_da_aba(nome_aba):
    try:
        mes_str, ano_str = nome_aba.split('-')
        return int(ano_str), meses_para_num[mes_str]
    except:
        return 9999, 12 

try:
    # ===================================================================
    # 1. MENU LATERAL COM A FOTO PARA A ANALIA
    # ===================================================================
    with st.sidebar:
        # Tenta carregar a imagem da pasta logos
        caminho_logo = "logos/logo.jpeg"
        if os.path.exists(caminho_logo):
            # width=150 deixa a imagem delicada e proporcional no menu
            st.image(caminho_logo, width=150)
            
        st.title("📅 Navegação")
        # O restante do código precisa acessar as abas antes de montar o selectbox
        
    # ===================================================================
    # 2. MAPEAMENTO E ORDENAÇÃO
    # ===================================================================
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    gc = gspread.service_account_from_dict(creds_dict)
    spreadsheet = gc.open_by_url(url_planilha)
    
    abas_brutas = [ws.title for ws in spreadsheet.worksheets()]
    abas = sorted(abas_brutas, key=extrair_data_da_aba)
    
    hoje = datetime.now()
    mes_atual_nome = meses_pt[hoje.month]
    ano_atual_curto = str(hoje.year)[-2:]
    aba_esperada = f"{mes_atual_nome}-{ano_atual_curto}"
    
    if aba_esperada in abas:
        index_padrao = abas.index(aba_esperada)
    else:
        index_padrao = 0

    with st.sidebar:
        aba_selecionada = st.selectbox("Selecione o Mês Base:", abas, index=index_padrao)
        st.divider()
        st.info("💡 **Dica:** O sistema carrega o mês atual, e projeta o futuro a partir dele.")

    df_raw = conn.read(spreadsheet=url_planilha, worksheet=aba_selecionada, ttl=0)
    
    # ===================================================================
    # 3. O "AGORA" - KPIs DO MÊS SELECIONADO
    # ===================================================================
    receita_tiago = df_raw.loc[1, 'Unnamed: 3']
    receita_analia = df_raw.loc[1, 'Unnamed: 4']
    total_a_pagar = df_raw.loc[1, 'Unnamed: 5']
    valor_pago = df_raw.loc[1, 'Unnamed: 6']
    valor_aberto = df_raw.loc[1, 'Unnamed: 7']
    saldo = df_raw.loc[1, 'Unnamed: 8']

    try:
        total_receitas = float(receita_tiago) + float(receita_analia)
        total_pagar_float = float(total_a_pagar)
        pago_float = float(valor_pago)
        saldo_float = float(saldo)
    except:
        total_receitas = total_pagar_float = pago_float = saldo_float = 0.0

    st.subheader(f"📌 Situação Atual ({aba_selecionada})")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    col1.metric("Receitas", formata_moeda(total_receitas))
    col2.metric("Total a Pagar", formata_moeda(total_a_pagar))
    col3.metric("Já Pago", formata_moeda(valor_pago))
    col4.metric("Em Aberto", formata_moeda(valor_aberto))
    
    cor_saldo = "normal" if saldo_float >= 0 else "inverse"
    col5.metric("Saldo do Mês", formata_moeda(saldo), delta="Positivo" if saldo_float >=0 else "Negativo", delta_color=cor_saldo)
    
    if total_pagar_float > 0:
        st.progress(pago_float / total_pagar_float, text=f"Progresso do mês: {(pago_float / total_pagar_float)*100:.1f}% concluído")

    st.divider()

    # --- EXTRAINDO A TABELA DO MÊS ATUAL ---
    linha_cabecalho = df_raw[df_raw['Unnamed: 1'].astype(str).str.strip().str.upper() == 'DESPESAS'].index[0]
    df_despesas = df_raw.loc[linha_cabecalho + 1 :].copy()
    df_despesas.columns = df_raw.loc[linha_cabecalho].values
    df_despesas = df_despesas.loc[:, df_despesas.columns.notnull()]
    
    colunas_finais = ['DESPESAS', 'Parcela', 'VALOR', 'Status', 'Observação']
    colunas_finais = [col for col in colunas_finais if col in df_despesas.columns]
    df_despesas = df_despesas[colunas_finais]
    df_despesas = df_despesas.dropna(subset=['DESPESAS'])
    df_despesas['VALOR'] = pd.to_numeric(df_despesas['VALOR'], errors='coerce')

    # ===================================================================
    # 4. O "FUTURO" - FLUXO DE CAIXA E AGRUPAMENTOS
    # ===================================================================
    abas_futuras = abas[abas.index(aba_selecionada) + 1:]
    
    if abas_futuras:
        st.subheader("🔭 Visão de Futuro (Acumulado dos próximos meses)")
        
        dados_futuros = []
        todas_despesas_futuras = []
        total_rec_futura = 0.0
        total_desp_futura = 0.0
        
        for aba_futura in abas_futuras:
            try:
                df_temp = conn.read(spreadsheet=url_planilha, worksheet=aba_futura, ttl=600)
                
                rec = float(df_temp.loc[1, 'Unnamed: 3']) + float(df_temp.loc[1, 'Unnamed: 4'])
                desp = float(df_temp.loc[1, 'Unnamed: 5'])
                total_rec_futura += rec
                total_desp_futura += desp
                dados_futuros.append({"Mês": aba_futura, "Receitas": rec, "Despesas": desp, "Saldo Livre": rec - desp})
                
                linha_cab_fut = df_temp[df_temp['Unnamed: 1'].astype(str).str.strip().str.upper() == 'DESPESAS'].index[0]
                df_desp_fut = df_temp.loc[linha_cab_fut + 1 :].copy()
                df_desp_fut.columns = df_temp.loc[linha_cab_fut].values
                df_desp_fut = df_desp_fut.loc[:, df_desp_fut.columns.notnull()]
                
                if 'DESPESAS' in df_desp_fut.columns and 'VALOR' in df_desp_fut.columns:
                    df_desp_fut = df_desp_fut.dropna(subset=['DESPESAS'])
                    df_desp_fut['VALOR'] = pd.to_numeric(df_desp_fut['VALOR'], errors='coerce')
                    
                    if 'Parcela' in df_desp_fut.columns:
                        df_desp_fut['Parcela'] = df_desp_fut['Parcela'].fillna('N/A').astype(str)
                    else:
                        df_desp_fut['Parcela'] = 'N/A'
                        
                    todas_despesas_futuras.append(df_desp_fut[['DESPESAS', 'VALOR', 'Parcela']])
            except:
                pass
        
        # --- MOTOR DE CLASSIFICAÇÃO INTELIGENTE ---
        df_futuro_consolidado = pd.concat(todas_despesas_futuras)
        
        def categorizar_despesa(row):
            d = str(row['DESPESAS']).lower()
            p = str(row['Parcela']).lower()
            
            if any(c in d for c in ['cartao', 'cartão', 'nubank', 'will', 'inter', 'mp', 'mart minas']):
                return '💳 Cartões de Crédito'
            elif 'fixo' in p or 'fixa' in p:
                return '📌 Despesas Fixas'
            elif p != 'n/a' and p != 'none' and p != '' and any(char.isdigit() for char in p):
                return '⏳ Parcelamentos'
            else:
                return '🛒 Outros / Variáveis'

        df_futuro_consolidado['Categoria'] = df_futuro_consolidado.apply(categorizar_despesa, axis=1)
        
        total_cartoes = df_futuro_consolidado[df_futuro_consolidado['Categoria'] == '💳 Cartões de Crédito']['VALOR'].sum()
        total_fixas = df_futuro_consolidado[df_futuro_consolidado['Categoria'] == '📌 Despesas Fixas']['VALOR'].sum()
        total_parc = df_futuro_consolidado[df_futuro_consolidado['Categoria'] == '⏳ Parcelamentos']['VALOR'].sum()
        total_outros = df_futuro_consolidado[df_futuro_consolidado['Categoria'] == '🛒 Outros / Variáveis']['VALOR'].sum()

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1: exibir_card_kpi("💳 Cartões Acumulados", formata_moeda(total_cartoes), "#FF9800")
        with c2: exibir_card_kpi("📌 Fixas Acumuladas", formata_moeda(total_fixas), "#4CAF50")
        with c3: exibir_card_kpi("⏳ Parcelamentos Acumulados", formata_moeda(total_parc), "#2196F3")
        with c4: exibir_card_kpi("🛒 Outras Contas", formata_moeda(total_outros), "#9C27B0")

        grafico_col1, grafico_col2 = st.columns(2)
        
        with grafico_col1:
            st.markdown("**Composição Geral de Despesas Futuras**")
            df_cat = df_futuro_consolidado.groupby('Categoria')['VALOR'].sum().reset_index()
            df_cat = df_cat[df_cat['VALOR'] > 0]
            
            grafico_donut = alt.Chart(df_cat).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="VALOR", type="quantitative"),
                color=alt.Color(field="Categoria", type="nominal", sort=None, 
                              scale=alt.Scale(domain=['💳 Cartões de Crédito', '📌 Despesas Fixas', '⏳ Parcelamentos', '🛒 Outros / Variáveis'], 
                                              range=['#FF9800', '#4CAF50', '#2196F3', '#9C27B0'])),
                tooltip=[alt.Tooltip("Categoria"), alt.Tooltip("VALOR", title="Total (R$)", format=",.2f")]
            ).properties(height=350)
            st.altair_chart(grafico_donut, use_container_width=True)

        with grafico_col2:
            st.markdown("**🔍 Raio-X dos Parcelamentos Futuros**")
            df_apenas_parc = df_futuro_consolidado[df_futuro_consolidado['Categoria'] == '⏳ Parcelamentos']
            if not df_apenas_parc.empty:
                df_parc_agrupado = df_apenas_parc.groupby('DESPESAS')['VALOR'].sum().reset_index()
                df_parc_agrupado = df_parc_agrupado.sort_values(by='VALOR', ascending=False)
                
                grafico_barras_parc = alt.Chart(df_parc_agrupado).mark_bar(cornerRadiusEnd=4).encode(
                    x=alt.X('VALOR:Q', title='Valor Acumulado (R$)'),
                    y=alt.Y('DESPESAS:N', sort='-x', title=''),
                    color=alt.value('#2196F3'),
                    tooltip=[alt.Tooltip("DESPESAS"), alt.Tooltip("VALOR", title="Total (R$)", format=",.2f")]
                ).properties(height=350)
                st.altair_chart(grafico_barras_parc, use_container_width=True)
            else:
                st.info("Nenhum parcelamento encontrado nos próximos meses.")

        st.divider()

    # ===================================================================
    # 5. DETALHAMENTO DE DESPESAS (Mês Selecionado)
    # ===================================================================
    st.subheader(f"📋 Detalhamento de Contas ({aba_selecionada})")
    
    status_unicos = df_despesas['Status'].dropna().unique().tolist()
    status_unicos.insert(0, "Todos")
    status_filtro = st.selectbox("Filtrar por Status:", status_unicos)
    
    if status_filtro != "Todos":
        df_mostrar = df_despesas[df_despesas["Status"] == status_filtro]
    else:
        df_mostrar = df_despesas
    
    st.dataframe(
        df_mostrar,
        use_container_width=True,
        hide_index=True,
        column_config={
            "VALOR": st.column_config.NumberColumn("Valor", format="R$ %.2f")
        }
    )

except Exception as e:
    st.error(f"Erro ao processar a planilha. Detalhes: {e}")