"""
update_data.py — Pembaruan data inflasi (Mode Master Admin ke JSONBin).

Alur:
  1. Unduh data eksisting langsung dari JSONBin (Cloud).
  2. Coba ambil otomatis dari BPS WebAPI (Bulanan & Tahunan).
  3. Bandingkan data BPS dengan data Cloud, MINTA KONFIRMASI.
  4. Bila disetujui, langsung tembak (PUT) ke JSONBin menggunakan Master Key.
  5. Bila pengambilan BPS gagal, beralih ke mode input MANUAL.
"""

import json
import shutil
import urllib.request
import urllib.error
from datetime import date
import core

# --------------------------------------------------------------------------
# KONFIGURASI JSONBIN (OTORITAS MASTER)
# --------------------------------------------------------------------------
BIN_ID = "6a601e15f5f4af5e29aee587"
# WAJIB MASTER KEY UNTUK MENGUBAH DATA (PUT)
MASTER_KEY = "$2a$10$f4oxcroY/2RTkOHExG4nA.pJV.KbIiDoLNx320J60WcvcQQwFxsq2"
URL_JSONBIN = f"https://api.jsonbin.io/v3/b/{BIN_ID}"

TAHUN_RENTANG_TH = 3  
CONFIG_FILE = "config.json"

DATA_CLOUD_TAHUNAN = {}
DATA_CLOUD_BULANAN = {}

# --------------------------------------------------------------------------
# Cloud Operations (GET & PUT)
# --------------------------------------------------------------------------
def ambil_data_cloud():
    global DATA_CLOUD_TAHUNAN, DATA_CLOUD_BULANAN
    print("\n[Menghubungkan ke Cloud] Mengunduh database JSONBin saat ini...")
    try:
        req = urllib.request.Request(URL_JSONBIN + "?meta=false")
        req.add_header('X-Master-Key', MASTER_KEY)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                DATA_CLOUD_TAHUNAN = data.get("tahunan", {})
                DATA_CLOUD_BULANAN = data.get("bulanan", {})
                print("  => Sukses! Data Cloud siap.")
                return True
    except Exception as e:
        print(f"  [FATAL ERROR] Gagal membaca JSONBin: {e}")
        print("  Pastikan internet aktif dan Master Key benar.")
    return False

def simpan_ke_cloud():
    print("\n[Mengunggah ke Cloud] Menyimpan pembaruan ke JSONBin...")
    data_gabungan = {
        "tahunan": DATA_CLOUD_TAHUNAN,
        "bulanan": DATA_CLOUD_BULANAN
    }
    
    try:
        with open(core.data_path("backup_sebelum_update.json"), "w", encoding="utf-8") as f:
            json.dump(data_gabungan, f, indent=2)
    except: pass

    payload = json.dumps(data_gabungan).encode('utf-8')
    req = urllib.request.Request(URL_JSONBIN, data=payload, method='PUT')
    req.add_header('X-Master-Key', MASTER_KEY)
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0')
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                print("  => SUKSES BESAR! Data di JSONBin telah diperbarui.")
                return True
    except Exception as e:
        print(f"  [ERROR] Gagal menyimpan ke JSONBin: {e}")
    return False

# --------------------------------------------------------------------------
# Util file & Validasi
# --------------------------------------------------------------------------
def muat_config():
    try:
        with open(core.data_path(CONFIG_FILE), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"config.json tidak ditemukan. Melanjutkan tanpa API key BPS (mode manual).")
        return {}

def ya(prompt):
    return input(prompt).strip().lower() in ("y", "ya", "yes")

def valid_bulanan(persen, cfg):
    lo = cfg.get("batas_bulanan_persen_min", -5.0)
    hi = cfg.get("batas_bulanan_persen_max", 10.0)
    return lo <= persen <= hi, lo, hi

def valid_tahunan(fraksi, cfg):
    lo = cfg.get("batas_tahunan_fraksi_min", -0.05)
    hi = cfg.get("batas_tahunan_fraksi_max", 0.25)
    return lo <= fraksi <= hi, lo, hi

# --------------------------------------------------------------------------
# Penyimpanan (Memory -> Trigger Cloud Push)
# --------------------------------------------------------------------------
def simpan_bulanan(tahun, bulan, persen, cfg):
    ok, lo, hi = valid_bulanan(persen, cfg)
    if not ok:
        print(f"  DITOLAK: {persen}% di luar batas wajar bulanan ({lo}%..{hi}%). Cek lagi angkanya.")
        return False
    
    ty = str(tahun)
    lama = DATA_CLOUD_BULANAN.get(ty, {}).get(bulan)
    print(f"  Inflasi bulanan {bulan} {tahun}: {persen}%" +
          (f"  (menimpa nilai lama {lama}%)" if lama is not None else ""))
    
    if not ya("  Simpan angka ini ke Cloud? (y/n): "):
        print("  Dilewati.")
        return False
    
    DATA_CLOUD_BULANAN.setdefault(ty, {})[bulan] = persen
    simpan_ke_cloud()
    return True

def simpan_tahunan(tahun, fraksi, cfg):
    ok, lo, hi = valid_tahunan(fraksi, cfg)
    if not ok:
        print(f"  DITOLAK: {fraksi} di luar batas wajar tahunan ({lo}..{hi}). Cek lagi angkanya.")
        return False
    
    ty = str(tahun)
    lama = DATA_CLOUD_TAHUNAN.get(ty)
    print(f"  Inflasi tahun kalender {tahun}: {fraksi}  (= {fraksi*100:.2f}%)" +
          (f"  (menimpa nilai lama {lama})" if lama is not None else ""))
    
    if not ya("  Simpan angka ini ke Cloud? (y/n): "):
        print("  Dilewati.")
        return False
    
    DATA_CLOUD_TAHUNAN[ty] = fraksi
    simpan_ke_cloud()
    return True

# --------------------------------------------------------------------------
# BPS WebAPI Operations & Extractors
# --------------------------------------------------------------------------
VERVAR_NASIONAL = "9999"

def ambil_bps(var_id, cfg, vervar=None, tahun_awal=None, tahun_akhir=None):
    key = cfg.get("bps_api_key", "").strip()
    if not key:
        return None
    domain = cfg.get("domain", "0000")
    if tahun_akhir is None:
        tahun_akhir = date.today().year
    if tahun_awal is None:
        tahun_awal = tahun_akhir - (TAHUN_RENTANG_TH - 1)
    
    th_range = f"{tahun_awal - 1900}:{tahun_akhir - 1900}"
    url = (f"https://webapi.bps.go.id/v1/api/list/model/data/lang/ind/"
           f"domain/{domain}/var/{var_id}/th/{th_range}/key/{key}/")
    if vervar:
        url += f"vervar/{vervar}/"
    
    url_tersamar = url.replace(key, key[:4] + "..." + key[-4:] if len(key) > 8 else "***")
    print(f"  [debug] URL BPS (Var {var_id}): {url_tersamar}")
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KalkulatorInflasi/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            mentah = resp.read().decode("utf-8")
            payload = json.loads(mentah)
            return payload
    except (urllib.error.URLError, ValueError, TimeoutError) as e:
        print(f"  Gagal menghubungi BPS: {e}")
        return None

def ekstrak_bulanan_nasional(payload):
    var_list = payload.get("var", [])
    turvar_list = payload.get("turvar", [])
    if not var_list or not turvar_list:
        return {}
    prefix = f"{VERVAR_NASIONAL}{var_list[0]['val']}{turvar_list[0]['val']}"
    tahun_label = {str(t["val"]): t["label"] for t in payload.get("tahun", [])}
    turtahun_label = {str(t["val"]): t["label"] for t in payload.get("turtahun", [])}

    hasil = {}
    for kunci, nilai in payload.get("datacontent", {}).items():
        if not kunci.startswith(prefix):
            continue
        sisa = kunci[len(prefix):]
        th_str, turtahun_str = sisa[:3], sisa[3:]
        thn = tahun_label.get(th_str)
        bln = turtahun_label.get(turtahun_str)
        if not thn or not bln or bln not in core.BULAN_LIST:
            continue  
        hasil[(int(thn), bln)] = nilai
    return hasil

def ekstrak_tahunan_nasional(payload):
    """Mengekstrak inflasi tahunan. Mengambil nilai pada bulan terakhir (YtD) di tiap tahun."""
    var_list = payload.get("var", [])
    turvar_list = payload.get("turvar", [])
    if not var_list or not turvar_list:
        return {}
    prefix = f"{VERVAR_NASIONAL}{var_list[0]['val']}{turvar_list[0]['val']}"
    tahun_label = {str(t["val"]): t["label"] for t in payload.get("tahun", [])}
    turtahun_label = {str(t["val"]): t["label"] for t in payload.get("turtahun", [])}

    temp_tahunan = {}
    for kunci, nilai in payload.get("datacontent", {}).items():
        if not kunci.startswith(prefix):
            continue
        sisa = kunci[len(prefix):]
        th_str, turtahun_str = sisa[:3], sisa[3:]
        thn = tahun_label.get(th_str)
        bln = turtahun_label.get(turtahun_str)
        
        if not thn or not bln: continue
        thn_int = int(thn)
        bln_lower = bln.lower()
        
        if thn_int not in temp_tahunan:
            temp_tahunan[thn_int] = {}
            
        if "tahunan" in bln_lower:
            temp_tahunan[thn_int][13] = nilai # Index tertinggi buatan untuk "Tahunan"
        elif bln in core.BULAN_LIST:
            temp_tahunan[thn_int][core.BULAN_LIST.index(bln)] = nilai
            
    hasil = {}
    for thn, data_bln in temp_tahunan.items():
        if not data_bln: continue
        # Mengambil nilai YtD di bulan paling akhir yang tersedia untuk tahun tersebut
        idx_max = max(data_bln.keys())
        # Konversi persen dari BPS menjadi fraksi desimal (mis. 1.79 -> 0.0179)
        hasil[thn] = data_bln[idx_max] / 100.0
        
    return hasil

def bandingkan_dengan_cloud(data_bps):
    beda = []
    for (thn, bln), nilai_bps in data_bps.items():
        nilai_cloud = DATA_CLOUD_BULANAN.get(str(thn), {}).get(bln)
        if nilai_cloud is None or abs(nilai_cloud - nilai_bps) > 1e-9:
            beda.append((thn, bln, nilai_bps, nilai_cloud))
    beda.sort(key=lambda x: (x[0], core.BULAN_LIST.index(x[1])))
    return beda

def bandingkan_dengan_cloud_tahunan(data_bps_tahunan):
    beda = []
    for thn, nilai_bps_fraksi in data_bps_tahunan.items():
        nilai_cloud = DATA_CLOUD_TAHUNAN.get(str(thn))
        # Toleransi selisih kalkulasi floating point
        if nilai_cloud is None or abs(nilai_cloud - nilai_bps_fraksi) > 1e-6:
            beda.append((thn, nilai_bps_fraksi, nilai_cloud))
    beda.sort(key=lambda x: x[0])
    return beda

# --------------------------------------------------------------------------
# Alur Otomatis & Manual
# --------------------------------------------------------------------------
def alur_otomatis(cfg):
    var_bulanan = cfg.get("var_inflasi_bulanan_m_to_m")
    var_tahunan = cfg.get("var_inflasi_tahun_kalender")
    tahun_ini = date.today().year
    
    # === BLOK 1: INFLASI BULANAN ===
    print("\n[Otomatis] Mengambil data INFLASI BULANAN dari API BPS...")
    payload_bulanan = ambil_bps(var_bulanan, cfg, vervar=VERVAR_NASIONAL,
                         tahun_awal=tahun_ini - (TAHUN_RENTANG_TH - 1), tahun_akhir=tahun_ini)
    
    if payload_bulanan is None or payload_bulanan.get("status") != "OK":
        print("  Gagal mengunduh inflasi bulanan. Beralih ke manual.")
        alur_manual_bulanan(cfg)
    else:
        data_bps_bulanan = ekstrak_bulanan_nasional(payload_bulanan)
        diff_bulanan = bandingkan_dengan_cloud(data_bps_bulanan)

        if not diff_bulanan:
            print("  Semua data BULANAN Cloud sinkron dengan BPS. Tidak ada update.")
        else:
            print(f"  Ditemukan {len(diff_bulanan)} entri bulanan baru/berbeda:")
            for thn, bln, baru, lama in diff_bulanan:
                status = "BARU" if lama is None else f"beda dari cloud ({lama}%)"
                print(f"    {bln} {thn}: BPS = {baru}%  [{status}]")
            print("\n  Konfirmasi tiap entri satu per satu:")
            for thn, bln, baru, lama in diff_bulanan:
                simpan_bulanan(thn, bln, baru, cfg)

    # === BLOK 2: INFLASI TAHUNAN ===
    if var_tahunan:
        print("\n[Otomatis] Mengambil data INFLASI TAHUNAN dari API BPS...")
        payload_tahunan = ambil_bps(var_tahunan, cfg, vervar=VERVAR_NASIONAL,
                             tahun_awal=tahun_ini - (TAHUN_RENTANG_TH - 1), tahun_akhir=tahun_ini)
        
        if payload_tahunan and payload_tahunan.get("status") == "OK":
            data_bps_tahunan = ekstrak_tahunan_nasional(payload_tahunan)
            diff_tahunan = bandingkan_dengan_cloud_tahunan(data_bps_tahunan)
            
            if not diff_tahunan:
                print("  Semua data TAHUNAN Cloud sinkron dengan BPS. Tidak ada update.")
            else:
                print(f"  Ditemukan {len(diff_tahunan)} entri tahunan baru/berbeda:")
                for thn, baru_fraksi, lama_fraksi in diff_tahunan:
                    status = "BARU" if lama_fraksi is None else f"beda dari cloud ({lama_fraksi*100:.2f}%)"
                    print(f"    Tahun {thn}: BPS = {baru_fraksi*100:.2f}%  [{status}]")
                print("\n  Konfirmasi tiap entri tahunan satu per satu:")
                for thn, baru_fraksi, lama_fraksi in diff_tahunan:
                    simpan_tahunan(thn, round(baru_fraksi, 6), cfg)
        else:
            print("  Gagal mengunduh inflasi tahunan BPS. Beralih ke manual.")
            alur_manual_tahunan(cfg)
    else:
        alur_manual_tahunan(cfg)
        
    return True


def minta_float(prompt):
    while True:
        teks = input(prompt).strip().replace(",", ".")
        if teks == "":
            return None
        try:
            return float(teks)
        except ValueError:
            print("  -> Bukan angka. Contoh: 0.68")

def minta_bulan():
    while True:
        b = input("  Bulan (ex: Juli, kosongkan untuk lewati): ").strip().capitalize()
        if b == "":
            return None
        if b in core.BULAN_LIST:
            return b
        print("  -> Nama bulan tidak dikenal.")

def minta_tahun():
    while True:
        t = input("  Tahun (ex: 2026): ").strip()
        if t == "":
            return None
        try:
            return int(t)
        except ValueError:
            print("  -> Tahun harus angka.")

def alur_manual_bulanan(cfg):
    print("\nA. Tambah/ubah inflasi BULANAN (m-to-m). Angka dalam PERSEN, mis. 0.68")
    tahun = minta_tahun()
    if tahun is not None:
        bulan = minta_bulan()
        if bulan is not None:
            persen = minta_float("  Inflasi bulanan (%): ")
            if persen is not None:
                simpan_bulanan(tahun, bulan, persen, cfg)

def alur_manual_tahunan(cfg):
    print("\nB. (Sekali/tahun) Perbarui inflasi TAHUN KALENDER tahun berjalan.")
    print("   Masukkan dalam PERSEN juga (mis. 1.79); akan disimpan sebagai 0.0179.")
    if ya("   Perbarui angka tahunan secara manual? (y/n): "):
        t2 = minta_tahun()
        if t2 is not None:
            persen_th = minta_float("  Inflasi tahun kalender (%): ")
            if persen_th is not None:
                simpan_tahunan(t2, round(persen_th / 100, 6), cfg)

def alur_manual(cfg):
    print("\n[Input Manual]")
    alur_manual_bulanan(cfg)
    alur_manual_tahunan(cfg)

# --------------------------------------------------------------------------
def main():
    print("=== PEMBARUAN DATA INFLASI KE JSONBIN ===")
    cfg = muat_config()

    sukses_cloud = ambil_data_cloud()
    if not sukses_cloud:
        print("\nSistem dihentikan karena JSONBin tidak dapat diakses.")
        return

    bulan_akhir, tahun_akhir = core.data_terakhir(DATA_CLOUD_BULANAN)
    if bulan_akhir:
        print(f"Data bulanan terakhir di Cloud saat ini: {bulan_akhir} {tahun_akhir}")

    punya_key = bool(cfg.get("bps_api_key", "").strip())
    print(f"API key BPS: {'terpasang' if punya_key else 'BELUM diisi (mode manual)'}")

    if punya_key:
        if not alur_otomatis(cfg):
            alur_manual(cfg)
    else:
        alur_manual(cfg)

    print("\nSelesai.")
    try:
        input("Tekan Enter untuk keluar...")
    except (EOFError, KeyboardInterrupt):
        pass

if __name__ == "__main__":
    main()