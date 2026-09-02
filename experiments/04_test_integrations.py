import os
import hashlib
import json
import time
from urllib.parse import quote
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Muat fail .env.local
ENV_PATH = "/home/braderdin/stremio-sub-engine/.env.local"
load_dotenv(dotenv_path=ENV_PATH)

# Konfigurasi B2 (Akaun 1)
B2_KEY_ID = os.getenv("B2_ACC1_KEY_ID")
B2_APP_KEY = os.getenv("B2_ACC1_APP_KEY")
B2_BUCKET_NAME = os.getenv("B2_ACC1_BUCKET_NAME")
B2_BUCKET_ID = os.getenv("B2_ACC1_BUCKET_ID")

# Konfigurasi Upstash
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
SEARCH_URL = os.getenv("UPSTASH_SEARCH_REST_URL")
SEARCH_TOKEN = os.getenv("UPSTASH_SEARCH_REST_TOKEN")

TEST_IMDB = "tt0111161"
SAMPLE_SRT_CONTENT = """1
00:00:01,000 --> 00:00:04,000
Ujian Subtitle Bahasa Melayu Stremio Engine.

2
00:00:05,000 --> 00:00:08,000
Sambungan Backblaze B2 Private dan Upstash berjaya!
"""

def test_backblaze_b2():
    console.print("\n[bold cyan]1. Menguji Backblaze B2 (Akaun 1)[/bold cyan]")
    if not B2_KEY_ID or not B2_APP_KEY or not B2_BUCKET_ID:
        console.print("[bold red]❌ Ralat: Kunci B2_ACC1 tidak lengkap dalam .env.local[/bold red]")
        return False

    try:
        # a. Pengesahan Akaun B2
        auth_resp = requests.get(
            "https://api.backblazeb2.com/b2api/v2/b2_authorize_account",
            auth=(B2_KEY_ID, B2_APP_KEY),
            timeout=10
        )
        if auth_resp.status_code != 200:
            console.print(f"[bold red]❌ Gagal Authorize B2: HTTP {auth_resp.status_code}[/bold red]")
            return False

        auth_data = auth_resp.json()
        api_url = auth_data["apiUrl"]
        auth_token = auth_data["authorizationToken"]
        download_url = auth_data["downloadUrl"]
        console.print("  [bold green]✔[/bold green] Pengesahan Akaun 1 B2 Berjaya!")

        # b. Dapatkan URL Muat Naik
        up_url_resp = requests.post(
            f"{api_url}/b2api/v2/b2_get_upload_url",
            headers={"Authorization": auth_token},
            json={"bucketId": B2_BUCKET_ID},
            timeout=10
        )
        if up_url_resp.status_code != 200:
            console.print(f"[bold red]❌ Gagal mendapatkan URL Upload B2: HTTP {up_url_resp.status_code}[/bold red]")
            return False

        upload_data = up_url_resp.json()
        upload_endpoint = upload_data["uploadUrl"]
        upload_token = upload_data["authorizationToken"]

        # c. Muat Naik Fail Sampel .srt ke Laluan Berstruktur
        target_path = f"subs/opensubtitles/movie/{TEST_IMDB}/may_test_sample.srt"
        content_bytes = SAMPLE_SRT_CONTENT.encode("utf-8")
        sha1_hash = hashlib.sha1(content_bytes).hexdigest()

        upload_headers = {
            "Authorization": upload_token,
            "X-Bz-File-Name": quote(target_path),
            "Content-Type": "text/plain",
            "Content-Length": str(len(content_bytes)),
            "X-Bz-Content-Sha1": sha1_hash
        }

        up_resp = requests.post(upload_endpoint, headers=upload_headers, data=content_bytes, timeout=15)
        if up_resp.status_code != 200:
            console.print(f"[bold red]❌ Gagal Muat Naik: HTTP {up_resp.status_code} - {up_resp.text}[/bold red]")
            return False

        file_id = up_resp.json()["fileId"]
        console.print(f"  [bold green]✔[/bold green] Berjaya Muat Naik: [white]{target_path}[/white]")
        console.print(f"  [dim]File ID: {file_id}[/dim]")

        # d. Uji Muat Turun Fail Menggunakan Authorization Token B2 Private
        file_download_endpoint = f"{download_url}/file/{B2_BUCKET_NAME}/{target_path}"
        dl_resp = requests.get(
            file_download_endpoint,
            headers={"Authorization": auth_token},
            timeout=10
        )
        if dl_resp.status_code == 200 and "Ujian Subtitle" in dl_resp.text:
            console.print("  [bold green]✔[/bold green] Ujian Bacaan Baldi Private B2 Berjaya Sah!")
            return True
        else:
            console.print(f"[bold red]❌ Gagal Muat Turun Ujian Private: HTTP {dl_resp.status_code}[/bold red]")
            return False

    except Exception as e:
        console.print(f"[bold red]💥 Ralat B2:[/bold red] {e}")
        return False

def test_upstash_redis():
    console.print("\n[bold cyan]2. Menguji Upstash Redis[/bold cyan]")
    if not REDIS_URL or not REDIS_TOKEN:
        console.print("[bold red]❌ Ralat: Kunci UPSTASH_REDIS tidak lengkap dalam .env.local[/bold red]")
        return False

    redis_headers = {"Authorization": f"Bearer {REDIS_TOKEN}"}
    redis_key = f"sub:{TEST_IMDB}"

    # Metadata yang akan diproses oleh Cloudflare Worker
    mock_sub_data = [
        {
            "id": f"{TEST_IMDB}_may_01",
            "lang": "may",
            "source": "opensubtitles",
            "acc": 1,
            "path": f"subs/opensubtitles/movie/{TEST_IMDB}/may_test_sample.srt",
            "release": "The.Shawshank.Redemption.1994.1080p.BluRay.x264-YTS",
            "format": "srt"
        },
        {
            "id": f"{TEST_IMDB}_ind_01",
            "lang": "ind",
            "source": "subscene",
            "acc": 1,
            "path": f"subs/subscene/movie/{TEST_IMDB}/ind_test_sample.srt",
            "release": "The.Shawshank.Redemption.1994.720p.WEB-DL",
            "format": "srt"
        }
    ]

    try:
        t0 = time.time()
        # a. Simpan Kunci (SET)
        set_resp = requests.post(
            f"{REDIS_URL}/set/{redis_key}",
            headers=redis_headers,
            data=json.dumps(mock_sub_data),
            timeout=8
        )
        latency_write = (time.time() - t0) * 1000

        if set_resp.status_code != 200:
            console.print(f"[bold red]❌ Ralat Simpan Redis: HTTP {set_resp.status_code}[/bold red]")
            return False

        console.print(f"  [bold green]✔[/bold green] SET Data Subtitle Berjaya ({latency_write:.1f}ms)")

        # b. Baca Semula Kunci (GET)
        t1 = time.time()
        get_resp = requests.get(f"{REDIS_URL}/get/{redis_key}", headers=redis_headers, timeout=8)
        latency_read = (time.time() - t1) * 1000

        if get_resp.status_code == 200:
            res_json = get_resp.json()
            raw_result = res_json.get("result")
            parsed_data = json.loads(raw_result) if isinstance(raw_result, str) else raw_result

            console.print(f"  [bold green]✔[/bold green] GET Data Berjaya ({latency_read:.1f}ms)")
            console.print(f"  [dim]Jumlah subtitle direkodkan untuk {TEST_IMDB}: {len(parsed_data)} fail[/dim]")
            return True
        else:
            console.print(f"[bold red]❌ Gagal GET Redis: HTTP {get_resp.status_code}[/bold red]")
            return False

    except Exception as e:
        console.print(f"[bold red]💥 Ralat Redis:[/bold red] {e}")
        return False

def test_upstash_search():
    console.print("\n[bold cyan]3. Menguji Upstash Search DB[/bold cyan]")
    if not SEARCH_URL or not SEARCH_TOKEN:
        console.print("[bold yellow]⚠ Kunci UPSTASH_SEARCH belum lengkap. Melepasi ujian ini.[/bold yellow]")
        return True

    search_headers = {
        "Authorization": f"Bearer {SEARCH_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        # a. Masukkan Indeks Dokumen (Upsert)
        doc_payload = {
            "id": TEST_IMDB,
            "content": {
                "imdb_id": TEST_IMDB,
                "title": "The Shawshank Redemption",
                "year": 1994,
                "has_malay": True,
                "has_indonesian": True
            }
        }
        
        upsert_resp = requests.post(
            f"{SEARCH_URL}/documents",
            headers=search_headers,
            json=doc_payload,
            timeout=8
        )

        if upsert_resp.status_code in [200, 201]:
            console.print("  [bold green]✔[/bold green] Dokumen Berjaya Didaftarkan ke Search DB")
        else:
            console.print(f"  [bold yellow]⚠ Respons Search Upsert: HTTP {upsert_resp.status_code}[/bold yellow]")

        # b. Ujian Carian Padanan Teks (Query)
        query_payload = {"query": "Shawshank", "limit": 1}
        query_resp = requests.post(
            f"{SEARCH_URL}/search",
            headers=search_headers,
            json=query_payload,
            timeout=8
        )

        if query_resp.status_code == 200:
            console.print("  [bold green]✔[/bold green] Ujian Carian Teks (Fuzzy/Title Query) Berjaya!")
            return True
        else:
            console.print(f"  [bold yellow]⚠ Search Query HTTP: {query_resp.status_code}[/bold yellow]")
            return False

    except Exception as e:
        console.print(f"[bold yellow]⚠ Ralat Ujian Search DB (Pilihan): {e}[/bold yellow]")
        return False

def run_all_tests():
    console.print(Panel.fit("🚀 [bold green]Ujian Diagnostik Storan B2 & Pangkalan Data Upstash[/bold green] ⚡", border_style="cyan"))

    b2_ok = test_backblaze_b2()
    redis_ok = test_upstash_redis()
    search_ok = test_upstash_search()

    result_table = Table(title="Keputusan Ujian Sistem", border_style="green")
    result_table.add_column("Komponen", style="cyan")
    result_table.add_column("Status Ujian", style="white")

    result_table.add_row("Backblaze B2 (Acc 1 Private Read/Write)", "[bold green]LULUS[/bold green]" if b2_ok else "[bold red]GAGAL[/bold red]")
    result_table.add_row("Upstash Redis (REST Latency & Store)", "[bold green]LULUS[/bold green]" if redis_ok else "[bold red]GAGAL[/bold red]")
    result_table.add_row("Upstash Search DB (Index & Search)", "[bold green]LULUS[/bold green]" if search_ok else "[bold yellow]PERLU PENYESUAIAN[/bold yellow]")

    console.print("\n", result_table)

if __name__ == "__main__":
    run_all_tests()