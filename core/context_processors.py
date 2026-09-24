"""
Context processor penyedia penanda menu aktif
============================================

Sidebar pada halaman Kasir dan Administrator perlu mengetahui menu mana
yang sedang dibuka supaya dapat menandainya. Alih-alih menambahkan
variabel pada setiap view, penentuan dilakukan di satu tempat ini
berdasarkan nama URL yang sedang diakses (request.resolver_match).

Cara ini menjaga view tetap ringkas: view hanya mengurus permintaan,
formulir, dan pemanggilan layanan.
"""

# Pemetaan nama URL ke kunci menu pada sidebar.
# Bila ada beberapa nama URL yang menuju halaman yang sama, semuanya
# dipetakan ke kunci yang sama.
PETA_MENU = {
    # Kasir
    "kasir_beranda": "beranda",
    "kasir_pesanan": "pesanan",
    "kasir_detail_pesanan": "pesanan",
    "kasir_ubah_status": "pesanan",
    "kasir_billing": "pesanan",
    "kasir_cetak_billing": "pesanan",
    "kasir_pembayaran": "pesanan",
    "kasir_bukti_pembayaran": "pesanan",
    # Administrator
    "kelola_produk": "produk",
    "kelola_produk_tambah": "produk",
    "kelola_produk_ubah": "produk",
    "kelola_produk_hapus": "produk",
    "kelola_kategori": "kategori",
    "kelola_kategori_tambah": "kategori",
    "kelola_kategori_ubah": "kategori",
    "kelola_kategori_hapus": "kategori",
    "kelola_stok": "stok",
    "kelola_stok_atur": "stok",
    "kelola_laporan": "laporan",
    "kelola_pengguna": "pengguna",
    "kelola_pengguna_tambah": "pengguna",
    "kelola_pengguna_ubah": "pengguna",
    "kelola_pengguna_hapus": "pengguna",
}


def penanda_menu(request):
    """Menyediakan variabel menu_aktif untuk template sidebar."""
    nama_url = ""
    if request.resolver_match is not None:
        nama_url = request.resolver_match.url_name or ""

    return {"menu_aktif": PETA_MENU.get(nama_url, "")}
