import os
import json
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

app = Flask(__name__)

# --- FIX: Menggunakan SQLite lokal biar aman dan gratis di Hugging Face ---
DATABASE_URL = os.environ.get("DATABASE_URL")        
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):    
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:    
    # Mengarah langsung ke file nutrisi.db yang kamu upload
    DATABASE_URL = 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'nutrisi.db')

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.slthdjtwnlubfbfbynax:Igfirli_cintam1ng@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 3600,
    'pool_pre_ping': True
}

IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), "static", "images")
os.makedirs(IMAGE_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = IMAGE_FOLDER

db = SQLAlchemy(app)
ALLOWED_CATEGORIES = {"buah", "sayur", "daging", "beras", "ikan", "biji-bijian", "umbi-umbian", "rempah-rempah", "olahan-produk"}

# --- MODEL DATABASE ---
class Makanan(db.Model):    
    id = db.Column(db.Integer, primary_key=True)    
    nama = db.Column(db.String(100), unique=True, nullable=False, index=True)    
    kategori = db.Column(db.String(50), nullable=False, index=True)     
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
    nama_gizi = db.Column(db.String(50), nullable=False, index=True) 
    nilai = db.Column(db.Float, nullable=False)    
    satuan = db.Column(db.String(20), nullable=False)    
    makanan_id = db.Column(db.Integer, db.ForeignKey('makanan.id'), nullable=False, index=True)

class Resep(db.Model):    
    id = db.Column(db.Integer, primary_key=True)    
    judul = db.Column(db.String(200), unique=True, nullable=False, index=True)    
    deskripsi = db.Column(db.Text, nullable=True)    
    gambar = db.Column(db.String(255), nullable=True)    
    bahan_entries = db.relationship('BahanResep', backref='resep', lazy=True, cascade="all, delete-orphan")

class BahanResep(db.Model):    
    id = db.Column(db.Integer, primary_key=True)    
    berat = db.Column(db.Float, nullable=False)    
    resep_id = db.Column(db.Integer, db.ForeignKey('resep.id'), nullable=False, index=True)    
    makanan_id = db.Column(db.Integer, db.ForeignKey('makanan.id'), nullable=False, index=True)    
    makanan_obj = db.relationship('Makanan', lazy='joined')

# --- ROUTES ---
@app.route("/")
def index():    
    selected_kategori = request.args.get('kategori')    
    query = Makanan.query.options(joinedload(Makanan.gizi_entries)).order_by(Makanan.nama)    
    if selected_kategori:        
        query = query.filter_by(kategori=selected_kategori)        
    makanan_list = query.all()    
    makanan_dict = {m.nama: m.to_dict() for m in makanan_list}    
    return render_template("index.html", makanan=makanan_dict, selected_kategori=selected_kategori)

@app.route('/kalkulator')
def form_kalkulator():    
    return render_template('kalkulator.html')

@app.route('/hitung', methods=['POST'])
def hitung_gizi():    
    try:        
        umur = int(request.form.get('umur'))        
        berat = float(request.form.get('berat'))        
        tinggi = float(request.form.get('tinggi'))        
        gender = request.form.get('gender')        
        faktor_aktivitas = float(request.form.get('aktivitas'))        
        bmr = 0        
        if gender == 'pria':            
            bmr = 88.362 + (13.397 * berat) + (4.799 * tinggi) - (5.677 * umur)        
        elif gender == 'wanita':            
            bmr = 447.593 + (9.247 * berat) + (3.098 * tinggi) - (4.330 * umur)        
        tdee = bmr * faktor_aktivitas                
        hasil = {            
            "kalori": round(tdee),            
            "protein": round((tdee * 0.15) / 4),            
            "karbohidrat": round((tdee * 0.60) / 4),            
            "lemak": round((tdee * 0.25) / 9)        
        }        
        return render_template('kalkulator.html', hasil=hasil, input_data=request.form)    
    except (ValueError, TypeError):        
        return render_template('kalkulator.html', error="Input tidak valid. Pastikan semua kolom diisi dengan angka.")

@app.route("/user")
def user_form():    
    query = Makanan.query.options(joinedload(Makanan.gizi_entries)).order_by(Makanan.nama).all()    
    makanan_dict = {m.nama: m.to_dict() for m in query}    
    return render_template("user.html", makanan=makanan_dict)

@app.route("/admin/")
def admin_form():
    return render_template("admin.html")

@app.route("/resep/<bahan_utama>")
def resep_by_bahan(bahan_utama):    
    list_resep = Resep.query\
        .join(BahanResep)\
        .join(Makanan)\
        .filter(Makanan.nama == bahan_utama.lower())\
        .options(            
            joinedload(Resep.bahan_entries)            
            .joinedload(BahanResep.makanan_obj)            
            .joinedload(Makanan.gizi_entries)        
        ).all()        
    hasil = []    
    for resep in list_resep:        
        total_gizi = {}        
        satuan_info = {}        
        bahan_list_for_template = []        
        langkah_langkah = [langkah.strip() for langkah in (resep.deskripsi or "").split('\n') if langkah.strip()]
        for bahan in resep.bahan_entries:            
            gizi_per_bahan = {                
                g.nama_gizi: {"nilai": g.nilai, "satuan": g.satuan}                 
                for g in bahan.makanan_obj.gizi_entries            
            }            
            bahan_list_for_template.append({                
                "nama": bahan.makanan_obj.nama,                 
                "berat": bahan.berat,                
                "gizi_mentah": gizi_per_bahan            
            })            
            for gizi_item in bahan.makanan_obj.gizi_entries:                
                nilai_terhitung = gizi_item.nilai * (bahan.berat / 100.0)                
                total_gizi[gizi_item.nama_gizi] = total_gizi.get(gizi_item.nama_gizi, 0) + nilai_terhitung                
                if gizi_item.nama_gizi not in satuan_info:                    
                    satuan_info[gizi_item.nama_gizi] = gizi_item.satuan        
        hasil.append({            
            "nama_resep": resep.judul,            
            "langkah": langkah_langkah,              
            "bahan": bahan_list_for_template,            
            "gizi": {k: round(v, 2) for k, v in total_gizi.items()},            
            "satuan": satuan_info,            
            "gambar": resep.gambar or ""        
        })    
    return render_template("resep.html", bahan=bahan_utama, hasil=hasil)

@app.route("/kategori/<nama_kategori>")
def tampilkan_kategori(nama_kategori):    
    makanan_dalam_kategori = Makanan.query\
        .options(joinedload(Makanan.gizi_entries))\
        .filter_by(kategori=nama_kategori)\
        .order_by(Makanan.nama).all()        
    return render_template("detail_kategori.html", makanan_list=makanan_dalam_kategori, nama_kategori=nama_kategori)

@app.route("/api/hitung-total", methods=["POST"])
def hitung_total_gizi():    
    list_bahan = request.json.get("bahan", [])    
    if not list_bahan:        
        return jsonify({"error": "Daftar bahan tidak boleh kosong."}), 400    
    bahan_dict = {item.get("nama", "").lower().strip(): float(item.get("berat", 0)) for item in list_bahan}    
    nama_bahan_list = list(bahan_dict.keys())    
    makanan_db = Makanan.query.options(joinedload(Makanan.gizi_entries)).filter(Makanan.nama.in_(nama_bahan_list)).all()        
    ditemukan = {m.nama for m in makanan_db}    
    tidak_ditemukan = set(nama_bahan_list) - ditemukan    
    if tidak_ditemukan:        
        return jsonify({"error": f'Bahan "{list(tidak_ditemukan)[0]}" tidak ditemukan.'}), 404    
    total_gizi = {}    
    satuan_info = {}    
    for m in makanan_db:        
        berat = bahan_dict[m.nama]        
        for gizi in m.gizi_entries:            
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
    makanan_persis = Makanan.query.options(joinedload(Makanan.gizi_entries)).filter_by(nama=nama_cari).first()    
    if makanan_persis:        
        return jsonify({"results": [kalkulasi_gizi(makanan_persis, berat)]})    
    rekomendasi_list = Makanan.query.options(joinedload(Makanan.gizi_entries)).filter(Makanan.nama.ilike(f"%{nama_cari}%")).limit(10).all()    
    if rekomendasi_list:        
        return jsonify({"results": [kalkulasi_gizi(item, berat) for item in rekomendasi_list]})    
    return jsonify({"error": f"Makanan '{req.get('nama')}' tidak ditemukan"}), 404

@app.route("/api/admin/list")
def admin_list_makanan():    
    page = request.args.get('page', 1, type=int)    
    per_page = request.args.get('per_page', 20, type=int)     
    pagination = Makanan.query.options(joinedload(Makanan.gizi_entries)).paginate(page=page, per_page=per_page, error_out=False)    
    
    return jsonify({        
        "items": {m.nama: m.to_dict() for m in pagination.items},        
        "total": pagination.total,        
        "page": pagination.page,        
        "pages": pagination.pages    
    })

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
            nama_gizi_bersih, nilai_str_bersih, satuan_bersih = k.strip(), v.strip().replace(",", "."), s.strip()            
            if nama_gizi_bersih and nilai_str_bersih and satuan_bersih:                
                try:                    
                    db.session.add(Gizi(                        
                        nama_gizi=nama_gizi_bersih,                         
                        nilai=float(nilai_str_bersih),                         
                        satuan=satuan_bersih,                         
                        makanan=new_makanan                    
                    ))                
                except ValueError:                    
                    db.session.rollback()                    
                    return jsonify({"success": False, "error": f"Nilai '{v}' tidak valid."}), 400            
            elif any([nama_gizi_bersih, nilai_str_bersih, satuan_bersih]):                
                db.session.rollback()                
                return jsonify({"success": False, "error": "Data gizi tidak lengkap."}), 400                
        
        # --- FIX: Peletakan indentasi commit dipindahkan ke luar loop dengan benar ---
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
        old_nama = request.form.get("old_nama", "").lower().strip()        
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
            nama_gizi_bersih, nilai_str_bersih, satuan_bersih = k.strip(), v.strip().replace(",", "."), s.strip()            
            if nama_gizi_bersih and nilai_str_bersih and satuan_bersih:                
                try:                    
                    db.session.add(Gizi(                        
                        nama_gizi=nama_gizi_bersih,                         
                        nilai=float(nilai_str_bersih),                         
                        satuan=satuan_bersih,                         
                        makanan_id=makanan.id                    
                    ))                
                except ValueError:                    
                    db.session.rollback()                    
                    return jsonify({"success": False, "error": f"Nilai '{v}' tidak valid."}), 400            
            elif any([nama_gizi_bersih, nilai_str_bersih, satuan_bersih]):                
                db.session.rollback()                
                return jsonify({"success": False, "error": "Data gizi tidak lengkap."}), 400        
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

@app.route("/api/admin/list_resep")
def admin_list_resep():    
    resep_list = []    
    query = Resep.query.options(joinedload(Resep.bahan_entries).joinedload(BahanResep.makanan_obj)).order_by(Resep.judul).all()        
    for resep in query:        
        resep_list.append({            
            "judul": resep.judul,            
            "deskripsi": resep.deskripsi,            
            "bahan": [{"nama": b.makanan_obj.nama, "berat": b.berat} for b in resep.bahan_entries],            
            "gambar": resep.gambar or ""          
        })    
    return jsonify(resep_list)

@app.route("/api/admin/add_resep", methods=["POST"])
def admin_add_resep():    
    judul = request.form.get("judul", "").strip()    
    deskripsi = request.form.get("deskripsi", "").strip()    
    try:        
        bahan = json.loads(request.form.get("bahan", "[]"))    
    except json.JSONDecodeError:        
        return jsonify({"success": False, "error": "Format data bahan tidak valid."}), 400    
    if not judul or not bahan:        
        return jsonify({"success": False, "error": "Judul dan bahan wajib diisi"}), 400    
    gambar_filename = ""    
    if "gambar" in request.files:        
        file = request.files["gambar"]        
        if file and file.filename:            
            gambar_filename = secure_filename(f"resep_{judul}_{file.filename}")            
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], gambar_filename))    
    new_resep = Resep(judul=judul, deskripsi=deskripsi, gambar=gambar_filename)    
    db.session.add(new_resep)    
    nama_bahan_list = [item.get("nama", "").lower() for item in bahan]    
    makanan_db = Makanan.query.filter(Makanan.nama.in_(nama_bahan_list)).all()    
    makanan_map = {m.nama: m.id for m in makanan_db}    
    for item in bahan:        
        nama = item.get("nama", "").lower()        
        if nama in makanan_map:            
            db.session.add(BahanResep(berat=float(item.get("berat", 0)), resep=new_resep, makanan_id=makanan_map[nama]))    
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
    try:        
        bahan_baru = json.loads(request.form.get("bahan", "[]"))    
    except json.JSONDecodeError:        
        return jsonify({"success": False, "error": "Format data bahan tidak valid."}), 400    
    if not resep.judul or not bahan_baru:        
        return jsonify({"success": False, "error": "Judul dan bahan wajib diisi"}), 400    
    if "gambar" in request.files:        
        file = request.files["gambar"]        
        if file and file.filename:            
            if resep.gambar and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], resep.gambar)):                
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], resep.gambar))                        
            gambar_filename = secure_filename(f"resep_{resep.judul}_{file.filename}")            
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], gambar_filename))            
            resep.gambar = gambar_filename    
    BahanResep.query.filter_by(resep_id=resep.id).delete()        
    nama_bahan_list = [item.get("nama", "").lower() for item in bahan_baru]    
    makanan_db = Makanan.query.filter(Makanan.nama.in_(nama_bahan_list)).all()    
    makanan_map = {m.nama: m.id for m in makanan_db}    
    for item in bahan_baru:        
        nama = item.get("nama", "").lower()        
        if nama in makanan_map:            
            db.session.add(BahanResep(berat=float(item.get("berat")), resep_id=resep.id, makanan_id=makanan_map[nama]))        
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

@app.route('/gizi/<nama_produk>')
def detail_gizi(nama_produk):    
    nama_dicari = nama_produk.strip().lower()    
    produk_db = Makanan.query.options(joinedload(Makanan.gizi_entries)).filter_by(nama=nama_dicari).first()        
    if not produk_db:        
        return "Produk tidak ditemukan", 404    
    data_siap_pakai = {        
        "nama": produk_db.nama,        
        "gambar": produk_db.gambar,        
        "kalori": 0, "karbo": 0, "protein": 0, "lemak": 0, "vitamin_c": 0    
    }    
    gizi_map = {g.nama_gizi.lower(): g.nilai for g in produk_db.gizi_entries}        
    for nama_gizi, nilai in gizi_map.items():        
        if "energi" in nama_gizi or "kalori" in nama_gizi:            
            data_siap_pakai["kalori"] = nilai        
        elif "karbo" in nama_gizi:            
            data_siap_pakai["karbo"] = nilai        
        elif "protein" in nama_gizi:            
            data_siap_pakai["protein"] = nilai        
        elif "lemak" in nama_gizi:            
            data_siap_pakai["lemak"] = nilai        
        elif "vitamin c" in nama_gizi:            
            data_siap_pakai["vitamin_c"] = nilai    
    return render_template('detail_gizi.html', produk=data_siap_pakai)

@app.before_request
def create_tables():
    db.create_all()
    
    # Deteksi jika database SQLite-nya masih kosong melompong
    if Makanan.query.count() == 0:
        json_path = os.path.join(os.path.dirname(__file__), "data_gizi.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Membaca isi data JSON kamu
                for nama_makanan, detail in data.items():
                    kategori = detail.get("kategori", "Lainnya")
                    gambar = detail.get("gambar", "")
                    
                    # Tambah data Makanan
                    new_makanan = Makanan(
                        nama=nama_makanan.strip(), 
                        kategori=kategori, 
                        gambar=gambar
                    )
                    db.session.add(new_makanan)
                    
                    # Ambil data gizinya (kalori, protein, dll) jika ada
                    gizi_data = detail.get("gizi", {})
                    for nama_gizi, info_gizi in gizi_data.items():
                        # Jika info gizi berbentuk dictionary seperti {"nilai": 10, "satuan": "g"}
                        if isinstance(info_gizi, dict):
                            nilai_gizi = float(info_gizi.get("nilai", 0))
                            satuan_gizi = info_gizi.get("satuan", "g")
                        else:
                            # Jika langsung angka/string tunggal
                            nilai_gizi = float(info_gizi)
                            satuan_gizi = "g"
                            
                        new_gizi = Gizi(
                            nama_gizi=nama_gizi,
                            nilai=nilai_gizi,
                            satuan=satuan_gizi,
                            makanan=new_makanan
                        )
                        db.session.add(new_gizi)
                        
                db.session.commit()
                print("Berhasil mengimpor data dari JSON ke SQLite local!")
            except Exception as e:
                db.session.rollback()
                print(f"Gagal migrasi otomatis: {str(e)}")

if __name__ == "__main__":    
    app.run(host="0.0.0.0", port=7860, debug=False)

app = app