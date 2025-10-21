import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
import json # Pastikan json diimpor di bagian atas file Anda
from werkzeug.utils import secure_filename # Pastikan ini juga diimpor

# =================================================================================
# KONFIGURASI APLIKASI
# =================================================================================

app = Flask(__name__)

# --- ⚙️ KONFIGURASI DATABASE POSTGRESQL ---
# Ganti nilai di bawah ini sesuai dengan konfigurasi PostgreSQL Anda di pgAdmin
DB_USER = "postgres"
DB_PASSWORD = "password354160"  # <-- GANTI DENGAN PASSWORD ANDA
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "nutrisense"           # <-- NAMA DATABASE YANG ANDA BUAT

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- KONFIGURASI FOLDER UPLOAD ---
IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), "static", "images")
os.makedirs(IMAGE_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = IMAGE_FOLDER

# --- Inisialisasi SQLAlchemy ---
db = SQLAlchemy(app)

# --- Kategori yang diizinkan ---
ALLOWED_CATEGORIES = {"buah", "sayur", "daging", "beras", "ikan", "biji-bijian", "umbi-umbian", "rempah-rempah"}


# =================================================================================
# MODEL DATABASE (Struktur Tabel)
# =================================================================================

class Makanan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), unique=True, nullable=False, index=True)
    kategori = db.Column(db.String(50), nullable=False)
    gambar = db.Column(db.String(255), nullable=True)
    gizi_entries = db.relationship('Gizi', backref='makanan', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "gizi": {g.nama_gizi: {"nilai": g.nilai, "satuan": g.satuan} for g in self.gizi_entries},
            "gambar": self.gambar,
            "kategori": self.kategori
        }

class Gizi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_gizi = db.Column(db.String(50), nullable=False)
    nilai = db.Column(db.Float, nullable=False)
    satuan = db.Column(db.String(20), nullable=False)
    makanan_id = db.Column(db.Integer, db.ForeignKey('makanan.id'), nullable=False)

class Resep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(200), unique=True, nullable=False)
    deskripsi = db.Column(db.Text, nullable=True)
    gambar = db.Column(db.String(255), nullable=True)
    bahan_entries = db.relationship('BahanResep', backref='resep', lazy=True, cascade="all, delete-orphan")

class BahanResep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    berat = db.Column(db.Float, nullable=False)
    resep_id = db.Column(db.Integer, db.ForeignKey('resep.id'), nullable=False)
    makanan_id = db.Column(db.Integer, db.ForeignKey('makanan.id'), nullable=False)
    makanan_obj = db.relationship('Makanan', lazy='joined')


# =================================================================================
# ROUTES UNTUK TAMPILAN (FRONTEND)
# =================================================================================

@app.route("/")
def index():
    makanan_dict = {m.nama: m.to_dict() for m in Makanan.query.order_by(Makanan.nama).all()}
    return render_template("index.html", makanan=makanan_dict)

@app.route("/user")
def user_form():
    makanan_dict = {m.nama: m.to_dict() for m in Makanan.query.order_by(Makanan.nama).all()}
    return render_template("user.html", makanan=makanan_dict)

@app.route("/admin")
def admin_form():
    return render_template("admin.html")

@app.route("/resep/<bahan_utama>")
def resep_by_bahan(bahan_utama):
    # Query resep yang mengandung bahan utama menggunakan JOIN
    list_resep = Resep.query.join(BahanResep).join(Makanan).filter(Makanan.nama == bahan_utama.lower()).all()
    
    hasil = []
    for resep in list_resep:
        total_gizi = {}
        satuan_info = {}
        bahan_list_for_template = []

        for bahan in resep.bahan_entries:
            bahan_list_for_template.append({"nama": bahan.makanan_obj.nama, "berat": bahan.berat})
            for gizi_item in bahan.makanan_obj.gizi_entries:
                nilai_terhitung = (gizi_item.nilai / 100.0) * bahan.berat
                total_gizi[gizi_item.nama_gizi] = total_gizi.get(gizi_item.nama_gizi, 0) + nilai_terhitung
                if gizi_item.nama_gizi not in satuan_info:
                    satuan_info[gizi_item.nama_gizi] = gizi_item.satuan
        
        # --- PENAMBAHAN BARU DI SINI ---
        # Ambil deskripsi dan ubah menjadi daftar langkah-langkah
        deskripsi_teks = resep.deskripsi or ""
        # Pecah teks berdasarkan baris baru, dan hapus baris yang kosong
        langkah_langkah = [langkah.strip() for langkah in deskripsi_teks.split('\n') if langkah.strip()]
        # --- AKHIR PENAMBAHAN ---

        hasil.append({
            "nama_resep": resep.judul,
            "langkah": langkah_langkah,  # Kirim daftar langkah ke template
            "bahan": bahan_list_for_template,
            "gizi": {k: round(v, 2) for k, v in total_gizi.items()},
            "satuan": satuan_info,
            "gambar": resep.gambar or ""
        })

    return render_template("resep.html", bahan=bahan_utama, hasil=hasil)


# =================================================================================
# API ENDPOINTS (UNTUK JAVASCRIPT)
# =================================================================================

# --- API untuk Kalkulasi Gizi ---
@app.route("/api/hitung-total", methods=["POST"])
def hitung_total_gizi():
    list_bahan = request.json.get("bahan", [])
    if not list_bahan:
        return jsonify({"error": "Daftar bahan tidak boleh kosong."}), 400

    total_gizi = {}
    satuan_info = {}
    for item in list_bahan:
        nama = item.get("nama", "").lower().strip()
        berat = float(item.get("berat", 0))
        data_makanan = Makanan.query.filter_by(nama=nama).first()

        if not data_makanan:
            return jsonify({"error": f'Bahan "{item.get("nama")}" tidak ditemukan.'}), 404
        
        for gizi in data_makanan.gizi_entries:
            nilai_terhitung = (gizi.nilai / 100.0) * berat
            total_gizi[gizi.nama_gizi] = total_gizi.get(gizi.nama_gizi, 0) + nilai_terhitung
            if gizi.nama_gizi not in satuan_info:
                satuan_info[gizi.nama_gizi] = gizi.satuan

    return jsonify({
        "total_gizi": {k: round(v, 2) for k, v in total_gizi.items()},
        "satuan": satuan_info
    })

@app.route("/api/gizi", methods=["POST"])
def get_gizi():
    req = request.json
    nama_cari = req.get("nama", "").lower().strip()
    berat = float(req.get("berat", 0))

    if not nama_cari or berat <= 0:
        return jsonify({"error": "Nama makanan dan berat harus valid"}), 400
    
    def kalkulasi_gizi(item, berat_gram):
        gizi_calc = {g.nama_gizi: round((g.nilai / 100.0) * berat_gram, 2) for g in item.gizi_entries}
        satuan_info = {g.nama_gizi: g.satuan for g in item.gizi_entries}
        return {
            "nama": item.nama.capitalize(), "berat": berat_gram, "gizi": gizi_calc,
            "satuan": satuan_info, "gambar": item.gambar or ""
        }

    makanan_persis = Makanan.query.filter_by(nama=nama_cari).first()
    if makanan_persis:
        return jsonify({"results": [kalkulasi_gizi(makanan_persis, berat)]})

    rekomendasi_list = Makanan.query.filter(Makanan.nama.ilike(f"%{nama_cari}%")).limit(10).all()
    if rekomendasi_list:
        return jsonify({"results": [kalkulasi_gizi(item, berat) for item in rekomendasi_list]})

    return jsonify({"error": f"Makanan '{req.get('nama')}' tidak ditemukan"}), 404

# --- API CRUD untuk Makanan ---
@app.route("/api/admin/list")
def admin_list_makanan():
    return jsonify({m.nama: m.to_dict() for m in Makanan.query.all()})

@app.route("/api/admin/add", methods=["POST"])
def admin_add_makanan():
    try:
        nama = request.form.get("nama", "").lower().strip()
        kategori = request.form.get("kategori", "").lower()
        if not nama or kategori not in ALLOWED_CATEGORIES:
            return jsonify({"success": False, "error": "Nama dan kategori valid wajib diisi"}), 400

        filename = ""
        if "gambar" in request.files and request.files["gambar"].filename:
            file = request.files["gambar"]
            filename = secure_filename(f"{nama}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_makanan = Makanan(nama=nama, kategori=kategori, gambar=filename)
        db.session.add(new_makanan)

        gizi_keys = request.form.getlist("gizi_nama[]")
        gizi_vals = request.form.getlist("gizi_nilai[]")
        gizi_satuans = request.form.getlist("gizi_satuan[]")
        for k, v, s in zip(gizi_keys, gizi_vals, gizi_satuans):
            if k and v and s:
                db.session.add(Gizi(nama_gizi=k.strip(), nilai=float(v), satuan=s.strip(), makanan=new_makanan))
        
        db.session.commit()
        return jsonify({"success": True})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "error": f"Nama makanan '{nama}' sudah ada."}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/admin/edit", methods=["POST"])
def admin_edit_makanan():
    try:
        old_nama = request.form.get("old_nama", "").lower()
        makanan = Makanan.query.filter_by(nama=old_nama).first()
        if not makanan:
            return jsonify({"success": False, "error": "Data lama tidak ditemukan"}), 404

        makanan.nama = request.form.get("nama", "").lower().strip()
        makanan.kategori = request.form.get("kategori", "").lower()
        if not makanan.nama or makanan.kategori not in ALLOWED_CATEGORIES:
            return jsonify({"success": False, "error": "Nama dan kategori baru wajib valid"}), 400

        if "gambar" in request.files and request.files["gambar"].filename:
            if makanan.gambar and os.path.exists(os.path.join(IMAGE_FOLDER, makanan.gambar)):
                os.remove(os.path.join(IMAGE_FOLDER, makanan.gambar))
            file = request.files["gambar"]
            filename = secure_filename(f"{makanan.nama}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            makanan.gambar = filename

        Gizi.query.filter_by(makanan_id=makanan.id).delete()
        gizi_keys = request.form.getlist("gizi_nama[]")
        gizi_vals = request.form.getlist("gizi_nilai[]")
        gizi_satuans = request.form.getlist("gizi_satuan[]")
        for k, v, s in zip(gizi_keys, gizi_vals, gizi_satuans):
            if k and v and s:
                db.session.add(Gizi(nama_gizi=k.strip(), nilai=float(v), satuan=s.strip(), makanan_id=makanan.id))

        db.session.commit()
        return jsonify({"success": True})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "error": f"Nama makanan '{makanan.nama}' sudah digunakan."}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/admin/delete", methods=["POST"])
def admin_delete_makanan():
    nama = request.json.get("nama", "").lower()
    makanan = Makanan.query.filter_by(nama=nama).first()
    if makanan:
        if makanan.gambar and os.path.exists(os.path.join(IMAGE_FOLDER, makanan.gambar)):
            os.remove(os.path.join(IMAGE_FOLDER, makanan.gambar))
        db.session.delete(makanan)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Data tidak ditemukan"}), 404

# --- API CRUD untuk Resep ---
@app.route("/api/admin/list_resep")
def admin_list_resep():
    resep_list = []
    for resep in Resep.query.order_by(Resep.judul).all():
        resep_list.append({
            "judul": resep.judul,
            "deskripsi": resep.deskripsi,
            "bahan": [{"nama": b.makanan_obj.nama, "berat": b.berat} for b in resep.bahan_entries],
            "gambar": resep.gambar or ""  # TAMBAHKAN INI untuk mengirim nama file gambar
        })
    return jsonify(resep_list)

@app.route("/api/admin/add_resep", methods=["POST"])
def admin_add_resep():
    # Mengambil data dari form, bukan JSON
    judul = request.form.get("judul", "").strip()
    deskripsi = request.form.get("deskripsi", "").strip()
    # Mengambil string JSON bahan dan mengubahnya menjadi list python
    bahan_str = request.form.get("bahan", "[]")
    try:
        bahan = json.loads(bahan_str)
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "Format data bahan tidak valid."}), 400

    if not judul or not bahan:
        return jsonify({"success": False, "error": "Judul dan bahan wajib diisi"}), 400

    # Proses upload gambar
    gambar_filename = ""
    if "gambar" in request.files:
        file = request.files["gambar"]
        if file and file.filename:
            # Gunakan judul resep untuk nama file agar unik
            gambar_filename = secure_filename(f"resep_{judul}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], gambar_filename))

    # Simpan ke database (Model Resep Anda)
    new_resep = Resep(
        judul=judul,
        deskripsi=deskripsi,
        gambar=gambar_filename
    )
    db.session.add(new_resep)

    for item in bahan:
        makanan = Makanan.query.filter_by(nama=item.get("nama", "").lower()).first()
        if makanan:
            new_bahan = BahanResep(
                berat=float(item.get("berat", 0)),
                resep=new_resep,
                makanan_id=makanan.id
            )
            db.session.add(new_bahan)

    try:
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route("/api/admin/edit_resep", methods=["POST"])
def admin_edit_resep():
    old_judul = request.form.get("old_judul", "").strip()
    resep = Resep.query.filter_by(judul=old_judul).first()
    if not resep:
        return jsonify({"success": False, "error": "Resep tidak ditemukan"}), 404

    resep.judul = request.form.get("judul", "").strip()
    resep.deskripsi = request.form.get("deskripsi", "").strip()
    bahan_str = request.form.get("bahan", "[]")
    try:
        bahan_baru = json.loads(bahan_str)
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "Format data bahan tidak valid."}), 400

    if not resep.judul or not bahan_baru:
        return jsonify({"success": False, "error": "Judul dan bahan wajib diisi"}), 400

    # Handle gambar baru
    if "gambar" in request.files:
        file = request.files["gambar"]
        if file and file.filename:
            # Hapus gambar lama jika ada
            if resep.gambar and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], resep.gambar)):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], resep.gambar))
            
            # Simpan gambar baru
            gambar_filename = secure_filename(f"resep_{resep.judul}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], gambar_filename))
            resep.gambar = gambar_filename

    # Hapus bahan lama dan tambahkan yang baru
    BahanResep.query.filter_by(resep_id=resep.id).delete()
    for item in bahan_baru:
        makanan = Makanan.query.filter_by(nama=item.get("nama", "").lower()).first()
        if makanan:
            db.session.add(BahanResep(berat=float(item.get("berat")), resep_id=resep.id, makanan_id=makanan.id))
    
    try:
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route("/api/admin/delete_resep", methods=["POST"])
def admin_delete_resep():
    judul = request.json.get("nama", "").strip()
    resep = Resep.query.filter_by(judul=judul).first()
    if resep:
        # Hapus file gambar terkait jika ada
        if resep.gambar and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], resep.gambar)):
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], resep.gambar))
            except OSError as e:
                print(f"Error removing file: {e}")
        
        db.session.delete(resep)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Resep tidak ditemukan"}), 404

@app.route("/static/images/<filename>")
def serve_image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)


# =================================================================================
# MENJALANKAN APLIKASI
# =================================================================================

if __name__ == "__main__":
    # Penting: Pastikan Anda sudah membuat tabel di database sebelum menjalankan aplikasi
    # Buka terminal Python dan jalankan:
    # from app import app, db
    # with app.app_context():
    #     db.create_all()
    app.run(debug=False) # Gunakan debug=True untuk pengembangan