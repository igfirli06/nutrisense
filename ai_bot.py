import os
import telebot
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits import create_sql_agent
from langchain_core.messages import HumanMessage, AIMessage

# --- KONFIGURASI ---
# 1. API KEY PROJECT BARU
GOOGLE_API_KEY = "" 
TELEGRAM_TOKEN = ''
DB_PASSWORD = ""

# Setup
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
DB_URI = f"postgresql://postgres:{DB_PASSWORD}@localhost:5432/nutrisense"
bot = telebot.TeleBot(TELEGRAM_TOKEN)

print("⚙️ Menghubungkan ke Gemini Flash Latest (Mode Strict)...")

try:
    # Model Setup
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest", 
        temperature=0
    )

    db = SQLDatabase.from_uri(DB_URI)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    print("✅ Siap!")

except Exception as e:
    print(f"❌ Error Setup: {e}")

# --- PERUBAHAN PENTING DI SINI (SYSTEM PROMPT) ---
# Kita paksa dia pakai Step-by-Step agar tidak halusinasi ID
system_instruction = """
Kamu adalah Data Analyst Nutrisense.
Tugas: Menjawab pertanyaan user dengan data dari database SQL.

ATURAN WAJIB (STRICT RULES):
1. JANGAN PERNAH menebak ID makanan. Kamu TIDAK TAHU ID sebelum mengeceknya.
2. Langkah PERTAMA selalu: Cek tabel `makanan` menggunakan `ILIKE`.
   Contoh: SELECT * FROM makanan WHERE nama_makanan ILIKE '%anggur%';
3. Setelah dapat ID dari langkah 2, baru cari gizinya di tabel `gizi`.
4. Jika Query SQL error, coba perbaiki query-nya.
5. Jawab dalam Bahasa Indonesia yang ramah.
6. Jika error parsing terjadi, ulangi dan berikan jawaban final langsung.
"""

user_memories = {}

def get_ai_response(user_id, user_message):
    if user_id not in user_memories:
        user_memories[user_id] = []
    
    # History pendek
    history = user_memories[user_id][-2:]
    context_str = "\n".join([f"{msg.type}: {msg.content}" for msg in history])
    
    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=True, # Kita lihat log-nya
        agent_type="zero-shot-react-description",
        handle_parsing_errors="Check your output and make sure it returns a string as Final Answer.", # <-- AUTO FIX ERROR
        prefix=system_instruction
    )

    try:
        full_query = f"Context:\n{context_str}\n\nUser Question: {user_message}"
        result = agent.invoke({"input": full_query})
        response = result['output']
        
        user_memories[user_id].append(HumanMessage(content=user_message))
        user_memories[user_id].append(AIMessage(content=response))
        return response

    except Exception as e:
        print(f"⚠️ ERROR SYSTEM: {e}")
        return "Maaf, data tidak ditemukan atau ada gangguan sistem. Coba nama makanan lain."

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    print(f"📩 Chat Masuk: {message.text}")
    bot.send_chat_action(message.chat.id, 'typing')
    jawaban = get_ai_response(message.chat.id, message.text)
    bot.reply_to(message, jawaban)

print("✅ Bot Jalan!")
bot.infinity_polling()