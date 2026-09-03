import gzip
import json
import time
import importlib
from pathlib import Path
from collections import defaultdict
from rich.console import Console

console = Console()

# Import konfigurasi dan kredensial secara dinamik dari 01_config (.env.local)
_config = importlib.import_module("01_config")
REDIS_URL = _config.REDIS_URL
REDIS_TOKEN = _config.REDIS_TOKEN
BASE_DIR = Path(_config.BASE_DIR)
CHUNKS_DIR = BASE_DIR / "data" / "chunks"

from upstash_redis import Redis

if not REDIS_URL or not REDIS_TOKEN:
    raise ValueError("UPSTASH_REDIS_REST_URL atau UPSTASH_REDIS_REST_TOKEN tiada dalam konfigurasi!")

redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
BATCH_SIZE = 300  # 300 operasi per 1 HTTP Request Pipeline

def build_redis_key(imdb_id, season=None, episode=None):
    if season and episode:
        return f"sub:{imdb_id}:{season}:{episode}"
    return f"sub:{imdb_id}"

def sync_chunk(file_path: Path):
    console.print(f"\n[yellow]📦 Memproses fail:[/yellow] [white]{file_path.name}[/white]")
    
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        data = json.load(f)

    # Kumpulkan metadata mengikut IMDb ID bagi mengelakkan pertindihan kunci
    grouped = defaultdict(list)
    for item in data:
        key = build_redis_key(item["imdb_id"], item.get("season"), item.get("episode"))
        grouped[key].append({
            "id": item["id"],
            "lang": item["lang"],
            "source": item["source"],
            "acc": item["acc"],
            "path": item["path"],
            "release": item["release"],
            "format": item["format"]
        })

    pipe = redis.pipeline()
    queued = 0
    total_http_requests = 0

    for key, sub_list in grouped.items():
        pipe.set(key, json.dumps(sub_list, ensure_ascii=False))
        queued += 1

        if queued >= BATCH_SIZE:
            pipe.exec()
            pipe = redis.pipeline()
            total_http_requests += 1
            queued = 0
            time.sleep(0.05)

    if queued > 0:
        pipe.exec()
        total_http_requests += 1

    console.print(f"  [bold green]✔ Siap:[/bold green] {len(grouped):,} filem/siri disegerakkan menggunakan [cyan]{total_http_requests} HTTP request[/cyan].")

def run():
    chunk_files = sorted(CHUNKS_DIR.glob("subtitles_part_*.json.gz"))
    if not chunk_files:
        console.print(f"[bold yellow]⚠ Tiada fail pecahan ditemui di {CHUNKS_DIR}. Sila jalankan 09_process_and_split.py dahulu.[/bold yellow]")
        return

    console.print(f"[bold cyan]🚀 Memulakan Segerak Upstash Redis (Jumlah Chunk: {len(chunk_files)})[/bold cyan]")
    for chunk in chunk_files:
        sync_chunk(chunk)

    console.print("\n[bold green]✨ Semua metadata berjaya disegerakkan ke Upstash Redis![/bold green]")

if __name__ == "__main__":
    run()