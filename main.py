"""
main.py — Kalkulator Inflasi Historis (versi aplikasi/.exe).

Untuk karyawan: cukup jalankan Kalkulator_Inflasi.exe, lalu ikuti petunjuk.
Data inflasi dibaca dari data_inflasi.json dan inflasi_tahunan.json yang
berada di folder yang sama dengan .exe.
"""

import core


def baca(prompt):
    """input() yang menutup aplikasi dengan rapi bila stream berakhir (Ctrl+C/EOF)."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\nKeluar.")
        raise SystemExit(0)


def minta_harga():
    """Meminta harga historis; menolak angka nol/negatif dan input non-angka."""
    while True:
        teks = baca("Masukkan Harga Historis (Rp): ").strip().replace(",", "")
        try:
            harga = float(teks)
        except ValueError:
            print("  -> Input bukan angka. Contoh yang benar: 150000")
            continue
        if harga <= 0:
            print("  -> Harga harus lebih besar dari 0.")
            continue
        return harga


def minta_bulan():
    while True:
        bulan = baca("Masukkan Bulan Pembelian (ex: Januari): ").strip().capitalize()
        if bulan in core.BULAN_LIST:
            return bulan
        print("  -> Nama bulan tidak dikenal. Contoh: Januari, Februari, ... Desember")


def minta_tahun(data_bulanan):
    while True:
        teks = baca("Masukkan Tahun Pembelian (ex: 2020): ").strip()
        try:
            tahun = int(teks)
        except ValueError:
            print("  -> Tahun harus berupa angka. Contoh: 2020")
            continue
        if str(tahun) not in data_bulanan:
            tersedia = ", ".join(sorted(data_bulanan.keys()))
            print(f"  -> Data untuk tahun {tahun} tidak ada. Tahun tersedia: {tersedia}")
            continue
        return tahun


def satu_kalkulasi(data_bulanan, data_tahunan):
    harga_historis = minta_harga()
    bulan_beli = minta_bulan()
    tahun_beli = minta_tahun(data_bulanan)

    hasil_presisi, info = core.hitung_harga_terkonversi(
        harga_historis, bulan_beli, tahun_beli, data_bulanan, data_tahunan
    )

    if hasil_presisi is None:
        # info berisi pesan error (string)
        print(f"\nError: {info}")
        return

    # info berisi daftar peringatan (list)
    for pesan in info:
        print(f"Peringatan: {pesan}")

    persentase_inflasi = ((hasil_presisi - harga_historis) / harga_historis) * 100
    hasil_bulat = round(hasil_presisi)
    harga_historis_bulat = round(harga_historis)

    bulan_akhir, tahun_akhir = core.data_terakhir(data_bulanan)
    acuan = f"{bulan_akhir} {tahun_akhir}" if bulan_akhir else str(tahun_akhir)

    print("\n--- HASIL KALKULASI ---")
    print(f"Harga Asli        : Rp {harga_historis_bulat:,.0f}")
    print(f"Waktu Pembelian   : {bulan_beli} {tahun_beli}")
    print(f"Nilai Setara Per  : {acuan}  (data terakhir)")
    print(f"Harga Terkonversi : Rp {hasil_bulat:,.0f}")
    print(f"Total Kenaikan    : {persentase_inflasi:.2f}%")


def main():
    print("=== KALKULATOR INFLASI HISTORIS ===")

    try:
        data_bulanan = core.muat_data(core.DATA_BULANAN_FILE)
        data_tahunan = core.muat_data(core.DATA_TAHUNAN_FILE)
    except FileNotFoundError as e:
        print(f"File database tidak ditemukan: {e}.")
        print("Pastikan data_inflasi.json dan inflasi_tahunan.json berada di folder yang sama dengan aplikasi ini.")
        baca("\nTekan Enter untuk keluar...")
        return

    bulan_akhir, tahun_akhir = core.data_terakhir(data_bulanan)
    if bulan_akhir:
        print(f"(Data inflasi terakhir: {bulan_akhir} {tahun_akhir})")

    while True:
        print()
        satu_kalkulasi(data_bulanan, data_tahunan)
        lagi = baca("\nHitung lagi? (y/n): ").strip().lower()
        if lagi != "y":
            break

    print("Terima kasih.")


if __name__ == "__main__":
    main()
