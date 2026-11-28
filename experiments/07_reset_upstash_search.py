#!/usr/bin/env python3
import sys
import os
import requests
import importlib
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

# Masukkan direktori utama projek ke sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def load_env(env_path):
    """Membaca fail .env.local secara manual."""
    env_vars = {}
    if not env_path.exists():
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip()
    return env_vars

def reset_search_via_sdk(index_name="subtitles"):
    """Mengosongkan Upstash Search menggunakan SDK melalui 01_config."""
    try:
        _cfg = importlib.import_module("01_config")
        get_search_index = getattr(_cfg, "get_search_index", None)
        
        if get_search_index:
            index = get_search_index(index_name=index_name)
            if hasattr(index, "reset"):
                index.reset()
                console.print(f"[bold green]✅ Indeks Search '{index_name}' berjaya dikosongkan (SDK index.reset())![/bold green]")
                return True
    except Exception as e:
        console.print(f"[yellow]⚠ SDK reset tidak berjaya ({e}), mencuba REST API secara terus...[/yellow]")
    return False

def reset_search_via_rest(url, token, index_name="subtitles"):
    """Mengosongkan Upstash Search melalui REST API dengan nama indeks."""
    if not url or not token:
        console.print("[bold red]❌ UPSTASH_SEARCH_REST_URL / TOKEN tiada dalam .env.local![/bold red]")
        return False

    base_url = url.rstrip('/')
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Laluan API Upstash Search berserta nama indeks
    endpoints = [
        f"{base_url}/reset/{index_name}",
        f"{base_url}/index/{index_name}/reset",
        f"{base_url}/reset"
    ]

    for endpoint in endpoints:
        try:
            # Mencuba POST dengan sasaran nama indeks
            res = requests.post(endpoint, headers=headers, json={"index": index_name}, timeout=10)
            if res.status_code == 200:
                console.print(f"[bold green]✅ Upstash Search DB ('{index_name}') berjaya dikosongkan via REST API![/bold green]")
                return True
        except Exception:
            continue

    console.print("[bold red]❌ Gagal membersihkan Upstash Search melalui REST API.[/bold red]")
    return False

def main():
    console.print(Panel.fit("🧹 [bold cyan]Pembersihan Upstash Search DB (Skrip 07)[/bold cyan]", border_style="cyan"))

    INDEX_NAME = "subtitles"

    # 1. Cuba guna SDK melalui module 01_config
    if reset_search_via_sdk(index_name=INDEX_NAME):
        console.print("[bold green]✨ Proses siap! Search DB kini bersih untuk projek baru.[/bold green]")
        return

    # 2. Jika SDK gagal, guna nilai dalam .env.local untuk REST API
    env_path = PROJECT_ROOT / ".env.local"
    env_vars = load_env(env_path)

    search_url = env_vars.get("UPSTASH_SEARCH_REST_URL")
    search_token = env_vars.get("UPSTASH_SEARCH_REST_TOKEN")

    if reset_search_via_rest(search_url, search_token, index_name=INDEX_NAME):
        console.print("[bold green]✨ Proses siap! Search DB kini bersih untuk projek baru.[/bold green]")

if __name__ == "__main__":
    main()