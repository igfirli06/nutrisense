import os
import telebot
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits import create_sql_agent
from langchain_core.messages import HumanMessage, AIMessage

# --- KONFIGURASI ---
GOOGLE_API_KEY = "" 
TELEGRAM_TOKEN = ''
DB_PASSWORD = ""

# Setup Environment
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
DB_URI = f"postgresql://postgres:{DB_PASSWORD}@localhost:5432/nutrisense"
bot = telebot.TeleBot(TELEGRAM_TOKEN)

print("⚙️ Menghubungkan ke Google AI (Mode Full Text)...")

try:
    # --- MODEL SETUP (DENGAN "NAPAS" LEBIH PANJANG) ---
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest", 
        temperature=0,
        max_output_tokens=2048  # <--- INI PENTING: Biar dia gak berhenti di tengah jalan
    )

    db = SQLDatabase.from_uri(
        DB_URI,
        include_tables=['makanan', 'gizi', 'resep', 'bahan_resep'],
        sample_rows_in_table_info=0
    )
    
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    print("✅ Siap! Terhubung.")

except Exception as e:
    print(f"❌ Error Setup: {e}")

# --- SYSTEM PROMPT (PERINTAH JANGAN SINGKAT) ---
# Perhatikan bagian "CRITICAL RULES" di bawah ini.
system_instruction = """
You are a SQL Agent for Nutrisense.

DATABASE CHEAT SHEET:
1. `makanan` (id, nama_makanan)
2. `gizi` (id, id_makanan, kalori, protein, lemak, karbohidrat)
3. `resep` (id, judul, deskripsi, gambar) -> Column name is 'judul'.
4. `bahan_resep` (id, resep_id, makanan_id, berat)

TASKS:
1. If user asks for recipes, query `resep` AND `bahan_resep`.
2. If user asks for nutrition, query `gizi` joined with `makanan`.

CRITICAL RULES FOR RECIPES:
- When you find a recipe, output the `deskripsi` column **EXACTLY AS IT IS**.
- **DO NOT SUMMARIZE** the description.
- **DO NOT TRUNCATE** or cut off the text.
- **DO NOT USE ELLIPSIS (...)**. Show every single step completely.
- Answer in INDONESIAN language.

FORMAT:
Thought: [Reasoning]
Action: sql_db_query
Action Input: [SQL Query]
Observation: [Result]
Final Answer: [FULL Indonesian Answer without summarizing]
"""

user_memories = {}

def get_ai_response(user_id, user_message):
    if user_id not in user_memories:
        user_memories[user_id] = []
    
    history = user_memories[user_id][-2:]
    context_str = "\n".join([f"{msg.type}: {msg.content}" for msg in history])
    
    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=True,
        agent_type="zero-shot-react-description",
        handle_parsing_errors=True,
        prefix=system_instruction
    )

    try:
        full_query = f"Context:\n{context_str}\n\nQuestion: {user_message}"
        result = agent.invoke({"input": full_query})
        response = result.get('output', "Maaf, gagal memproses data.")
        
        user_memories[user_id].append(HumanMessage(content=user_message))
        user_memories[user_id].append(AIMessage(content=response))
        return response

    except Exception as e:
        error_msg = str(e)
        print(f"⚠️ ERROR SYSTEM: {error_msg}")
        
        if "429" in error_msg:
             return "⏳ Sabar ya, kuota Google Gratisan lagi penuh. Tunggu 1 menit lagi."
        
        return "Maaf, sistem sedang sibuk."

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    print(f"📩 Chat Masuk: {message.text}")
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        jawaban = get_ai_response(message.chat.id, message.text)
        bot.reply_to(message, jawaban)
    except Exception as e:
        print(f"❌ Error Telegram: {e}")

print("✅ Bot Jalan! (Tekan Ctrl+C untuk stop)")
bot.infinity_polling()