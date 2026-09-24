"""
Pembuatan tagihan PDF
=====================

Modul ini menyusun tagihan pesanan menjadi berkas PDF yang dapat
diunduh dari halaman kasir. Berkas dibuat di sisi server memakai
reportlab, bukan melalui fitur cetak peramban, sehingga hasilnya berupa
berkas PDF sungguhan yang bentuknya selalu sama di setiap peramban.

Urutan yang dijaga modul ini
----------------------------
Tagihan hanya dapat dicetak setelah pembayaran tuntas. Pemeriksaan
dilakukan melalui Pesanan.boleh_dicetak(), dan fungsi pada modul ini
melemparkan KesalahanLayanan bila syarat itu belum terpenuhi. Dengan
begitu aturan tersebut tetap berlaku walau alamat PDF dibuka langsung
dari peramban, bukan melalui tombol pada halaman.

Penamaan berkas memakai nomor pesanan, misalnya
Tagihan-PSN-20260923-0001.pdf, supaya berkas mudah dicari ketika
disimpan atau dikirim ke pelanggan.
"""

import io

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.models import PAJAK_PERSEN

# Warna garis dan teks mengikuti tampilan aplikasi agar tagihan tetap
# terasa satu kesatuan dengan halamannya.
WARNA_GARIS = colors.HexColor("#d8dee6")
WARNA_KEPALA = colors.HexColor("#eef2f7")
WARNA_TEKS_REDUP = colors.HexColor("#5b6673")


def rupiah(nilai):
    """Menyusun nilai uang menjadi teks rupiah dengan titik pemisah."""
    return f"Rp{nilai:,.0f}".replace(",", ".")


def nama_berkas(pesanan):
    """Nama berkas PDF untuk sebuah pesanan."""
    return f"Tagihan-{pesanan.nomor_pesanan}.pdf"


def _gaya():
    """Menyusun gaya teks yang dipakai pada tagihan."""
    dasar = getSampleStyleSheet()
    return {
        "judul": ParagraphStyle(
            "JudulTagihan",
            parent=dasar["Title"],
            fontSize=16,
            spaceAfter=2,
            textColor=colors.HexColor("#1f2933"),
        ),
        "anak_judul": ParagraphStyle(
            "AnakJudulTagihan",
            parent=dasar["Normal"],
            fontSize=9,
            textColor=WARNA_TEKS_REDUP,
            spaceAfter=10,
        ),
        "bagian": ParagraphStyle(
            "Bagian",
            parent=dasar["Heading2"],
            fontSize=11,
            spaceBefore=8,
            spaceAfter=4,
            textColor=colors.HexColor("#1f2933"),
        ),
        "isi": ParagraphStyle("Isi", parent=dasar["Normal"], fontSize=9),
        "kecil": ParagraphStyle(
            "Kecil",
            parent=dasar["Normal"],
            fontSize=8,
            textColor=WARNA_TEKS_REDUP,
        ),
    }


def buat_pdf_tagihan(pesanan, billing, pembayaran=None):
    """Membuat berkas PDF tagihan dan mengembalikannya sebagai bytes.

    Parameter
    ---------
    pesanan    : objek Pesanan yang ditagih
    billing    : objek Billing yang memuat subtotal, pajak, dan total
    pembayaran : objek Pembayaran, dipakai untuk menampilkan metode dan
                 status pembayaran pada tagihan

    Mengembalikan isi berkas PDF dalam bentuk bytes.

    Melempar KesalahanLayanan bila pesanan belum dibayar, karena
    tagihan hanya boleh dicetak setelah pembayaran tuntas.
    """
    # Diimpor di dalam fungsi untuk menghindari ketergantungan melingkar
    # antara modul layanan dan modul ini.
    from core.services import KesalahanLayanan

    if not pesanan.boleh_dicetak():
        raise KesalahanLayanan(
            f"Tagihan {pesanan.nomor_pesanan} belum dapat dicetak. "
            f"Tagihan hanya dapat dicetak setelah pembayaran selesai."
        )

    penampung = io.BytesIO()
    dokumen = SimpleDocTemplate(
        penampung,
        pagesize=A4,
        # Margin bawah dilebihkan sedikit untuk ruang catatan kaki.
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Tagihan {pesanan.nomor_pesanan}",
        author="Dapur Ina Aina",
    )

    gaya = _gaya()
    isi = []

    # --- Kepala tagihan
    isi.append(Paragraph("Dapur Ina Aina", gaya["judul"]))
    isi.append(
        Paragraph(
            "Tagihan Pesanan", gaya["anak_judul"]
        )
    )

    # --- Keterangan pesanan
    keterangan = [
        ["Nomor Pesanan", pesanan.nomor_pesanan],
        ["Nama Pemesan", pesanan.pelanggan.nama],
        ["Nomor Meja", pesanan.pelanggan.nomor_meja],
        ["Waktu Pesan", pesanan.dibuat_pada.strftime("%d-%m-%Y %H:%M") + " WIB"],
        ["Status Pesanan", pesanan.get_status_display()],
    ]
    if pembayaran is not None:
        keterangan.append(
            ["Metode Pembayaran", pembayaran.get_metode_display()]
        )
        keterangan.append(
            ["Waktu Pembayaran", pembayaran.dibayar_pada.strftime("%d-%m-%Y %H:%M") + " WIB"]
        )
        if pembayaran.nomor_referensi:
            keterangan.append(
                ["Nomor Referensi", pembayaran.nomor_referensi]
            )

    tabel_keterangan = Table(keterangan, colWidths=[38 * mm, 120 * mm])
    tabel_keterangan.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), WARNA_TEKS_REDUP),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    isi.append(tabel_keterangan)

    # --- Rincian item
    isi.append(Paragraph("Rincian Pesanan", gaya["bagian"]))

    baris = [["Produk", "Jumlah", "Harga Satuan", "Subtotal"]]
    for detail in pesanan.detail_list.select_related("produk").all():
        baris.append(
            [
                detail.produk.nama,
                str(detail.jumlah),
                rupiah(detail.harga_satuan),
                rupiah(detail.hitung_subtotal_item()),
            ]
        )

    tabel_item = Table(
        baris, colWidths=[78 * mm, 18 * mm, 32 * mm, 30 * mm], repeatRows=1
    )
    tabel_item.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), WARNA_KEPALA),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                # Kolom angka dirapatkan ke kanan supaya mudah dibaca.
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (1, 0), (-1, 0), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, WARNA_GARIS),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    isi.append(tabel_item)

    # --- Ringkasan pembayaran
    isi.append(Paragraph("Ringkasan Pembayaran", gaya["bagian"]))

    ringkasan = [
        ["Subtotal", rupiah(billing.subtotal)],
        [f"Pajak ({PAJAK_PERSEN:.0f}%)", rupiah(billing.pajak)],
        ["Total Tagihan", rupiah(billing.total)],
        ["Jumlah Item", f"{billing.hitung_total_item()} porsi"],
    ]

    if pembayaran is not None:
        ringkasan.append(["Jumlah Diterima", rupiah(pembayaran.jumlah_diterima)])
        if pembayaran.metode == "TUNAI":
            ringkasan.append(["Kembalian", rupiah(pembayaran.kembalian)])

    tabel_ringkasan = Table(ringkasan, colWidths=[52 * mm, 40 * mm], hAlign="RIGHT")
    tabel_ringkasan.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, 2), (-1, 2), 0.6, WARNA_GARIS),
                # Baris total ditebalkan karena menjadi angka terpenting.
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TEXTCOLOR", (0, 0), (0, -1), WARNA_TEKS_REDUP),
            ]
        )
    )
    isi.append(tabel_ringkasan)

    # --- Catatan kaki
    isi.append(Spacer(1, 8 * mm))
    isi.append(
        Paragraph(
            f"Tagihan ini dicetak pada "
            f"{timezone.localtime().strftime('%d-%m-%Y %H:%M')} WIB.",
            gaya["kecil"],
        )
    )
    isi.append(
        Paragraph(
            "Terima kasih telah memesan di Dapur Ina Aina.",
            gaya["kecil"],
        )
    )

    dokumen.build(isi)
    pdf = penampung.getvalue()
    penampung.close()
    return pdf
