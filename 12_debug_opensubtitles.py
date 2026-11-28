import os
import json
import time
from pathlib import Path
from camoufox.sync_api import Camoufox
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.traceback import install

install(show_locals=False)
console = Console()

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

COOKIE_FILE = TEMP_DIR / "opensub_cookies.json"
TARGET_SUB_ID = "3107442"
TARGET_URL = f"https://dl.opensubtitles.org/en/download/sub/{TARGET_SUB_ID}"

# Tetapan Firefox untuk benarkan Cookie & matikan Sekatan Tracking
FIREFOX_CONFIG = {
    "network.cookie.cookieBehavior": 0,          # 0 = Benarkan semua cookie
    "privacy.trackingprotection.enabled": False,  # Matikan Tracking Protection
    "privacy.trackingprotection.pbmode.enabled": False,
    "dom.storage.enabled": True,                 # Benarkan LocalStorage & SessionStorage
}

def run_camoufox_headful_handshake():
    console.print(Panel.fit(
        f"🦊 [bold cyan]Camoufox Headful & Cookie Unlocked[/bold cyan] ⚡\n"
        f"🎯 Sasaran: [yellow]{TARGET_URL}[/yellow]",
        border_style="cyan"
    ))

    downloaded_file = []

    with Camoufox(
        headless=False,
        geoip=True,
        humanize=True,
        enable_cache=True,
        config=FIREFOX_CONFIG,  # Memasukkan konfig Cookie/Tracking
        i_know_what_i_am_doing=True
    ) as browser:
        context = browser.new_context(
            accept_downloads=True,
            ignore_https_errors=True
        )

        if COOKIE_FILE.exists():
            try:
                with open(COOKIE_FILE, "r") as f:
                    cookies = json.load(f)
                    context.add_cookies(cookies)
                console.print("[dim green]✔ Cookie lama di-load ke context.[/dim green]")
            except Exception as e:
                console.print(f"[dim red]⚠️ Gagal muat naik cookie: {e}[/dim red]")

        page = context.new_page()

        def handle_download(download):
            console.print(f"\n[bold green]🎉 Acara Muat Turun Dikesan: {download.suggested_filename}[/bold green]")
            downloaded_file.append(download)

        page.on("download", handle_download)
        t0 = time.time()

        with console.status("[cyan]Menavigasi & memproses PoW Anubis...", spinner="dots"):
            try:
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                console.print(f"[dim yellow]⚠️ Navigasi Note: {e}[/dim yellow]")

            max_wait = 25
            start_time = time.time()
            while time.time() - start_time < max_wait:
                if downloaded_file:
                    break
                try:
                    title = page.title()
                    url = page.url
                    if "bot" not in title.lower() and "anubis" not in url.lower():
                        time.sleep(2)
                        if downloaded_file:
                            break
                except Exception:
                    pass
                time.sleep(1)

        # Simpan Cookie Anubis terbaharu
        try:
            saved_cookies = context.cookies()
            with open(COOKIE_FILE, "w") as f:
                json.dump(saved_cookies, f, indent=2)
            console.print("[dim green]💾 Sesi Cookie Anubis berjaya disimpan.[/dim green]")
        except Exception as e:
            console.print(f"[dim red]⚠️ Gagal menyimpan cookie: {e}[/dim red]")

        latency = (time.time() - t0) * 1000

        if downloaded_file:
            download = downloaded_file[0]
            save_path = TEMP_DIR / download.suggested_filename
            download.save_as(save_path)

            table = Table(title="Laporan Muat Turun", border_style="green")
            table.add_column("Parameter", style="bold white", width=20)
            table.add_column("Nilai Dikesan", style="yellow")

            table.add_row("Status", "[bold green]BERJAYA[/bold green]")
            table.add_row("Fail Disimpan", download.suggested_filename)
            table.add_row("Lokasi", str(save_path))
            table.add_row("Saiz", f"{os.path.getsize(save_path):,} bait")
            table.add_row("Masa Diproses", f"{latency:.0f} ms")

            console.print(table)
        else:
            console.print(Panel(
                f"[bold red]❌ Gagal memuat turun fail selepas {max_wait} saat.[/bold red]",
                title="[bold red]Ralat[/bold red]",
                border_style="red"
            ))

if __name__ == "__main__":
    try:
        run_camoufox_headful_handshake()
    except Exception:
        console.print_exception(show_locals=False)