import os
import gzip
import json
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()

BASE_DIR = "/home/braderdin/stremio-sub-engine"
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

GZ_FILE = os.path.join(DATA_DIR, "subtitles_all.txt.gz")
SAMPLE_OUTPUT = os.path.join(OUTPUT_DIR, "opensubtitles_dump_sample.json")

# Indeks Kolum Tetap Mengikut Header Rasmi OpenSubtitles
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
IDX_KIND = 14
IDX_URL = 15

def format_imdb(raw_id):
    if not raw_id or raw_id == "0":
        return "N/A"
    clean_id = str(raw_id).strip()
    return f"tt{clean_id.zfill(7)}" if clean_id.isdigit() else clean_id

def parse_language(lang_name, iso_code):
    l_name = lang_name.lower().strip()
    l_iso = iso_code.lower().strip()

    # Sekatan ketat: Abaikan Malayalam
    if "malayalam" in l_name:
        return None

    # Bahasa Melayu (ISO 639-2: may)
    if l_iso in ["ms", "may", "msa"] or l_name in ["malay", "bahasa melayu", "melayu"]:
        return "may"

    # Bahasa Indonesia (ISO 639-2: ind)
    if l_iso in ["id", "ind"] or l_name in ["indonesian", "bahasa indonesia", "indonesia"]:
        return "ind"

    # Bahasa Inggeris (ISO 639-2: eng)
    if l_iso in ["en", "eng"] or l_name == "english":
        return "eng"

    return None

def run_inspector():
    console.print(Panel.fit("📦 [bold cyan]OpenSubtitles Accurate Dump Parser[/bold cyan] 🚀", border_style="cyan"))

    if not os.path.exists(GZ_FILE):
        console.print(f"[bold red]❌ Fail tidak wujud:[/bold red] {GZ_FILE}")
        return

    stats = {"may": 0, "ind": 0, "eng": 0, "other": 0, "total": 0}
    samples_may_ind = []

    start_time = time.time()

    with gzip.open(GZ_FILE, mode="rt", encoding="utf-8", errors="ignore") as f:
        # Langkau baris header
        header = f.readline().strip().split("\t")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[yellow]Memproses 10 Juta Rekod...[/yellow]", total=None)

            for line in f:
                stats["total"] += 1
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) <= IDX_URL:
                    continue

                lang_name = parts[IDX_LANG_NAME]
                iso_code = parts[IDX_ISO639]
                matched_lang = parse_language(lang_name, iso_code)

                if matched_lang == "may":
                    stats["may"] += 1
                elif matched_lang == "ind":
                    stats["ind"] += 1
                elif matched_lang == "eng":
                    stats["eng"] += 1
                else:
                    stats["other"] += 1
                    continue

                # Kumpul sampel untuk rujukan Stremio (utuk BM dan ID)
                if matched_lang in ["may", "ind"] and len(samples_may_ind) < 100:
                    samples_may_ind.append({
                        "sub_id": parts[IDX_SUB_ID],
                        "lang_code": matched_lang,
                        "raw_lang": lang_name,
                        "iso639": iso_code,
                        "movie_name": parts[IDX_MOVIE_NAME],
                        "year": parts[IDX_MOVIE_YEAR],
                        "imdb_id": format_imdb(parts[IDX_IMDB_ID]),
                        "parent_imdb": format_imdb(parts[IDX_PARENT_IMDB]),
                        "season": parts[IDX_SEASON],
                        "episode": parts[IDX_EPISODE],
                        "kind": parts[IDX_KIND],
                        "release_name": parts[IDX_RELEASE_NAME],
                        "format": parts[IDX_FORMAT],
                        "direct_url": parts[IDX_URL]
                    })

                if stats["total"] % 500000 == 0:
                    progress.update(
                        task,
                        description=f"[cyan]Diproses: {stats['total']:,} | BM: [green]{stats['may']:,}[/green] | ID: [green]{stats['ind']:,}[/green] | ENG: {stats['eng']:,}[/cyan]"
                    )

    duration = time.time() - start_time

    # Paparan Hasil
    summary = Table(title=f"Analisis Selesai ({duration:.1f}s)", border_style="green")
    summary.add_column("Bahasa", style="cyan")
    summary.add_column("Kod Stremio", style="yellow")
    summary.add_column("Jumlah Rekod", style="white")

    summary.add_row("Bahasa Melayu", "may", f"[bold green]{stats['may']:,}[/bold green]")
    summary.add_row("Bahasa Indonesia", "ind", f"[bold green]{stats['ind']:,}[/bold green]")
    summary.add_row("Bahasa Inggeris", "eng", f"{stats['eng']:,}")
    summary.add_row("Lain-lain", "-", f"{stats['other']:,}")
    summary.add_row("Jumlah Keseluruhan", "-", f"[bold cyan]{stats['total']:,}[/bold cyan]")
    console.print(summary)

    # Simpan sampel ke fail output
    with open(SAMPLE_OUTPUT, "w", encoding="utf-8") as out:
        json.dump(samples_may_ind, out, indent=2, ensure_ascii=False)

    console.print(f"\n📁 [bold green]100 Sampel BM & ID berjaya disimpan ke:[/bold green] {SAMPLE_OUTPUT}")

if __name__ == "__main__":
    run_inspector()