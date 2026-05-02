#!/usr/bin/env python3
"""
espionar-concorrente (LITE) — orquestrador CLI

Versão LITE: scrape + download de ativos brutos. SEM análise IA, SEM HTML report.
A versão FULL (transcrição, vision, HTML report) está na Mentoria Bravo.

Uso:
    python main.py --name "Hyeser" 'https://www.facebook.com/ads/library/?...view_all_page_id=XXX'
    python main.py --name "Foo Bar" --max-ads 30 '<URL>'
    python main.py --name "Foo Bar" --no-headless '<URL>'
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


# ─────────────────────────────────────────────────────────────────
# Validação de .env
# ─────────────────────────────────────────────────────────────────

REQUIRED_ENV = {
    "OBSIDIAN_VAULT_PATH": "Caminho absoluto onde criar concorrentes/",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="espionar-concorrente",
        description="Scrape Facebook Ads Library — versão LITE (sem análise IA).",
    )
    p.add_argument("url", help="URL completa da Facebook Ads Library")
    p.add_argument(
        "--name",
        type=str,
        default=None,
        help="Nome do concorrente (ex: 'Hyeser'). Usado como label e slug da pasta.",
    )
    p.add_argument(
        "--max-ads",
        type=int,
        default=int(os.getenv("MAX_ADS", "20")),
        help="Limite de anúncios pra processar (default: 20 ou env MAX_ADS).",
    )
    headless_default = os.getenv("PLAYWRIGHT_HEADLESS", "true").strip().lower() == "true"
    p.add_argument("--headless", dest="headless", action="store_true", default=headless_default)
    p.add_argument("--no-headless", dest="headless", action="store_false")
    p.add_argument(
        "--output-base",
        type=str,
        default=None,
        help="Sobrescreve OBSIDIAN_VAULT_PATH como diretório base de saída.",
    )
    return p.parse_args()


def slugify(text: str) -> str:
    """Normaliza pra slug seguro de filesystem (lowercase, hífens, sem acentos)."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")[:60]


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

    # ── Validação .env ──────────────────────────────────────────
    output_base_str = args.output_base or os.getenv("OBSIDIAN_VAULT_PATH")
    if not output_base_str:
        print("✗ OBSIDIAN_VAULT_PATH não definido.")
        print("  → Configure no .env (cp .env.example .env e edita) ou use --output-base.")
        for var, desc in REQUIRED_ENV.items():
            print(f"    {var}: {desc}")
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
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"→ output: {out_dir}")
    print(f"→ slug: {slug}")
    print(f"→ display name: {display_name}")
    print(f"→ max_ads: {args.max_ads}  headless: {args.headless}")

    t0 = time.time()

    # ── 1. Scrape ─────────────────────────────────────────────
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

    # ── 2. Download de ativos ─────────────────────────────────
    print(f"→ baixando ativos para {out_dir} ...")
    ads = scrape.download_assets(ads, out_dir)

    # ── 3. index.json minimalista ─────────────────────────────
    index = {
        "advertiser": display_name,
        "slug": slug,
        "source_url": args.url,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "country": "BR",
        "total_ads": len(ads),
        "max_ads": args.max_ads,
        "ads": [
            {
                "id": f"ad-{ad['idx']:03d}",
                "library_id": ad.get("library_id"),
                "hook": ad.get("hook", ""),
                "copy": ad.get("copy", ""),
                "cta_text": ad.get("cta_text", ""),
                "active_since": ad.get("active_since"),
                "type": ad.get("type", "unknown"),
                "dir": ad.get("dir"),
                "local_images": ad.get("local_images", []),
                "local_videos": ad.get("local_videos", []),
            }
            for ad in ads
        ],
    }

    index_path = out_dir / "index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0

    # ── 4. Resumo final ───────────────────────────────────────
    print()
    print(f"✓ {len(ads)} ads baixados em {elapsed:.1f}s")
    print(f"✓ pasta: {out_dir}")
    print(f"✓ index: {index_path}")
    print()
    print("ℹ️  versão LITE — sem análise IA. Pra transcrição + vision + HTML report,")
    print("   use a versão FULL (Mentoria Bravo).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
