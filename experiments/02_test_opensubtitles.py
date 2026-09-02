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

# Direktori Projek
BASE_DIR = "/home/braderdin/stremio-sub-engine"
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "opensubtitles_extracted.json")

for folder in [OUTPUT_DIR, TEMP_DIR]:
    os.makedirs(folder, exist_ok=True)

BASE_URL = "https://www.opensubtitles.org"

LANG_MAP = {
    "mal": "may",
    "may": "may",
    "msa": "may",
    "ind": "ind",
    "eng": "eng"
}

def create_stealth_session():
    """Membina sesi pelayar lengkap dengan pemanasan kuki."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ms;q=0.8,id;q=0.7",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }
    session = requests.Session(impersonate="chrome124", headers=headers)
    
    # Pemanasan sesi: Dapatkan PHPSESSID dari halaman utama dahulu
    try:
        console.print("[yellow]🔄 Melakukan pemanasan sesi (handshake) di OpenSubtitles...[/yellow]")
        init_resp = session.get(f"{BASE_URL}/en", timeout=12)
        if init_resp.status_code == 200:
            console.print("[bold green]✔ Sesi sedia ada diterima dengan kuki aktif.[/bold green]")
        else:
            console.print(f"[bold yellow]⚠ Respons laman utama: HTTP {init_resp.status_code}[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Gagal memulakan jabat tangan sesi:[/bold red] {e}")
        
    return session

def load_existing_data():
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def scrape_opensubtitles(session, search_path):
    url = urljoin(BASE_URL, search_path)
    console.print(f"[cyan]🌐 Mengakses Sasaran:[/cyan] [bold white]{url}[/bold white]")
    
    # Tetapkan Referer tepat
    session.headers["Referer"] = f"{BASE_URL}/en"
    
    try:
        resp = session.get(url, timeout=15)
        
        if resp.status_code != 200:
            console.print(f"[bold red]❌ HTTP {resp.status_code}[/bold red]")
            # Diagnostik jika disekat
            snippet = resp.text[:250].replace("\n", " ")
            console.print(f"[dim]Pratonton Respons: {snippet}[/dim]")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        
        # Semak jadual carian
        table = soup.find("table", id="search_results")
        rows = table.select("tr.change") if table else soup.select("tr.change")

        for row in rows:
            # Dapatkan ID subtitle
            row_id = row.get("id", "")
            sub_id = re.sub(r'\D', '', row_id) if row_id else None

            title_cell = row.find("a", href=re.compile(r'/subtitles/\d+'))
            if not title_cell:
                continue

            detail_url = urljoin(BASE_URL, title_cell["href"])
            if not sub_id:
                id_match = re.search(r'/subtitles/(\d+)', detail_url)
                sub_id = id_match.group(1) if id_match else None

            release_title = title_cell.get_text(strip=True)

            # Kenal pasti bahasa melalui ikon bendera atau pautan bahasa
            lang_code = "unknown"
            lang_cell = row.find("a", href=re.compile(r'/sublanguageid-'))
            if lang_cell:
                match = re.search(r'/sublanguageid-([a-z]{3})', lang_cell["href"])
                if match:
                    raw_code = match.group(1)
                    lang_code = LANG_MAP.get(raw_code, raw_code)

            # Abaikan jika bukan bahasa sasaran
            if lang_code not in ["may", "ind", "eng"]:
                continue

            dl_tag = row.find("a", href=re.compile(r'/download/'))
            dl_url = urljoin(BASE_URL, dl_tag["href"]) if dl_tag else None

            results.append({
                "sub_id": sub_id,
                "lang_code": lang_code,
                "release_name": release_title,
                "detail_url": detail_url,
                "direct_download_url": dl_url,
                "source": "opensubtitles.org"
            })

        return results
    except Exception as e:
        console.print(f"[bold red]💥 Ralat sambungan:[/bold red] {e}")
        return []

def run_opensubtitles_test():
    console.print(Panel.fit("🎬 [bold green]OpenSubtitles.org Scraper v2 (Session Enabled)[/bold green] ⚡", border_style="green"))
    session = create_stealth_session()
    existing_records = load_existing_data()
    seen_sub_ids = {r.get("sub_id") for r in existing_records if r.get("sub_id")}

    # Senarai variasi URL untuk diuji (menguji carian nama dan carian ID filem)
    test_paths = [
        "/en/search/sublanguageid-may,ind,eng/moviename-rambo",
        "/en/search/sublanguageid-may,ind,eng/idmovie-27792",
        "/en/search/sublanguageid-may/moviename-rambo"
    ]

    extracted_subs = []
    for path in test_paths:
        extracted_subs = scrape_opensubtitles(session, path)
        if extracted_subs:
            break
        time.sleep(1.5)

    new_entries = []
    for sub in extracted_subs:
        if sub["sub_id"] and sub["sub_id"] not in seen_sub_ids:
            new_entries.append(sub)
            seen_sub_ids.add(sub["sub_id"])

    # Jadual Paparan Hasil
    table = Table(title=f"Subtitle Ditemui ({len(new_entries)} Baharu)", border_style="magenta")
    table.add_column("Sub ID", style="cyan", width=12)
    table.add_column("Bahasa", style="yellow", width=8)
    table.add_column("Release Name", style="white")
    table.add_column("Detail Link", style="dim")

    for item in new_entries[:8]:
        table.add_row(
            str(item["sub_id"]),
            item["lang_code"],
            item["release_name"][:40],
            item["detail_url"]
        )
    console.print(table)

    all_records = new_entries + existing_records
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)

    console.print(f"\n[bold green]✔ Selesai![/bold green] Status: {len(new_entries)} data disimpan.")
    console.print(f"📁 [cyan]Fail JSON:[/cyan] {OUTPUT_FILE}\n")

if __name__ == "__main__":
    run_opensubtitles_test()