import os
import json
from curl_cffi import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Direktori Projek
BASE_DIR = "/home/braderdin/stremio-sub-engine"
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "opensubtitles_extracted.json")

for folder in [OUTPUT_DIR, TEMP_DIR]:
    os.makedirs(folder, exist_ok=True)

# Endpoint Rasmi REST API v3
API_BASE_URL = "https://api.opensubtitles.com/api/v1/subtitles"

# Dapatkan API Key percuma dari opensubtitles.com/en/consumers
# Anda boleh letak kunci anda di sini atau masukkan ke dalam .env.local
API_KEY = os.getenv("OPENSUBTITLES_API_KEY", "")

# Pemetaan Bahasa ISO 639-2 untuk Stremio
LANG_MAP = {
    "ms": "may",
    "id": "ind",
    "en": "eng"
}

def search_subtitles_api(imdb_id="0111161", languages="ms,id,en"):
    """
    imdb_id: Nombor IMDb tanpa 'tt' (Contoh tt0111161 -> 0111161)
    languages: ms (Malay), id (Indonesian), en (English)
    """
    headers = {
        "User-Agent": "stremio-sub-engine v1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    # Masukkan Api-Key jika ada
    if API_KEY:
        headers["Api-Key"] = API_KEY

    params = {
        "imdb_id": imdb_id.replace("tt", ""),
        "languages": languages,
        "order_by": "download_count",
        "order_direction": "desc"
    }

    console.print(f"[cyan]🌐 Menghubungi API v3 untuk IMDb ID:[/cyan] [bold white]tt{params['imdb_id']}[/bold white]")

    try:
        session = requests.Session(impersonate="chrome124")
        resp = session.get(API_BASE_URL, headers=headers, params=params, timeout=15)
        
        if resp.status_code == 401:
            console.print("[bold red]❌ Ralat 401: API Key diperlukan untuk capaian endpoint ini.[/bold red]")
            console.print("[yellow]💡 Sila daftar akaun percuma di https://www.opensubtitles.com/en/consumers untuk mendapatkan API-Key.[/yellow]")
            return []
            
        if resp.status_code != 200:
            console.print(f"[bold red]❌ Gagal: HTTP {resp.status_code}[/bold red]")
            return []

        data = resp.json()
        subtitles = []

        for item in data.get("data", []):
            attr = item.get("attributes", {})
            files = attr.get("files", [])
            file_id = files[0].get("file_id") if files else None
            raw_lang = attr.get("language", "en")
            
            subtitles.append({
                "sub_id": str(item.get("id")),
                "file_id": file_id,
                "language": raw_lang,
                "lang_code": LANG_MAP.get(raw_lang, raw_lang),
                "release_name": attr.get("release", "Unknown Release"),
                "fps": attr.get("fps"),
                "download_url": f"https://api.opensubtitles.com/api/v1/download",
                "movie_title": attr.get("feature_details", {}).get("title"),
                "source": "api.opensubtitles.com"
            })

        return subtitles
    except Exception as e:
        console.print(f"[bold red]💥 Ralat sambungan API:[/bold red] {e}")
        return []

def run_test():
    console.print(Panel.fit("🎬 [bold green]OpenSubtitles REST API v3 Engine[/bold green] 🚀", border_style="green"))
    
    # Uji cuba filem Rambo (IMDb ID: tt0083944 / 0083944)
    target_imdb = "0083944" 
    results = search_subtitles_api(imdb_id=target_imdb)

    if not results:
        console.print("[yellow]Tiada hasil diperolehi (semak API Key anda).[/yellow]")
        return

    table = Table(title=f"Hasil API untuk tt{target_imdb}", border_style="cyan")
    table.add_column("Sub ID", style="cyan", width=10)
    table.add_column("Bahasa", style="yellow", width=8)
    table.add_column("Release Name", style="white")
    table.add_column("File ID", style="green")

    for item in results[:6]:
        table.add_row(
            item["sub_id"],
            item["lang_code"],
            item["release_name"][:35],
            str(item["file_id"])
        )
    console.print(table)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    console.print(f"\n[bold green]✔ Berjaya![/bold green] Rekod disimpan ke 📁 {OUTPUT_FILE}")

if __name__ == "__main__":
    run_test()