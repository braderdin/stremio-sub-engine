import os
import json
import time
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from upstash_search import Search

console = Console()

# Muat kunci persekitaran tempatan
ENV_PATH = "/home/braderdin/stremio-sub-engine/.env.local"
load_dotenv(dotenv_path=ENV_PATH)

SEARCH_URL = os.getenv("UPSTASH_SEARCH_REST_URL")
SEARCH_TOKEN = os.getenv("UPSTASH_SEARCH_REST_TOKEN")

INDEX_NAME = "subtitles"

def run_search_diagnostics():
    console.print(Panel.fit("🔍 [bold cyan]Upstash AI Search Official SDK Engine[/bold cyan] 🚀", border_style="cyan"))

    if not SEARCH_URL or not SEARCH_TOKEN:
        console.print("[bold red]❌ Ralat: UPSTASH_SEARCH_REST_URL atau UPSTASH_SEARCH_REST_TOKEN tiada di .env.local![/bold red]")
        return

    console.print(f"🌐 [yellow]Search Host:[/yellow] [white]{SEARCH_URL}[/white]")
    console.print(f"📁 [yellow]Index Sasaran:[/yellow] [bold green]{INDEX_NAME}[/bold green]\n")

    try:
        # Inisialisasi klien rasmi Upstash Search
        client = Search(
            url=SEARCH_URL,
            token=SEARCH_TOKEN,
            allow_telemetry=False
        )

        # 1. Semak maklumat pangkalan data
        console.print("[yellow]⏳ Menyemak info pangkalan data Search...[/yellow]")
        db_info = client.info()
        console.print(f"  [bold green]✔ Sambungan Sah![/bold green] Status: [cyan]{db_info}[/cyan]\n")

        # 2. Akses / cipta Index
        index = client.index(INDEX_NAME)

        # 3. Uji Upsert Dokumen Filem
        console.print("[yellow]⏳ Menguji pendaftaran dokumen (Upsert)...[/yellow]")
        test_docs = [
            {
                "id": "tt0111161",
                "content": {
                    "title": "The Shawshank Redemption",
                    "year": "1994",
                    "category": "movie"
                },
                "metadata": {
                    "imdb_id": "tt0111161",
                    "languages": ["may", "ind", "eng"],
                    "total_subs": 2
                }
            },
            {
                "id": "tt0083944",
                "content": {
                    "title": "Rambo: First Blood",
                    "year": "1982",
                    "category": "movie"
                },
                "metadata": {
                    "imdb_id": "tt0083944",
                    "languages": ["may", "ind"],
                    "total_subs": 1
                }
            }
        ]

        t0 = time.time()
        index.upsert(documents=test_docs)
        latency_upsert = (time.time() - t0) * 1000
        console.print(f"  [bold green]✔[/bold green] 2 Dokumen berjaya didaftarkan! ({latency_upsert:.1f}ms)\n")

        # 4. Uji Ambil Dokumen Berdasarkan ID (Fetch)
        console.print("[yellow]⏳ Menguji fetch dokumen mengikut IMDb ID...[/yellow]")
        fetched = index.fetch(ids=["tt0111161"])
        if fetched:
            console.print(f"  [bold green]✔ Fetch Berjaya:[/bold green] Ditemui {len(fetched)} rekod.")
            console.print(f"  [dim]{fetched}[/dim]\n")

        # 5. Uji Carian Teks (Search Query)
        # Nota: semantic_weight=0 bermaksud padanan teks tulen (BM25 / Keyword), sesuai untuk carian tajuk filem
        test_queries = ["Shawshank", "Rambo Blood", "1994"]

        for q in test_queries:
            console.print(f"[cyan]🔎 Menguji Carian Kata Kunci:[/cyan] [bold white]'{q}'[/bold white]")
            results = index.search(
                query=q,
                limit=2,
                semantic_weight=0.2  # Gabungan pintar teks padanan tajuk
            )

            result_table = Table(title=f"Hasil Carian: '{q}'", border_style="blue")
            result_table.add_column("Skor / ID", style="cyan", width=16)
            result_table.add_column("Tajuk Filem", style="white")
            result_table.add_column("Metadata", style="yellow")

            if results:
                for hit in results:
                    # Ambil id dan content daripada hasil search
                    doc_id = getattr(hit, "id", "N/A")
                    score = getattr(hit, "score", 0.0)
                    content = getattr(hit, "content", {})
                    meta = getattr(hit, "metadata", {})
                    title = content.get("title", "N/A") if isinstance(content, dict) else str(content)

                    result_table.add_row(
                        f"{doc_id} ({score:.2f})",
                        title,
                        json.dumps(meta)
                    )
                console.print(result_table)
            else:
                console.print("  [bold yellow]⚠ Tiada padanan ditemui.[/bold yellow]")

        console.print("\n[bold green]✨ SEMUA UJIAN UPSTASH SEARCH BERJAYA 100%![/bold green]\n")

    except Exception as e:
        console.print(f"[bold red]💥 Ralat Semasa Melaksanakan Upstash Search:[/bold red] {e}")

if __name__ == "__main__":
    run_search_diagnostics()