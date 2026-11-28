#!/usr/bin/env python3
import sys
import os
import json
import time
import requests
import importlib
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Pastikan laluan utama projek ditambah ke sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import konfigurasi dinamik daripada 01_config
_cfg = importlib.import_module("01_config")
B2_ACCOUNTS = _cfg.B2_ACCOUNTS
DATA_DIR = _cfg.DATA_DIR
LEDGER_FILE = getattr(_cfg, "LEDGER_FILE", os.path.join(DATA_DIR, "uploaded_ledger.json"))
STATE_FILE = os.path.join(DATA_DIR, "b2_storage_state.json")


def authorize_b2(key_id, app_key):
    """Mendapatkan token pengesahan dan URL API B2."""
    url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
    resp = requests.get(url, auth=(key_id, app_key), timeout=15)
    if resp.status_code != 200:
        raise ConnectionError(f"Gagal Authorize B2: HTTP {resp.status_code} - {resp.text}")
    
    data = resp.json()
    return data["apiUrl"], data["authorizationToken"]


def list_all_file_versions(api_url, auth_token, bucket_id):
    """Mengambil senarai semua versi fail dalam baldi B2 (termasuk fail terselindung/lama)."""
    url = f"{api_url}/b2api/v2/b2_list_file_versions"
    headers = {"Authorization": auth_token}
    
    all_files = []
    start_file_name = None
    start_file_id = None

    while True:
        body = {
            "bucketId": bucket_id,
            "maxFileCount": 1000
        }
        if start_file_name and start_file_id:
            body["startFileName"] = start_file_name
            body["startFileId"] = start_file_id

        resp = requests.post(url, headers=headers, json=body, timeout=20)
        if resp.status_code != 200:
            console.print(f"[bold red]❌ Ralat menyenaraikan fail:[/bold red] HTTP {resp.status_code} - {resp.text}")
            break

        data = resp.json()
        files = data.get("files", [])
        all_files.extend(files)

        start_file_name = data.get("nextFileName")
        start_file_id = data.get("nextFileId")

        if not start_file_name or not start_file_id:
            break

    return all_files


def delete_file_version(api_url, auth_token, file_name, file_id):
    """Memadam satu versi fail spesifik daripada B2."""
    url = f"{api_url}/b2api/v2/b2_delete_file_version"
    headers = {"Authorization": auth_token}
    body = {
        "fileName": file_name,
        "fileId": file_id
    }
    
    resp = requests.post(url, headers=headers, json=body, timeout=15)
    return resp.status_code == 200


def clear_bucket(acc):
    """Memadam semua fail dalam baldi B2 untuk satu akaun."""
    acc_idx = acc["index"]
    bucket_name = acc["bucket_name"]
    bucket_id = acc["bucket_id"]

    console.print(f"\n🔍 [bold cyan]Akaun {acc_idx}:[/bold cyan] Mengimbas [yellow]{bucket_name}[/yellow]...")

    try:
        api_url, auth_token = authorize_b2(acc["key_id"], acc["app_key"])
    except Exception as e:
        console.print(f"  [bold red]❌ Gagal log masuk ke Akaun {acc_idx}:[/bold red] {e}")
        return 0, 0

    files = list_all_file_versions(api_url, auth_token, bucket_id)
    total_files = len(files)

    if total_files == 0:
        console.print(f"  [dim]✔ Baldi {bucket_name} sudah sedia kosong.[/dim]")
        return 0, 0

    console.print(f"  📦 Ditemui [bold red]{total_files}[/bold red] fail/versi fail untuk dipadam.")

    deleted_count = 0
    total_bytes = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(f"Memadam fail di Akaun {acc_idx}...", total=total_files)

        for f in files:
            fname = f["fileName"]
            fid = f["fileId"]
            fsize = f.get("contentLength", 0)

            if delete_file_version(api_url, auth_token, fname, fid):
                deleted_count += 1
                total_bytes += fsize
            
            progress.advance(task)

    console.print(f"  [bold green]✅ Akaun {acc_idx} Selesai:[/bold green] {deleted_count}/{total_files} fail dipadam ({total_bytes / (1024*1024):.2f} MB cleared).")
    return deleted_count, total_bytes


def reset_local_states():
    """Mengosongkan fail penjejak status B2 dan ledger di persekitaran tempatan."""
    console.print("\n🧹 [bold cyan]Mengosongkan fail penjejak keadaan setempat...[/bold cyan]")

    # 1. Reset b2_storage_state.json
    initial_state = {
        "active_account_index": 1,
        "accounts_usage": {str(acc["index"]): 0 for acc in B2_ACCOUNTS}
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_state, f, indent=2)
    console.print(f"  [green]✔ Reset STATE_FILE ({STATE_FILE}) -> Akaun aktif 1 (0 bytes).[/green]")

    # 2. Reset uploaded_ledger.json
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
        console.print(f"  [green]✔ Reset LEDGER_FILE ({LEDGER_FILE}) -> Kosong.[/green]")


def main():
    console.print(Panel.fit("🔥 [bold red]Pembersihan Penuh Multi-Akaun Backblaze B2 Storage (Skrip 08)[/bold red]", border_style="red"))

    if not B2_ACCOUNTS:
        console.print("[bold red]❌ Tiada akaun B2 dikesan dalam konfigurasi .env.local![/bold red]")
        return

    console.print(f"📋 Dikesan [bold yellow]{len(B2_ACCOUNTS)} Akaun B2[/bold yellow] untuk dibersihkan.\n")

    grand_total_files = 0
    grand_total_bytes = 0

    for acc in B2_ACCOUNTS:
        files_deleted, bytes_deleted = clear_bucket(acc)
        grand_total_files += files_deleted
        grand_total_bytes += bytes_deleted

    # Reset tracker tempatan
    reset_local_states()

    console.print("\n" + "="*60)
    console.print(f"[bold green]✨ SEMUA B2 STORAGE TELAH DIBERSIHKAN![/bold green]")
    console.print(f"📊 Jumlah Fail Dipadam : [bold yellow]{grand_total_files}[/bold yellow]")
    console.print(f"💾 Jumlah Storan Dibebaskan: [bold yellow]{grand_total_bytes / (1024*1024):.2f} MB[/bold yellow]")
    console.print("="*60)


if __name__ == "__main__":
    main()