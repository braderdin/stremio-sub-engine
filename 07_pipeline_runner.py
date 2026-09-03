import os
import gzip
import json
import time
import importlib
import argparse
from pathlib import Path
from curl_cffi import requests
from rich.console import Console
from rich.panel import Panel

console = Console()

# 1. Import modul modular
_config = importlib.import_module("01_config")
DATA_DIR = Path(_config.DATA_DIR)
LEDGER_FILE = Path(_config.LEDGER_FILE)
CHUNKS_DIR = DATA_DIR / "chunks"

_b2 = importlib.import_module("03_b2_storage")
upload_subtitle_to_b2 = _b2.upload_subtitle_to_b2

# Sesi Stealth menggunakan curl_cffi untuk melepasi sekatan anti-bot pelayan
session = requests.Session(impersonate="chrome124")

def load_ledger():
    """Membaca lejar sarikata yang telah berjaya dimuat naik ke B2."""
    if LEDGER_FILE.exists():
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_ledger(ledger_data):
    """Menyimpan rekod lejar setempat."""
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger_data, f, indent=2)

def download_raw_subtitle(sub_id):
    """
    Memuat turun fail sarikata fizikal (.srt) daripada pelayan OpenSubtitles.
    Menyokong nyahmampat automatik dan pelbagai pengekodan teks.
    """
    url = f"https://dl.opensubtitles.org/en/download/sub/{sub_id}"
    headers = {
        "Referer": "https://www.opensubtitles.org/",
        "Accept": "*/*"
    }

    try:
        resp = session.get(url, headers=headers, timeout=12)
        
        # Had muat turun atau sekatan IP
        if resp.status_code in [429, 403]:
            console.print(f"  [bold red]⛔ Had Muat Turun Dicapai / Sekatan IP (HTTP {resp.status_code})[/bold red]")
            return None

        if resp.status_code != 200:
            return None

        content = resp.content
        # Abaikan jika pelayan memulangkan dokumen HTML ralat/sekatan
        if b"<!DOCTYPE html" in content[:100] or b"<html" in content[:100]:
            return None

        # Nyahmampat gzip jika kandungan dimampatkan
        try:
            decompressed = gzip.decompress(content)
        except Exception:
            decompressed = content

        # Uji nyahkod mengikut turutan format pengekodan teks biasa
        for enc in ["utf-8", "latin-1", "windows-1252", "cp1256"]:
            try:
                return decompressed.decode(enc)
            except UnicodeDecodeError:
                continue

        return decompressed.decode("utf-8", errors="ignore")
    except Exception:
        return None

def process_chunks_ingestion(limit=50, delay_sec=1.0):
    console.print(Panel.fit("🚀 [bold cyan]Pipeline Ingestion: Membaca Terus Dari Chunks BM/ID[/bold cyan] ⚡", border_style="cyan"))

    chunk_files = sorted(CHUNKS_DIR.glob("subtitles_part_*.json.gz"))
    if not chunk_files:
        console.print(f"[bold red]❌ Tiada fail chunk ditemui di {CHUNKS_DIR}[/bold red]")
        return

    ledger = load_ledger()
    console.print(f"📋 Lejar Semasa: [yellow]{len(ledger):,} fail[/yellow] sudah dimuat naik ke B2.")
    console.print(f"🎯 Sasaran Sesi Ini: [bold green]{limit if limit > 0 else 'Semua'}[/bold green] fail fizikal.")

    processed = 0
    start_time = time.time()

    try:
        for chunk_path in chunk_files:
            if limit > 0 and processed >= limit:
                break

            console.print(f"\n[yellow]📂 Membuka fail pecahan:[/yellow] {chunk_path.name}")
            with gzip.open(chunk_path, "rt", encoding="utf-8") as f:
                records = json.load(f)

            for item in records:
                if limit > 0 and processed >= limit:
                    break

                sub_id = str(item["sub_id"])
                if sub_id in ledger:
                    continue

                target_path = item["path"]
                title_display = item.get("title") or item.get("release") or "Movie"
                console.print(f"📥 Menyedut Sub ID: [bold white]{sub_id}[/bold white] ({item['lang'].upper()}) - {title_display}")

                # 1. Muat turun teks SRT fizikal
                srt_content = download_raw_subtitle(sub_id)
                if not srt_content or len(srt_content.strip()) < 20:
                    console.print(f"  [yellow]⚠ Gagal muat turun kandungan sub {sub_id}. Melangkau...[/yellow]")
                    time.sleep(delay_sec)
                    continue

                # 2. Muat naik fail fizikal ke Backblaze B2 (dengan kawalan rollover 9.5GB)
                try:
                    b2_res = upload_subtitle_to_b2(target_path, srt_content)
                    console.print(f"  [bold green]✔ B2 Upload:[/bold green] Akaun {b2_res['account_index']} ({b2_res['size_bytes']} bytes)")
                except Exception as e:
                    console.print(f"  [bold red]❌ B2 Upload Gagal:[/bold red] {e}")
                    continue

                # 3. Kemas kini Lejar Setempat
                ledger[sub_id] = {
                    "imdb_id": item["imdb_id"],
                    "lang": item["lang"],
                    "acc": b2_res["account_index"],
                    "path": target_path,
                    "timestamp": int(time.time())
                }
                save_ledger(ledger)

                processed += 1
                time.sleep(delay_sec)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠ Proses dihentikan pengguna (Ctrl+C). Menyimpan lejar terkini...[/bold yellow]")
        save_ledger(ledger)

    duration = time.time() - start_time
    console.print(f"\n[bold green]✨ Pusingan Selesai![/bold green] {processed} fail sarikata fizikal berjaya disimpan ke B2 dalam {duration:.1f}s.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stremio Sub Engine - Chunk Based Pipeline Ingestion")
    parser.add_argument("--limit", type=int, default=10, help="Had muat naik sesi ini (0 untuk tanpa had)")
    parser.add_argument("--delay", type=float, default=1.0, help="Sela masa permintaan (saat)")
    args = parser.parse_args()

    process_chunks_ingestion(limit=args.limit, delay_sec=args.delay)