"""
Middleware penyedia data pengguna yang sedang login
==================================================

Middleware ini menempelkan objek Pengguna yang sedang login ke setiap
request sebagai request.pengguna. Dengan cara ini, seluruh view dan
template dapat membaca data pengguna tanpa mengambilnya sendiri dari
basis data, dan tidak ada pengambilan berulang pada satu permintaan.

Ditempatkan setelah SessionMiddleware karena middleware ini membaca
data dari sesi.
"""

from core.autentikasi import ambil_pengguna_sesi


class PenggunaSesiMiddleware:
    """Menempelkan request.pengguna pada setiap permintaan.

    Nilainya None bila pengguna belum login (misalnya Pelanggan yang
    memang tidak perlu login).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.pengguna = ambil_pengguna_sesi(request)
        return self.get_response(request)
