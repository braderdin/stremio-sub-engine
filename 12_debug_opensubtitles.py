import os
import time
from pathlib import Path
from camoufox.sync_api import Camoufox
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.traceback import install

# Format paparan traceback ralat supaya ringkas dan kemas
install(show_locals=False)
console = Console()

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

TARGET_SUB_ID = "3107442"
TARGET_URL = f"https://dl.opensubtitles.org/en/download/sub/{TARGET_SUB_ID}"
HTML_OUTPUT = TEMP_DIR / f"opensub_{TARGET_SUB_ID}_dom.html"
SCREENSHOT_OUTPUT = TEMP_DIR / f"opensub_{TARGET_SUB_ID}_view.png"

def run_camoufox_inspection():
    console.print(Panel.fit(
        f"🦊 [bold cyan]Camoufox Anti-Detect Inspector (Anubis Clean Fix)[/bold cyan] ⚡\n"
        f"🎯 Sasaran: [yellow]{TARGET_URL}[/yellow]",
        border_style="cyan"
    ))

    downloaded_file = []

    with Camoufox(
        headless=True,
        geoip=True,
        humanize=True,
        enable_cache=True
    ) as browser:
        context = browser.new_context(
            accept_downloads=True,
            ignore_https_errors=True
        )

        # Gunakan HTTP Redirect (307) untuk alih http ke https dengan selamat
        def enforce_https(route, request):
            url = request.url
            if url.startswith("http://"):
                https_url = "https://" + url[7:]
                route.fulfill(status=307, headers={"Location": https_url})
            else:
                route.continue_()

        context.route("**/*", enforce_https)
        page = context.new_page()

        def handle_download(download):
            console.print(f"\n[bold green]🎉 Acara Muat Turun Dikesan: {download.suggested_filename}[/bold green]")
            downloaded_file.append(download)

        page.on("download", handle_download)
        t0 = time.time()

        # Gunakan Rich Status Spinner untuk paparan terminal yang bersih
        with console.status("[cyan]Menavigasi & memproses cabaran Anubis PoW...", spinner="dots"):
            try:
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                console.print(f"[dim yellow]⚠️ Nota Navigasi: {e}[/dim yellow]")

            max_wait = 30
            start_wait = time.time()
            while time.time() - start_wait < max_wait:
                if downloaded_file:
                    break
                try:
                    title = page.title()
                    url = page.url
                    if "Oh noes!" not in title and "anubis" not in url.lower():
                        time.sleep(2)
                        if downloaded_file:
                            break
                except Exception:
                    pass
                time.sleep(1)

        latency = (time.time() - t0) * 1000

        # Jika muat turun berjaya
        if downloaded_file:
            download = downloaded_file[0]
            save_path = TEMP_DIR / download.suggested_filename
            download.save_as(save_path)

            table = Table(title="Laporan Muat Turun OpenSubtitles", border_style="green")
            table.add_column("Parameter", style="bold white", width=20)
            table.add_column("Nilai Dikesan", style="yellow")

            table.add_row("Status", "[bold green]BERJAYA[/bold green]")
            table.add_row("Fail", download.suggested_filename)
            table.add_row("Lokasi Disimpan", str(save_path))
            table.add_row("Masa Diproses", f"{latency:.0f} ms")
            table.add_row("Saiz Fail", f"{os.path.getsize(save_path):,} bait")

            console.print(table)
        else:
            # Simpan DOM HTML
            try:
                dom_html = page.content()
                with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
                    f.write(dom_html)
            except Exception as e:
                console.print(f"[red]Gagal menyimpan DOM HTML: {e}[/red]")

            # Tangkap screenshot dengan timeout terhad (5 saat) supaya tidak terhenti
            try:
                page.screenshot(path=str(SCREENSHOT_OUTPUT), full_page=True, timeout=5000)
            except Exception as e:
                console.print(f"[dim yellow]⚠️ Tangkap layar dilepaskan (timeout/font issue): {e}[/dim yellow]")

            console.print(Panel(
                f"[bold red]❌ Gagal memuat turun fail dalam tempoh {max_wait} saat.[/bold red]\n\n"
                f"📄 DOM HTML: [yellow]{HTML_OUTPUT}[/yellow]\n"
                f"🖼️ Tangkap Layar: [yellow]{SCREENSHOT_OUTPUT}[/yellow]",
                title="[bold red]Laporan Diagnostik[/bold red]",
                border_style="red"
            ))

if __name__ == "__main__":
    try:
        run_camoufox_inspection()
    except Exception:
        console.print_exception(show_locals=False)