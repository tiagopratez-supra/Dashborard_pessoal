import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot import apihelper
import requests
import base64
import os
import time
import json
import re
from datetime import datetime
from io import BytesIO
from PIL import Image
from supabase import create_client, Client

# ==========================================
# 0. CARREGAMENTO SEGURO DE SENHAS
# ==========================================
try:
    import toml
    secrets = toml.load(".streamlit/secrets.toml")
    SUPABASE_URL = secrets["connections"]["supabase"]["url"]
    SUPABASE_KEY = secrets["connections"]["supabase"]["key"]
    TOKEN_TELEGRAM = secrets["api_keys"]["telegram"]
    CHAVE_GEMINI = secrets["api_keys"]["gemini"]
except Exception:
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    TOKEN_TELEGRAM = os.environ.get("TOKEN_TELEGRAM")
    CHAVE_GEMINI = os.environ.get("CHAVE_GEMINI")

apihelper.CONNECT_TIMEOUT = 30
apihelper.READ_TIMEOUT = 90

bot = telebot.TeleBot(TOKEN_TELEGRAM)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

meses_pt = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 
    7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}

# Dicionário de estado para armazenar as transações pendentes de confirmação
pendencias_lancamento = {}

# ==========================================
# FUNÇÕES DE IA (GEMINI) E UTILITÁRIOS
# ==========================================
def consultar_ia(prompt, img_base64=None, bot_instance=None, chat_id=None, msg_id=None):
    # CORREÇÃO AQUI: Adicionado '-latest' no nome do modelo do Google
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={CHAVE_GEMINI}"
    parts = [{"text": prompt}]
    if img_base64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_base64}})
        
    payload = {"contents": [{"parts": parts}]}
    max_tentativas = 3
    for tentativa in range(max_tentativas):
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        elif response.status_code in [429, 503]:
            time.sleep(10)
        else:
            raise Exception(f"Erro {response.status_code}: {response.json()}")

# ==========================================
# BUSCADORES DO BANCO DE DADOS
# ==========================================
def get_cartoes():
    return supabase.table("cartoes").select("id, nome").execute().data

def get_categorias():
    return supabase.table("categorias").select("id, nome").execute().data

# ==========================================
# MOTOR DE LANÇAMENTO E CONFIRMAÇÕES
# ==========================================
def fluxo_confirmacao_despesa(chat_id, msg_id, dados):
    """Gerencia as etapas de falta de categoria, parcela ou salvamento final."""
    
    # 1. Checa se falta Categoria
    if not dados.get("categoria"):
        categorias = get_categorias()
        markup = InlineKeyboardMarkup(row_width=2)
        botoes = [InlineKeyboardButton(c['nome'], callback_data=f"cat_{c['nome']}") for c in categorias]
        markup.add(*botoes)
        
        # Salva em memória
        pendencias_lancamento[chat_id] = dados
        
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"🛒 Compra: *{dados['nome']}*\n💸 Valor: R$ {dados['valor']:.2f}\n\n⚠️ *Qual a Categoria desta despesa?*",
            parse_mode="Markdown", reply_markup=markup
        )
        return

    # 2. Checa se tem parcelas > 1 e precisa confirmar
    if int(dados.get("parcelas", 1)) > 1 and not dados.get("parcelas_confirmadas"):
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✅ Sim, Inicia este mês", callback_data="parc_sim"),
            InlineKeyboardButton("⏩ Não, Próximo mês", callback_data="parc_nao")
        )
        pendencias_lancamento[chat_id] = dados
        bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=f"💳 Identifiquei **{dados['parcelas']} parcelas de R$ {dados['valor']:.2f}** para '{dados['nome']}'.\n\nO primeiro pagamento entra já na fatura deste mês?",
            parse_mode="Markdown", reply_markup=markup
        )
        return

    # 3. Salva no banco de dados
    salvar_despesa_final(chat_id, msg_id, dados)


def salvar_despesa_final(chat_id, msg_id, dados):
    bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="⏳ Gravando no sistema...")
    
    # Define a Origem: Avulsa/Bot (Se for dinheiro/pix) ou App Web (Se for Cartão para unificar nas faturas)
    origem = "Avulsa (Bot)" if not dados.get('cartao_id') else "App Web"
    status = dados.get('status', 'Pago' if not dados.get('cartao_id') else 'Aberto')
    
    qtd_parcelas = int(dados.get('parcelas', 1))
    mes_atual = int(dados['mes'])
    ano_atual = int(dados['ano'])
    
    registros = []
    for i in range(qtd_parcelas):
        m = mes_atual + i
        a = ano_atual
        while m > 12:
            m -= 12
            a += 1
            
        parcela_str = f"{i+1}/{qtd_parcelas}" if qtd_parcelas > 1 else "N/A"
        
        registros.append({
            "nome": dados['nome'], "valor": float(dados['valor']), 
            "mes": m, "ano": a, "parcela": parcela_str, "status": status, 
            "categoria": dados['categoria'], "cartao_id": dados.get('cartao_id'),
            "origem": origem
        })
        
    resposta = supabase.table("despesas").insert(registros).execute()
    id_gerado = resposta.data[0]['id'] if resposta.data else "N/A"
    
    nome_cat = dados.get('categoria', 'Sem Categoria')
    ic = "🟢" if status.lower() == 'pago' else "🟡"
    
    msg_sucesso = f"✅ **Lançamento Registrado!**\n\n🛒 Local: {dados['nome']}\n🏷 Categoria: {nome_cat}\n💸 Valor: R$ {dados['valor']:.2f}\n📅 Mês: {meses_pt[mes_atual]}/{ano_atual}\n{ic} Status: {status}"
    
    if qtd_parcelas > 1:
        msg_sucesso += f"\n🔄 Parcelas geradas: {qtd_parcelas}"
        
    bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=msg_sucesso, parse_mode="Markdown")
    
    if chat_id in pendencias_lancamento:
        del pendencias_lancamento[chat_id]


# ==========================================
# HANDLERS DOS BOTÕES INLINE (CATEGORIA / PARCELAS)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_') or call.data.startswith('parc_'))
def botoes_inline(call):
    chat_id = call.message.chat.id
    dados = pendencias_lancamento.get(chat_id)
    
    if not dados:
        bot.answer_callback_query(call.id, "Sessão expirada. Tente enviar de novo.")
        return
        
    if call.data.startswith('cat_'):
        cat_nome = call.data.split('_')[1]
        dados['categoria'] = cat_nome
        bot.answer_callback_query(call.id, f"Categoria {cat_nome} selecionada!")
        
    elif call.data.startswith('parc_'):
        if call.data == 'parc_nao':
            # Joga pro mes que vem
            m = dados['mes'] + 1
            if m > 12:
                dados['mes'] = 1
                dados['ano'] += 1
            else:
                dados['mes'] = m
        dados['parcelas_confirmadas'] = True
        bot.answer_callback_query(call.id, "Parcelamento ajustado!")

    # Retorna pro motor continuar o fluxo
    fluxo_confirmacao_despesa(chat_id, call.message.message_id, dados)


# ==========================================
# ROTEADOR DE MENSAGENS (TEXTO)
# ==========================================
@bot.message_handler(content_types=['text'])
def processar_texto(mensagem):
    msg_status = bot.reply_to(mensagem, "🤖 Analisando seu pedido...")
    hoje = datetime.now()
    
    try:
        # Passo 1: Descobrir o que o usuário quer fazer
        prompt_roteador = f"""
        O usuário enviou a mensagem: "{mensagem.text}"
        
        Classifique a intenção EXATAMENTE com um destes números:
        1 - Lançar nova despesa (ex: comprei algo, lança, paguei, cartão, pix, debito).
        2 - Consulta e BI (ex: resumo do mês, projeção, saldo, quanto gastei).
        3 - Alterar ou Excluir (ex: alterar valor da elisa, apagar conta luz, edita, excluir).
        
        Retorne APENAS o número.
        """
        intencao = consultar_ia(prompt_roteador).strip()
        
        # ----------------------------------------------------
        # FLUXO 1: LANÇAMENTO DE DESPESA
        # ----------------------------------------------------
        if "1" in intencao:
            cartoes = get_cartoes()
            categorias = get_categorias()
            str_cartoes = ", ".join([f"ID {c['id']}: {c['nome']}" for c in cartoes])
            str_cats = ", ".join([c['nome'] for c in categorias])
            
            prompt = f"""
            Extraia os dados financeiros da frase: "{mensagem.text}"
            
            Regras estritas:
            1. nome: Resuma o nome do local ou despesa.
            2. valor: Apenas o número float. Se ele falou de parcelas, coloque o valor DA PARCELA.
            3. mes: Mês sugerido (1 a 12). Padrão é {hoje.month}.
            4. status: "Pago" (se for pix/dinheiro/débito) ou "Aberto" (se for cartão ou a vencer).
            5. parcelas: Quantidade numérica (padrão é 1).
            6. cartao_id: Se a pessoa usar um cartão, veja esta lista [{str_cartoes}] e retorne o ID. Se for PIX/Débito, retorne null.
            7. categoria: Tente classificar em uma destas [{str_cats}]. Se não tiver certeza absoluta, retorne null.
            
            Retorne APENAS um JSON válido.
            Exemplo: {{"nome": "Ifood", "valor": 45.0, "mes": 9, "status": "Pago", "parcelas": 1, "cartao_id": null, "categoria": "Alimentação"}}
            """
            
            texto_ia = consultar_ia(prompt)
            dados = extrair_json_da_ia(texto_ia)
            
            if not dados or "valor" not in dados or dados["valor"] <= 0:
                bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="❌ Não consegui entender os valores. Tente: 'Comprei lanche de 30 reais no pix'.")
                return
            
            dados['ano'] = hoje.year
            fluxo_confirmacao_despesa(mensagem.chat.id, msg_status.message_id, dados)

        # ----------------------------------------------------
        # FLUXO 2: CONSULTA (DASHBOARD VIA TELEGRAM)
        # ----------------------------------------------------
        elif "2" in intencao:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="📊 Levantando dados do sistema...")
            
            # Puxa o mês atual e o próximo para projeção
            mes_atual = hoje.month
            prox_mes = mes_atual + 1 if mes_atual < 12 else 1
            ano_prox = hoje.year if mes_atual < 12 else hoje.year + 1
            
            despesas = supabase.table("despesas").select("nome,valor,status,cartao_id,origem,mes").in_("mes", [mes_atual, prox_mes]).gte("ano", hoje.year).execute().data
            receitas = supabase.table("receitas").select("tiago,analia,extra,mes").in_("mes", [mes_atual, prox_mes]).gte("ano", hoje.year).execute().data
            
            prompt_bi = f"""
            Atue como o Gerente Financeiro Pessoal do Tiago e Analia.
            O usuário perguntou: "{mensagem.text}"
            
            Use os DADOS GERAIS DESTE MÊS ({mes_atual}) e MÊS QUE VEM ({prox_mes}) para responder de forma curta e bonita no Telegram (com Emojis).
            
            DADOS:
            Despesas: {despesas}
            Receitas: {receitas}
            
            REGRAS PARA O RESUMO MENSAL:
            - Calcule a Receita Total do mês.
            - Separe "Despesas do Mês" (origem = 'App Web' ou que possuam cartao_id) das "Despesas Avulsas" (origem = 'Avulsa (Bot)', que são os gastos esporádicos no débito/pix).
            - Mostre o Saldo Livre.
            - Seja direto, claro e formate tudo em Reais (R$ 1.500,00).
            """
            
            resposta_final = consultar_ia(prompt_bi)
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text=resposta_final, parse_mode="Markdown")

        # ----------------------------------------------------
        # FLUXO 3: ALTERAÇÃO / EXCLUSÃO
        # ----------------------------------------------------
        elif "3" in intencao:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="🔄 Analisando o que precisa ser alterado...")
            
            prompt_alt = f"""
            O usuário pediu para alterar dados: "{mensagem.text}"
            Identifique:
            1. "termo_busca": uma palavra do nome da despesa para procurar no banco (ex: "elisa").
            2. "novo_valor": o novo valor em formato numérico (float). Se não for alterar valor, retorne null.
            3. "excluir": booleano (true ou false) caso ele tenha pedido para apagar a conta.
            Retorne APENAS um JSON válido. Ex: {{"termo_busca": "elisa", "novo_valor": 100.0, "excluir": false}}
            """
            
            dados_alt = extrair_json_da_ia(consultar_ia(prompt_alt))
            if not dados_alt or not dados_alt.get('termo_busca'):
                bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="❌ Não consegui identificar qual conta você quer alterar.")
                return

            busca = supabase.table("despesas").select("id, nome, valor").ilike("nome", f"%{dados_alt['termo_busca']}%").eq("mes", hoje.month).execute().data
            
            if not busca:
                bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text=f"❌ Nenhuma conta encontrada com o nome '{dados_alt['termo_busca']}' neste mês.")
                return
                
            alvo = busca[0] # Pega o primeiro que bateu com a busca
            
            if dados_alt.get("excluir"):
                supabase.table("despesas").delete().eq("id", alvo["id"]).execute()
                bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text=f"🗑 Conta **{alvo['nome']}** de R$ {alvo['valor']:.2f} foi excluída com sucesso deste mês!", parse_mode="Markdown")
            elif dados_alt.get("novo_valor"):
                supabase.table("despesas").update({"valor": float(dados_alt["novo_valor"])}).eq("id", alvo["id"]).execute()
                bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text=f"✅ Valor de **{alvo['nome']}** atualizado de R$ {alvo['valor']:.2f} para R$ {dados_alt['novo_valor']:.2f}!", parse_mode="Markdown")
            else:
                bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="🤷‍♂️ Entendi a conta, mas não entendi o que é para fazer com ela.")

    except Exception as e:
        try:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text=f"❌ Falha interna: {e}")
        except:
            bot.send_message(mensagem.chat.id, f"❌ Falha: {e}")

# ==========================================
# ROTEADOR DE MENSAGENS (FOTO)
# ==========================================
@bot.message_handler(content_types=['photo'])
def processar_foto(mensagem):
    msg_status = bot.reply_to(mensagem, "📸 Analisando o comprovante...")
    try:
        id_arquivo = mensagem.photo[-1].file_id
        info_arquivo = bot.get_file(id_arquivo)
        foto_baixada = bot.download_file(info_arquivo.file_path)
        
        imagem = Image.open(BytesIO(foto_baixada))
        if imagem.mode != 'RGB': imagem = imagem.convert('RGB')
            
        buffer = BytesIO()
        imagem.save(buffer, format="JPEG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        cartoes = get_cartoes()
        categorias = get_categorias()
        str_cartoes = ", ".join([f"ID {c['id']}: {c['nome']}" for c in cartoes])
        str_cats = ", ".join([c['nome'] for c in categorias])
        
        prompt = f"""
        Extraia os dados deste comprovante de pagamento/nota fiscal.
        1. nome: Local da compra.
        2. valor: Valor total (float).
        3. mes: {datetime.now().month}
        4. status: "Pago".
        5. parcelas: 1.
        6. cartao_id: Se o recibo citar máquina de crédito parecida com estes cartões [{str_cartoes}], retorne o ID. Se for débito/pix, null.
        7. categoria: Tente classificar em uma destas [{str_cats}]. Se não tiver certeza, null.
        
        Retorne APENAS um JSON válido.
        Ex: {{"nome": "Posto Ipiranga", "valor": 100.0, "mes": 9, "status": "Pago", "parcelas": 1, "cartao_id": null, "categoria": "Combustível"}}
        """
        
        texto_ia = consultar_ia(prompt, img_base64)
        dados = extrair_json_da_ia(texto_ia)
        
        if not dados or "valor" not in dados or dados["valor"] <= 0:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="❌ Não consegui ler o valor no comprovante. A foto está nítida?")
            return
            
        dados['ano'] = datetime.now().year
        fluxo_confirmacao_despesa(mensagem.chat.id, msg_status.message_id, dados)
        
    except Exception as e:
        bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text=f"❌ Falha ao processar foto: {e}")


print("🤖 Agente ERP Inteligente Rodando no Telegram!")
bot.infinity_polling(timeout=60, long_polling_timeout=60)