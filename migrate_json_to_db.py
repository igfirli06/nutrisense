import json
import os

# Mengimpor semua yang kita butuhkan dari file aplikasi utama
from app import app, db, Makanan, Gizi, Resep, BahanResep

# Lokasi file JSON lama Anda
DATA_FILE = os.path.join(os.path.dirname(__file__), "data_gizi.json")

def load_old_data():
    """Fungsi untuk membaca data dari file JSON lama."""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            print("Membaca file data_gizi.json...")
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("Error: File data_gizi.json tidak ditemukan atau isinya tidak valid.")
        return None

def migrate_data():
    """Fungsi utama untuk memindahkan data dari JSON ke database."""
    old_data = load_old_data()
    if not old_data:
        return

    # Gunakan app_context agar bisa berinteraksi dengan database
    with app.app_context():
        print("Memulai proses migrasi ke database PostgreSQL...")
        
        print("Membersihkan data lama di database...")
        BahanResep.query.delete()
        Resep.query.delete()
        Gizi.query.delete()
        Makanan.query.delete()
        db.session.commit()

        # --- MIGRASI DATA MAKANAN & GIZI ---
        makanan_data = old_data.get("makanan", {})
        print(f"Menemukan {len(makanan_data)} data makanan untuk dimigrasi.")
        for nama_makanan, info in makanan_data.items():
            new_makanan = Makanan(
                nama=nama_makanan.lower().strip(),
                kategori=info.get("kategori", "lainnya"),
                gambar=info.get("gambar", "")
            )
            db.session.add(new_makanan)
            
            for nama_gizi, gizi_info in info.get("gizi", {}).items():
                new_gizi = Gizi(
                    nama_gizi=nama_gizi,
                    nilai=gizi_info.get("nilai", 0),
                    satuan=gizi_info.get("satuan", "g"),
                    makanan=new_makanan
                )
                db.session.add(new_gizi)
        
        # --- MIGRASI DATA RESEP & BAHAN ---
        resep_data = old_data.get("resep", {})
        print(f"Menemukan {len(resep_data)} data resep untuk dimigrasi.")
        for judul_resep, info in resep_data.items():
            new_resep = Resep(
                judul=judul_resep.strip(),
                deskripsi=info.get("deskripsi", ""),
                gambar=info.get("gambar", "")
            )
            db.session.add(new_resep)

            # --- PERBAIKAN DI BAGIAN INI ---
            # Cek format bahan (bisa string atau dictionary)
            for bahan_item in info.get("bahan", []):
                nama_bahan = ""
                berat_bahan = 0.0

                if isinstance(bahan_item, dict):
                    # Format baru: {"nama": "...", "berat": ...}
                    nama_bahan = bahan_item.get("nama", "").lower().strip()
                    berat_bahan = float(bahan_item.get("berat", 0))
                elif isinstance(bahan_item, str):
                    # Format lama: "..."
                    nama_bahan = bahan_item.lower().strip()
                    berat_bahan = 1.0 # Asumsi 1 buah/siung jika berat tidak ada
                else:
                    # Lewati jika format tidak dikenali
                    continue
                
                # Lanjutkan proses dengan data yang sudah diseragamkan
                if nama_bahan:
                    makanan_obj = Makanan.query.filter_by(nama=nama_bahan).first()
                    if makanan_obj:
                        new_bahan = BahanResep(
                            berat=berat_bahan,
                            resep=new_resep,
                            makanan_id=makanan_obj.id
                        )
                        db.session.add(new_bahan)
                    else:
                        print(f"PERINGATAN: Bahan '{nama_bahan}' untuk resep '{judul_resep}' tidak ditemukan di data makanan. Bahan ini dilewati.")

        # Simpan semua perubahan ke database
        try:
            db.session.commit()
            print("✅ SUKSES! Semua data telah berhasil dipindahkan ke database PostgreSQL.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ GAGAL! Terjadi error saat menyimpan data: {e}")

if __name__ == "__main__":
    migrate_data()