import os
import importlib
from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rich.console import Console

console = Console()

# Import modul teras projek secara dinamik
_config = importlib.import_module("01_config")
ADDON_SECRET_TOKEN = _config.ADDON_SECRET_TOKEN
CF_WORKER_URL = _config.CF_WORKER_URL

_redis = importlib.import_module("04_redis_manager")
get_subtitles_for_stream = _redis.get_subtitles_for_stream

MANIFEST = {
    "id": "org.community.stremiosubengine",
    "version": "1.0.0",
    "name": "Sub Engine (BM & ID)",
    "description": "Penyedia Sarikata Bahasa Melayu & Indonesia Automatik dan Pantas.",
    "resources": ["subtitles"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"],
    "catalogs": []
}

app = FastAPI(title="Stremio Sub Engine Addon")

# Benarkan sambungan dari aplikasi Stremio (Web, Desktop, Android)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/manifest.json")
@app.get(f"/{ADDON_SECRET_TOKEN}/manifest.json")
async def get_manifest():
    """Menyajikan manifest rasmi Addon kepada pemain Stremio."""
    return JSONResponse(content=MANIFEST)

@app.get("/subtitles/{media_type}/{id_path}.json")
@app.get(f"/{ADDON_SECRET_TOKEN}/subtitles/{{media_type}}/{{id_path}}.json")
async def get_subtitles(media_type: str, id_path: str, extra: Optional[str] = None):
    """
    Mengambil metadata subtitle dari Upstash Redis berdasarkan IMDb ID.
    Contoh id_path:
      - Filem   : tt0309530
      - Siri TV : tt0903747:1:1 (IMDb:Season:Episode)
    """
    # Bersihkan parameter jika ada sambungan .json
    clean_path = id_path.replace(".json", "")
    parts = clean_path.split(":")

    imdb_id = parts[0]
    season = parts[1] if len(parts) > 1 else None
    episode = parts[2] if len(parts) > 2 else None

    try:
        # Panggilan pantas (1 read command) ke Upstash Redis
        subs_list = get_subtitles_for_stream(imdb_id, season=season, episode=episode)
        
        if not subs_list:
            return JSONResponse(content={"subtitles": []})

        formatted_subs: List[Dict[str, Any]] = []

        for sub in subs_list:
            # Tetapkan URL muat turun (menggunakan Cloudflare Worker atau pautan terus B2)
            base_url = CF_WORKER_URL if CF_WORKER_URL and "belum" not in CF_WORKER_URL else "http://localhost:7000/proxy"
            file_url = f"{base_url}/{sub.get('path')}"

            # Format label paparan di Stremio
            release_tag = sub.get("release", "Default")
            source_tag = sub.get("source", "sub").upper()
            lang_code = sub.get("lang", "may")

            formatted_subs.append({
                "id": str(sub.get("id", "")),
                "url": file_url,
                "lang": lang_code,
                "format": "srt",
                "label": f"[{source_tag}] {release_tag}"
            })

        return JSONResponse(content={"subtitles": formatted_subs})

    except Exception as e:
        console.print(f"[bold red]❌ Ralat Mengambil Subtitle:[/bold red] {e}")
        return JSONResponse(content={"subtitles": []})

if __name__ == "__main__":
    import uvicorn
    console.print("[bold green]🚀 Memulakan Stremio Addon Server di http://127.0.0.1:7000[/bold green]")
    uvicorn.run("08_addon_server:app", host="0.0.0.0", port=7000, reload=True)