import os
from flask import Flask, request, jsonify, render_template, redirect, send_from_directory
import json
from werkzeug.utils import secure_filename


app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "data_gizi.json")
IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), "static", "images")
os.makedirs(IMAGE_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = IMAGE_FOLDER

# KATEGORI "IKAN" TELAH DITAMBAHKAN DI SINI
ALLOWED_CATEGORIES = {"buah", "sayur", "daging", "beras", "ikan", "biji-bijian", "umbi-umbian", "rempah-rempah"}


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"makanan": {}, "resep": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"makanan": {}, "resep": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def convert_to_backward_compatible(gizi_data):
    result = {}
    for gizi_nama, gizi_info in gizi_data.items():
        if isinstance(gizi_info, dict) and 'nilai' in gizi_info:
            result[gizi_nama] = gizi_info['nilai']
        else:
            result[gizi_nama] = gizi_info
    return result

@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", makanan=data.get("makanan", {}))

@app.route("/user")
def user_form():
    data = load_data()
    return render_template("user.html", makanan=data.get("makanan", {}))

@app.route("/admin")
def admin_form():
    return render_template("admin.html")

@app.route("/api/hitung-total", methods=["POST"])
def hitung_total_gizi():
    req_data = request.json
    list_bahan = req_data.get("bahan", [])

    if not list_bahan:
        return jsonify({"error": "Daftar bahan tidak boleh kosong."}), 400

    data = load_data()
    semua_makanan = data.get("makanan", {})
    
    total_gizi = {}
    satuan_info = {}

    for item in list_bahan:
        nama = item.get("nama", "").lower().strip()
        berat = float(item.get("berat", 0))

        data_makanan = semua_makanan.get(nama)

        if not data_makanan:
            return jsonify({"error": f'Bahan "{item.get("nama")}" tidak ditemukan di database. Pastikan penulisan benar.'}), 404
        
        for gizi_nama, gizi_data in data_makanan.get("gizi", {}).items():
            if isinstance(gizi_data, dict) and 'nilai' in gizi_data:
                nilai_per_100g = gizi_data['nilai']
                satuan = gizi_data.get('satuan', 'g')
            else: 
                nilai_per_100g = gizi_data
                satuan = 'g'

            nilai_terhitung = (nilai_per_100g / 100.0) * berat
            
            total_gizi[gizi_nama] = total_gizi.get(gizi_nama, 0) + nilai_terhitung
            
            if gizi_nama not in satuan_info:
                satuan_info[gizi_nama] = satuan

    total_gizi_rounded = {k: round(v, 2) for k, v in total_gizi.items()}

    return jsonify({
        "total_gizi": total_gizi_rounded,
        "satuan": satuan_info
    })


@app.route("/api/gizi", methods=["POST"])
def get_gizi():
    req = request.json
    nama_cari = req.get("nama", "").lower()
    berat = float(req.get("berat", 0))
    
    if not nama_cari or berat <= 0:
        return jsonify({"error": "Nama makanan dan berat harus diisi dengan benar"}), 400

    data = load_data()
    semua_makanan = data.get("makanan", {})

    def kalkulasi_gizi(item_makanan, berat_gram, nama_asli):
        hasil = {}
        satuan_info = {}
        for k, v in item_makanan["gizi"].items():
            if isinstance(v, dict) and 'nilai' in v:
                nilai_gizi = v['nilai']
                satuan = v.get('satuan', 'g')
            else:
                nilai_gizi = v
                satuan = 'g'  

            hasil[k] = round((nilai_gizi / 100.0) * berat_gram, 2)
            satuan_info[k] = satuan
            
        return {
            "nama": nama_asli.capitalize(),
            "berat": berat_gram,
            "gizi": hasil,
            "satuan": satuan_info,
            "gambar": item_makanan.get("gambar", "")
        }

    makanan_persis = semua_makanan.get(nama_cari)
    if makanan_persis:
        hasil_tunggal = kalkulasi_gizi(makanan_persis, berat, nama_cari)
        return jsonify({"results": [hasil_tunggal]})

    hasil_rekomendasi = []
    for nama_makanan, data_makanan in semua_makanan.items():
        if nama_cari in nama_makanan:
            hasil_item = kalkulasi_gizi(data_makanan, berat, nama_makanan)
            hasil_rekomendasi.append(hasil_item)

    if hasil_rekomendasi:
        return jsonify({"results": hasil_rekomendasi})

    return jsonify({"error": f"Makanan yang mengandung kata '{req.get('nama')}' tidak ditemukan"}), 404

@app.route("/api/admin/add", methods=["POST"])
def admin_add():
    nama = request.form.get("nama", "").lower().strip()
    kategori = request.form.get("kategori", "").lower()
    
    if not nama:
        return jsonify({"success": False, "error": "Nama makanan wajib diisi"}), 400
    
    if kategori not in ALLOWED_CATEGORIES:
        return jsonify({"success": False, "error": "Kategori tidak valid"}), 400

    gizi_keys = request.form.getlist("gizi_nama[]")
    gizi_vals = request.form.getlist("gizi_nilai[]")
    gizi_satuans = request.form.getlist("gizi_satuan[]")
    
    gizi = {}
    for k, v, s in zip(gizi_keys, gizi_vals, gizi_satuans):
        if k and v and s:
            try:
                gizi[k.strip()] = {
                    "nilai": float(v),
                    "satuan": s.strip()
                }
            except ValueError:
                continue

    if not gizi:
        return jsonify({"success": False, "error": "Minimal satu data gizi harus diisi"}), 400

    gambar = ""
    if "gambar" in request.files:
        file = request.files["gambar"]
        if file and file.filename:
            filename = secure_filename(nama + "_" + file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            gambar = filename

    data = load_data()
    if "makanan" not in data:
        data["makanan"] = {}
    
    data["makanan"][nama] = {
        "gizi": gizi, 
        "gambar": gambar, 
        "kategori": kategori
    }
    save_data(data)
    return jsonify({"success": True})

@app.route("/api/admin/delete", methods=["POST"])
def admin_delete():
    req = request.json
    nama = req.get("nama", "").lower()
    data = load_data()
    if nama in data.get("makanan", {}):
        gambar = data["makanan"][nama].get("gambar")
        if gambar:
            try:
                os.remove(os.path.join(IMAGE_FOLDER, gambar))
            except Exception:
                pass
        del data["makanan"][nama]
        save_data(data)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Data tidak ditemukan"}), 404

@app.route("/api/admin/edit", methods=["POST"])
def admin_edit():
    old_nama = request.form.get("old_nama", "").lower()
    nama = request.form.get("nama", "").lower().strip()
    kategori = request.form.get("kategori", "").lower()

    if not nama:
        return jsonify({"success": False, "error": "Nama makanan wajib diisi"}), 400

    if kategori not in ALLOWED_CATEGORIES:
        return jsonify({"success": False, "error": "Kategori tidak valid"}), 400

    gizi_keys = request.form.getlist("gizi_nama[]")
    gizi_vals = request.form.getlist("gizi_nilai[]")
    gizi_satuans = request.form.getlist("gizi_satuan[]")
    
    gizi = {}
    for k, v, s in zip(gizi_keys, gizi_vals, gizi_satuans):
        if k and v and s:
            try:
                gizi[k.strip()] = {
                    "nilai": float(v),
                    "satuan": s.strip()
                }
            except ValueError:
                continue

    if not gizi:
        return jsonify({"success": False, "error": "Minimal satu data gizi harus diisi"}), 400

    data = load_data()
    
    if old_nama not in data.get("makanan", {}):
        return jsonify({"success": False, "error": "Data tidak ditemukan"}), 404

    makanan_data = data["makanan"][old_nama]
    gambar = makanan_data.get("gambar", "")
    if "gambar" in request.files:
        file = request.files["gambar"]
        if file and file.filename:
            filename = secure_filename(nama + "_" + file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            gambar = filename

    if old_nama != nama:
        del data["makanan"][old_nama]

    data["makanan"][nama] = {
        "gizi": gizi, 
        "gambar": gambar, 
        "kategori": kategori
    }
    save_data(data)

    return jsonify({"success": True})

@app.route("/api/admin/list")
def admin_list():
    data = load_data()
    return jsonify(data.get("makanan", {}))

@app.route("/static/images/<filename>")
def serve_image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

@app.route("/api/admin/add_resep", methods=["POST"])
def admin_add_resep():
    req = request.json
    judul = req.get("judul", "").strip()
    deskripsi = req.get("deskripsi", "").strip()
    bahan = req.get("bahan", [])

    if not judul:
        return jsonify({"success": False, "error": "Judul wajib diisi"}), 400

    if not bahan or not isinstance(bahan, list) or len(bahan) == 0:
        return jsonify({"success": False, "error": "Minimal satu bahan wajib ada"}), 400

    # Validasi setiap item di dalam list bahan
    for item in bahan:
        if not (isinstance(item, dict) and "nama" in item and "berat" in item):
            return jsonify({"success": False, "error": "Format data bahan tidak valid."}), 400
        try:
            float(item["berat"])
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": f"Berat untuk '{item['nama']}' harus berupa angka."}), 400

    data = load_data()
    if "resep" not in data:
        data["resep"] = {}

    data["resep"][judul] = {
        "deskripsi": deskripsi,
        "bahan": bahan, 
        "gambar": ""
    }
    save_data(data)
    return jsonify({"success": True})

@app.route("/api/admin/list_resep")
def admin_list_resep():
    data = load_data()
    resep_list = []
    for judul, info in data.get("resep", {}).items():
        resep_list.append({
            "judul": judul,
            "deskripsi": info.get("deskripsi", ""),
            "bahan": info.get("bahan", [])
        })
    return jsonify(resep_list)

@app.route("/api/admin/delete_resep", methods=["POST"])
def admin_delete_resep():
    req = request.json
    nama = req.get("nama", "").strip()
    data = load_data()
    if "resep" in data and nama in data["resep"]:
        gambar = data["resep"][nama].get("gambar")
        if gambar:
            try:
                os.remove(os.path.join(IMAGE_FOLDER, gambar))
            except Exception:
                pass
        del data["resep"][nama]
        save_data(data)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Resep tidak ditemukan"}), 404

@app.route("/api/admin/edit_resep", methods=["POST"])
def admin_edit_resep():
    req = request.json
    old_judul = req.get("old_judul", "").strip()
    judul = req.get("judul", "").strip()
    deskripsi = req.get("deskripsi", "").strip()
    bahan = req.get("bahan", [])

    if not judul or not bahan:
        return jsonify({"success": False, "error": "Judul dan bahan wajib diisi"}), 400
    
    # Validasi sama seperti 'add_resep'
    for item in bahan:
        if not (isinstance(item, dict) and "nama" in item and "berat" in item):
            return jsonify({"success": False, "error": "Format data bahan tidak valid."}), 400

    data = load_data()
    
    if old_judul not in data.get("resep", {}):
        return jsonify({"success": False, "error": "Resep tidak ditemukan"}), 404

    resep_lama = data["resep"].pop(old_judul)

    data["resep"][judul] = {
        "deskripsi": deskripsi,
        "bahan": bahan,
        "gambar": resep_lama.get("gambar", "")
    }
    save_data(data)

    return jsonify({"success": True})

@app.route("/resep/<bahan_utama>")
def resep_by_bahan(bahan_utama):
    data = load_data()
    makanan_db = data.get("makanan", {})
    resep_db = data.get("resep", {})

    hasil = []
    for nama_resep, info in resep_db.items():
        resep_bahan_list = info.get("bahan", [])
        
        bahan_ada = False
        # === PERBAIKAN 1: Cek bahan dengan aman (bisa string atau dict) ===
        for b in resep_bahan_list:
            nama_bahan_resep = ""
            if isinstance(b, dict):
                nama_bahan_resep = b.get("nama", "").lower()
            elif isinstance(b, str):
                nama_bahan_resep = b.lower()
            
            if nama_bahan_resep == bahan_utama.lower():
                bahan_ada = True
                break

        if bahan_ada:
            total_gizi = {}
            satuan_info = {}
            
            for bahan_item in resep_bahan_list:
                nama_bhn = ""
                berat_bhn = 0.0

                # === PERBAIKAN 2: Ambil nama & berat dengan aman ===
                # Jika format baru (dict), ambil nama dan beratnya
                if isinstance(bahan_item, dict):
                    nama_bhn = bahan_item.get("nama", "").lower()
                    berat_bhn = float(bahan_item.get("berat", 0))
                # Jika format lama (str), gunakan nama itu dan asumsikan berat 100g
                elif isinstance(bahan_item, str):
                    nama_bhn = bahan_item.lower()
                    berat_bhn = 100.0 # Asumsi default untuk data lama

                if nama_bhn in makanan_db and berat_bhn > 0:
                    data_makanan = makanan_db[nama_bhn]
                    for gizi_nama, gizi_data in data_makanan.get("gizi", {}).items():
                        nilai_per_100g = float(gizi_data.get('nilai', 0))
                        satuan = gizi_data.get('satuan', 'g')
                        
                        nilai_terhitung = (nilai_per_100g / 100.0) * berat_bhn
                        total_gizi[gizi_nama] = total_gizi.get(gizi_nama, 0) + nilai_terhitung
                        
                        if gizi_nama not in satuan_info:
                            satuan_info[gizi_nama] = satuan

            hasil.append({
                "nama_resep": nama_resep,
                "deskripsi": info.get("deskripsi", ""),
                "bahan": resep_bahan_list,
                "gizi": {k: round(v, 2) for k, v in total_gizi.items()},
                "satuan": satuan_info,
                "gambar": info.get("gambar", "")
            })

    return render_template("resep.html", bahan=bahan_utama, hasil=hasil)

if __name__ == "__main__":
    app.run(debug=False)