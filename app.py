import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Controle Financeiro", layout="wide")

st.title("💸 Controle Financeiro Pessoal")

# 1. Simulando a leitura dos dados (aqui você conectaria no Google Sheets)
# Receitas
receita_tiago = 7000.00
receita_analia = 2200.00
total_recebimentos = receita_tiago + receita_analia

# Despesas (simulando a soma da coluna VALOR)
total_a_pagar = 9781.68 
valor_pago = 0.00
valor_aberto = total_a_pagar - valor_pago

# 2. Seção de Resumo (KPIs Superiores)
st.subheader("Resumo do Mês")

# Criando as colunas de indicadores
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Recebimentos (Receitas)", f"R$ {total_recebimentos:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col2.metric("Total a Pagar", f"R$ {total_a_pagar:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col3.metric("Valor Pago", f"R$ {valor_pago:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
col4.metric("Valor Aberto", f"R$ {valor_aberto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

# Adicionando um alerta visual para o saldo projetado (se pagar tudo, quanto sobra/falta?)
saldo_projetado = total_recebimentos - total_a_pagar
cor_alerta = "normal" if saldo_projetado >= 0 else "inverse" # Fica vermelho se for negativo
col5.metric("Saldo Projetado", f"R$ {saldo_projetado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta="Atenção ao orçamento" if saldo_projetado < 0 else "Dentro do orçamento", delta_color=cor_alerta)

st.divider()

# 3. Tabela de Despesas Interativa
st.subheader("📋 Detalhamento de Despesas")

# Dados simulados baseados nas primeiras linhas da sua imagem
dados_despesas = {
    "DESPESAS": ["Carro", "Faculdade", "Zelo", "Emprestimo", "Internet"],
    "Parcela": ["21", "N/A", "Fixo", "7", "Fixo"],
    "VALOR": [1122.00, 723.00, 80.27, 399.20, 130.00],
    "Status": ["Aberto", "Aberto", "Aberto", "Aberto", "Aberto"],
    "Observação": ["", "", "", "", ""]
}
df_despesas = pd.DataFrame(dados_despesas)

# Adicionando um filtro simples
status_filtro = st.selectbox("Filtrar por Status:", ["Todos", "Aberto", "Pago"])
if status_filtro != "Todos":
    df_despesas = df_despesas[df_despesas["Status"] == status_filtro]

# Mostrando a tabela
st.dataframe(df_despesas, use_container_width=True)