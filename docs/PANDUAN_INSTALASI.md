# Panduan Instalasi dan Pemindahan Proyek

Sistem Informasi Restoran Dapur Ina Aina

Dokumen ini menjelaskan cara memasang, memindahkan, dan menjalankan
aplikasi pada komputer lain, termasuk komputer laboratorium tempat
ujikom dilaksanakan. Seluruh perintah sudah diuji langsung, bukan
perkiraan.

---

## 1. Ringkasan Persyaratan

| Kebutuhan | Keterangan |
| --- | --- |
| Sistem operasi | Windows 10 atau 11 (perintah Linux dan macOS dicantumkan bila berbeda) |
| Python | Versi 3.11 (wajib, lihat catatan pada bagian 2) |
| Internet | Diperlukan sekali saja, untuk memasang dependensi |
| Ruang penyimpanan | Sekitar 90 MB (proyek 0,7 MB, virtual environment 79 MB) |
| Basis data | Tidak perlu dipasang, memakai SQLite yang sudah termasuk di Python |

Tidak diperlukan Composer, npm, Node.js, Docker, MySQL, atau XAMPP.
Aplikasi berjalan sendiri dengan satu berkas basis data.

---

## 2. Catatan Penting Sebelum Memasang

### 2.1 Gunakan Python 3.11

Proyek ini memakai Django 5.0.14. Django 5.0 hanya mendukung Python
3.10 sampai 3.12. Bila komputer memakai Python 3.13 atau 3.14, Django
dapat terpasang tetapi berisiko gagal dijalankan.

Cara memeriksa versi Python yang tersedia:

```bat
python --version
py --list
```

Bila muncul beberapa versi, pakai Python 3.11 secara eksplisit:

```bat
py -3.11 --version
```

### 2.2 Jangan memindahkan folder venv

Folder `venv` menyimpan alamat lengkap komputer asal di dalam
berkasnya, misalnya `C:\Users\ISKANDAR\...`. Bila folder itu ikut
disalin ke komputer lain, perintah Python akan menunjuk alamat yang
salah dan aplikasi gagal dijalankan.

Karena itu, saat memindahkan proyek:

- Jangan menyalin folder `venv`
- Jangan menyalin folder `__pycache__`
- Buat `venv` baru di komputer tujuan dengan perintah di bagian 4

Folder `venv` memakan 79 MB dari total 80 MB, sehingga tidak menyalinnya
juga membuat proses pemindahan jauh lebih cepat.

---

## 3. Dependensi dan Pustaka yang Dipakai

### 3.1 Pustaka yang perlu dipasang

Isi `requirements.txt`:

| Pustaka | Versi | Kegunaan |
| --- | --- | --- |
| Django | 5.0.14 | Framework utama, menangani alamat halaman, basis data, templat, dan keamanan |
| pytest | 9.1.1 | Kerangka pengujian unit untuk Tugas 4 |
| pytest-django | 4.14.0 | Penghubung pytest dengan Django agar pengujian dapat memakai basis data uji |

Pustaka pendukung terpasang otomatis, tidak perlu ditulis sendiri:

| Pustaka | Dipasang oleh | Kegunaan |
| --- | --- | --- |
| asgiref | Django | Penghubung kode sinkron dan asinkron |
| sqlparse | Django | Penyusun perintah SQL |
| tzdata | Django | Data zona waktu untuk Windows |
| packaging, pluggy, iniconfig | pytest | Pendukung kerja pytest |
| colorama, Pygments | pytest | Pewarnaan teks hasil pengujian |

### 3.2 Pustaka yang tidak perlu dipasang

| Bagian | Keterangan |
| --- | --- |
| Bootstrap 5 | Berkas CSS dan JavaScript sudah disimpan di dalam proyek pada `static/vendor/`. Tidak perlu npm, tidak perlu unduh, tidak boleh memakai CDN |
| SQLite | Sudah termasuk di dalam Python, tidak perlu dipasang terpisah |
| Ikon, huruf, gambar | Tidak memakai pustaka luar. Ikon dibuat dengan CSS dan berkas `static/favicon.svg` dibuat sendiri |

### 3.3 Daftar perintah yang dipakai

Seluruh perintah dijalankan dari dalam folder proyek, yaitu folder yang
memuat berkas `manage.py`. Cara masuk ke folder tersebut:

```bat
cd /d "G:\DapurInaAina"
```

Bila proyek disimpan di alamat lain, sesuaikan alamatnya.

---

## 4. Langkah Instalasi dari Awal

Dijalankan pada komputer tujuan, setelah proyek selesai dipindahkan.

### Langkah 1: Buat virtual environment

```bat
py -3.11 -m venv venv
```

Bila `py` tidak tersedia, pakai:

```bat
python -m venv venv
```

Perintah ini membuat folder `venv`. Prosesnya memakan waktu sekitar 20
detik dan tidak menampilkan pesan apa pun bila berhasil.

### Langkah 2: Aktifkan virtual environment

```bat
venv\Scripts\activate
```

Bila berhasil, nama folder proyek akan muncul di depan baris perintah,
misalnya:

```text
(venv) C:\DapurInaAina>
```

Untuk PowerShell, bila muncul pesan larangan menjalankan skrip:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Untuk Linux atau macOS:

```bash
source venv/bin/activate
```

### Langkah 3: Pasang dependensi

```bat
pip install -r requirements.txt
```

Proses ini mengunduh sekitar 15 MB dan memakan waktu 1 sampai 3 menit
tergantung koneksi. Bila berhasil, muncul keterangan bahwa Django,
pytest, dan pytest-django sudah terpasang.

### Langkah 4: Buat basis data

```bat
python manage.py migrate
```

Perintah ini membaca `core/models.py` dan membuat berkas `db.sqlite3`
berisi seluruh tabel. Hasilnya sekitar 200 KB.

### Langkah 5: Isi data awal

```bat
python manage.py seed
```

Perintah ini membuat akun bawaan dan data produk:

| Peran | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `admin123` |
| Kasir | `kasir` | `kasir123` |

Perintah ini juga membuat 3 kategori wajib (Makanan Utama, Appetizer,
Minuman) dan 8 contoh produk. Aman dijalankan berulang, data yang sudah
ada akan dilewati.

Ganti password tersebut sebelum presentasi, atau buat akun baru melalui
halaman Kelola Pengguna.

### Langkah 6 (pilihan): Isi data contoh

```bat
python manage.py seed_demo
```

Perintah ini membuat 6 pesanan contoh dengan berbagai status, 2 di
antaranya sudah dibayar, sehingga halaman Laporan Penjualan dan daftar
pesanan langsung berisi data saat didemonstrasikan.

### Langkah 7: Jalankan aplikasi

```bat
python manage.py runserver
```

Bila berhasil, muncul keterangan:

```text
Starting development server at http://127.0.0.1:8000/
```

Buka peramban lalu akses alamat tersebut. Hentikan aplikasi dengan
menekan `Ctrl` dan `C` bersamaan.

### Langkah 8: Periksa hasil pemasangan

```bat
python manage.py check
```

Bila pemasangan benar, muncul keterangan:

```text
System check identified no issues (0 silenced).
```

---

## 5. Pemindahan Proyek Melalui Drive G

### 5.1 Ringkasan

| Tahap | Dikerjakan di | Hasil |
| --- | --- | --- |
| Menyalin ke drive G | Komputer asal | Proyek tanpa venv, sekitar 0,7 MB |
| Menyalin dari drive G | Komputer tujuan | Berkas proyek lengkap |
| Memasang venv dan basis data | Komputer tujuan | Aplikasi siap dijalankan |

### 5.2 Menyalin dari komputer asal ke drive G

Cara paling aman memakai robocopy, karena perintah ini dapat
mengecualikan folder yang tidak boleh ikut tersalin.

Buka Command Prompt, lalu sesuaikan alamat sumber dan tujuan:

```bat
robocopy "C:\Users\ISKANDAR\Downloads\Web_Project_LSP\DapurInaAina" "G:\DapurInaAina" /E /XD venv __pycache__ .pytest_cache /XF db.sqlite3
```

Keterangan pilihan perintah:

| Pilihan | Arti |
| --- | --- |
| `/E` | Menyalin semua folder termasuk yang kosong |
| `/XD` | Melewati folder bernama venv, `__pycache__`, dan `.pytest_cache` |
| `/XF` | Melewati berkas `db.sqlite3` |

Bila ingin membawa data yang sudah ada sekarang, termasuk seluruh
pesanan dan pembayaran hasil uji coba, hilangkan pilihan `/XF
db.sqlite3` sehingga berkas basis data ikut tersalin. Bila memilih
cara ini, langkah 4 dan 5 pada bagian 4 tidak perlu dijalankan.

Setelah perintah selesai, periksa bahwa drive G berisi berkas berikut:

```text
G:\DapurInaAina\
  manage.py
  requirements.txt
  pytest.ini
  README_SETUP.md
  db.sqlite3          (bila ikut disalin)
  config\
  core\
  docs\
  static\
  templates\
```

Folder `config` dan `core` wajib ada karena memuat seluruh kode
program. Folder `static` dan `templates` wajib ada karena memuat
tampilan. Bila salah satu tidak ikut tersalin, aplikasi akan gagal
dijalankan.

### 5.3 Menyalin dari drive G ke komputer tujuan

Di komputer laboratorium, buka Command Prompt dan salin ke folder
Documents agar mudah ditemukan:

```bat
robocopy "G:\DapurInaAina" "%USERPROFILE%\Documents\DapurInaAina" /E
```

Atau salin memakai Windows Explorer dengan cara menyeret folder dari
drive G ke Documents.

Setelah tersalin, masuk ke folder tersebut:

```bat
cd /d "%USERPROFILE%\Documents\DapurInaAina"
```

Lanjutkan dengan langkah 1 sampai 8 pada bagian 4 untuk membuat venv,
memasang dependensi, dan membuat basis data.

### 5.4 Bila ingin memasang tanpa internet

Dependensi dapat dipasang tanpa internet dengan cara membawa berkas
paketnya sekaligus. Lakukan pada komputer yang masih terhubung
internet:

```bat
pip download -r requirements.txt -d "G:\DapurInaAina\paket"
```

Lalu di komputer laboratorium, dari dalam folder proyek:

```bat
pip install --no-index --find-links paket -r requirements.txt
```

Pilihan `--no-index` membuat pip hanya membaca dari folder `paket` dan
tidak mencoba mengunduh.

---

## 6. Daftar Perintah Lengkap

Seluruh perintah dijalankan dari dalam folder proyek, dalam keadaan
virtual environment aktif.

### 6.1 Perintah sehari hari

| Perintah | Kegunaan |
| --- | --- |
| `python manage.py runserver` | Menjalankan aplikasi di `http://127.0.0.1:8000/` |
| `python manage.py runserver 8080` | Menjalankan pada port lain, misalnya 8080 |
| `python manage.py check` | Memeriksa kesalahan pada kode dan pengaturan |
| `python manage.py migrate` | Membuat atau memperbarui tabel basis data |
| `python manage.py seed` | Mengisi akun dan data produk awal |
| `python manage.py seed_demo` | Mengisi data contoh untuk presentasi |
| `python manage.py test` | Menjalankan pengujian unit |
| `pytest` | Menjalankan pengujian unit dengan tampilan lebih rinci |

### 6.2 Perintah pemeriksaan

| Perintah | Kegunaan |
| --- | --- |
| `python --version` | Memastikan versi Python yang dipakai |
| `pip list` | Menampilkan daftar pustaka yang sudah terpasang |
| `python manage.py showmigrations core` | Menampilkan status migrasi, tanda `[X]` berarti sudah diterapkan |
| `python manage.py makemigrations --check --dry-run` | Memastikan model dan migrasi sudah selaras |
| `python manage.py diffsettings` | Menampilkan seluruh pengaturan yang sedang dipakai |

### 6.3 Perintah basis data

| Perintah | Kegunaan |
| --- | --- |
| `python manage.py shell` | Membuka Python dengan Django yang sudah siap |
| `python manage.py migrate` | Membuat tabel yang belum ada tanpa menghapus data |

Untuk mengosongkan seluruh data, cara yang paling aman adalah menghapus
berkas `db.sqlite3` lalu membuatnya kembali. Cara ini sudah diuji dan
tidak menyentuh kode program maupun tampilan:

```bat
del db.sqlite3
python manage.py migrate
python manage.py seed
python manage.py seed_demo
```

Basis data SQLite juga tidak dapat dibuka dengan perintah `dbshell`
karena perintah itu memerlukan program `sqlite3` yang dipasang
terpisah, di luar Python. Untuk memeriksa isi tabel, pakai
`python manage.py shell` lalu tuliskan perintah berikut:

```python
from core.models import Produk, Pesanan

Produk.objects.count()
Pesanan.objects.all()
```

Cara lain, `db.sqlite3` dapat dibuka memakai aplikasi
[DB Browser for SQLite](https://sqlitebrowser.org/) yang tersedia
gratis. Aplikasi ini hanya untuk memeriksa data, tidak diperlukan
untuk menjalankan proyek.

### 6.4 Bila port sudah dipakai

Bila muncul pesan `That port is already in use`, jalankan pada port
lain:

```bat
python manage.py runserver 8017
```

Atau hentikan proses yang memakai port tersebut:

```bat
netstat -ano | findstr :8000
taskkill /F /PID <nomor PID dari kolom paling kanan>
```

---

## 7. Berkas dan Folder Penting

```text
manage.py                         Perintah utama Django
requirements.txt                  Daftar dependensi
pytest.ini                        Pengaturan pengujian unit
README_SETUP.md                   Keterangan umum proyek
db.sqlite3                        Basis data (dibuat oleh migrate)

config/
  settings.py                     Pengaturan aplikasi
  urls.py                         Alamat halaman utama

core/
  models.py                       Model sesuai Class Diagram, 9 tabel
  services.py                     Proses lintas tabel dalam satu transaksi
  views.py                        Class based view untuk seluruh halaman
  forms.py                        Formulir dan validasi masukan
  autentikasi.py                  Login berbasis sesi
  middleware.py                   Penyedia data pengguna yang sedang login
  context_processors.py           Penanda menu aktif pada sidebar
  migrations/                     Riwayat perubahan struktur tabel
  management/commands/
    seed.py                       Data awal
    seed_demo.py                  Data contoh

templates/                        Seluruh halaman tampilan
static/
  vendor/                         Bootstrap 5, disimpan lokal
  css/app.css                     Palet warna dan gaya komponen
  js/app.js                       Skrip tampilan
  favicon.svg                     Ikon aplikasi

docs/
  schema.sql                      Skema SQL murni hasil Class Diagram
  PANDUAN_INSTALASI.md            Dokumen ini
```

Jangan menghapus folder `core/migrations`. Folder tersebut memuat
riwayat perubahan tabel, dan tanpa folder itu perintah `migrate` tidak
dapat dijalankan.

---

## 8. Pemecahan Masalah

| Gejala | Sebab | Penyelesaian |
| --- | --- | --- |
| `'python' is not recognized` | Python belum terpasang atau belum masuk PATH | Pasang Python 3.11, saat memasang centang pilihan Add Python to PATH |
| `No module named django` | Venv belum aktif atau dependensi belum dipasang | Jalankan `venv\Scripts\activate` lalu `pip install -r requirements.txt` |
| `Fatal error in launcher` | Folder venv ikut tersalin dari komputer lain | Hapus folder `venv`, buat ulang dengan `py -3.11 -m venv venv` |
| `That port is already in use` | Port 8000 sedang dipakai program lain | Pakai port lain, misalnya `python manage.py runserver 8017` |
| `no such table: core_produk` | Perintah `migrate` belum dijalankan | Jalankan `python manage.py migrate` |
| Halaman tampil tanpa warna | Folder `static` tidak ikut tersalin | Pastikan folder `static` ada di dalam folder proyek |
| `Table 'core_pengguna' already exists` | Basis data ada tetapi riwayat migrasi hilang | Hapus `db.sqlite3`, jalankan ulang `migrate` lalu `seed` |
| `IndentationError` atau `SyntaxError` | Berkas kode rusak saat tersalin | Salin ulang berkas tersebut, bandingkan ukurannya dengan aslinya |
| Tidak dapat masuk padahal password benar | Data awal belum diisi | Jalankan `python manage.py seed` |
| Halaman tampil berantakan setelah mengubah CSS | Peramban menyimpan berkas lama | Muat ulang paksa dengan `Ctrl` dan `F5` |

### Memulai ulang dari keadaan bersih

Bila aplikasi sudah tidak dapat dijalankan karena percobaan yang salah,
langkah berikut mengembalikannya ke keadaan awal tanpa menyentuh kode
program:

```bat
del db.sqlite3
python manage.py migrate
python manage.py seed
python manage.py seed_demo
python manage.py runserver
```

Perintah di atas hanya menghapus dan membuat ulang basis data. Seluruh
kode program, tampilan, dan dokumen tidak terpengaruh.

---

## 9. Daftar Periksa Sebelum Presentasi

Jalankan berurutan dan pastikan semuanya sesuai harapan.

| Pemeriksaan | Perintah atau cara | Hasil yang diharapkan |
| --- | --- | --- |
| 1. Pengaturan benar | `python manage.py check` | `no issues` |
| 2. Migrasi selaras | `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| 3. Migrasi terpasang | `python manage.py showmigrations core` | Tanda `[X]` pada `0001_initial` |
| 4. Data awal tersedia | `python manage.py seed` | Akun `admin` dan `kasir` disebutkan sudah ada |
| 5. Data contoh tersedia | `python manage.py seed_demo` | Enam pesanan contoh muncul |
| 6. Aplikasi berjalan | `python manage.py runserver` | Alamat `127.0.0.1:8000` tampil |
| 7. Halaman pelanggan | Buka `/` di peramban | Menu restoran tampil berwarna |
| 8. Halaman kasir | Masuk sebagai `kasir` | Beranda kasir tampil |
| 9. Halaman admin | Masuk sebagai `admin` | Menu pengelolaan tampil lengkap |
| 10. Password bawaan | Halaman Kelola Pengguna | Password `admin123` dan `kasir123` sudah diganti |

### Catatan keamanan sebelum presentasi

Aplikasi ini disiapkan untuk dijalankan secara lokal di satu komputer,
sehingga pengaturannya masih dalam mode pengembangan. Dua hal berikut
perlu diketahui dan disebutkan bila ditanya asesor, tetapi tidak perlu
diubah karena presentasi dilakukan secara lokal:

- `DEBUG = True` pada `config/settings.py`. Mode ini menampilkan rincian
  kesalahan saat terjadi masalah. Berguna saat demonstrasi, tetapi harus
  dimatikan bila aplikasi dipasang di server sungguhan.
- `SECRET_KEY` masih tertulis di dalam berkas pengaturan. Pada aplikasi
  sungguhan, nilai ini disimpan di berkas terpisah yang tidak ikut
  dibagikan.

---

## 10. Urutan Perintah Ringkas

Ringkasan seluruh langkah, dari drive G sampai aplikasi berjalan.

```bat
:: 1. Salin dari drive G
robocopy "G:\DapurInaAina" "%USERPROFILE%\Documents\DapurInaAina" /E

:: 2. Masuk ke folder proyek
cd /d "%USERPROFILE%\Documents\DapurInaAina"

:: 3. Buat dan aktifkan virtual environment
py -3.11 -m venv venv
venv\Scripts\activate

:: 4. Pasang dependensi
pip install -r requirements.txt

:: 5. Siapkan basis data dan data awal
python manage.py migrate
python manage.py seed
python manage.py seed_demo

:: 6. Periksa lalu jalankan
python manage.py check
python manage.py runserver
```

Buka `http://127.0.0.1:8000/` di peramban. Akun untuk masuk:
`admin` dengan password `admin123`, atau `kasir` dengan password
`kasir123`.
