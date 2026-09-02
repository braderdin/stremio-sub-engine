import os
import re
import json
import time
from urllib.parse import urljoin
from curl_cffi import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

# Definisi Direktori
BASE_DIR = "/home/braderdin/stremio-sub-engine"
EXP_DIR = os.path.join(BASE_DIR, "experiments")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

for folder in [OUTPUT_DIR, TEMP_DIR]:
    os.makedirs(folder, exist_ok=True)

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "subscene_extracted.json")
BASE_URL = "https://sub-scene.com"

# Pemetaan Bahasa Sasaran (ISO 639-2)
TARGET_LANGS = {
    "malay": "may",
    "bahasa melayu": "may",
    "melayu": "may",
    "indonesian": "ind",
    "bahasa indonesia": "ind",
    "english": "eng"
}

def create_session():
    return requests.Session(impersonate="chrome120")

def load_existing_data():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[bold red]❌ Gagal membaca JSON sedia ada:[/bold red] {e}")
    return []

def search_movies(session, query):
    search_url = f"{BASE_URL}/search?query={query.replace(' ', '+')}"
    console.print(f"[cyan]🔎 Mencari di Subscene:[/cyan] [bold white]{search_url}[/bold white]")
    
    try:
        resp = session.get(search_url, timeout=12)
        if resp.status_code != 200:
            console.print(f"[bold red]❌ Ralat HTTP {resp.status_code} semasa carian.[/bold red]")
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        
        # Ekstrak pautan hasil carian
        for link in soup.select("div.search-result ul li a, table.search-result tr a, a[href*='/subscene/']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if "/subscene/" in href and title:
                match_id = re.search(r'/subscene/(\d+)', href)
                subscene_id = match_id.group(1) if match_id else href.split("/")[-1]
                results.append({
                    "id": subscene_id,
                    "title": title,
                    "url": urljoin(BASE_URL, href)
                })
        
        # Buang duplikasi pautan carian
        unique_results = {r["id"]: r for r in results}.values()
        return list(unique_results)
    except Exception as e:
        console.print(f"[bold red]💥 Ralat sambungan carian:[/bold red] {e}")
        return []

def extract_movie_subtitles(session, movie_url, movie_id):
    console.print(f"[yellow]📥 Menyelidiki halaman filem:[/yellow] {movie_url}")
    try:
        resp = session.get(movie_url, timeout=15)
        if resp.status_code != 200:
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        subtitles = []

        rows = soup.select("table tr, div.subtitle-entry")
        for row in rows:
            text = row.get_text(strip=True).lower()
            
            # Kenal pasti bahasa sasaran
            matched_lang = None
            lang_code = None
            for name, code in TARGET_LANGS.items():
                if name in text:
                    matched_lang = name.capitalize()
                    lang_code = code
                    break
            
            if not matched_lang:
                continue

            link_tag = row.find("a", href=True)
            if not link_tag:
                continue
            
            sub_page = urljoin(BASE_URL, link_tag["href"])
            release_title = link_tag.get_text(strip=True) or "Unknown Release"
            
            sub_id_match = re.search(r'/subtitles/([^/]+)/([^/]+)/(\d+)', sub_page) or re.search(r'/(\d+)$', sub_page)
            unique_sub_id = sub_id_match.group(0) if sub_id_match else sub_page
            
            subtitles.append({
                "sub_id": unique_sub_id,
                "language": matched_lang,
                "lang_code": lang_code,
                "release_name": release_title,
                "detail_url": sub_page
            })
            
        return subtitles
    except Exception as e:
        console.print(f"[bold red]💥 Ralat membaca halaman filem:[/bold red] {e}")
        return []

def test_download_subtitle(session, detail_url, filename):
    try:
        resp = session.get(detail_url, timeout=12)
        if resp.status_code != 200:
            return False
        
        soup = BeautifulSoup(resp.text, "html.parser")
        dl_btn = soup.select_one("a#downloadButton, a.download, a[href*='/download/']")
        if not dl_btn:
            return False
        
        dl_url = urljoin(BASE_URL, dl_btn["href"])
        sub_resp = session.get(dl_url, timeout=15)
        
        if sub_resp.status_code == 200 and len(sub_resp.content) > 0:
            dest_path = os.path.join(TEMP_DIR, filename)
            with open(dest_path, "wb") as f:
                f.write(sub_resp.content)
            return True
    except Exception:
        pass
    return False

def run_subscene_test():
    console.print(Panel.fit("🎬 [bold green]Subscene Scraper & Inspector[/bold green] 🚀", border_style="cyan"))
    session = create_session()
    existing_records = load_existing_data()
    existing_ids = {item.get("sub_id") for item in existing_records}

    # 1. Carian Filem
    query = "Resident Evil"
    movies = search_movies(session, query)
    
    if not movies:
        # Fallback terus ke URL contoh jika carian gagal
        movies = [{"id": "95203", "title": "Resident Evil: Extinction", "url": "https://sub-scene.com/subscene/95203"}]

    table = Table(title="Hasil Filem Ditemui", border_style="blue")
    table.add_column("ID", style="cyan")
    table.add_column("Tajuk", style="white")
    table.add_column("URL", style="dim")
    for m in movies[:3]:
        table.add_row(m["id"], m["title"], m["url"])
    console.print(table)

    new_subtitles = []
    
    # 2. Proses Setiap Filem (Uji 1 filem pertama)
    target_movie = movies[0]
    raw_subs = extract_movie_subtitles(session, target_movie["url"], target_movie["id"])
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[yellow]Menapis Subtitle...[/yellow]", total=len(raw_subs))
        
        for sub in raw_subs:
            if sub["sub_id"] not in existing_ids:
                sub["movie_title"] = target_movie["title"]
                sub["source"] = "sub-scene.com"
                new_subtitles.append(sub)
                existing_ids.add(sub["sub_id"])
            progress.advance(task)
            time.sleep(0.05)

    # 3. Uji Muat Turun Sampel (< 50KB)
    if new_subtitles:
        sample = new_subtitles[0]
        sample_file = f"sample_subscene_{sample['lang_code']}.zip"
        console.print(f"\n[cyan]🧪 Menguji muat turun 1 fail sampel:[/cyan] {sample['release_name']}")
        if test_download_subtitle(session, sample["detail_url"], sample_file):
            console.print(f"[bold green]✔ Berjaya dimuat turun ke:[/bold green] [white]{TEMP_DIR}/{sample_file}[/white]")
        else:
            console.print("[bold yellow]⚠ Pautan muat turun memerlukan penyesuaian lanjut.[/bold yellow]")

    # 4. Simpan ke fail JSON
    final_output = new_subtitles + existing_records
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)

    console.print(f"\n[bold green]✨ Ujian Subscene Selesai![/bold green] +{len(new_subtitles)} subtitle baharu direkodkan.")
    console.print(f"📁 [cyan]Data JSON disimpan di:[/cyan] {OUTPUT_FILE}\n")

if __name__ == "__main__":
    run_subscene_test()