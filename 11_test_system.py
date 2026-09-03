import time
import requests
import importlib
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Muat konfigurasi teras daripada 01_config
_cfg = importlib.import_module("01_config")
B2_ACCOUNTS = _cfg.B2_ACCOUNTS
REDIS_URL = _cfg.REDIS_URL
REDIS_TOKEN = _cfg.REDIS_TOKEN
SEARCH_URL = _cfg.SEARCH_URL
SEARCH_TOKEN = _cfg.SEARCH_TOKEN
CF_WORKER_URL = _cfg.CF_WORKER_URL
ADDON_SECRET_TOKEN = _cfg.ADDON_SECRET_TOKEN

def check_b2_account(acc):
    """Menguji pengesahan API rasmi Backblaze B2 bagi akaun tertentu."""
    url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
    t0 = time.time()
    try:
        r = requests.get(url, auth=(acc["key_id"], acc["app_key"]), timeout=10)
        latency = (time.time() - t0) * 1000
        if r.status_code == 200:
            return True, f"{latency:.0f}ms", acc["bucket_name"]
        return False, f"HTTP {r.status_code}", acc["bucket_name"]
    except Exception as e:
        return False, str(e)[:25], acc["bucket_name"]

def check_redis():
    """Menguji operasi ping REST API Upstash Redis."""
    if not REDIS_URL or not REDIS_TOKEN:
        return False, "Tiada Kunci", "-"
    t0 = time.time()
    try:
        r = requests.get(
            f"{REDIS_URL}/ping",
            headers={"Authorization": f"Bearer {REDIS_TOKEN}"},
            timeout=8
        )
        latency = (time.time() - t0) * 1000
        if r.status_code == 200 and r.json().get("result") == "PONG":
            return True, f"{latency:.0f}ms", "PONG"
        return False, f"HTTP {r.status_code}", "-"
    except Exception as e:
        return False, str(e)[:25], "-"

def check_search_db():
    """Menguji sambungan Upstash Search DB info endpoint."""
    if not SEARCH_URL or not SEARCH_TOKEN:
        return False, "Tiada Kunci", "-"
    t0 = time.time()
    try:
        r = requests.get(
            f"{SEARCH_URL}/",
            headers={"Authorization": f"Bearer {SEARCH_TOKEN}"},
            timeout=8
        )
        latency = (time.time() - t0) * 1000
        if r.status_code == 200:
            return True, f"{latency:.0f}ms", "Aktif (v1)"
        return False, f"HTTP {r.status_code}", "-"
    except Exception as e:
        return False, str(e)[:25], "-"

def check_cloudflare_worker():
    """Menguji endpoint manifest Cloudflare Worker yang sedang live."""
    if not CF_WORKER_URL or "belum" in CF_WORKER_URL:
        return False, "URL Belum Diset", "-"
    manifest_url = f"{CF_WORKER_URL}/{ADDON_SECRET_TOKEN}/manifest.json"
    t0 = time.time()
    try:
        r = requests.get(manifest_url, timeout=10)
        latency = (time.time() - t0) * 1000
        if r.status_code == 200 and "resources" in r.text:
            data = r.json()
            return True, f"{latency:.0f}ms", f"v{data.get('version', '1.0.0')}"
        return False, f"HTTP {r.status_code}", "-"
    except Exception as e:
        return False, str(e)[:25], "-"

def run_diagnostics():
    console.print(Panel.fit("🔍 [bold cyan]Diagnostik Kesihatan Sistem Penuh (Health Check)[/bold cyan] ⚡", border_style="cyan"))

    results_table = Table(title="Keputusan Ujian Sambungan & Latensi", border_style="blue")
    results_table.add_column("Komponen / Perkhidmatan", style="white", width=34)
    results_table.add_column("Status", style="bold", width=12)
    results_table.add_column("Latensi", style="yellow", width=12)
    results_table.add_column("Maklumat Tambahan", style="dim", width=32)

    # 1. Uji Semua Akaun Backblaze B2
    for acc in B2_ACCOUNTS:
        ok, lat, info = check_b2_account(acc)
        status_str = "[bold green]ONLINE[/bold green]" if ok else "[bold red]OFFLINE[/bold red]"
        results_table.add_row(f"Backblaze B2 (Akaun {acc['index']})", status_str, lat, info)

    # 2. Uji Upstash Redis
    r_ok, r_lat, r_info = check_redis()
    results_table.add_row("Upstash Redis (REST)", "[bold green]ONLINE[/bold green]" if r_ok else "[bold red]OFFLINE[/bold red]", r_lat, r_info)

    # 3. Uji Upstash Search DB
    s_ok, s_lat, s_info = check_search_db()
    results_table.add_row("Upstash Search DB", "[bold green]ONLINE[/bold green]" if s_ok else "[bold red]OFFLINE[/bold red]", s_lat, s_info)

    # 4. Uji Cloudflare Worker Live
    cf_ok, cf_lat, cf_info = check_cloudflare_worker()
    results_table.add_row("Cloudflare Worker (Stremio Gateway)", "[bold green]ONLINE[/bold green]" if cf_ok else "[bold red]OFFLINE[/bold red]", cf_lat, cf_info)

    console.print(results_table)

    total_pass = sum([1 for acc in B2_ACCOUNTS if check_b2_account(acc)[0]]) + int(r_ok) + int(s_ok) + int(cf_ok)
    total_checks = len(B2_ACCOUNTS) + 3

    if total_pass == total_checks:
        console.print(f"\n[bold green]✔ SEMUA {total_checks} KOMPONEN SISTEM BERFUNGSI DENGAN CEMERLANG![/bold green]\n")
    else:
        console.print(f"\n[bold yellow]⚠ {total_pass}/{total_checks} komponen lulus ujian. Sila semak baris bertanda merah di atas.[/bold yellow]\n")

if __name__ == "__main__":
    run_diagnostics()