"""
core.py — Logika inti Kalkulator Inflasi.

Berisi pemuatan data yang aman untuk .exe (frozen) dan fungsi kalkulasi.
Matematika kalkulasi SAMA PERSIS dengan versi asli main.py buatan Rafa —
sengaja tidak diubah supaya hasil angkanya tetap cocok dengan Excel yang
sudah divalidasi. Yang ditambahkan hanya: path aman untuk .exe, informasi
tanggal data terakhir, dan penjagaan input.
"""

import os
import sys
import json
import urllib.request
import urllib.error

# Konfigurasi JSONBin
BIN_ID = "6a601e15f5f4af5e29aee587" 
# Menggunakan Access Key khusus (KALKULATOR_INFLASI_INALUM)
ACCESS_KEY = "$2a$10$A6h6uEHgsspVBK2N1c.6IubG8UhmXIa5kYXB01TKcsDM/o0.KfMOO"
URL_JSONBIN = f"https://api.jsonbin.io/v3/b/{BIN_ID}?meta=false"

# File Cache Lokal Gabungan
CACHE_FILE = "cache_inflasi.json"

# Variabel Global Penyimpanan Memori
DATA_BULANAN = {}
DATA_TAHUNAN = {}

# Urutan bulan untuk mempermudah pencarian indeks (Sistem Basis 0)
BULAN_LIST = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
              "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

def app_dir():
    """Folder tempat file data berada."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def data_path(filename):
    """Path lengkap ke sebuah file data, relatif terhadap lokasi aplikasi."""
    return os.path.join(app_dir(), filename)

def muat_data_lokal():
    """Membaca data dari cache lokal (cache_inflasi.json) sebagai fallback jika offline."""
    global DATA_BULANAN, DATA_TAHUNAN
    path = data_path(CACHE_FILE)
    
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
                DATA_TAHUNAN = data.get("tahunan", {})
                DATA_BULANAN = data.get("bulanan", {})
                return True
        except Exception as e:
            print(f"Error membaca cache lokal: {e}")
    return False

def sinkronisasi_latar_belakang():
    """Mengunduh JSON terbaru dari JSONBin dan menimpanya ke cache lokal."""
    global DATA_BULANAN, DATA_TAHUNAN
    try:
        req = urllib.request.Request(URL_JSONBIN)
        
        # 1. Menyamar sebagai browser untuk melewati blokir Cloudflare
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 2. Header otentikasi (Menggunakan X-Access-Key karena Anda memakai Access Key)
        req.add_header('X-Access-Key', ACCESS_KEY)
        
        # Timeout 5 detik agar aplikasi tidak menggantung
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data_api = json.loads(response.read().decode('utf-8'))
                
                # Validasi struktur sebelum menimpa file
                if 'tahunan' in data_api and 'bulanan' in data_api:
                    with open(data_path(CACHE_FILE), 'w', encoding='utf-8') as f:
                        json.dump(data_api, f, indent=4)
                    
                    DATA_TAHUNAN = data_api.get('tahunan', {})
                    DATA_BULANAN = data_api.get('bulanan', {})
                    print("Sinkronisasi JSONBin sukses.")
                    return True
    except Exception as e:
        print(f"Sinkronisasi gagal, masuk mode offline: {e}")
    
    return False

def data_terakhir(data_bulanan):
    """Mengembalikan (bulan, tahun) data bulanan paling baru yang tersedia."""
    if not data_bulanan:
        return None, None
    tahun_terbaru = max(int(y) for y in data_bulanan.keys())
    bulan_tahun_itu = data_bulanan[str(tahun_terbaru)]
    
    bulan_ada = [b for b in BULAN_LIST if b in bulan_tahun_itu]
    if not bulan_ada:
        return None, str(tahun_terbaru)
    return bulan_ada[-1], str(tahun_terbaru)

def hitung_harga_terkonversi(harga_historis, bulan_beli, tahun_beli,
                             data_inflasi_bulanan, data_inflasi_tahunan):
    """Konversi harga historis ke nilai 'sekarang' (data terakhir yang ada)."""
    tahun_beli_str = str(tahun_beli)

    # Validasi input pengguna terhadap database
    if tahun_beli_str not in data_inflasi_bulanan:
        return None, f"Data bulanan untuk tahun {tahun_beli} tidak ditemukan."
    if bulan_beli not in BULAN_LIST:
        return None, "Format bulan salah. Pastikan penulisan nama bulan sudah benar."

    tahun_tersedia = [int(y) for y in data_inflasi_tahunan.keys()]
    tahun_terakhir = max(tahun_tersedia)

    # 1. Hitung inflasi pada sisa tahun pembelian (Bulan Pembelian + 1 s.d Desember)
    idx_bulan_beli = BULAN_LIST.index(bulan_beli)
    sisa_bulan = BULAN_LIST[idx_bulan_beli + 1:]

    total_inflasi_tahun_awal = 0
    for bulan in sisa_bulan:
        total_inflasi_tahun_awal += data_inflasi_bulanan[tahun_beli_str].get(bulan, 0)

    angka_inflasi_awal = total_inflasi_tahun_awal / 100
    harga_terkonversi = harga_historis * (1 + angka_inflasi_awal)

    # 2. Hitung inflasi untuk tahun-tahun berikutnya menggunakan database tahunan
    peringatan = []
    for tahun in range(tahun_beli + 1, tahun_terakhir + 1):
        tahun_str = str(tahun)

        if tahun_str not in data_inflasi_tahunan:
            peringatan.append(f"Data tahunan untuk {tahun} hilang. Melewati tahun ini.")
            continue

        angka_inflasi_tahunan = data_inflasi_tahunan[tahun_str]
        harga_terkonversi = harga_terkonversi * (1 + angka_inflasi_tahunan)

    return harga_terkonversi, peringatan