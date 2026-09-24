"""
Konfigurasi URL utama proyek
============================

Berkas ini hanya menjadi pintu masuk. Seluruh alamat halaman aplikasi
Dapur Ina Aina didefinisikan di core/urls.py, sedangkan alamat Django
Admin tetap dipakai sebagai alat bantu pemeriksaan data.

Pembagian alamat (lihat perencanaan):
  /admin/   Django Admin (alat bantu, bukan antarmuka utama)
  /         seluruh halaman aplikasi, diatur di core/urls.py
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Alat bantu pemeriksaan data selama pengembangan dan saat ujikom.
    path("admin/", admin.site.urls),
    # Seluruh halaman aplikasi (Pelanggan, Kasir, Administrator).
    path("", include("core.urls")),
]
