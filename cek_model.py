import google.generativeai as genai

# --- MASUKKAN API KEY KAMU DI SINI ---
API_KEY = "AIzaSyBiq5tnecewJQk1j8KhagOCJXKy4czsX8c"

genai.configure(api_key=API_KEY)

print("🔍 Sedang mengecek daftar model yang tersedia untukmu...")

try:
    available_models = []
    for m in genai.list_models():
        # Kita cari model yang bisa generate text (chat)
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ DITEMUKAN: {m.name}")
            available_models.append(m.name)

    print("\n-------------------------------------------")
    if 'models/gemini-1.5-flash' in available_models:
        print("🎉 KABAR BAIK: Akunmu SUDAH PUNYA 'gemini-1.5-flash'!")
        print("Solusi: Pastikan library di-update dan nama model di kodingan benar.")
    elif 'models/gemini-pro' in available_models:
        print("⚠️ Info: Kamu cuma punya 'gemini-pro'. Gunakan nama itu di kodingan.")
    else:
        print("❌ Waduh: Tidak ada model Gemini yang aktif. Cek API Key / Billing.")

except Exception as e:
    print(f"❌ ERROR KONEKSI: {e}")
    print("Kemungkinan API Key salah atau Internet bermasalah.")