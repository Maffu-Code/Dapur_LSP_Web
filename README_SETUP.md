# Sistem Informasi Restoran Dapur Ina Aina

Aplikasi web untuk mengelola pemesanan, transaksi penjualan, stok produk, dan
laporan penjualan pada restoran Dapur Ina Aina. Dibuat untuk ujikom Associate
Programmer LSP Universitas Gunadarma.

Aplikasi dijalankan secara lokal (tanpa deployment) dengan satu berkas basis
data SQLite, dan seluruh aset tampilan disimpan di dalam proyek sehingga
aplikasi tetap berjalan walau komputer lab tidak terhubung ke internet.

## Teknologi

| Bagian | Keterangan |
| --- | --- |
| Bahasa | Python 3.11 |
| Framework | Django 5.0.14 |
| Basis data | SQLite (satu berkas: `db.sqlite3`) |
| Tampilan | Django Templates + HTML + CSS + JavaScript, Bootstrap 5 (lokal) |
| Pengujian | pytest dan pytest-django |

Tanpa Composer, npm, atau Docker. Tanpa CDN. Dependensi hanya Django dan pytest
(lihat `requirements.txt`).

## Cara Menjalankan

### 1. Siapkan lingkungan Python

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux atau macOS
source venv/bin/activate
```

### 2. Pasang dependensi

```bash
pip install -r requirements.txt
```

### 3. Buat basis data

```bash
python manage.py migrate
```

Perintah ini membaca `core/models.py` (hasil implementasi Class Diagram) dan
membuat berkas `db.sqlite3` beserta seluruh tabelnya.

### 4. Isi data awal

```bash
python manage.py seed
```

Membuat akun bawaan dan data produk:

| Peran | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `admin123` |
| Kasir | `kasir` | `kasir123` |

Perintah ini juga membuat 3 kategori wajib (Makanan Utama, Appetizer, Minuman)
dan 8 contoh produk. Aman dijalankan berulang.

Ganti password tersebut sebelum presentasi. Untuk data contoh yang lebih
lengkap (pesanan pada tiap status, termasuk yang sudah dibayar) jalankan:

```bash
python manage.py seed_demo
```

### 5. Jalankan aplikasi

```bash
python manage.py runserver
```

Buka `http://127.0.0.1:8000/`.

## Halaman Aplikasi

| Alamat | Untuk | Keterangan |
| --- | --- | --- |
| `/` | Pelanggan | Menu per kategori, dapat disaring |
| `/pesan/` | Pelanggan | Formulir pemesanan (nama dan nomor meja) |
| `/status/` | Pelanggan | Cek status pesanan berdasarkan nomor pesanan |
| `/masuk/` | Kasir, Administrator | Halaman masuk |
| `/keluar/` | Kasir, Administrator | Keluar dari aplikasi |
| `/kasir/` | Kasir | Ringkasan pesanan hari ini |
| `/kasir/pesanan/` | Kasir | Daftar pesanan dan perubahan status |
| `/kasir/pesanan/<pk>/billing/` | Kasir | Billing dan cetak billing |
| `/kasir/pesanan/<pk>/bayar/` | Kasir | Pembayaran tunai dan non tunai |
| `/kelola/produk/` | Administrator | Data produk |
| `/kelola/kategori/` | Administrator | Kategori produk |
| `/kelola/stok/` | Administrator | Input dan pembaruan stok |
| `/kelola/laporan/` | Administrator | Laporan mingguan dan bulanan |
| `/kelola/pengguna/` | Administrator | Data pengguna |
| `/admin/` | Administrator | Django Admin (alat bantu pemeriksaan data) |

Pelanggan tidak memerlukan akun. Kasir dan Administrator masuk memakai akun
dari tabel `pengguna` (bukan tabel pengguna bawaan Django).

## Aturan Sistem

**Alur status pesanan**

```
BARU -> DIPROSES -> SELESAI -> DIBAYAR
BARU -> DIBATALKAN
DIPROSES -> DIBATALKAN   (stok dikembalikan saat pembatalan)
```

**Perhitungan uang**

Pajak / service charge 10 persen dari subtotal. Nilai pajak dibulatkan ke 2
angka desimal sebelum dijumlahkan, sehingga subtotal + pajak selalu sama
dengan total yang tersimpan.

**Stok**

Stok berkurang otomatis saat pesanan dibuat, dan kembali otomatis bila
pesanan dibatalkan. Status Tersedia atau Habis ditentukan otomatis dari nilai
stok, tidak diisi manual.

**Pembayaran**

Tunai: kasir mengisi jumlah uang diterima, sistem menghitung kembalian.
Non tunai: kasir memilih jenis kartu (Debit atau Kartu Kredit) dan mengisi
nomor referensi. Pembayaran non tunai bersifat simulasi, tanpa payment gateway.

## Struktur Proyek

```
config/                  Pengaturan proyek Django (settings, urls)
core/
  models.py              Model sesuai Class Diagram (9 tabel)
  services.py            Proses lintas tabel (transaksi basis data)
  views.py               Class based view untuk seluruh halaman
  forms.py               Formulir dan validasi masukan
  autentikasi.py         Login berbasis sesi untuk Kasir dan Administrator
  middleware.py          Penyedia data pengguna yang sedang login
  context_processors.py  Penanda menu aktif pada sidebar
  admin.py               Pendaftaran model ke Django Admin
  management/commands/
    seed.py              Data awal
    seed_demo.py         Data contoh untuk presentasi
templates/               Seluruh halaman tampilan
static/
  vendor/                Bootstrap 5 (disimpan lokal, bukan CDN)
  css/app.css            Palet warna dan gaya komponen
  js/app.js              Skrip tampilan
docs/
  schema.sql             Skema SQL murni hasil Class Diagram
  PANDUAN_INSTALASI.md   Panduan pemasangan dan pemindahan proyek
pytest.ini               Konfigurasi pengujian unit
```

## Dokumentasi

| Dokumen | Isi |
| --- | --- |
| `README_SETUP.md` | Keterangan umum proyek, cara menjalankan, dan pembagian tanggung jawab kode |
| `docs/PANDUAN_INSTALASI.md` | Pemasangan dari awal, pemindahan melalui drive G, daftar perintah, dan pemecahan masalah |
| `docs/schema.sql` | Skema SQL murni hasil penerjemahan Class Diagram |

## Pembagian Tanggung Jawab Kode

Aturan transaksi dipisahkan menurut lingkupnya supaya kode tidak saling
tumpang tindih dan mudah diuji satu per satu:

| Berkas | Tanggung jawab | Contoh |
| --- | --- | --- |
| `core/models.py` | Aturan pada satu baris data | `Produk.kurangi_stok()`, `Pesanan.ubah_status()` |
| `core/services.py` | Proses beberapa tabel dalam satu transaksi | `buat_pesanan()`, `proses_pembayaran()`, `buat_laporan()` |
| `core/views.py` | Menerima permintaan, memvalidasi formulir, memanggil layanan | `FormPesananView`, `PembayaranView` |
| `core/forms.py` | Validasi masukan dan pesan kesalahan | `FormPesanan`, `FormPembayaran` |

Alur satu permintaan: view menerima permintaan, formulir memvalidasi masukan,
layanan menjalankan transaksi basis data, model menjaga aturan datanya.
Bila ada kesalahan aturan, layanan melempar `KesalahanLayanan` berisi pesan
berbahasa Indonesia yang langsung ditampilkan kepada pengguna.

## Pengujian Unit

Pengujian unit otomatis belum ditulis. Berkas `core/tests.py` masih
kosong dan `pytest.ini` sudah siap dipakai bila pengujian akan
ditambahkan kemudian.

```bash
pytest
```

Saat ini jaminan kebenaran aplikasi diperoleh dengan dua cara:

1. Pemeriksaan bawaan Django
   ```bash
   python manage.py check
   python manage.py makemigrations --check --dry-run
   ```
2. Penelusuran alur secara langsung melalui peramban, mulai dari
   pemesanan Pelanggan, pengelolaan pesanan Kasir, pembayaran, sampai
   pengelolaan data oleh Administrator.

## Tampilan

Tampilan disusun dari satu berkas gaya, `static/css/app.css`, yang
memuat seluruh palet warna dan gaya komponen. Bootstrap dipakai hanya
untuk tata letak dan komponen dasar, lalu warnanya ditimpa agar tidak
memakai warna bawaan Bootstrap.

Warna dasar yang dipakai:

| Kegunaan | Warna | Keterangan |
| --- | --- | --- |
| Aksen | `#35618f` | Tombol utama, tautan, penanda menu aktif |
| Latar halaman | `#f8fafc` | Warna dasar seluruh halaman |
| Permukaan | `#ffffff` | Kartu dan panel isi |
| Judul | `#1e293b` | Teks judul dan sidebar |
| Teks isi | `#334155` | Teks biasa |
| Teks redup | `#5b6b7f` | Keterangan dan teks bantu |
| Garis | `#e2e8f0` | Garis pemisah dan batas tabel |

Warna status pesanan dibuat terpisah agar setiap tahap mudah dibedakan
sekilas: Baru (abu), Diproses (kuning), Selesai (toska), Dibayar
(hijau), Dibatalkan (merah). Setiap pasangan warna teks dan latar
lencana dipilih agar tetap terbaca, bukan hanya berbeda.

Selain komponen, bagian bawaan peramban juga disesuaikan supaya
halaman terasa satu kesatuan:

- Warna sorotan teks saat diseret
- Warna batang gulir
- Warna kursor pada kolom isian
- Aturan `@media print` yang menyembunyikan sidebar, bilah atas,
  tombol, dan pesan sistem saat halaman billing dicetak, sehingga
  yang keluar hanya isi tagihan

Seluruh berkas tampilan disimpan lokal di folder `static/vendor`.
Aplikasi tidak memanggil CDN mana pun, jadi tetap tampil normal pada
komputer laboratorium tanpa sambungan internet.

Skrip `static/js/app.js` hanya menangani keperluan tampilan:

1. Mencegah tombol simpan diklik dua kali pada transaksi uang
2. Meminta persetujuan sebelum tindakan yang tidak dapat dibatalkan
3. Menyesuaikan isian pembayaran dengan metode yang dipilih

Tanpa JavaScript, seluruh isian tetap tampil dan validasi tetap
dikerjakan di server, sehingga aplikasi tidak bergantung pada skrip
ini.

## Keamanan Dasar

- Password disimpan dalam bentuk hash (`make_password`), tidak pernah teks asli
- Proteksi CSRF aktif (bawaan Django)
- Seluruh akses basis data memakai Django ORM, tanpa SQL mentah
- Validasi masukan dikerjakan di sisi server, bukan hanya di tampilan
- Sesi login dibuat ulang setelah masuk untuk mencegah session fixation
- Akun yang sedang dipakai login dan akun yang pernah menangani pembayaran
  tidak dapat dihapus
