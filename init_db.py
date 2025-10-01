from flask import Flask, request, jsonify
import sqlite3, json

app = Flask(__name__)
DB = "nutrisi.db"

# === Helper koneksi DB ===
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# === INIT TABEL (buat kalau belum ada) ===
def init_db():
    conn = get_db()
    c = conn.cursor()

    # Tabel makanan
    c.execute("""
    CREATE TABLE IF NOT EXISTS makanan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT UNIQUE,
        kategori TEXT,
        berat REAL DEFAULT 0
    )
    """)

    # Tabel gizi
    c.execute("""
    CREATE TABLE IF NOT EXISTS gizi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        makanan_id INTEGER,
        nama_gizi TEXT,
        nilai REAL,
        FOREIGN KEY(makanan_id) REFERENCES makanan(id)
    )
    """)

    # Tabel resep
    c.execute("""
    CREATE TABLE IF NOT EXISTS resep (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_resep TEXT,
        gambar TEXT,
        bahan TEXT, -- simpan JSON string
        gizi TEXT   -- simpan JSON string
    )
    """)

    conn.commit()
    conn.close()

# === API MAKANAN ===
@app.route("/api/admin/list")
def list_makanan():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM makanan")
    makanan_list = {}
    for row in c.fetchall():
        makanan_id = row["id"]
        nama = row["nama"]
        c.execute("SELECT nama_gizi, nilai FROM gizi WHERE makanan_id=?", (makanan_id,))
        gizi = {g["nama_gizi"]: g["nilai"] for g in c.fetchall()}
        makanan_list[nama] = {"kategori": row["kategori"], "gizi": gizi}
    conn.close()
    return jsonify(makanan_list)

@app.route("/api/admin/add", methods=["POST"])
def add_makanan():
    nama = request.form.get("nama")
    kategori = request.form.get("kategori", "")
    gizi_nama = request.form.getlist("gizi_nama[]")
    gizi_nilai = request.form.getlist("gizi_nilai[]")

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO makanan (nama, kategori, berat) VALUES (?, ?, ?)", (nama, kategori, 0))
    makanan_id = c.lastrowid

    for i in range(len(gizi_nama)):
        c.execute("INSERT INTO gizi (makanan_id, nama_gizi, nilai) VALUES (?, ?, ?)",
                  (makanan_id, gizi_nama[i], gizi_nilai[i]))

    conn.commit()
    conn.close()
    return jsonify({"success": True})

# === API RESEP ===
@app.route("/api/admin/list_resep")
def list_resep():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM resep")
    resep_list = []
    for row in c.fetchall():
        try:
            bahan_dict = json.loads(row["bahan"]) if row["bahan"] else {}
        except:
            bahan_dict = {}
        try:
            gizi_dict = json.loads(row["gizi"]) if row["gizi"] else {}
        except:
            gizi_dict = {}

        resep_list.append({
            "id": row["id"],
            "nama_resep": row["nama_resep"],
            "gambar": row["gambar"],
            "bahan": bahan_dict,
            "gizi": gizi_dict
        })
    conn.close()
    return jsonify(resep_list)

@app.route("/api/admin/add_resep", methods=["POST"])
def add_resep():
    nama_resep = request.form.get("nama_resep")
    gambar = request.form.get("gambar", "")
    bahan = request.form.get("bahan")  # JSON string
    gizi = request.form.get("gizi")    # JSON string

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO resep (nama_resep, gambar, bahan, gizi) VALUES (?, ?, ?, ?)",
              (nama_resep, gambar, bahan, gizi))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/admin/delete_resep", methods=["POST"])
def delete_resep():
    resep_id = request.json.get("id")
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM resep WHERE id=?", (resep_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# === MAIN ===
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
