import telebot
from telebot import apihelper
import requests
import base64
import os
import time
from datetime import datetime
from io import BytesIO
from PIL import Image
from supabase import create_client, Client

# ==========================================
# 0. CARREGAMENTO SEGURO DE SENHAS (BLINDADO)
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
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

# ==========================================
# FUNÇÃO 1: COMUNICAÇÃO COM O GOOGLE GEMINI
# ==========================================
def consultar_ia(prompt, img_base64=None, bot_instance=None, chat_id=None, msg_id=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={CHAVE_GEMINI}"
    
    parts = [{"text": prompt}]
    if img_base64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_base64}})
        
    payload = {"contents": [{"parts": parts}]}
    
    max_tentativas = 4
    for tentativa in range(max_tentativas):
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
            
        elif response.status_code == 429:
            if tentativa < max_tentativas - 1:
                if bot_instance and chat_id and msg_id:
                    try:
                        bot_instance.edit_message_text(
                            chat_id=chat_id, message_id=msg_id, 
                            text=f"⏳ O Google pediu para ir devagar. Aguardando 15 segundos antes de tentar de novo ({tentativa+1}/{max_tentativas})..."
                        )
                    except:
                        pass
                time.sleep(15) 
            else:
                raise Exception("Limite de requisições do Google excedido. Tente novamente em 1 minuto.")
                
        elif response.status_code == 503:
            if tentativa < max_tentativas - 1:
                time.sleep(5)
            else:
                raise Exception("Servidores do Google sobrecarregados. Tente mais tarde.")
        else:
            raise Exception(f"Erro {response.status_code}: {response.json()}")

# ==========================================
# FUNÇÃO 2 E 3: GRAVAÇÃO E PARCELAMENTO
# ==========================================
def salvar_banco(nome_despesa, valor_despesa, mes_numero, status_despesa, ano_despesa, parcela_str="N/A"):
    dados = {
        "nome": nome_despesa, "valor": float(valor_despesa), "mes": mes_numero, "ano": ano_despesa,
        "parcela": parcela_str, "status": status_despesa, "origem": "Bot Telegram"
    }
    resposta = supabase.table("despesas").insert(dados).execute()
    return resposta.data[0]['id']

def processar_parcelas(mensagem, dados_despesa):
    try:
        resposta = mensagem.text.strip().lower()
        mes_inicio = dados_despesa['mes']
        ano_inicio = dados_despesa['ano']

        if resposta in ['sim', 's', 'y']:
            pass 
        elif resposta in ['não', 'nao', 'n']:
            mes_inicio += 1
            if mes_inicio > 12:
                mes_inicio = 1
                ano_inicio += 1
        else:
            msg = bot.send_message(mensagem.chat.id, "❌ Resposta inválida. Por favor, responda apenas **Sim** ou **Não**.")
            bot.register_next_step_handler(msg, processar_parcelas, dados_despesa)
            return

        bot.send_message(mensagem.chat.id, f"⏳ Gravando {dados_despesa['parcelas']} parcelas no banco. Aguarde...")

        linhas_lancadas = []
        for i in range(dados_despesa['parcelas']):
            mes_atual = mes_inicio + i
            ano_atual = ano_inicio
            
            while mes_atual > 12:
                mes_atual -= 12
                ano_atual += 1

            parcela_str = str(dados_despesa['parcelas'] - i)
            id_db = salvar_banco(dados_despesa['nome'], dados_despesa['valor'], mes_atual, dados_despesa['status'], ano_atual, parcela_str)
            linhas_lancadas.append(f"- {meses_pt[mes_atual]}/{ano_atual}: ID {id_db}")

        resumo = "\n".join(linhas_lancadas)
        bot.send_message(
            mensagem.chat.id,
            f"✅ **{dados_despesa['parcelas']} parcelas salvas no Banco!**\n\n🛒 Local: {dados_despesa['nome']}\n💸 Valor p/ parcela: R$ {dados_despesa['valor']:.2f}\n🟢 Status: {dados_despesa['status']}\n\n📍 **Registros (IDs):**\n{resumo}",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.send_message(mensagem.chat.id, f"❌ Erro ao gravar parcelas: {e}")

# ==========================================
# HANDLER PRINCIPAL: MENSAGEM DE TEXTO 
# ==========================================
@bot.message_handler(content_types=['text'])
def processar_texto(mensagem):
    try:
        msg_status = bot.reply_to(mensagem, "🤖 Pensando...")
        hoje = datetime.now()
        ano_atual = hoje.year
        
        prompt_roteador = f"""
        Analise a seguinte mensagem do usuário: "{mensagem.text}"
        
        Sua tarefa é classificar a intenção:
        - Se o usuário estiver ordenando um LANÇAMENTO (ex: "comprei pão 10", "pagar carro 500 no mes 9", "lança 50"), retorne APENAS o número 1.
        - Se o usuário estiver fazendo uma CONSULTA ou PERGUNTA (ex: "quanto devo", "qual o saldo", "quanto falta pagar de cartão"), retorne APENAS o número 2.
        """
        intencao = consultar_ia(prompt_roteador, bot_instance=bot, chat_id=mensagem.chat.id, msg_id=msg_status.message_id).strip()
        
        if "1" in intencao:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="📝 Extraindo dados do lançamento...")
            prompt = f"""
            Você é um assistente financeiro. Extraia os dados da despesa: "{mensagem.text}"
            Regras:
            1. Nome da despesa.
            2. VALOR da parcela. 
            3. Mês (1 a 12). Se não informar, use {hoje.month}.
            4. Status: "Pago" ou "Aberto".
            5. Quantidade de PARCELAS. Se não mencionar, retorne 1.
            Retorne EXATAMENTE (5 informações separadas por pipe): Nome|ValorDaParcela|Mes|Status|Parcelas
            """
            texto_ia = consultar_ia(prompt, bot_instance=bot, chat_id=mensagem.chat.id, msg_id=msg_status.message_id)
            dados = texto_ia.strip().split('|')
            
            nome, valor, mes, status, parcelas = dados[0].strip(), float(dados[1].strip()), int(dados[2].strip()), dados[3].strip(), int(dados[4].strip())
            
            if valor <= 0:
                bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="❌ **Valor Inválido!** O valor não pode ser zero.", parse_mode="Markdown")
                return
                
            if parcelas > 1:
                dados_despesa = {'nome': nome, 'valor': valor, 'mes': mes, 'ano': ano_atual, 'status': status, 'parcelas': parcelas}
                msg = bot.edit_message_text(
                    chat_id=mensagem.chat.id, message_id=msg_status.message_id,
                    text=f"💳 Identifiquei **{parcelas} parcelas de R$ {valor:.2f}** para '{nome}'.\n\nO primeiro pagamento é para este mês de **{meses_pt[mes]}**?\n*(Responda com Sim ou Não)*",
                    parse_mode="Markdown"
                )
                bot.register_next_step_handler(mensagem, processar_parcelas, dados_despesa)
                return

            id_db = salvar_banco(nome, valor, mes, status, ano_atual)
            icone_status = "🟢" if status.lower() == "pago" else "🟡"
            bot.edit_message_text(
                chat_id=mensagem.chat.id, message_id=msg_status.message_id, 
                text=f"✅ **Registro Salvo no Banco!**\n\n🛒 Local: {nome}\n💸 Valor: R$ {valor:.2f}\n📅 Mês: {meses_pt[mes]}/{ano_atual}\n{icone_status} Status: {status}\n🔑 ID do Banco: #{id_db}",
                parse_mode="Markdown"
            )
            
        elif "2" in intencao:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="🔍 Consultando o banco de dados...")
            
            despesas_bd = supabase.table("despesas").select("nome,valor,mes,ano,parcela,status").gte("ano", ano_atual).execute().data
            receitas_bd = supabase.table("receitas").select("mes,ano,tiago,analia,extra").gte("ano", ano_atual).execute().data
            
            prompt_consulta = f"""
            Você é o consultor financeiro do Tiago e da Analia. 
            Eles fizeram a seguinte pergunta no Telegram: "{mensagem.text}"
            
            Baseie sua resposta ESTRITAMENTE nos dados reais do banco de dados abaixo. 
            Faça as contas matemáticas necessárias antes de responder.
            Retorne uma resposta amigável, direta, curta e fácil de ler no celular.
            IMPORTANTE: Sempre formate os valores em Reais (ex: R$ 1.500,00). 
            Se a pergunta for sobre um mês específico, some os valores solicitados daquele mês.
            
            DADOS DE DESPESAS: {despesas_bd}
            DADOS DE RECEITAS: {receitas_bd}
            """
            
            resposta_final = consultar_ia(prompt_consulta, bot_instance=bot, chat_id=mensagem.chat.id, msg_id=msg_status.message_id)
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text=resposta_final, parse_mode="Markdown")

        else:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="❌ IA Confusa: Não entendi se você quis lançar uma conta ou fazer uma pergunta.")
            
    except Exception as e:
        try:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text=f"❌ Falha: {e}")
        except:
            bot.send_message(mensagem.chat.id, f"❌ Falha: {e}")

# ==========================================
# HANDLER 2: FOTO (NOTA FISCAL)
# ==========================================
@bot.message_handler(content_types=['photo'])
def processar_foto(mensagem):
    try:
        msg_status = bot.reply_to(mensagem, "📸 Lendo o comprovante e conectando ao banco...")
        id_arquivo = mensagem.photo[-1].file_id
        info_arquivo = bot.get_file(id_arquivo)
        foto_baixada = bot.download_file(info_arquivo.file_path)
        
        imagem = Image.open(BytesIO(foto_baixada))
        if imagem.mode != 'RGB': imagem = imagem.convert('RGB')
            
        buffer = BytesIO()
        imagem.save(buffer, format="JPEG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        prompt = """
        Analise esta imagem de recibo ou comprovante. 
        Extraia o nome do estabelecimento e o valor total.
        Retorne a resposta EXATAMENTE neste formato: Nome da Despesa|150.50
        """
        
        texto_ia = consultar_ia(prompt, img_base64, bot_instance=bot, chat_id=mensagem.chat.id, msg_id=msg_status.message_id)
        dados = texto_ia.strip().split('|')
        
        nome, valor = dados[0].strip(), float(dados[1].strip())
        mes_atual, ano_atual = datetime.now().month, datetime.now().year
        
        if valor <= 0:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text="❌ A IA não conseguiu identificar um valor válido na foto.")
            return
        
        id_db = salvar_banco(nome, valor, mes_atual, "Pago", ano_atual)
        bot.edit_message_text(
            chat_id=mensagem.chat.id, message_id=msg_status.message_id, 
            text=f"✅ **Despesa salva no banco com sucesso!**\n\n🛒 Local: {nome}\n💸 Valor: R$ {valor:.2f}\n📅 Mês: {meses_pt[mes_atual]}/{ano_atual}\n🟢 Status: Pago\n🔑 ID do Banco: #{id_db}",
            parse_mode="Markdown"
        )
    except Exception as e:
        try:
            bot.edit_message_text(chat_id=mensagem.chat.id, message_id=msg_status.message_id, text=f"❌ Falha: {e}")
        except:
            bot.send_message(mensagem.chat.id, f"❌ Falha: {e}")

print("🤖 Agente Financeiro Inteligente Rodando! (Seguro e pronto para Nuvem)")
bot.infinity_polling(timeout=60, long_polling_timeout=60)