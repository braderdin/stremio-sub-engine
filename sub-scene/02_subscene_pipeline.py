import sys
import time
import json
import importlib
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Sambung direktori utama projek
SUB_SCENE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SUB_SCENE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Muat B2 & Redis
_b2 = importlib.import_module("03_b2_storage")
upload_subtitle_to_b2 = _b2.upload_subtitle_to_b2

_redis = importlib.import_module("04_redis_manager")
save_subtitle_record = _redis.save_subtitle_record

# Muat pengikis Subscene
_scraper = importlib.import_module("01_subscene_scraper")
create_stealth_session = _scraper.create_stealth_session
search_subscene = _scraper.search_subscene
get_movie_subtitles = _scraper.get_movie_subtitles
download_and_extract_srt = _scraper.download_and_extract_srt

LEDGER_PATH = SUB_SCENE_DIR / "subscene_ledger.json"

def load_ledger():
    if LEDGER_PATH.exists():
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_bytes": 0, "total_files": 0, "items": {}}

def save_ledger(data):
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def run_pipeline(seed_queries: list, target_mb: int = 100, delay_sec: float = 0.5):
    max_bytes = target_mb * 1024 * 1024
    ledger = load_ledger()

    console.print(Panel.fit(
        f"🎬 [bold cyan]Subscene Ingestion Pipeline (BM & ID Sahaja)[/bold cyan] ⚡\n"
        f"🎯 Had Sasaran: [bold green]{target_mb} MB[/bold green] | Terkumpul: [yellow]{ledger['total_bytes'] / (1024*1024):.2f} MB[/yellow]",
        border_style="cyan"
    ))

    # Mulakan sesi stealth dengan priming
    session, ok = create_stealth_session()
    if not ok:
        console.print("[bold red]❌ Gagal melepasi tapisan permulaan Cloudflare. Sesi dibatalkan.[/bold red]")
        return

    session_bytes = 0
    session_files = 0

    try:
        for query in seed_queries:
            if ledger["total_bytes"] >= max_bytes or session_bytes >= max_bytes:
                console.print(f"\n[bold green]🎯 Sasaran {target_mb} MB dicapai sepenuhnya! Menghentikan pipeline.[/bold green]")
                break

            console.print(f"\n[cyan]🔎 Mencari:[/cyan] [bold white]{query}[/bold white]")
            movies = search_subscene(session, query)
            if not movies:
                time.sleep(delay_sec)
                continue

            for movie in movies[:3]:
                if ledger["total_bytes"] >= max_bytes or session_bytes >= max_bytes:
                    break

                console.print(f"  [yellow]📂 Meneliti:[/yellow] {movie['title']}")
                subs = get_movie_subtitles(session, movie["url"])
                if not subs:
                    continue

                for sub in subs:
                    if ledger["total_bytes"] >= max_bytes or session_bytes >= max_bytes:
                        break

                    sub_key = f"subscene_{sub['sub_id']}"
                    if sub_key in ledger["items"]:
                        continue

                    console.print(f"    📥 Menyedut: [{sub['lang'].upper()}] {sub['release']}")

                    srt_text, size_bytes = download_and_extract_srt(session, sub["detail_url"])
                    if not srt_text or size_bytes < 100:
                        time.sleep(delay_sec)
                        continue

                    b2_path = f"subs/subscene/{movie['id']}/{sub['lang']}_{sub['sub_id']}.srt"

                    # Muat naik ke B2
                    try:
                        b2_res = upload_subtitle_to_b2(b2_path, srt_text)
                        console.print(f"      [bold green]✔ B2 Upload:[/bold green] Akaun {b2_res['account_index']} ({size_bytes:,} bytes)")
                    except Exception as e:
                        console.print(f"      [bold red]❌ B2 Gagal:[/bold red] {e}")
                        continue

                    # Simpan metadata ke Upstash Redis
                    redis_item = {
                        "id": sub_key,
                        "lang": sub["lang"],
                        "source": "subscene",
                        "acc": b2_res["account_index"],
                        "path": b2_path,
                        "release": sub["release"],
                        "format": "srt"
                    }
                    save_subtitle_record(movie["id"], redis_item)

                    ledger["total_bytes"] += size_bytes
                    ledger["total_files"] += 1
                    ledger["items"][sub_key] = {
                        "title": movie["title"],
                        "lang": sub["lang"],
                        "size": size_bytes,
                        "path": b2_path
                    }

                    session_bytes += size_bytes
                    session_files += 1
                    save_ledger(ledger)

                    time.sleep(delay_sec)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠ Sesi dihentikan manual (Ctrl+C). Lejar disimpan.[/bold yellow]")

    # Paparan Rumusan
    summary = Table(title="Rumusan Pengekstrakan Subscene", border_style="green")
    summary.add_column("Metrik", style="white")
    summary.add_column("Sesi Ini", style="cyan")
    summary.add_column("Jumlah Lejar", style="green")

    summary.add_row("Fail Dimuat Naik", f"{session_files:,}", f"{ledger['total_files']:,}")
    summary.add_row("Kapasiti Data", f"{session_bytes / (1024*1024):.2f} MB", f"{ledger['total_bytes'] / (1024*1024):.2f} MB")
    console.print(summary)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mb", type=int, default=100, help="Had muat naik dalam MB")
    parser.add_argument("--delay", type=float, default=0.5, help="Sela masa permintaan (saat)")
    args = parser.parse_args()

    SEEDS = [
        "Avatar", "Avengers", "Spider-Man", "Batman", "Harry Potter",
        "Fast and Furious", "John Wick", "Transformers", "Jurassic",
        "Resident Evil", "The Matrix", "Munafik", "Dukun", "Ejen Ali"
    ]

    run_pipeline(SEEDS, target_mb=args.mb, delay_sec=args.delay)