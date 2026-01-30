Tech stack: 
1. Backend Framework
Python (Flask): Framework utama yang digunakan untuk menangani routing, logika bisnis (kalkulasi gizi), dan integrasi API.
Werkzeug: Digunakan untuk utilitas keamanan file (seperti secure_filename) saat mengunggah gambar makanan atau resep.

2. Database & ORM
PostgreSQL: Sistem manajemen database relasional (RDBMS) yang digunakan sebagai media penyimpanan data (terlihat dari konfigurasi port 5432).
SQLAlchemy (Flask-SQLAlchemy): Library ORM (Object Relational Mapper) yang digunakan untuk berinteraksi dengan database menggunakan objek Python, bukan query SQL mentah.
Optimization Tech: Kode ini menggunakan teknik Eager Loading (joinedload). Ini adalah optimasi penting untuk mencegah masalah N+1 Query, sehingga pengambilan data relasi (seperti makanan beserta daftar gizinya) menjadi sangat cepat.

3. Frontend & Templating
Jinja2 (Flask Templates): Mesin templating yang digunakan untuk merender file HTML secara dinamis (seperti index.html, kalkulator.html, dan resep.html).
JSON: Digunakan sebagai format pertukaran data antara Frontend dan Backend, terutama pada API admin dan kalkulasi total gizi.

4. Logic & Features
Medical Calculation: Implementasi rumus kesehatan nyata untuk menghitung BMR (Basal Metabolic Rate) dan TDEE (Total Daily Energy Expenditure) berdasarkan input jenis kelamin, berat, tinggi, dan usia.
Image Handling: Menggunakan sistem penyimpanan lokal (os.makedirs) untuk mengelola aset gambar makanan dan resep di folder /static/images.

Ringkasan Arsitektur Data
Secara struktural, kode ini memiliki skema database yang saling terhubung:
Makanan: Menyimpan data dasar (nama, kategori, gambar).
Gizi: Terhubung ke tabel Makanan (menyimpan nilai protein, kalori, dll).
Resep: Menyimpan data judul dan deskripsi cara memasak.
BahanResep: Tabel penghubung antara Resep dan Makanan untuk menghitung total gizi dalam satu masakan.
