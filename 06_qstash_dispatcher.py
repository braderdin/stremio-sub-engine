import os
import json
import time
import requests
import importlib
from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel

console = Console()

# 1. Muat konfigurasi daripada 01_config secara dinamik
_cfg = importlib.import_module("01_config")
QSTASH_URL = (_cfg.QSTASH_URL or "").rstrip("/")
QSTASH_TOKEN = _cfg.QSTASH_TOKEN
GH_PAT = _cfg.GH_PAT
GH_OWNER = _cfg.GH_OWNER
GH_REPO = _cfg.GH_REPO
GH_WORKFLOW_FILE = _cfg.GH_WORKFLOW_FILE

def publish_message(
    destination_url: str,
    payload: Dict[str, Any],
    delay_seconds: int = 0,
    deduplication_id: Optional[str] = None,
    forward_headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Menghantar mesej asinkron ke Upstash QStash dengan kawalan deduplikasi dan sela masa.
    - destination_url: URL sasaran webhook (cth: GitHub REST API atau Cloudflare Worker)
    - delay_seconds: Masa tunggu sebelum dihantar (cth: 30s untuk elak spam)
    - deduplication_id: ID unik untuk elak mesej sama dihantar 2 kali dalam tetingkap masa
    """
    if not QSTASH_URL or not QSTASH_TOKEN:
        raise ValueError("QSTASH_URL atau QSTASH_TOKEN tiada dalam konfigurasi .env.local!")

    endpoint = f"{QSTASH_URL}/v2/publish/{destination_url}"
    
    headers = {
        "Authorization": f"Bearer {QSTASH_TOKEN}",
        "Content-Type": "application/json"
    }

    # Tetapkan sela masa pelaksanaan jika ada
    if delay_seconds > 0:
        headers["Upstash-Delay"] = f"{delay_seconds}s"

    # Halang duplikasi mesej (mengoptimumkan had 1,000 mesej percuma harian)
    if deduplication_id:
        headers["Upstash-Deduplication-Id"] = deduplication_id

    # Majukan header khas ke pelayan sasaran
    if forward_headers:
        for k, v in forward_headers.items():
            headers[f"Upstash-Forward-{k}"] = v

    resp = requests.post(
        endpoint,
        headers=headers,
        data=json.dumps(payload),
        timeout=15
    )

    if resp.status_code not in [200, 201, 202]:
        raise ConnectionError(f"Gagal menghantar ke QStash: HTTP {resp.status_code} - {resp.text}")

    return resp.json()

def dispatch_github_workflow(
    imdb_id: str,
    season: Optional[str] = None,
    episode: Optional[str] = None,
    delay_seconds: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Memicu GitHub Action (workflow_dispatch) melalui QStash secara asinkron apabila
    subtitle filem/siri belum wujud di Redis (Cache-Miss Handler).
    """
    if not GH_PAT or not GH_WORKFLOW_FILE or GH_WORKFLOW_FILE == "NONE":
        console.print("[yellow]⚠ GitHub Workflow Dispatch dilangkau (GH_WORKFLOW_FILE belum ditetapkan).[/yellow]")
        return None

    target_url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/actions/workflows/{GH_WORKFLOW_FILE}/dispatches"
    
    payload = {
        "ref": "main",
        "inputs": {
            "imdb_id": imdb_id,
            "season": str(season) if season else "",
            "episode": str(episode) if episode else "",
            "source": "qstash_auto_dispatch"
        }
    }

    forward_headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Stremio-QStash-Dispatcher"
    }

    # Dedup ID unik berasaskan ID filem untuk elak GitHub Action berjalan berkali-kali
    dedup_key = f"gh_dispatch_{imdb_id}_{season or '0'}_{episode or '0'}"

    try:
        result = publish_message(
            destination_url=target_url,
            payload=payload,
            delay_seconds=delay_seconds,
            deduplication_id=dedup_key,
            forward_headers=forward_headers
        )
        return result
    except Exception as e:
        console.print(f"[bold red]❌ Ralat QStash Dispatch:[/bold red] {e}")
        return None

def test_qstash_connection():
    """Menguji pautan ke pelayan QStash dengan menghantar mesej ujian ke URL echo."""
    console.print(Panel.fit("⚡ [bold cyan]Ujian Diagnostik Upstash QStash Dispatcher[/bold cyan]", border_style="cyan"))

    if not QSTASH_URL or not QSTASH_TOKEN:
        console.print("[bold red]❌ QStash token tiada dalam .env.local![/bold red]")
        return False

    console.print(f"🌐 [yellow]QStash Endpoint:[/yellow] [white]{QSTASH_URL}[/white]")
    
    # Uji kirim mesej ke HTTPbin echo URL
    test_destination = "https://httpbin.org/post"
    test_payload = {
        "event": "ping_test",
        "timestamp": int(time.time()),
        "service": "stremio-sub-engine"
    }
    
    t0 = time.time()
    try:
        # Gunakan deduplication id unik setiap ujian
        dedup = f"ping_{int(time.time())}"
        res = publish_message(
            destination_url=test_destination,
            payload=test_payload,
            delay_seconds=1,
            deduplication_id=dedup
        )
        latency = (time.time() - t0) * 1000

        console.print(f"  [bold green]✔ Mesej Berjaya Didaftarkan ke QStash![/bold green] ({latency:.0f}ms)")
        console.print(f"  [dim]Message ID: {res.get('messageId', 'N/A')}[/dim]")
        return True
    except Exception as e:
        console.print(f"  [bold red]❌ Gagal menghantar mesej QStash:[/bold red] {e}")
        return False

if __name__ == "__main__":
    test_qstash_connection()