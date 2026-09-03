import os
import gzip
import json
from pathlib import Path
from rich.console import Console

console = Console()

BASE_DIR = Path("/home/braderdin/stremio-sub-engine")
INPUT_FILE = BASE_DIR / "data" / "subtitles_all.txt.gz"
OUTPUT_DIR = BASE_DIR / "data" / "chunks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Indeks Kolum Rasmi Dump OpenSubtitles
IDX_SUB_ID = 0
IDX_MOVIE_NAME = 1
IDX_MOVIE_YEAR = 2
IDX_LANG_NAME = 3
IDX_ISO639 = 4
IDX_IMDB_ID = 6
IDX_FORMAT = 7
IDX_RELEASE_NAME = 9
IDX_SEASON = 11
IDX_EPISODE = 12
IDX_PARENT_IMDB = 13

RECORDS_PER_CHUNK = 100000  # ~15-20MB mampatan gzip setiap fail

def get_col(cols, idx, default=""):
    """Mengambil nilai kolum secara selamat tanpa mencetuskan IndexError."""
    return cols[idx].strip() if len(cols) > idx else default

def clean_imdb(raw_id):
    if not raw_id or raw_id == "0":
        return None
    c_id = str(raw_id).strip()
    return f"tt{c_id.zfill(7)}" if c_id.isdigit() else c_id

def flush_chunk(records, part_idx):
    target = OUTPUT_DIR / f"subtitles_part_{part_idx:03d}.json.gz"
    with gzip.open(target, "wt", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)
    size_mb = os.path.getsize(target) / (1024 * 1024)
    console.print(f"💾 [bold green]Bahagian {part_idx:03d} disimpan:[/bold green] {len(records):,} rekod ({size_mb:.2f} MB)")

def process():
    if not INPUT_FILE.exists():
        console.print(f"[bold red]❌ Fail sumber tidak wujud di:[/bold red] {INPUT_FILE}")
        return

    part_idx = 1
    current_batch = []
    total_matched = 0

    console.print("[yellow]⏳ Memulakan penapisan BM/ID & pembahagian fail...[/yellow]")

    with gzip.open(INPUT_FILE, "rt", encoding="utf-8", errors="ignore") as gz:
        gz.readline()  # Langkau baris tajuk kolum

        for line in gz:
            cols = line.rstrip("\r\n").split("\t")
            
            # Wajib sekurang-kurangnya mempunyai data asas sehingga kolum IMDb
            if len(cols) <= IDX_IMDB_ID:
                continue

            lang_name = get_col(cols, IDX_LANG_NAME).lower()
            iso_code = get_col(cols, IDX_ISO639).lower()

            # Tolak Malayalam secara mutlak
            if "malayalam" in lang_name:
                continue

            # Tapis hanya BM dan ID
            matched_lang = None
            if iso_code in ["ms", "may", "msa"] or "malay" in lang_name:
                matched_lang = "may"
            elif iso_code in ["id", "ind"] or "indonesia" in lang_name:
                matched_lang = "ind"

            if not matched_lang:
                continue

            imdb_id = clean_imdb(get_col(cols, IDX_IMDB_ID))
            parent_imdb = clean_imdb(get_col(cols, IDX_PARENT_IMDB))
            target_imdb = parent_imdb if parent_imdb else imdb_id

            if not target_imdb:
                continue

            season_val = get_col(cols, IDX_SEASON)
            episode_val = get_col(cols, IDX_EPISODE)
            season = season_val if season_val and season_val != "0" else None
            episode = episode_val if episode_val and episode_val != "0" else None

            sub_format = get_col(cols, IDX_FORMAT) or "srt"
            sub_id = get_col(cols, IDX_SUB_ID)
            movie_name = get_col(cols, IDX_MOVIE_NAME)
            movie_year = get_col(cols, IDX_MOVIE_YEAR)
            release_name = get_col(cols, IDX_RELEASE_NAME) or movie_name

            if season and episode:
                storage_path = f"subs/opensubtitles/series/{target_imdb}/s{season}e{episode}/{matched_lang}_{sub_id}.{sub_format}"
            else:
                storage_path = f"subs/opensubtitles/movie/{target_imdb}/{matched_lang}_{sub_id}.{sub_format}"

            record = {
                "id": f"opensub_{sub_id}",
                "sub_id": sub_id,
                "imdb_id": target_imdb,
                "season": season,
                "episode": episode,
                "lang": matched_lang,
                "source": "opensubtitles",
                "acc": 1,
                "path": storage_path,
                "release": release_name,
                "format": sub_format,
                "title": movie_name,
                "year": movie_year
            }

            current_batch.append(record)
            total_matched += 1

            if len(current_batch) >= RECORDS_PER_CHUNK:
                flush_chunk(current_batch, part_idx)
                part_idx += 1
                current_batch = []

    if current_batch:
        flush_chunk(current_batch, part_idx)

    console.print(f"\n[bold green]✨ Selesai![/bold green] Jumlah {total_matched:,} rekod BM & ID dibahagikan kepada fail pecahan di folder [cyan]{OUTPUT_DIR}[/cyan].")

if __name__ == "__main__":
    process()