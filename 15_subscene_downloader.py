import re
import time
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from curl_cffi import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

# Direktori & Sasaran Data
TARGET_DIR = Path("/home/braderdin/stremio-sub-engine/data/sub-scene-file")
TARGET_DIR.mkdir(parents=True, exist_ok=True)

TARGET_SIZE_MB = 10
TARGET_SIZE_BYTES = TARGET_SIZE_MB * 1024 * 1024
BASE_URL = "https://sub-scene.com"

# Perkataan Kunci Carian Filem
SEEDS = [
    "Resident Evil", "Avatar", "Avengers", "Spider-Man", 
    "Batman", "Harry Potter", "Fast and Furious", "John Wick", 
    "Transformers", "Munafik", "Dukun", "Ejen Ali"
]

# Pautan terus fallback jika carian utama disekat
DIRECT_MOVIES = [
    {"title": "Resident Evil: Extinction", "url": "https://sub-scene.com/subscene/95203"},
    {"title": "Avatar", "url": "https://sub-scene.com/subscene/avatar"},
    {"title": "Avengers: Endgame", "url": "https://sub-scene.com/subscene/avengers-endgame"},
    {"title": "The Batman", "url": "https://sub-scene.com/subscene/the-batman"}
]

def get_dir_size(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.glob("*") if f.is_file())

def sanitize_name(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def filter_lang(text: str) -> bool:
    clean = text.lower().strip()
    if "malayalam" in clean:
        return False
    keywords = ["malay", "melayu", "indonesian", "indonesia", "may", "ind"]
    return any(re.search(rf'\b{kw}\b', clean) for kw in keywords)

def create_stealth_session():
    session = requests.Session(impersonate="chrome120")
    session.headers.update({
        "Accept-Language": "en-US,en;q=0.9,ms;q=0.8,id;q=0.7",
        "Referer": BASE_URL
    })
    try:
        session.get(BASE_URL, timeout=10)
    except Exception:
        pass
    return session

def search_movies(session, query):
    search_url = f"{BASE_URL}/search?query={query.replace(' ', '+')}"
    results = []
    try:
        resp = session.get(search_url, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.select("div.search-result ul li a, table tr a, a[href*='/subscene/'], a[href*='/subtitles/']"):
                href = link.get("href")
                title = link.get_text(strip=True)
                if href and title and not href.startswith("#"):
                    results.append({"title": title, "url": urljoin(BASE_URL, href)})
    except Exception:
        pass
    return results

def get_subtitles_from_movie(session, movie_url):
    subs = []
    try:
        resp = session.get(movie_url, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for row in soup.select("table tr, div.subtitle-entry"):
                if not filter_lang(row.get_text(" ", strip=True)):
                    continue
                link_tag = row.find("a", href=True)
                if link_tag:
                    subs.append({
                        "release": link_tag.get_text(strip=True) or "Subtitle_File",
                        "url": urljoin(BASE_URL, link_tag["href"])
                    })
    except Exception:
        pass
    return subs

def download_sub_file(session, detail_url):
    try:
        resp = session.get(detail_url, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            dl_btn = soup.select_one("a#downloadButton, a.download, a[href*='/download/']")
            if dl_btn and dl_btn.get("href"):
                dl_url = urljoin(BASE_URL, str(dl_btn["href"]))
                dl_resp = session.get(dl_url, timeout=15)
                if dl_resp.status_code == 200 and len(dl_resp.content) > 100:
                    return dl_resp.content
    except Exception:
        pass
    return None

def run_pipeline():
    console.print(Panel.fit(
        f"🎬 [bold cyan]Subscene Fast Downloader (BM/ID)[/bold cyan] ⚡\n"
        f"📂 Sasaran: [yellow]{TARGET_DIR}[/yellow] | Had Saiz: [green]{TARGET_SIZE_MB} MB[/green]",
        border_style="cyan"
    ))

    session = create_stealth_session()
    downloaded_files = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        main_task = progress.add_task("[cyan]Memuat turun subtitle...[/cyan]", total=TARGET_SIZE_BYTES)
        
        # 1. Uji Carian Berasaskan Seed
        all_movies = []
        for seed in SEEDS:
            if get_dir_size(TARGET_DIR) >= TARGET_SIZE_BYTES:
                break
            progress.update(main_task, description=f"[cyan]Mencari:[/cyan] {seed}")
            found = search_movies(session, seed)
            all_movies.extend(found[:2])
            time.sleep(0.2)

        # 2. Tambah Direct Fallback Jika Carian Kosong
        if not all_movies:
            all_movies.extend(DIRECT_MOVIES)

        # 3. Proses Muat Turun Subtitle
        for movie in all_movies:
            curr_bytes = get_dir_size(TARGET_DIR)
            if curr_bytes >= TARGET_SIZE_BYTES:
                break

            progress.update(main_task, description=f"[yellow]Memproses:[/yellow] {movie['title'][:25]}")
            subs = get_subtitles_from_movie(session, movie["url"])

            for sub in subs:
                curr_bytes = get_dir_size(TARGET_DIR)
                if curr_bytes >= TARGET_SIZE_BYTES:
                    break

                content = download_sub_file(session, sub["url"])
                if content:
                    file_name = sanitize_name(sub["release"]) + ".zip"
                    save_path = TARGET_DIR / file_name
                    with open(save_path, "wb") as f:
                        f.write(content)

                    downloaded_files += 1
                    updated_size = get_dir_size(TARGET_DIR)
                    progress.update(main_task, completed=min(updated_size, TARGET_SIZE_BYTES))
                    time.sleep(0.3)

        progress.update(main_task, completed=TARGET_SIZE_BYTES, description="[bold green]Selesai![/bold green]")

    # Laporan Ringkas
    total_mb = get_dir_size(TARGET_DIR) / (1024 * 1024)
    summary = Table(title="Rumusan Muat Turun Subscene", border_style="green")
    summary.add_column("Parameter", style="white")
    summary.add_column("Nilai", style="yellow")
    summary.add_row("Jumlah Fail Dimuat Turun", str(downloaded_files))
    summary.add_row("Jumlah Saiz Direktori", f"{total_mb:.2f} MB")
    summary.add_row("Lokasi Storage", str(TARGET_DIR))
    console.print(summary)

if __name__ == "__main__":
    run_pipeline()