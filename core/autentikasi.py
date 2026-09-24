"""
Autentikasi berbasis sesi untuk Kasir dan Administrator
======================================================

Sistem ini TIDAK memakai django.contrib.auth.User (tabel auth_user).
Alasannya: pada Class Diagram, pengguna sistem adalah class Pengguna
dengan tabelnya sendiri (tabel pengguna), lengkap dengan atribut
username, password_hash, nama, role, dan aktif. Menambah tabel pengguna
kedua akan membuat rancangan basis data tidak sesuai diagram.

Karena itu, proses login dijalankan sendiri dengan alur:
  1. Cek kelengkapan input.
  2. Cari Pengguna berdasarkan username.
  3. Cocokkan password dengan hash tersimpan (check_password).
  4. Buat sesi berisi id pengguna.

Sesi hanya menyimpan id pengguna, bukan objek atau perannya. Objek
Pengguna selalu diambil ulang dari basis data pada setiap permintaan
(lihat core/middleware.py), sehingga perubahan data pengguna seperti
penonaktifan akun langsung berlaku tanpa perlu login ulang.
"""

from django.contrib import messages
from django.shortcuts import redirect

from core.models import Pengguna

# Kunci sesi yang dipakai untuk menyimpan id pengguna yang sedang login.
KUNCI_SESI = "pengguna_id"


def catat_masuk(request, pengguna):
    """Membuat sesi login untuk pengguna.

    Sesi lama dibersihkan lebih dahulu sebelum sesi baru dibuat. Cara ini
    mencegah session fixation, yaitu kondisi ketika penyerang menyiapkan
    id sesi lalu memakainya setelah korban login.
    """
    request.session.flush()
    request.session[KUNCI_SESI] = pengguna.pk


def catat_keluar(request):
    """Menghapus seluruh data sesi (logout)."""
    request.session.flush()


def ambil_pengguna_sesi(request):
    """Mengembalikan objek Pengguna yang sedang login, atau None.

    Mengembalikan None bila belum ada sesi, id pengguna tidak ditemukan,
    atau akun sudah dinonaktifkan (aktif = False).
    """
    id_pengguna = request.session.get(KUNCI_SESI)
    if not id_pengguna:
        return None
    return Pengguna.objects.filter(pk=id_pengguna, aktif=True).first()


class WajibLoginMixin:
    """Mixin untuk class based view yang hanya boleh diakses setelah login.

    Dipakai oleh seluruh halaman Kasir dan Administrator. Bila pengguna
    belum login, ia diarahkan ke halaman masuk dengan pesan pemberitahuan,
    bukan halaman error, supaya alurnya jelas saat didemonstrasikan.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.pengguna is None:
            messages.warning(request, "Silakan masuk terlebih dahulu.")
            return redirect("core:masuk")
        return super().dispatch(request, *args, **kwargs)


class WajibAdministratorMixin(WajibLoginMixin):
    """Mixin untuk halaman yang hanya boleh diakses Administrator.

    Halaman pengelolaan produk, kategori, stok, laporan, dan pengguna
    hanya untuk Administrator. Kasir yang mencoba membukanya diarahkan
    kembali ke daftar pesanan dengan pesan error.
    """

    def dispatch(self, request, *args, **kwargs):
        if (
            request.pengguna is not None
            and not request.pengguna.adalah_administrator
        ):
            messages.error(
                request, "Halaman tersebut hanya dapat diakses Administrator."
            )
            return redirect("core:kasir_pesanan")
        return super().dispatch(request, *args, **kwargs)
