import importlib
from rich.console import Console
from rich.table import Table

console = Console()

# Import konfigurasi daripada 01_config
_config = importlib.import_module("01_config")
get_search_index = _config.get_search_index

def upsert_movie_to_search(imdb_id, title, year="N/A", languages=None, category="movie"):
    """
    Mendaftarkan atau mengemas kini metadata filem ke Upstash Search DB.
    - languages: contoh ['may', 'ind']
    """
    clean_imdb = str(imdb_id).strip()
    if not clean_imdb.startswith("tt") and clean_imdb.isdigit():
        clean_imdb = f"tt{clean_imdb.zfill(7)}"

    langs = languages or ["may", "ind"]
    index = get_search_index(index_name="subtitles")

    doc = {
        "id": clean_imdb,
        "content": {
            "title": title,
            "year": str(year),
            "category": category
        },
        "metadata": {
            "imdb_id": clean_imdb,
            "languages": langs
        }
    }

    try:
        index.upsert(documents=[doc])
        return True
    except Exception as e:
        console.print(f"[bold red]❌ Ralat Search Upsert ({clean_imdb}):[/bold red] {e}")
        return False

def search_movies(query, limit=5):
    """Carian tajuk filem (fuzzy/keyword matching) untuk Stremio fallback."""
    index = get_search_index(index_name="subtitles")
    try:
        hits = index.search(query=query, limit=limit, semantic_weight=0.2)
        results = []
        for hit in hits:
            content = getattr(hit, "content", {})
            metadata = getattr(hit, "metadata", {})
            results.append({
                "imdb_id": getattr(hit, "id", ""),
                "score": getattr(hit, "score", 0.0),
                "title": content.get("title") if isinstance(content, dict) else str(content),
                "year": content.get("year") if isinstance(content, dict) else "",
                "languages": metadata.get("languages", []) if isinstance(metadata, dict) else []
            })
        return results
    except Exception as e:
        console.print(f"[bold red]❌ Ralat Search Query:[/bold red] {e}")
        return []

if __name__ == "__main__":
    console.print("[bold cyan]🧪 Menguji Modul 05_search_manager...[/bold cyan]")
    
    # 1. Uji Upsert
    ok = upsert_movie_to_search(
        imdb_id="tt0083944",
        title="Rambo: First Blood",
        year="1982",
        languages=["may", "ind"]
    )
    console.print(f"Status Upsert: {'[bold green]Berjaya[/bold green]' if ok else '[bold red]Gagal[/bold red]'}")

    # 2. Uji Query
    results = search_movies("First Blood", limit=2)
    tbl = Table(title="Hasil Carian Upstash Search", border_style="green")
    tbl.add_column("IMDb ID", style="cyan")
    tbl.add_column("Tajuk", style="white")
    tbl.add_column("Tahun", style="yellow")
    tbl.add_column("Bahasa", style="green")

    for item in results:
        tbl.add_row(item["imdb_id"], item["title"], item["year"], ", ".join(item["languages"]))
    console.print(tbl)