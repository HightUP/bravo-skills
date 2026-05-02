#!/usr/bin/env python3
"""
espionar-concorrente-full — orquestrador CLI

Uso:
    python main.py "https://www.facebook.com/ads/library/?...view_all_page_id=XXX"
    python main.py "https://www.facebook.com/ads/library/?...search_terms=foo" --max-ads 30
    python main.py "<url>" --no-headless --skip-analyze
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

# garante que dá pra importar os módulos irmãos quando rodado de qualquer cwd
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import scrape  # noqa: E402
import analyze  # noqa: E402
import render  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="espionar-concorrente-full",
        description="Scrape Facebook Ads Library + análise IA + HTML report.",
    )
    p.add_argument("url", help="URL completa da Facebook Ads Library")
    p.add_argument(
        "--max-ads",
        type=int,
        default=int(os.getenv("MAX_ADS", "20")),
        help="Limite de anúncios pra processar (default: 20 ou env MAX_ADS)",
    )
    headless_default = os.getenv("PLAYWRIGHT_HEADLESS", "true").strip().lower() == "true"
    p.add_argument("--headless", dest="headless", action="store_true", default=headless_default)
    p.add_argument("--no-headless", dest="headless", action="store_false")
    p.add_argument(
        "--skip-analyze",
        action="store_true",
        help="Só faz scrape + download. Pula transcrição/descrição/agregação.",
    )
    p.add_argument(
        "--rerun-only-analyze",
        action="store_true",
        help="Pula scrape + download. Lê meta.json de cada ad-XXX/ no out_dir e só refaz a análise IA + render.",
    )
    p.add_argument(
        "--rerun-only-aggregate",
        action="store_true",
        help="Reaproveita transcriptions/descriptions já salvas em meta.json e só roda o passo de agregação + render.",
    )
    p.add_argument(
        "--output-base",
        type=str,
        default=None,
        help="Sobrescreve OBSIDIAN_VAULT_PATH como diretório base de saída.",
    )
    p.add_argument(
        "--name",
        type=str,
        default=None,
        help="Nome do concorrente (ex: 'Hyeser'). Usado como label no report e slug da pasta.",
    )
    return p.parse_args()


def slugify(text: str) -> str:
    """Normaliza pra slug seguro de filesystem (lowercase, hífens, sem acentos)."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")[:60]


def _load_ads_from_disk(out_dir: Path) -> list[dict]:
    """Reconstrói lista de ads lendo cada ad-XXX/meta.json. Inclui transcriptions/descriptions."""
    ads: list[dict] = []
    ad_dirs = sorted(p for p in out_dir.iterdir() if p.is_dir() and p.name.startswith("ad-"))
    for ad_dir in ad_dirs:
        meta_path = ad_dir / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  · ✗ erro lendo {meta_path}: {e}")
            continue
        meta["dir"] = str(ad_dir)
        # garantia: paths de mídia precisam apontar pro disco atual
        local_videos = []
        for n in range(1, 10):
            p = ad_dir / f"video-{n}.mp4"
            if p.exists():
                local_videos.append(str(p))
        if local_videos:
            meta["local_videos"] = local_videos
        local_images = []
        for n in range(1, 10):
            p = ad_dir / f"image-{n}.jpg"
            if p.exists():
                local_images.append(str(p))
        if local_images:
            meta["local_images"] = local_images
        # se descriptions tá vazio mas description.txt existe, recarrega
        if not meta.get("descriptions"):
            desc_path = ad_dir / "description.txt"
            if desc_path.exists():
                txt = desc_path.read_text(encoding="utf-8")
                meta["descriptions"] = [d.strip() for d in txt.split("\n\n---\n\n") if d.strip()]
        # se transcriptions tá vazio mas transcription.txt existe, recarrega
        if not meta.get("transcriptions"):
            tx_path = ad_dir / "transcription.txt"
            if tx_path.exists():
                meta["transcriptions"] = [tx_path.read_text(encoding="utf-8").strip()]
        ads.append(meta)
    return ads


def slug_from_url(url: str) -> str:
    """Extrai um slug estável da URL — view_all_page_id, search_terms ou hash."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    page_id = qs.get("view_all_page_id", [None])[0]
    if page_id:
        return f"page-{page_id}"

    terms = qs.get("search_terms", [None])[0] or qs.get("q", [None])[0]
    if terms:
        return "term-" + re.sub(r"[^a-z0-9]+", "-", terms.lower()).strip("-")[:60]

    # fallback
    return "intel-" + datetime.now().strftime("%Y%m%d-%H%M%S")


def main() -> int:
    load_dotenv(SCRIPT_DIR.parent / ".env")  # tenta .env da pasta da skill
    load_dotenv()  # e .env do cwd, sem sobrescrever

    args = parse_args()

    # Defesa contra URL quebrada por copy-paste mal feito (espaços dentro do meio dos parâmetros)
    args.url = re.sub(r"\s+", "", args.url)

    output_base_str = args.output_base or os.getenv("OBSIDIAN_VAULT_PATH")
    if not output_base_str:
        print("✗ OBSIDIAN_VAULT_PATH não definido. Configure no .env ou use --output-base.")
        return 2
    output_base = Path(output_base_str).expanduser().resolve()

    # Nome customizado tem prioridade sobre slug derivado da URL
    if args.name:
        display_name = args.name.strip()
        slug = slugify(display_name) or slug_from_url(args.url)
    else:
        slug = slug_from_url(args.url)
        display_name = slug  # fallback: usa o slug como label

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = output_base / "concorrentes" / slug / today
    rerun = args.rerun_only_analyze or args.rerun_only_aggregate
    if rerun:
        if not out_dir.exists():
            # tenta achar a pasta mais recente do mesmo slug
            slug_dir = output_base / "concorrentes" / slug
            if slug_dir.exists():
                candidates = sorted(
                    [p for p in slug_dir.iterdir() if p.is_dir()],
                    reverse=True,
                )
                if candidates:
                    out_dir = candidates[0]
                    print(f"→ rerun: pasta de hoje não existe, usando {out_dir.name}")
        if not out_dir.exists():
            print(f"✗ rerun: nenhuma pasta encontrada em {output_base / 'concorrentes' / slug}")
            return 2
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    print(f"→ output: {out_dir}")
    print(f"→ slug: {slug}")
    print(f"→ display name: {display_name}")
    mode = "rerun-aggregate" if args.rerun_only_aggregate else (
        "rerun-analyze" if args.rerun_only_analyze else "full"
    )
    print(f"→ max_ads: {args.max_ads}  headless: {args.headless}  mode: {mode}")

    t0 = time.time()

    # ── 1. Scrape + Download (ou reuso) ───────────────────────
    if rerun:
        ads = _load_ads_from_disk(out_dir)
        if not ads:
            print(f"✗ rerun: nenhum ad-XXX/meta.json encontrado em {out_dir}")
            return 1
        print(f"→ rerun: {len(ads)} anúncios carregados do disco")
    else:
        print(f"→ scraping {args.url} ...")
        try:
            ads = scrape.scrape_ads_library(
                url=args.url,
                max_ads=args.max_ads,
                headless=args.headless,
            )
        except Exception as e:
            print(f"✗ falha no scrape: {e}")
            return 1

        print(f"→ {len(ads)} anúncios encontrados")
        if not ads:
            print("✗ nenhum anúncio. Abortando.")
            return 1

        # ── 2. Download de ativos ─────────────────────────────
        print(f"→ baixando ativos para {out_dir} ...")
        ads = scrape.download_assets(ads, out_dir)

    # ── 3. Análise IA ─────────────────────────────────────────
    insights: list = []
    patterns: list = []
    recommendations: list = []

    if not args.skip_analyze:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            print("⚠ GEMINI_API_KEY ausente — pulando análise IA. Use --skip-analyze pra silenciar.")
        else:
            try:
                if args.rerun_only_aggregate:
                    # transcriptions/descriptions já estão em meta.json (carregadas em _load_ads_from_disk)
                    print("  · só agregação (transcriptions/descriptions reaproveitadas)")
                    from google import genai
                    client = genai.Client(api_key=api_key)
                    insights, patterns, recommendations = analyze._aggregate(client, ads, out_dir=out_dir)
                else:
                    ads, insights, patterns, recommendations = analyze.analyze_all(
                        ads, api_key=api_key, out_dir=out_dir
                    )
            except Exception as e:
                print(f"✗ falha na análise IA: {e}")
                # segue mesmo assim, com os dados que tiver
    else:
        print("→ análise IA pulada (--skip-analyze)")

    # ── 4. Render do report ───────────────────────────────────
    page_meta = {
        "url": args.url,
        "slug": slug,
        "display_name": display_name,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "scraped_at_human": datetime.now().strftime("%d / %b / %Y").lower(),
        "total_ads": len(ads),
        "max_ads": args.max_ads,
    }

    print("→ gerando report.html, insights.md, index.json ...")
    render.render_all(
        out_dir=out_dir,
        ads=ads,
        page_meta=page_meta,
        insights=insights,
        patterns=patterns,
        recommendations=recommendations,
    )

    elapsed = time.time() - t0
    print(f"✓ pronto em {elapsed:.1f}s")
    print(f"✓ abrir: open '{out_dir / 'report.html'}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
