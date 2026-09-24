from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Konfigurasi aplikasi utama (core).

    Nama tampilan dipakai pada halaman Django Admin agar terbaca
    sebagai aplikasi Dapur Ina Aina, bukan sekadar "core".
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Dapur Ina Aina"
