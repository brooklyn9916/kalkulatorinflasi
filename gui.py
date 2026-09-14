"""
gui.py — Kalkulator Inflasi (versi aplikasi jendela / GUI).

Ringan: memakai Tkinter yang sudah menyatu dengan Python, jadi .exe hasilnya
tetap kecil dan cepat dibuka di komputer kantor. Logika perhitungan diambil
dari core.py (identik dengan versi awal yang sudah divalidasi).
"""

import re
import sys
import tkinter as tk
from tkinter import ttk, font as tkfont
from fpdf import FPDF
from tkinter import filedialog, messagebox
import threading

import core

# --- Palet (kontras sudah diverifikasi WCAG) --------------------------------
BG        = "#F6F7F9"   # latar jendela, near-white sejuk (bukan cream)
SURFACE   = "#FFFFFF"   # panel input
RESULT_BG = "#EEF2F1"   # panel hasil, netral sejuk
INK       = "#14171A"   # teks utama
MUTED     = "#5A616B"   # teks sekunder
BORDER    = "#E2E5EA"
ACCENT    = "#0E7C6B"   # teal — aksi utama & angka hasil
ACCENT_HI = "#0B6558"   # teal lebih gelap (hover)
ACCENT_D  = "#0B5E50"   # teal gelap untuk teks kecil
WHITE     = "#FFFFFF"

FAM = "Segoe UI"


def rupiah(n):
    return "Rp " + f"{round(n):,.0f}".replace(",", ".")

def persen(p):
    return f"{p:.2f}".replace(".", ",") + "%"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Kalkulator Inflasi")
        root.configure(bg=BG)
        root.resizable(False, False)

        # 1. Coba muat cache lokal agar UI bisa langsung tampil
        ada_cache = core.muat_data_lokal()
        self.data_bulanan = core.DATA_BULANAN
        self.data_tahunan = core.DATA_TAHUNAN
        
        self.bulan_akhir, self.tahun_akhir = core.data_terakhir(self.data_bulanan)

        self._build_styles()
        self._build_ui()
        
        if not ada_cache:
            self._render_error("Sedang mengunduh data dari server...\nMohon tunggu beberapa detik.")
        else:
            self._render_empty()
            
        self._fit(reposition=True)
        
        # 2. Mulai sinkronisasi background secara diam-diam
        self.mulai_sinkronisasi()

    def mulai_sinkronisasi(self):
        """Memulai thread background untuk mengunduh data."""
        thread_sync = threading.Thread(target=self.proses_sinkronisasi_bg)
        thread_sync.daemon = True
        thread_sync.start()

    def proses_sinkronisasi_bg(self):
        """Fungsi yang dieksekusi oleh thread di belakang layar."""
        sukses = core.sinkronisasi_latar_belakang()
        if sukses:
            # Update referensi ke data memori baru
            self.data_bulanan = core.DATA_BULANAN
            self.data_tahunan = core.DATA_TAHUNAN
            self.bulan_akhir, self.tahun_akhir = core.data_terakhir(self.data_bulanan)
            
            # Panggil fungsi perbaikan UI (karena Tkinter butuh di-trigger dari Main Thread)
            self.root.after(0, self._perbarui_ui_setelah_sync)
        else:
            # JIKA GAGAL, beritahu UI agar tidak hang selamanya
            self.root.after(0, self._gagal_sync_ui)

    def _gagal_sync_ui(self):
        """Memperbarui UI jika proses unduh gagal dan cache tidak tersedia."""
        if not self.data_bulanan:
            # Jika ini instalasi bersih (belum ada cache sama sekali)
            self._render_error("Gagal mengunduh data dari server.\nPastikan koneksi internet aktif, lalu restart aplikasi.")
            self.lbl_footer.config(text="Sinkronisasi gagal. Aplikasi tidak dapat digunakan.")
        else:
            # Jika punya cache lama, tetap bisa jalan, tapi beri peringatan di footer
            self.lbl_footer.config(text=f"Mode Offline. Menggunakan data lama s.d. {self.bulan_akhir} {self.tahun_akhir}")

    def _perbarui_ui_setelah_sync(self):
        """Memperbarui elemen antarmuka yang mengandalkan data setelah unduhan selesai."""
        # Logika pembersihan UI yang lebih kebal (mengubah semua teks ke huruf kecil untuk dicocokkan)
        if not self.result.winfo_children():
            self._render_empty()
        else:
            box = self.result.winfo_children()[0]
            if box.winfo_children():
                teks_layar = box.winfo_children()[0].cget("text").lower()
                if "mengunduh" in teks_layar:
                    self._render_empty()
            
        self.lbl_footer.config(text=f"Data inflasi s.d. {self.bulan_akhir} {self.tahun_akhir}")

    # -- fonts & ttk styles --------------------------------------------------
    def _build_styles(self):
        self.f_title = tkfont.Font(family=FAM, size=17, weight="bold")
        self.f_sub   = tkfont.Font(family=FAM, size=10)
        self.f_label = tkfont.Font(family=FAM, size=10)
        self.f_input = tkfont.Font(family=FAM, size=12)
        self.f_btn   = tkfont.Font(family=FAM, size=11, weight="bold")
        self.f_big   = tkfont.Font(family=FAM, size=30, weight="bold")
        self.f_small = tkfont.Font(family=FAM, size=10)
        self.f_foot  = tkfont.Font(family=FAM, size=9)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Kalk.TCombobox",
                        fieldbackground=SURFACE, background=SURFACE,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                        arrowcolor=INK, foreground=INK, relief="flat",
                        padding=(10, 7))
        style.map("Kalk.TCombobox",
                  fieldbackground=[("readonly", SURFACE)],
                  bordercolor=[("focus", ACCENT), ("hover", ACCENT)],
                  arrowcolor=[("active", ACCENT)])
        self.root.option_add("*TCombobox*Listbox.background", SURFACE)
        self.root.option_add("*TCombobox*Listbox.foreground", INK)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", WHITE)
        self.root.option_add("*TCombobox*Listbox.font", self.f_input)

    # -- layout --------------------------------------------------------------
    def _build_ui(self):
        PADX = 28

        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=PADX, pady=(24, 16))
        tk.Label(head, text="Kalkulator Inflasi", bg=BG, fg=INK,
                 font=self.f_title, anchor="w").pack(fill="x")
        tk.Label(head, text="Konversi harga lama ke nilai setara sekarang.",
                 bg=BG, fg=MUTED, font=self.f_sub, anchor="w").pack(fill="x", pady=(3, 0))

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        card = tk.Frame(self.root, bg=SURFACE)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=SURFACE)
        inner.pack(fill="x", padx=PADX, pady=22)

        self.entry_harga = self._field_entry(inner, "Harga historis (Rp)")
        
        # Fitur Autocomplete untuk Bulan
        self.cb_bulan = self._field_combo(inner, "Bulan pembelian", core.BULAN_LIST, state="normal")
        self.cb_bulan.bind('<KeyRelease>', self._on_bulan_key)
        
        # Mengubah Tahun menjadi input teks bebas
        self.entry_tahun = self._field_entry(inner, "Tahun pembelian")

        btn = tk.Button(inner, text="Hitung", command=self.on_hitung,
                        bg=ACCENT, fg=WHITE, activebackground=ACCENT_HI,
                        activeforeground=WHITE, relief="flat", bd=0,
                        font=self.f_btn, cursor="hand2", pady=11)
        btn.pack(fill="x", pady=(18, 0))
        btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT_HI))
        btn.bind("<Leave>", lambda e: btn.config(bg=ACCENT))
        self.root.bind("<Return>", lambda e: self.on_hitung())

        self.result = tk.Frame(self.root, bg=RESULT_BG)
        self.result.pack(fill="x")

        foot_txt = (f"Data inflasi s.d. {self.bulan_akhir} {self.tahun_akhir}"
                    if self.bulan_akhir else "Data belum disinkronisasi")
        self.lbl_footer = tk.Label(self.root, text=foot_txt, bg=BG, fg=MUTED, font=self.f_foot, anchor="w")
        self.lbl_footer.pack(fill="x", padx=PADX, pady=(12, 16))

    def _field_entry(self, parent, label):
        tk.Label(parent, text=label, bg=SURFACE, fg=MUTED, font=self.f_label,
                 anchor="w").pack(fill="x", pady=(0, 6))
        e = tk.Entry(parent, font=self.f_input, fg=INK, bg=SURFACE,
                     relief="flat", highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=ACCENT,
                     insertbackground=INK)
        e.configure(bd=6)
        e.pack(fill="x", ipady=4, pady=(0, 14))
        return e

    def _field_combo(self, parent, label, values, state="readonly"):
        tk.Label(parent, text=label, bg=SURFACE, fg=MUTED, font=self.f_label,
                 anchor="w").pack(fill="x", pady=(0, 6))
        cb = ttk.Combobox(parent, values=values, state=state,
                          style="Kalk.TCombobox", font=self.f_input)
        cb.pack(fill="x", pady=(0, 14))
        return cb

    def _on_bulan_key(self, event):
        """Menyaring isi dropdown bulan berdasarkan teks yang diketik pengguna."""
        value = event.widget.get()
        if value == '':
            self.cb_bulan['values'] = core.BULAN_LIST
        else:
            data = [item for item in core.BULAN_LIST if value.lower() in item.lower()]
            self.cb_bulan['values'] = data

    # -- states --------------------------------------------------------------
    def _clear_result(self):
        for w in self.result.winfo_children():
            w.destroy()

    def _render_empty(self):
        self._clear_result()
        box = tk.Frame(self.result, bg=RESULT_BG)
        box.pack(fill="x", padx=28, pady=22)
        tk.Label(box, text="Hasil konversi akan tampil di sini.", bg=RESULT_BG,
                 fg=MUTED, font=self.f_small, anchor="w").pack(fill="x")

    def _render_error(self, msg):
        self._clear_result()
        box = tk.Frame(self.result, bg=RESULT_BG)
        box.pack(fill="x", padx=28, pady=22)
        tk.Label(box, text=msg, bg=RESULT_BG, fg=ACCENT_D, font=self.f_small,
                 anchor="w", justify="left").pack(fill="x")
        self._fit()

    def _render_result(self, harga_asli, bulan, tahun, hasil, pct):
        self._clear_result()
        box = tk.Frame(self.result, bg=RESULT_BG)
        box.pack(fill="x", padx=28, pady=(20, 10))

        acuan = f"{self.bulan_akhir} {self.tahun_akhir}" if self.bulan_akhir else "data terakhir"
        tk.Label(box, text=f"Nilai setara per {acuan}", bg=RESULT_BG, fg=MUTED,
                 font=self.f_small, anchor="w").pack(fill="x")
        tk.Label(box, text=rupiah(hasil), bg=RESULT_BG, fg=ACCENT,
                 font=self.f_big, anchor="w").pack(fill="x", pady=(2, 4))

        row = tk.Frame(box, bg=RESULT_BG)
        row.pack(fill="x")
        tk.Label(row, text=f"dari {rupiah(harga_asli)} · {bulan} {tahun}",
                 bg=RESULT_BG, fg=MUTED, font=self.f_small).pack(side="left")
        tanda = "+" if pct >= 0 else ""
        tk.Label(row, text=f"{tanda}{persen(pct)}", bg=RESULT_BG, fg=ACCENT_D,
                 font=tkfont.Font(family=FAM, size=10, weight="bold")).pack(side="right")

        btn_pdf = tk.Button(self.result, text="Unduh Laporan PDF", command=self.on_download_pdf,
                            bg="#E2E5EA", fg="#14171A", activebackground="#D1D5DB", 
                            relief="flat", bd=0, font=self.f_btn, cursor="hand2", pady=8)
        btn_pdf.pack(fill="x", padx=28, pady=(20, 20))

        self._fit()

    # -- actions -------------------------------------------------------------
    def on_download_pdf(self):
        if not self.result.winfo_children() or not hasattr(self, 'last_calc'):
            messagebox.showwarning("Peringatan", "Lakukan perhitungan (Hitung) terlebih dahulu sebelum mengunduh PDF.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Simpan Laporan PDF",
            initialfile="Laporan_Lengkap_Inflasi.pdf"
        )
        if not filepath:
            return

        try:
            pdf = FPDF()
            
            # --- SETUP MARGIN Kustom ---
            pdf.set_margins(40, 20, 40)
            pdf.set_auto_page_break(auto=True, margin=20)
            pdf.add_page()
            
            area_cetak = 130

            # -- palet ledger (dipakai di semua tabel & lampiran) --
            INK = (28, 26, 22)
            MUTED_C = (107, 99, 85)
            GOLD = (176, 141, 62)
            GOLD_LIGHT = (250, 238, 208)
            TAN_PALE = (243, 240, 233)
            BORDER_C = (228, 221, 202)
            GREEN_C = (63, 107, 63)
            RED_C = (163, 74, 63)
            
            tahun_terakhir_int = int(self.tahun_akhir)
            tahun_paling_awal = min(int(k) for k in self.data_tahunan.keys())
            
            bulan_beli = self.last_calc['bulan']
            tahun_beli = self.last_calc['tahun']
            idx_bulan_beli = core.BULAN_LIST.index(bulan_beli)
            sisa_bulan = core.BULAN_LIST[idx_bulan_beli + 1:]
            
            # =========================================================
            # TABEL 1: RINCIAN INFLASI BULANAN
            # =========================================================
            pdf.set_font("Times", 'B', 14)
            pdf.set_text_color(*INK)
            pdf.cell(0, 10, "Rincian Data Inflasi Bulanan (Umum)", ln=True, align='C')
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)

            col1_w = 45
            col2_w = 45
            start_x1 = 40 + ((area_cetak - (col1_w + col2_w)) / 2)

            # -- header ledger (tanpa kotak abu-abu, cukup garis atas-bawah) --
            header_y = pdf.get_y()
            pdf.set_draw_color(*INK)
            pdf.set_line_width(0.5)
            pdf.line(start_x1, header_y, start_x1 + col1_w + col2_w, header_y)
            pdf.set_font("Arial", 'B', 9)
            pdf.set_text_color(*INK)
            pdf.set_x(start_x1)
            pdf.cell(col1_w, 8, "TAHUN / BULAN", align='L')
            pdf.cell(col2_w, 8, "NILAI (%)", align='C')
            pdf.set_text_color(0, 0, 0)
            pdf.ln()
            pdf.set_draw_color(*INK)
            pdf.set_line_width(0.35)
            pdf.line(start_x1, pdf.get_y(), start_x1 + col1_w + col2_w, pdf.get_y())

            def _cek_page_break_tabel1(row_h):
                """Pindah halaman manual SEBELUM rect digambar, agar kotak highlight
                dan teksnya tidak terpisah oleh auto page-break FPDF."""
                if pdf.get_y() + row_h > pdf.page_break_trigger:
                    pdf.add_page()
                    # ulang header tabel di halaman baru agar tabel tetap terbaca
                    header_y_new = pdf.get_y()
                    pdf.set_draw_color(*INK)
                    pdf.set_line_width(0.5)
                    pdf.line(start_x1, header_y_new, start_x1 + col1_w + col2_w, header_y_new)
                    pdf.set_font("Arial", 'B', 9)
                    pdf.set_text_color(*INK)
                    pdf.set_x(start_x1)
                    pdf.cell(col1_w, 8, "TAHUN / BULAN", align='L')
                    pdf.cell(col2_w, 8, "NILAI (%)", align='C')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln()
                    pdf.set_draw_color(*INK)
                    pdf.set_line_width(0.35)
                    pdf.line(start_x1, pdf.get_y(), start_x1 + col1_w + col2_w, pdf.get_y())

            for y in range(tahun_terakhir_int, tahun_paling_awal - 1, -1):
                y_str = str(y)
                if y_str in self.data_tahunan:
                    val_thn = self.data_tahunan[y_str] * 100
                    _cek_page_break_tabel1(7.5)
                    row_y = pdf.get_y()
                    pdf.set_fill_color(*TAN_PALE)
                    pdf.rect(start_x1, row_y, col1_w + col2_w, 7.5, style='F')
                    pdf.set_font("Arial", 'B', 9.5)
                    pdf.set_text_color(*INK)
                    pdf.set_x(start_x1)
                    pdf.cell(col1_w, 7.5, f"  {y_str}", align='L')
                    pdf.cell(col2_w, 7.5, f"{val_thn:.2f}", align='C')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln()

                if y_str in self.data_bulanan:
                    bulan_ada = [b for b in reversed(core.BULAN_LIST) if b in self.data_bulanan[y_str]]
                    for b in bulan_ada:
                        val_bln = self.data_bulanan[y_str][b]
                        _cek_page_break_tabel1(6.5)
                        row_y = pdf.get_y()

                        is_pembelian_month = (y == tahun_beli and b == bulan_beli)
                        is_sisa_bulan = (y == tahun_beli and b in sisa_bulan)
                        is_highlight = is_pembelian_month or is_sisa_bulan

                        if is_highlight:
                            # bar gold di kiri menandai baris ini relevan dengan perhitungan
                            pdf.set_fill_color(*GOLD)
                            pdf.rect(start_x1, row_y, 0.8, 6.5, style='F')

                        if is_pembelian_month:
                            # bulan pembelian: hanya kolom BULAN yang di-highlight
                            pdf.set_fill_color(*GOLD_LIGHT)
                            pdf.rect(start_x1, row_y, col1_w, 6.5, style='F')
                        elif is_sisa_bulan:
                            # sisa bulan berjalan: hanya kolom NILAI yang di-highlight
                            pdf.set_fill_color(*GOLD_LIGHT)
                            pdf.rect(start_x1 + col1_w, row_y, col2_w, 6.5, style='F')

                        pdf.set_x(start_x1)
                        pdf.set_font("Arial", 'B' if is_pembelian_month else '', 8.5)
                        pdf.set_text_color(*INK if is_pembelian_month else (60, 60, 60))
                        pdf.cell(col1_w, 6.5, f"      {b}", align='L')

                        pdf.set_font("Arial", 'B' if is_sisa_bulan else '', 8.5)
                        pdf.set_text_color(*INK if is_sisa_bulan else (60, 60, 60))
                        pdf.cell(col2_w, 6.5, f"{val_bln:.2f}", align='C')
                        pdf.set_text_color(0, 0, 0)
                        pdf.ln()

                        pdf.set_draw_color(*BORDER_C)
                        pdf.set_line_width(0.15)
                        pdf.line(start_x1, pdf.get_y(), start_x1 + col1_w + col2_w, pdf.get_y())

            pdf.ln(8)
            pdf.set_font("Arial", '', 8)
            pdf.set_text_color(*MUTED_C)
            url_bps = "https://www.bps.go.id/id/statistics-table/1/OTA4IzE=/inflasi-umum-inti-harga-diatur-pemerintah-dan-bergejolak-nasional-m-to-m-dan-y-to-d-2009-2026.html"
            pdf.multi_cell(0, 5, url_bps, align='C')
            pdf.set_text_color(0, 0, 0)

            # =========================================================
            # TABEL 2: REKAPITULASI TAHUNAN & LAST PO
            # =========================================================
            pdf.add_page()

            pdf.set_font("Times", 'B', 14)
            pdf.set_text_color(*INK)
            pdf.cell(0, 10, "Rekapitulasi Inflasi Tahunan & Agregasi", ln=True, align='C')
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)

            col_w = [25, 30, 25, 50]
            start_x2 = 40
            table_w2 = sum(col_w)

            bulan_beli_singkat = bulan_beli[:3].upper()
            header_col4 = f"Last PO {bulan_beli_singkat} {tahun_beli}"

            header_y2 = pdf.get_y()
            pdf.set_draw_color(*INK)
            pdf.set_line_width(0.5)
            pdf.line(start_x2, header_y2, start_x2 + table_w2, header_y2)
            pdf.set_font("Arial", 'B', 8.5)
            pdf.set_text_color(*INK)
            pdf.set_x(start_x2)
            pdf.cell(col_w[0], 8, "TAHUN", align='C')
            pdf.cell(col_w[1], 8, "SUM UMUM", align='C')
            pdf.cell(col_w[2], 8, "INFLASI", align='C')
            pdf.cell(col_w[3], 8, header_col4.upper(), align='C')
            pdf.set_text_color(0, 0, 0)
            pdf.ln()
            pdf.set_draw_color(*INK)
            pdf.set_line_width(0.35)
            pdf.line(start_x2, pdf.get_y(), start_x2 + table_w2, pdf.get_y())

            grand_total_umum = 0
            arr_nama_bulan = []
            arr_nilai_bulan = []
            val_last_po = 0
            arr_tahun_majemuk = []

            for y in range(tahun_paling_awal, tahun_terakhir_int + 1):
                y_str = str(y)

                if y_str in self.data_tahunan:
                    fraksi_inflasi = self.data_tahunan[y_str]
                    sum_umum = fraksi_inflasi * 100
                    grand_total_umum += sum_umum

                    str_sum_umum = f"{sum_umum:.2f}".replace(".", ",")
                    str_fraksi = f"{fraksi_inflasi:.4g}".replace(".", ",")

                    row_h2 = 7
                    if pdf.get_y() + row_h2 > pdf.page_break_trigger:
                        pdf.add_page()
                        # ulang header tabel di halaman baru
                        header_y_new2 = pdf.get_y()
                        pdf.set_draw_color(*INK)
                        pdf.set_line_width(0.5)
                        pdf.line(start_x2, header_y_new2, start_x2 + table_w2, header_y_new2)
                        pdf.set_font("Arial", 'B', 8.5)
                        pdf.set_text_color(*INK)
                        pdf.set_x(start_x2)
                        pdf.cell(col_w[0], 8, "TAHUN", align='C')
                        pdf.cell(col_w[1], 8, "SUM UMUM", align='C')
                        pdf.cell(col_w[2], 8, "INFLASI", align='C')
                        pdf.cell(col_w[3], 8, header_col4.upper(), align='C')
                        pdf.set_text_color(0, 0, 0)
                        pdf.ln()
                        pdf.set_draw_color(*INK)
                        pdf.set_line_width(0.35)
                        pdf.line(start_x2, pdf.get_y(), start_x2 + table_w2, pdf.get_y())

                    row_y = pdf.get_y()

                    is_majemuk = y > tahun_beli
                    is_beli = (y == tahun_beli)

                    if is_majemuk:
                        pdf.set_fill_color(*GOLD_LIGHT)
                        pdf.rect(start_x2 + col_w[0] + col_w[1], row_y, col_w[2], row_h2, style='F')
                    if is_beli:
                        pdf.set_fill_color(*GOLD_LIGHT)
                        pdf.rect(start_x2 + col_w[0] + col_w[1] + col_w[2], row_y, col_w[3], row_h2, style='F')

                    pdf.set_font("Arial", '', 9)
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_x(start_x2)
                    pdf.cell(col_w[0], row_h2, y_str, align='C')
                    pdf.cell(col_w[1], row_h2, str_sum_umum, align='C')

                    pdf.set_font("Arial", 'B' if is_majemuk else '', 9)
                    pdf.set_text_color(*INK if is_majemuk else (60, 60, 60))
                    pdf.cell(col_w[2], row_h2, str_fraksi, align='C')
                    pdf.set_text_color(0, 0, 0)
                    if is_majemuk:
                        arr_tahun_majemuk.append((y_str, fraksi_inflasi))

                    if is_beli:
                        total_sisa = 0
                        for m in sisa_bulan:
                            val_b = self.data_bulanan.get(y_str, {}).get(m, 0)
                            total_sisa += val_b
                            arr_nama_bulan.append(m)
                            arr_nilai_bulan.append(f"{val_b}".replace(".", ","))

                        val_last_po = total_sisa / 100
                        arr_tahun_majemuk.insert(0, (y_str, val_last_po))

                        str_total_sisa = f"{val_last_po:.4f}".replace(".", ",")
                        pdf.set_font("Arial", 'B', 9)
                        pdf.set_text_color(*INK)
                        pdf.cell(col_w[3], row_h2, str_total_sisa, align='C')
                        pdf.set_text_color(0, 0, 0)
                    else:
                        pdf.cell(col_w[3], row_h2, "", align='C')

                    pdf.ln()
                    pdf.set_draw_color(*BORDER_C)
                    pdf.set_line_width(0.15)
                    pdf.line(start_x2, pdf.get_y(), start_x2 + table_w2, pdf.get_y())

            str_grand_total = f"{grand_total_umum:.2f}".replace(".", ",")
            total_y = pdf.get_y()
            pdf.set_draw_color(*INK)
            pdf.set_line_width(0.5)
            pdf.line(start_x2, total_y, start_x2 + table_w2, total_y)
            pdf.set_font("Arial", 'B', 9.5)
            pdf.set_text_color(*INK)
            pdf.set_x(start_x2)
            pdf.cell(col_w[0] + col_w[1], 8, "GRAND TOTAL   " + str_grand_total, align='R')
            pdf.cell(col_w[2], 8, "", align='C')
            pdf.cell(col_w[3], 8, "", align='C')
            pdf.set_text_color(0, 0, 0)
            pdf.ln()

            # =========================================================
            # LAMPIRAN 3: JEJAK PERHITUNGAN (EKSPANSI ANGKA LENGKAP)
            # =========================================================
            pdf.add_page()
            
            harga_awal = self.last_calc['harga_asli']
            harga_final = self.last_calc['hasil']
            str_hf = f"{harga_final:,.0f}".replace(",", ".")
            str_ha = f"{harga_awal:,.0f}".replace(",", ".")
            str_angka_last_po = f"{val_last_po:.4g}".replace(".", ",")
            
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "LAMPIRAN: JEJAK PERHITUNGAN", ln=True)
            
            pdf.set_font("Arial", '', 11)
            pdf.set_text_color(90, 97, 107) 
            pdf.cell(0, 6, f"Data Input: Harga Pembelian {rupiah(harga_awal)} pada {bulan_beli} {tahun_beli}", ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(6)

            # =========================================================
            # DESAIN "LEDGER" (v3) — urutan: Inflasi Last PO -> Harga Final -> Persentase Nilai
            # =========================================================
            pct_inflasi = ((harga_final - harga_awal) / harga_awal) * 100
            str_pct = f"{pct_inflasi:.2f}".replace(".", ",") + "%"
            tanda_pct = "+" if pct_inflasi >= 0 else ""

            INK = (28, 26, 22)
            MUTED_C = (107, 99, 85)
            GOLD = (176, 141, 62)
            TAN_LIGHT = (217, 207, 184)
            BORDER_C = (228, 221, 202)
            GREEN_C = (63, 107, 63)
            RED_C = (163, 74, 63)

            CL = pdf.l_margin
            CW = pdf.w - pdf.l_margin - pdf.r_margin
            NUM_W = 13   # ruang untuk angka besar "01" / "02" / "03"
            CONTENT_X = CL + NUM_W

            def fraction(num_text, den_text, x, y, font_size=10):
                pdf.set_font("Arial", '', font_size)
                w = max(pdf.get_string_width(num_text), pdf.get_string_width(den_text)) + 4
                pdf.set_xy(x, y)
                pdf.set_text_color(*INK)
                pdf.cell(w, 6, num_text, border="B", align='C')
                pdf.set_xy(x, y + 6)
                pdf.cell(w, 6, den_text, align='C')
                pdf.set_text_color(0, 0, 0)
                return w

            def ledger_rule(y, color=BORDER_C, width=0.3):
                pdf.set_draw_color(*color)
                pdf.set_line_width(width)
                pdf.line(CONTENT_X, y, CL + CW, y)

            def big_number(num_text, x, y):
                pdf.set_font("Times", 'B', 20)
                pdf.set_text_color(*TAN_LIGHT)
                pdf.set_xy(x, y)
                pdf.cell(NUM_W, 10, num_text)
                pdf.set_text_color(0, 0, 0)

            def step_title(text, x, y):
                pdf.set_font("Times", 'B', 13)
                pdf.set_text_color(*INK)
                pdf.set_xy(x, y)
                pdf.cell(0, 8, text)
                pdf.set_text_color(0, 0, 0)

            def result_underline(text, x, y, font_size=13):
                pdf.set_font("Arial", 'B', font_size)
                w = pdf.get_string_width(text)
                pdf.set_xy(x, y)
                pdf.set_text_color(*INK)
                pdf.cell(w + 2, 7, text)
                pdf.set_draw_color(*GOLD)
                pdf.set_line_width(0.7)
                pdf.line(x, y + 7.2, x + w + 2, y + 7.2)
                pdf.set_text_color(0, 0, 0)
                return w + 2

            def breadcrumb(y):
                items = [("1", "Inflasi last PO"), ("2", "Harga final"), ("3", "Persentase nilai")]
                x = CL
                for i, (num, label) in enumerate(items):
                    r = 2.3
                    pdf.set_draw_color(*TAN_LIGHT)
                    pdf.set_line_width(0.4)
                    pdf.set_fill_color(255, 255, 255)
                    pdf.ellipse(x, y, r * 2, r * 2, style='D')
                    pdf.set_xy(x, y)
                    pdf.set_font("Arial", 'B', 6.5)
                    pdf.set_text_color(*INK)
                    pdf.cell(r * 2, r * 2, num, align='C')
                    x += r * 2 + 1.5
                    pdf.set_font("Arial", 'B', 8.5)
                    pdf.set_text_color(*INK)
                    w_lbl = pdf.get_string_width(label)
                    pdf.set_xy(x, y + r - 2)
                    pdf.cell(w_lbl + 2, 4.6, label)
                    x += w_lbl + 2
                    if i < len(items) - 1:
                        pdf.set_font("Arial", '', 9)
                        pdf.set_text_color(*TAN_LIGHT)
                        pdf.set_xy(x, y + r - 2)
                        pdf.cell(8, 4.6, "->", align='C')
                        x += 8
                pdf.set_text_color(0, 0, 0)

            # -- garis pembatas tebal + breadcrumb --
            divider_y = pdf.get_y()
            pdf.set_draw_color(*INK)
            pdf.set_line_width(0.6)
            pdf.line(CL, divider_y, CL + CW, divider_y)
            pdf.ln(8)

            breadcrumb(pdf.get_y())
            pdf.ln(13)

            # ---------------------------------------------------------
            # LANGKAH 1 — INFLASI LAST PO
            # ---------------------------------------------------------
            y1 = pdf.get_y()
            big_number("01", CL, y1)
            step_title("Inflasi last PO", CONTENT_X, y1 + 1)
            pdf.set_xy(CONTENT_X, y1 + 9)
            pdf.set_font("Arial", 'I', 9)
            pdf.set_text_color(*MUTED_C)
            if arr_nama_bulan:
                desc1 = f"Rata-rata inflasi bulanan dari {arr_nama_bulan[0]} sampai {arr_nama_bulan[-1]} {tahun_beli}."
            else:
                desc1 = "Pembelian dilakukan bulan Desember, sehingga tidak ada sisa bulan berjalan."
            pdf.multi_cell(CW - NUM_W, 5, desc1)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

            ledger_top1 = pdf.get_y()
            ledger_rule(ledger_top1, color=INK, width=0.35)
            content_y1 = ledger_top1 + 5

            if arr_nama_bulan:
                n = len(arr_nama_bulan)
                cols = 3
                rows = -(-n // cols)  # ceil
                col_w = (CW - NUM_W) / cols
                row_h = 5.2
                for i, (m, v) in enumerate(zip(arr_nama_bulan, arr_nilai_bulan)):
                    col, row = divmod(i, rows)
                    cx = CONTENT_X + col * col_w
                    cy = content_y1 + row * row_h
                    pdf.set_font("Arial", '', 8.5)
                    pdf.set_text_color(*MUTED_C)
                    pdf.set_xy(cx, cy)
                    pdf.cell(col_w * 0.55, row_h - 1, m)
                    try:
                        val_f = float(str(v).replace(',', '.'))
                    except ValueError:
                        val_f = 0
                    vcolor = GREEN_C if val_f >= 0 else RED_C
                    pdf.set_font("Arial", 'B', 8.5)
                    pdf.set_text_color(*vcolor)
                    pdf.set_xy(cx + col_w * 0.55, cy)
                    pdf.cell(col_w * 0.45 - 2, row_h - 1, f"{v}%", align='R')
                    pdf.set_text_color(0, 0, 0)
                    if row < rows - 1:
                        pdf.set_draw_color(*BORDER_C)
                        pdf.set_line_width(0.15)
                        pdf.line(cx, cy + row_h - 1, cx + col_w - 3, cy + row_h - 1)
                grid_bottom1 = content_y1 + rows * row_h + 3

                num_val = " + ".join(arr_nilai_bulan)
                font_num = 8 if len(arr_nilai_bulan) > 6 else 9
                w_frac1 = fraction(num_val, "100", CONTENT_X, grid_bottom1, font_size=font_num)
                pdf.set_xy(CONTENT_X + w_frac1 + 4, grid_bottom1 + 3)
                pdf.set_font("Arial", '', 10)
                pdf.set_text_color(*MUTED_C)
                pdf.cell(6, 7, "=")
                pdf.set_text_color(0, 0, 0)
                result_underline(f"{str_angka_last_po}%", CONTENT_X + w_frac1 + 12, grid_bottom1 + 2, font_size=13)
                ledger_bottom1 = grid_bottom1 + 16
            else:
                pdf.set_xy(CONTENT_X, content_y1)
                pdf.set_font("Arial", '', 10)
                pdf.cell(0, 6, "Inflasi last PO = 0")
                ledger_bottom1 = content_y1 + 8

            ledger_rule(ledger_bottom1, color=BORDER_C, width=0.3)
            pdf.set_y(ledger_bottom1 + 10)

            # ---------------------------------------------------------
            # LANGKAH 2 — HARGA FINAL
            # ---------------------------------------------------------
            y2 = pdf.get_y()
            big_number("02", CL, y2)
            step_title("Harga final", CONTENT_X, y2 + 1)
            pdf.set_xy(CONTENT_X, y2 + 9)
            pdf.set_font("Arial", 'I', 9)
            pdf.set_text_color(*MUTED_C)
            pdf.multi_cell(CW - NUM_W, 5, "Harga awal dikalikan berturut-turut dengan inflasi tiap tahun, dimulai dari angka last PO di atas.")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

            ledger_top2 = pdf.get_y()
            ledger_rule(ledger_top2, color=INK, width=0.35)
            content_y2 = ledger_top2 + 6

            pieces = [(f"Rp {str_ha}", True, 11, INK), (" x ", False, 10, MUTED_C),
                      (f"(1 + {str_angka_last_po})", True, 10, MUTED_C)]
            for t in arr_tahun_majemuk[1:]:
                factor_txt = f"(1 + {t[1]:.4g})".replace(".", ",")
                pieces.append((" x ", False, 10, MUTED_C))
                pieces.append((factor_txt, True, 10, MUTED_C))
            pieces.append((" = ", False, 10, MUTED_C))

            row_h_chain = 8
            max_right2 = CL + CW
            cx, cy = CONTENT_X, content_y2
            for text, bold, size, color in pieces:
                pdf.set_font("Arial", 'B' if bold else '', size)
                w = pdf.get_string_width(text) + 2
                if cx + w > max_right2 and cx > CONTENT_X:
                    cx = CONTENT_X
                    cy += row_h_chain
                pdf.set_xy(cx, cy)
                pdf.set_text_color(*color)
                pdf.cell(w, row_h_chain, text)
                pdf.set_text_color(0, 0, 0)
                cx += w

            pdf.set_font("Arial", 'B', 13)
            result_w_est = pdf.get_string_width(f"Rp {str_hf}") + 4
            if cx + result_w_est > max_right2:
                cx = CONTENT_X
                cy += row_h_chain
            result_underline(f"Rp {str_hf}", cx, cy - 1, font_size=13)
            ledger_bottom2 = cy + row_h_chain + 6

            ledger_rule(ledger_bottom2, color=BORDER_C, width=0.3)
            pdf.set_y(ledger_bottom2 + 10)

            # ---------------------------------------------------------
            # LANGKAH 3 — PERSENTASE NILAI
            # ---------------------------------------------------------
            # Proteksi Page Break untuk bagian terakhir agar tidak terpotong
            if pdf.get_y() + 40 > 270:
                pdf.add_page()

            y3 = pdf.get_y()
            big_number("03", CL, y3)
            step_title("Persentase nilai", CONTENT_X, y3 + 1)
            pdf.set_xy(CONTENT_X, y3 + 9)
            pdf.set_font("Arial", 'I', 9)
            pdf.set_text_color(*MUTED_C)
            pdf.multi_cell(CW - NUM_W, 5, "Selisih harga final terhadap harga awal, dinyatakan dalam persen.")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

            ledger_top3 = pdf.get_y()
            ledger_rule(ledger_top3, color=INK, width=0.35)
            content_y3 = ledger_top3 + 6

            w_frac3 = fraction(f"Rp {str_hf} - Rp {str_ha}", f"Rp {str_ha}", CONTENT_X, content_y3)
            pdf.set_xy(CONTENT_X + w_frac3 + 4, content_y3 + 3)
            pdf.set_font("Arial", '', 10)
            pdf.set_text_color(*MUTED_C)
            pdf.cell(20, 7, "x 100% =")
            pdf.set_text_color(0, 0, 0)
            result_underline(str_pct, CONTENT_X + w_frac3 + 26, content_y3 + 2, font_size=13)
            ledger_bottom3 = content_y3 + 16
            ledger_rule(ledger_bottom3, color=BORDER_C, width=0.3)
            pdf.set_y(ledger_bottom3 + 8)

            # -- footer lampiran --
            pdf.set_font("Arial", '', 7.5)
            pdf.set_text_color(*MUTED_C)
            pdf.set_xy(CL, pdf.get_y())
            pdf.cell(CW * 0.6, 5, "Dihasilkan otomatis dari sistem perhitungan HPS")
            pdf.set_xy(CL + CW * 0.6, pdf.get_y())
            pdf.cell(CW * 0.4, 5, "Lampiran 3", align='R')
            pdf.set_text_color(0, 0, 0)


            # --- Output PDF ---
            pdf.output(filepath)
            messagebox.showinfo("Sukses", f"PDF berhasil disimpan di:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuat PDF:\n{str(e)}")

    def on_hitung(self):
        digits = re.sub(r"[^\d]", "", self.entry_harga.get())
        if not digits:
            self._render_error("Masukkan harga historis terlebih dahulu.")
            return
        harga = float(digits)
        
        # Ekstraksi Input Baru
        bulan_input = self.cb_bulan.get().strip()
        tahun_input = self.entry_tahun.get().strip()

        if not bulan_input or not tahun_input:
            self._render_error("Pilih/ketik bulan dan tahun pembelian.")
            return
            
        # Standarisasi Ejaan Bulan
        bulan = bulan_input.capitalize()
        if bulan not in core.BULAN_LIST:
            self._render_error("Nama bulan tidak valid. (Cth: Januari).")
            return

        # Validasi Ketat Angka Tahun
        try:
            tahun = int(tahun_input)
        except ValueError:
            self._render_error("Tahun harus berupa angka bulat (Cth: 2024).")
            return

        hasil, _info = core.hitung_harga_terkonversi(
            harga, bulan, tahun, self.data_bulanan, self.data_tahunan)
            
        if hasil is None:
            self._render_error("Data untuk kombinasi tersebut tidak tersedia.")
            return
            
        pct = ((hasil - harga) / harga) * 100
        
        self.last_calc = {
            'harga_asli': harga,
            'bulan': bulan,
            'tahun': tahun,
            'hasil': hasil
        }
        
        self._render_result(harga, bulan, tahun, hasil, pct)

    # -- util ----------------------------------------------------------------
    def _fit(self, reposition=False):
        self.root.update_idletasks()
        w = max(462, self.root.winfo_reqwidth())
        h = self.root.winfo_reqheight()
        self.root.geometry(f"{w}x{h}")
        if reposition:
            self.root.update_idletasks()
            x = (self.root.winfo_screenwidth() - w) // 2
            y = (self.root.winfo_screenheight() - h) // 3
            self.root.geometry(f"+{x}+{y}")

    def _fatal(self, msg):
        self.root.configure(bg=BG)
        tk.Label(self.root, text=msg, bg=BG, fg=INK, font=(FAM, 11),
                 wraplength=380, justify="left").pack(padx=28, pady=28)
        self.root.geometry("440x220")


def _enable_dpi_awareness():
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                windll.user32.SetProcessDPIAware()
            except Exception:
                pass

def _run():
    _enable_dpi_awareness()
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    except Exception:
        pass
    app = App(root)
    root.mainloop()

def main():
    try:
        _run()
    except Exception:
        import traceback
        jejak = traceback.format_exc()
        try:
            with open(core.data_path("error_log.txt"), "w", encoding="utf-8") as f:
                f.write(jejak)
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror("Kalkulator Inflasi — Error", jejak)
        except Exception:
            pass
        raise

if __name__ == "__main__":
    main()