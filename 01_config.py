import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from upstash_redis import Redis
from upstash_search import Search

console = Console()

# 1. Muat pemboleh ubah persekitaran
# Keutamaan: Baca .env.local jika wujud (Local WSL), jika tiada baca dari system env (GitHub Actions)
LOCAL_ENV = os.path.join(os.path.dirname(__file__), ".env.local")
if os.path.exists(LOCAL_ENV):
    load_dotenv(dotenv_path=LOCAL_ENV, override=True)
else:
    load_dotenv()

# 2. Direktori Asas Projek
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
LEDGER_FILE = os.path.join(DATA_DIR, "uploaded_ledger.json")

for folder in [DATA_DIR, OUTPUT_DIR, TEMP_DIR]:
    os.makedirs(folder, exist_ok=True)

# 3. Konfigurasi Keselamatan & Addon
ADDON_SECRET_TOKEN = os.getenv("ADDON_SECRET_TOKEN", "default_secret_token")
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "").rstrip("/")

# 4. Konfigurasi GitHub Actions & CI/CD
GH_PAT = os.getenv("GH_PAT")
GH_OWNER = os.getenv("GH_OWNER", "braderdin")
GH_REPO = os.getenv("GH_REPO", "stremio-sub-engine")
GH_WORKFLOW_FILE = os.getenv("GH_WORKFLOW_FILE", "translate.yml")

# 5. Konfigurasi Upstash Services
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
SEARCH_URL = os.getenv("UPSTASH_SEARCH_REST_URL")
SEARCH_TOKEN = os.getenv("UPSTASH_SEARCH_REST_TOKEN")
QSTASH_URL = os.getenv("QSTASH_URL")
QSTASH_TOKEN = os.getenv("QSTASH_TOKEN")

# Had Bait Storan Backblaze B2 (9.5 GB selamat = 9.5 * 1024^3)
B2_MAX_STORAGE_BYTES = 10200547328 

# 6. Pengesanan Dinamik Akaun Backblaze B2 (Akaun 1 hingga 30)
B2_ACCOUNTS = []
for i in range(1, 31):
    key_id = os.getenv(f"B2_ACC{i}_KEY_ID")
    app_key = os.getenv(f"B2_ACC{i}_APP_KEY")
    bucket_name = os.getenv(f"B2_ACC{i}_BUCKET_NAME")
    bucket_id = os.getenv(f"B2_ACC{i}_BUCKET_ID")
    key_name = os.getenv(f"B2_ACC{i}_KEY_NAME")
    s3_endpoint = os.getenv(f"B2_ACC{i}_S3_API_ENDPOINT")

    # Jika akaun ini tidak ditakrifkan dalam env, langkau
    if not key_id or not app_key or not bucket_name:
        continue

    B2_ACCOUNTS.append({
        "index": i,
        "key_id": key_id,
        "app_key": app_key,
        "bucket_name": bucket_name,
        "bucket_id": bucket_id,
        "key_name": key_name,
        "s3_endpoint": s3_endpoint
    })

def get_redis_client():
    """Inisialisasi Klien Rasmi Upstash Redis REST."""
    if not REDIS_URL or not REDIS_TOKEN:
        console.print("[bold red]❌ Ralat: UPSTASH_REDIS credentials tiada![/bold red]")
        sys.exit(1)
    return Redis(url=REDIS_URL, token=REDIS_TOKEN)

def get_search_index(index_name="subtitles"):
    """Inisialisasi Klien Rasmi Upstash Search Index."""
    if not SEARCH_URL or not SEARCH_TOKEN:
        console.print("[bold red]❌ Ralat: UPSTASH_SEARCH credentials tiada![/bold red]")
        sys.exit(1)
    client = Search(url=SEARCH_URL, token=SEARCH_TOKEN, allow_telemetry=False)
    return client.index(index_name)

if __name__ == "__main__":
    console.print(f"[bold green]✔ Konfigurasi Berjaya Dimuatkan![/bold green]")
    console.print(f"📁 Direktori Asas: [cyan]{BASE_DIR}[/cyan]")
    console.print(f"📦 Akaun B2 Dikesan: [bold yellow]{len(B2_ACCOUNTS)} Akaun[/bold yellow]")
    for acc in B2_ACCOUNTS:
        console.print(f"   👉 Akaun {acc['index']}: [white]{acc['bucket_name']}[/white] ({acc['s3_endpoint']})")
    console.print(f"🐙 GitHub Target: [cyan]{GH_OWNER}/{GH_REPO}[/cyan] (PAT Terkesan: {'YA' if GH_PAT else 'TIDAK'})")