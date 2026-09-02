import os
import json
from urllib.parse import urljoin
from curl_cffi import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

BASE_DIR = "/home/braderdin/stremio-sub-engine"
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "opensubtitles_dom_structure.json")

# URL sasaran: Carian filem dengan tapisan bahasa
TARGET_URL = "https://www.opensubtitles.org/en/search/sublanguageid-may,ind,eng/moviename-rambo"

def inspect_page_structure():
    console.print(Panel.fit("🔍 [bold cyan]OpenSubtitles DOM & Layout Inspector[/bold cyan]", border_style="cyan"))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ms;q=0.8",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }

    session = requests.Session(impersonate="chrome124", headers=headers)

    console.print(f"[yellow]🌐 Menghubungi:[/yellow] {TARGET_URL}")
    try:
        resp = session.get(TARGET_URL, timeout=15)
    except Exception as e:
        console.print(f"[bold red]❌ Gagal menghubungi pelayan:[/bold red] {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    is_challenge = "Making sure you're not a bot" in resp.text or "challenge-platform" in resp.text

    # 1. Pengekstrakan Borang & Input Tersembunyi
    forms_data = []
    for form in soup.find_all("form"):
        form_info = {
            "action": form.get("action", ""),
            "method": form.get("method", "get").upper(),
            "inputs": []
        }
        for inp in form.find_all(["input", "select"]):
            form_info["inputs"].append({
                "name": inp.get("name"),
                "type": inp.get("type", "text"),
                "value": inp.get("value", "")
            })
        forms_data.append(form_info)

    # 2. Pengekstrakan Struktur Jadual
    tables_data = []
    for idx, tbl in enumerate(soup.find_all("table")):
        tbl_id = tbl.get("id", f"table_{idx}")
        tbl_class = tbl.get("class", [])
        
        # Ambil header lajur
        headers_found = [th.get_text(strip=True) for th in tbl.find_all("th")]
        
        # Ambil 3 sampel baris data
        rows_sample = []
        for tr in tbl.find_all("tr")[:4]:
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows_sample.append(cells)

        tables_data.append({
            "table_id": tbl_id,
            "classes": tbl_class,
            "headers": headers_found,
            "rows_sample": rows_sample
        })

    # 3. Analisis Corak Pautan (Links Pattern)
    links_pattern = {
        "subtitles_links": [],
        "download_links": [],
        "language_links": []
    }
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/subtitles/" in href:
            links_pattern["subtitles_links"].append(href)
        elif "/download/" in href:
            links_pattern["download_links"].append(href)
        elif "/sublanguageid-" in href:
            links_pattern["language_links"].append(href)

    # Singkirkan duplikasi pautan
    for k in links_pattern:
        links_pattern[k] = list(set(links_pattern[k]))[:10]

    # 4. Bina Metadata Penuh
    structure_report = {
        "status_code": resp.status_code,
        "is_bot_challenge": is_challenge,
        "page_title": soup.title.get_text(strip=True) if soup.title else "N/A",
        "response_headers": dict(resp.headers),
        "cookies_received": session.cookies.get_dict(),
        "forms_detected": forms_data,
        "tables_detected": tables_data,
        "sample_links": links_pattern,
        "raw_html_snippet": resp.text[:1500]
    }

    # Simpan ke fail JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(structure_report, f, indent=2, ensure_ascii=False)

    # Paparan Ringkasan Terminal
    summary_table = Table(title="Laporan Struktur Web OpenSubtitles", border_style="green")
    summary_table.add_column("Komponen", style="cyan")
    summary_table.add_column("Status / Kiraan", style="white")

    summary_table.add_row("HTTP Status Code", str(resp.status_code))
    summary_table.add_row("Bot Challenge Terkesan", "[bold red]YA[/bold red]" if is_challenge else "[bold green]TIDAK[/bold green]")
    summary_table.add_row("Tajuk Halaman", structure_report["page_title"])
    summary_table.add_row("Jumlah Jadual", str(len(tables_data)))
    summary_table.add_row("Borang Dikesan", str(len(forms_data)))
    summary_table.add_row("Pautan Subtitle Terjumpa", str(len(links_pattern["subtitles_links"])))

    console.print(summary_table)
    console.print(f"\n📁 [bold green]Struktur penuh disimpan ke:[/bold green] {OUTPUT_FILE}")

if __name__ == "__main__":
    inspect_page_structure()