-- ============================================================================
-- Skema Database - Sistem Informasi Restoran Dapur Ina Aina
-- ============================================================================
-- Dihasilkan dari Class Diagram (Class_Diagram_Dapur_Ina_Aina.drawio) melalui
-- Django ORM, dengan perintah:
--
--     python manage.py sqlmigrate core 0001
--
-- Isi berkas ini disamakan dengan skema yang benar benar dibuat oleh
-- perintah `python manage.py migrate`. Skema ini disediakan sebagai
-- dokumen Tugas 2 dan dapat dijalankan langsung lewat SQLite tanpa Django
-- (misalnya dengan DB Browser for SQLite atau sqlite3 CLI).
--
-- Urutan tabel mengikuti urutan dependensi kunci asing: tabel induk
-- dibuat lebih dahulu, baru tabel anak.
-- Basis data: SQLite 3
--
-- Keterangan relasi (sesuai Class Diagram):
--   Asosiasi terarah (-->): induk tidak boleh dihapus bila masih dipakai.
--                           Pada Django memakai on_delete=PROTECT.
--   Komposisi (part-of)  : anak ikut terhapus bila induk dihapus.
--                           Pada Django memakai on_delete=CASCADE.
--
-- Catatan penting tentang pelaksanaan aturan
-- ------------------------------------------
-- Django ORM tidak menuliskan aturan DELETE dan pemeriksaan nilai kolom
-- sebagai perintah SQL pada skema. Keduanya dijalankan di lapisan Django:
--
--   1. on_delete=PROTECT dan CASCADE dijalankan oleh Django sebelum
--      perintah DELETE dikirim ke basis data.
--   2. Pemeriksaan nilai kolom (role, tipe, status, metode, periode)
--      dijalankan oleh Django berdasarkan pilihan yang ditetapkan di
--      core/models.py.
--
-- Karena itu skema di bawah ini adalah bentuk yang benar benar dipakai
-- aplikasi. Bila berkas ini dijalankan langsung tanpa Django, aturan
-- tersebut tidak ikut aktif.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- Tabel: pengguna   (Class: Pengguna, untuk Kasir dan Administrator)
-- ----------------------------------------------------------------------------
-- Menyimpan akun staf. Pelanggan tidak memakai tabel ini karena tidak
-- memiliki akun.
--
-- Keterangan kolom:
--   id            : kunci utama, dibuat otomatis
--   username      : nama akun untuk masuk, wajib, tidak boleh sama
--   password_hash : password yang sudah diacak, tidak pernah teks asli
--   nama          : nama lengkap pengguna
--   role          : peran, hanya ADMINISTRATOR atau KASIR
--   aktif         : penanda akun dapat dipakai untuk masuk
--   dibuat_pada   : waktu akun dibuat
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "pengguna" (
    "id"            integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "username"      varchar(50)  NOT NULL UNIQUE,
    "password_hash" varchar(255) NOT NULL,
    "nama"          varchar(100) NOT NULL,
    "role"          varchar(20)  NOT NULL,
    "aktif"         bool         NOT NULL,
    "dibuat_pada"   datetime     NOT NULL
);

-- ----------------------------------------------------------------------------
-- Tabel: kategori_produk   (Class: KategoriProduk)
-- ----------------------------------------------------------------------------
-- Tiga kategori tetap sesuai studi kasus: Makanan Utama, Appetizer, Minuman.
--
--   id   : kunci utama
--   nama : nama kategori, unik
--   tipe : pengelompokan tetap, hanya MAKANAN_UTAMA, APPETIZER, MINUMAN
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "kategori_produk" (
    "id"   integer      NOT NULL PRIMARY KEY AUTOINCREMENT,
    "nama" varchar(50)  NOT NULL UNIQUE,
    "tipe" varchar(20)  NOT NULL
);

-- ----------------------------------------------------------------------------
-- Tabel: produk   (Class: Produk)
-- ----------------------------------------------------------------------------
-- Relasi: KategoriProduk 1 --> 0..* Produk  (asosiasi terarah, PROTECT)
-- Produk tidak boleh dihapus bila masih dipakai oleh detail pesanan.
--
--   kategori_id : rujukan ke kategori produk
--   nama        : nama produk yang tampil pada menu
--   deskripsi   : keterangan singkat produk
--   harga       : harga satuan sebelum pajak
--   stok        : jumlah persediaan, tidak boleh negatif
--   status_stok : TERSEDIA bila stok lebih dari 0, HABIS bila stok 0
--   aktif       : penanda produk ditampilkan pada menu pelanggan
--
-- Catatan tipe kolom stok: pada Django, field ini didefinisikan sebagai
-- PositiveIntegerField sehingga Django menuliskan tipenya sebagai
-- "integer unsigned" (ketentuan khusus Django). Pada dokumen ini dipakai
-- "integer" disertai pemeriksaan CHECK (stok >= 0), yang menghasilkan
-- batasan yang sama dan dapat langsung dibaca perkakas SQLite biasa.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "produk" (
    "id"          integer       NOT NULL PRIMARY KEY AUTOINCREMENT,
    "nama"        varchar(100)  NOT NULL,
    "deskripsi"   text          NOT NULL,
    "harga"       decimal       NOT NULL,
    "stok"        integer       NOT NULL CHECK ("stok" >= 0),
    "status_stok" varchar(10)   NOT NULL,
    "aktif"       bool          NOT NULL,
    "kategori_id" bigint        NOT NULL REFERENCES "kategori_produk" ("id")
                                DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "produk_kategori_id_index" ON "produk" ("kategori_id");

-- ----------------------------------------------------------------------------
-- Tabel: pelanggan   (Class: Pelanggan)
-- ----------------------------------------------------------------------------
-- Pelanggan tanpa akun. Dikenali dari nama dan nomor meja saat memesan.
--
--   nama       : nama pemesan
--   nomor_meja : nomor meja tempat pelanggan duduk
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "pelanggan" (
    "id"         integer      NOT NULL PRIMARY KEY AUTOINCREMENT,
    "nama"       varchar(100) NOT NULL,
    "nomor_meja" varchar(10)  NOT NULL
);

-- ----------------------------------------------------------------------------
-- Tabel: pesanan   (Class: Pesanan)
-- ----------------------------------------------------------------------------
-- Relasi: Pelanggan 1 --> 0..* Pesanan  (asosiasi terarah, PROTECT)
--
--   nomor_pesanan   : nomor otomatis berformat PSN-YYYYMMDD-XXXX, unik
--   pelanggan_id    : rujukan ke pelanggan pembuat pesanan
--   status          : BARU, DIPROSES, SELESAI, DIBAYAR, atau DIBATALKAN
--   dibuat_pada     : waktu pesanan dibuat
--   diperbarui_pada : waktu pesanan terakhir diubah
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "pesanan" (
    "id"              integer      NOT NULL PRIMARY KEY AUTOINCREMENT,
    "nomor_pesanan"   varchar(20)  NOT NULL UNIQUE,
    "status"          varchar(20)  NOT NULL,
    "dibuat_pada"     datetime     NOT NULL,
    "diperbarui_pada" datetime     NOT NULL,
    "pelanggan_id"    bigint       NOT NULL REFERENCES "pelanggan" ("id")
                                   DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "pesanan_pelanggan_id_index" ON "pesanan" ("pelanggan_id");

-- ----------------------------------------------------------------------------
-- Tabel: detail_pesanan   (Class: DetailPesanan)
-- ----------------------------------------------------------------------------
-- Relasi: Pesanan 1 *-- 1..* DetailPesanan  (komposisi, CASCADE)
--         Produk  1 --> 0..* DetailPesanan  (asosiasi terarah, PROTECT)
--
--   pesanan_id  : rujukan ke pesanan induk, ikut terhapus bila pesanan dihapus
--   produk_id   : rujukan ke produk yang dipesan
--   jumlah      : banyaknya item, tidak boleh negatif
--   harga_satuan: harga produk saat dipesan, disalin agar nilai transaksi
--                 tidak berubah bila harga produk diubah kemudian
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "detail_pesanan" (
    "id"           integer   NOT NULL PRIMARY KEY AUTOINCREMENT,
    "jumlah"       integer   NOT NULL CHECK ("jumlah" >= 0),
    "harga_satuan" decimal   NOT NULL,
    "pesanan_id"   bigint    NOT NULL REFERENCES "pesanan" ("id")
                             DEFERRABLE INITIALLY DEFERRED,
    "produk_id"    bigint    NOT NULL REFERENCES "produk" ("id")
                             DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "detail_pesanan_pesanan_id_index" ON "detail_pesanan" ("pesanan_id");
CREATE INDEX IF NOT EXISTS "detail_pesanan_produk_id_index" ON "detail_pesanan" ("produk_id");

-- ----------------------------------------------------------------------------
-- Tabel: billing   (Class: Billing)
-- ----------------------------------------------------------------------------
-- Relasi: Pesanan 1 *-- 0..1 Billing  (komposisi, CASCADE)
-- Satu pesanan hanya memiliki satu billing, karena itu pesanan_id dibuat
-- UNIQUE.
--
--   subtotal     : jumlah seluruh subtotal item
--   pajak        : pajak / service charge 10 persen dari subtotal
--   total        : subtotal ditambah pajak
--   dicetak_pada : waktu billing ditampilkan untuk dicetak
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "billing" (
    "id"          integer  NOT NULL PRIMARY KEY AUTOINCREMENT,
    "subtotal"    decimal  NOT NULL,
    "pajak"       decimal  NOT NULL,
    "total"       decimal  NOT NULL,
    "dicetak_pada" datetime NULL,
    "pesanan_id"  bigint   NOT NULL UNIQUE REFERENCES "pesanan" ("id")
                           DEFERRABLE INITIALLY DEFERRED
);

-- ----------------------------------------------------------------------------
-- Tabel: pembayaran   (Class: Pembayaran)
-- ----------------------------------------------------------------------------
-- Relasi: Billing 1 *-- 0..1 Pembayaran   (komposisi, CASCADE)
--         Pengguna 1 --> 0..* Pembayaran  (asosiasi terarah, PROTECT)
--
--   billing_id      : rujukan ke billing yang dibayar, unik
--   kasir_id        : rujukan ke kasir yang melayani pembayaran
--   metode          : TUNAI, DEBIT, atau KARTU_KREDIT
--   jumlah_diterima : uang yang diterima (tunai) atau sebesar total (non tunai)
--   kembalian       : selisih jumlah diterima dengan total, khusus tunai
--   nomor_referensi : nomor bukti transaksi kartu, wajib untuk non tunai
--   dibayar_pada    : waktu pembayaran disimpan
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "pembayaran" (
    "id"              integer     NOT NULL PRIMARY KEY AUTOINCREMENT,
    "metode"          varchar(20) NOT NULL,
    "jumlah_diterima" decimal     NOT NULL,
    "kembalian"       decimal     NOT NULL,
    "nomor_referensi" varchar(50) NOT NULL,
    "dibayar_pada"    datetime    NOT NULL,
    "billing_id"      bigint      NOT NULL UNIQUE REFERENCES "billing" ("id")
                                  DEFERRABLE INITIALLY DEFERRED,
    "kasir_id"        bigint      NOT NULL REFERENCES "pengguna" ("id")
                                  DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "pembayaran_kasir_id_index" ON "pembayaran" ("kasir_id");

-- ----------------------------------------------------------------------------
-- Tabel: laporan_penjualan   (Class: LaporanPenjualan)
-- ----------------------------------------------------------------------------
-- Menyimpan riwayat pembuatan laporan. Nilai total dihitung dari pesanan
-- berstatus DIBAYAR pada rentang tanggal yang dipilih.
--
--   periode         : MINGGUAN atau BULANAN
--   tanggal_mulai   : awal periode laporan
--   tanggal_selesai : akhir periode laporan
--   total_penjualan : jumlah total tagihan pesanan berstatus DIBAYAR
--   dibuat_pada     : waktu laporan dibuat
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "laporan_penjualan" (
    "id"              integer      NOT NULL PRIMARY KEY AUTOINCREMENT,
    "periode"         varchar(20)  NOT NULL,
    "tanggal_mulai"   date         NOT NULL,
    "tanggal_selesai" date         NOT NULL,
    "total_penjualan" decimal      NOT NULL,
    "dibuat_pada"     datetime     NOT NULL
);
