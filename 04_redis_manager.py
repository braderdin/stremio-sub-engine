import json
import importlib
from rich.console import Console

console = Console()

# Import konfigurasi daripada 01_config
_config = importlib.import_module("01_config")
get_redis_client = _config.get_redis_client

def _build_redis_key(imdb_id, season=None, episode=None):
    """Menjana format kunci standard Redis bagi filem atau siri TV."""
    clean_imdb = str(imdb_id).strip()
    if not clean_imdb.startswith("tt") and clean_imdb.isdigit():
        clean_imdb = f"tt{clean_imdb.zfill(7)}"

    if season and episode:
        return f"sub:{clean_imdb}:{season}:{episode}"
    return f"sub:{clean_imdb}"

def save_subtitle_record(imdb_id, sub_item, season=None, episode=None):
    """
    Menyimpan atau mengemas kini metadata subtitle ke dalam senarai JSON Redis.
    sub_item: {
        "id": "opensub_12345",
        "lang": "may",
        "source": "opensubtitles",
        "acc": 1,
        "path": "subs/opensubtitles/movie/tt0111161/may_12345.srt",
        "release": "The.Shawshank.Redemption.1080p.BluRay",
        "format": "srt"
    }
    """
    redis = get_redis_client()
    key = _build_redis_key(imdb_id, season, episode)

    # 1. Baca data sedia ada
    current_data = []
    raw_val = redis.get(key)
    if raw_val:
        try:
            current_data = json.loads(raw_val) if isinstance(raw_val, str) else raw_val
        except Exception:
            current_data = []

    # 2. Semak jika path / sub_id sudah wujud (Deduplikasi)
    existing_paths = {item.get("path") for item in current_data}
    if sub_item.get("path") in existing_paths:
        return False  # Rekod sudah wujud

    # 3. Masukkan rekod baharu dan simpan ke Redis
    current_data.append(sub_item)
    redis.set(key, json.dumps(current_data, ensure_ascii=False))
    return True

def get_subtitles_for_stream(imdb_id, season=None, episode=None):
    """Mendapatkan senarai subtitle untuk disajikan kepada Cloudflare Worker / Stremio."""
    redis = get_redis_client()
    key = _build_redis_key(imdb_id, season, episode)
    raw_val = redis.get(key)

    if not raw_val:
        return []

    try:
        return json.loads(raw_val) if isinstance(raw_val, str) else raw_val
    except Exception:
        return []

if __name__ == "__main__":
    console.print("[bold cyan]🧪 Menguji Modul 04_redis_manager...[/bold cyan]")
    test_imdb = "tt0111161"
    sample_entry = {
        "id": "test_may_99",
        "lang": "may",
        "source": "opensubtitles",
        "acc": 1,
        "path": "subs/opensubtitles/movie/tt0111161/may_99.srt",
        "release": "Shawshank.Test.1080p",
        "format": "srt"
    }

    added = save_subtitle_record(test_imdb, sample_entry)
    console.print(f"Status Simpan: {'[green]Rekod Baharu Disimpan[/green]' if added else '[yellow]Rekod Sudah Wujud[/yellow]'}")

    records = get_subtitles_for_stream(test_imdb)
    console.print(f"✔ Jumlah Subtitle Terdaftar untuk {test_imdb}: [bold green]{len(records)}[/bold green]")
    for r in records:
        console.print(f"   👉 [{r['lang'].upper()}] {r['release']} ({r['source']})")