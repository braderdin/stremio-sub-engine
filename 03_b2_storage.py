import os
import json
import hashlib
import importlib
import time
from urllib.parse import quote
import requests
from rich.console import Console

# Import dinamik modul yang bermula dengan angka
_config = importlib.import_module("01_config")
B2_ACCOUNTS = _config.B2_ACCOUNTS
B2_MAX_STORAGE_BYTES = _config.B2_MAX_STORAGE_BYTES
DATA_DIR = _config.DATA_DIR

console = Console()

# Fail penjejak saiz dan akaun aktif
STATE_FILE = os.path.join(DATA_DIR, "b2_storage_state.json")

# Memori cache bagi sesi B2 (mengelakkan panggilan auth berulang)
_B2_AUTH_CACHE = {}
_B2_UPLOAD_CACHE = {}

def _load_storage_state():
    """Membaca rekod penggunaan saiz bagi setiap akaun."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    # Keadaan awal lalai
    initial_state = {
        "active_account_index": 1,
        "accounts_usage": {str(acc["index"]): 0 for acc in B2_ACCOUNTS}
    }
    _save_storage_state(initial_state)
    return initial_state

def _save_storage_state(state):
    """Menyimpan rekod penggunaan saiz ke fail JSON."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def _get_account_by_index(acc_index):
    """Mencari objek konfigurasi akaun B2 berdasarkan indeks."""
    for acc in B2_ACCOUNTS:
        if acc["index"] == acc_index:
            return acc
    return None

def authorize_b2_account(acc_index):
    """Mendapatkan token pengesahan B2 dengan sokongan cache 24 jam."""
    now = time.time()
    if acc_index in _B2_AUTH_CACHE:
        cache = _B2_AUTH_CACHE[acc_index]
        # Sahkan token sah jika belum melepasi 20 jam
        if now - cache["timestamp"] < 72000:
            return cache["data"]

    acc = _get_account_by_index(acc_index)
    if not acc:
        raise ValueError(f"Akaun B2 index {acc_index} tidak ditemui!")

    url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
    resp = requests.get(url, auth=(acc["key_id"], acc["app_key"]), timeout=15)
    
    if resp.status_code != 200:
        raise ConnectionError(f"Gagal Authorize Akaun B2 {acc_index}: HTTP {resp.status_code} - {resp.text}")

    auth_data = resp.json()
    _B2_AUTH_CACHE[acc_index] = {
        "data": auth_data,
        "timestamp": now
    }
    return auth_data

def get_b2_upload_url(acc_index):
    """Mendapatkan URL muat naik khusus untuk baldi akaun B2."""
    if acc_index in _B2_UPLOAD_CACHE:
        return _B2_UPLOAD_CACHE[acc_index]

    acc = _get_account_by_index(acc_index)
    if not acc:
        raise ValueError(f"Akaun B2 index {acc_index} tidak ditemui!")

    auth_data = authorize_b2_account(acc_index)
    api_url = auth_data["apiUrl"]
    auth_token = auth_data["authorizationToken"]

    url = f"{api_url}/b2api/v2/b2_get_upload_url"
    resp = requests.post(
        url,
        headers={"Authorization": auth_token},
        json={"bucketId": acc["bucket_id"]},
        timeout=15
    )

    if resp.status_code != 200:
        raise ConnectionError(f"Gagal mendapatkan upload URL B2 {acc_index}: HTTP {resp.status_code}")

    upload_data = resp.json()
    _B2_UPLOAD_CACHE[acc_index] = upload_data
    return upload_data

def upload_subtitle_to_b2(target_path, content, content_type="text/plain"):
    """
    Memuat naik fail subtitle ke akaun B2 aktif dengan kawalan had 9.5GB automatik.
    """
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content

    file_size = len(content_bytes)
    sha1_hash = hashlib.sha1(content_bytes).hexdigest()

    state = _load_storage_state()
    active_idx = state.get("active_account_index", 1)

    # 1. Semakan Had 9.5GB & Pertukaran Akaun (Rollover)
    current_acc_usage = state["accounts_usage"].get(str(active_idx), 0)
    
    if current_acc_usage + file_size >= B2_MAX_STORAGE_BYTES:
        console.print(f"[bold yellow]⚠ Had 9.5GB untuk Akaun {active_idx} dicapai! Mengalihkan ke akaun seterusnya...[/bold yellow]")
        active_idx += 1
        acc_check = _get_account_by_index(active_idx)
        
        if not acc_check:
            raise OverflowError("Semua akaun Backblaze B2 yang didaftarkan telah mencapai had storan 9.5GB!")
            
        state["active_account_index"] = active_idx
        _save_storage_state(state)

    acc = _get_account_by_index(active_idx)
    if not acc:
        raise ValueError(f"Akaun B2 index {active_idx} tidak ditemui!")
    
    # 2. Ambil Upload URL
    upload_info = get_b2_upload_url(active_idx)
    upload_url = upload_info["uploadUrl"]
    upload_auth = upload_info["authorizationToken"]

    headers = {
        "Authorization": upload_auth,
        "X-Bz-File-Name": quote(target_path),
        "Content-Type": content_type,
        "Content-Length": str(file_size),
        "X-Bz-Content-Sha1": sha1_hash
    }

    # 3. Hantar Fail ke B2
    resp = requests.post(upload_url, headers=headers, data=content_bytes, timeout=30)

    # Jika token muat naik luput, muat semula sekali lagi
    if resp.status_code in [401, 503]:
        _B2_UPLOAD_CACHE.pop(active_idx, None)
        upload_info = get_b2_upload_url(active_idx)
        headers["Authorization"] = upload_info["authorizationToken"]
        resp = requests.post(upload_info["uploadUrl"], headers=headers, data=content_bytes, timeout=30)

    if resp.status_code != 200:
        raise IOError(f"Ralat Muat Naik B2 ({acc['bucket_name']}): HTTP {resp.status_code} - {resp.text}")

    upload_result = resp.json()
    file_id = upload_result.get("fileId")

    # 4. Kemas kini rekod penjejak saiz setempat
    state["accounts_usage"][str(active_idx)] = current_acc_usage + file_size
    _save_storage_state(state)

    return {
        "account_index": active_idx,
        "bucket_name": acc["bucket_name"],
        "target_path": target_path,
        "file_id": file_id,
        "size_bytes": file_size
    }

if __name__ == "__main__":
    console.print("[bold cyan]🧪 Menguji Enjin Multi-Akaun B2...[/bold cyan]")
    test_path = "subs/test/diagnostics_sample.srt"
    test_content = "1\n00:00:01,000 --> 00:00:03,000\nUjian Sistem Multi-Account B2 Berjaya."
    
    try:
        result = upload_subtitle_to_b2(test_path, test_content)
        console.print(f"[bold green]✔ Muat Naik Berjaya![/bold green]")
        console.print(f"📦 Akaun Digunakan : [cyan]Akaun {result['account_index']} ({result['bucket_name']})[/cyan]")
        console.print(f"📁 Laluan Fail     : [white]{result['target_path']}[/white]")
        console.print(f"🆔 B2 File ID      : [dim]{result['file_id']}[/dim]")
        
        state_data = _load_storage_state()
        console.print(f"📊 Penggunaan Saiz Akaun 1 : [yellow]{state_data['accounts_usage']['1']} bytes[/yellow] / {B2_MAX_STORAGE_BYTES} bytes")
    except Exception as e:
        console.print(f"[bold red]❌ Gagal:[/bold red] {e}")