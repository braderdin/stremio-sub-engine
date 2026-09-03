import os
from pathlib import Path
from curl_cffi import requests
from rich.console import Console
from rich.panel import Panel

console = Console()

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

SUB_ID = "3107442"
# Link muat turun terus OpenSubtitles
TARGET_URL = f"https://dl.opensubtitles.org/en/download/sub/{SUB_ID}"
OUTPUT_FILE = TEMP_DIR / f"subtitle_{SUB_ID}.srt"

def download_sub_fast():
    console.print(Panel.fit(
        f"⚡ [bold green]OpenSubtitles Fast Downloader (curl_cffi)[/bold green]\n"
        f"🎯 ID Subtitle: [yellow]{SUB_ID}[/yellow]",
        border_style="green"
    ))

    # Header rasmi meniru browser Chrome sebenar
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.opensubtitles.org/",
    }

    try:
        console.print("[cyan]🚀 Menghantar permintaan berselindung TLS Chrome...[/cyan]")
        
        # impersonate="chrome120" akan tiru JA3/JA4 TLS fingerprint Chrome
        response = requests.get(
            TARGET_URL,
            headers=headers,
            impersonate="chrome120",
            allow_redirects=True,
            timeout=15
        )

        if response.status_code == 200:
            # Semak samada respon adalah kandungan subtitle SRT
            content = response.text
            if "1\n00:" in content or "-->" in content or "srt" in response.headers.get("Content-Disposition", ""):
                with open(OUTPUT_FILE, "wb") as f:
                    f.write(response.content)
                
                console.print(f"[bold green]✔ BERJAYA! Subtitle disimpan di:[/bold green] {OUTPUT_FILE}")
                console.print(f"[dim]Saiz fail: {len(response.content)} bait[/dim]")
            else:
                console.print("[bold red]❌ Terkena sekaan Anubis / Cloudflare WAF (Bukan fail SRT).[/bold red]")
                print(content[:300])
        else:
            console.print(f"[bold red]❌ HTTP Ralat:[/bold red] {response.status_code}")

    except Exception as e:
        console.print(f"[bold red]❌ Ralat Rangkaian:[/bold red] {e}")

if __name__ == "__main__":
    download_sub_fast()