"""
scrape.py — Playwright varre a Facebook Ads Library e baixa ativos.

Funções públicas:
    scrape_ads_library(url, max_ads, headless) -> list[dict]
    download_assets(ads, out_dir) -> list[dict]   # mesmas dicts, com paths locais
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PWTimeout,
    sync_playwright,
)

# ─────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Discriminante único: todo anúncio real tem "Library ID" / "Identificação da biblioteca".
# UI da Ads Library (filtros, avatar, etc) não tem.
LIBRARY_ID_RX = re.compile(r"(?:Library ID|Identificação da biblioteca|ID da biblioteca)\s*[:#]?\s*(\d+)", re.IGNORECASE)

ACTIVE_SINCE_RX = re.compile(
    r"(?:Veiculação iniciada|Started running|Active since|Ativo desde)[^\d]*([\d/.\-]+)",
    re.IGNORECASE,
)

# JS que encontra ad cards reais usando Library ID como âncora.
# Sobe pelo DOM até achar um container "razoável" (não gigante o bastante pra conter outros ads).
FIND_AD_CARDS_JS = """
() => {
  const RE = /(?:Identificação da biblioteca|Library ID|ID da biblioteca)\\s*[:#]?\\s*\\d+/i;
  const RE_GLOBAL = /(?:Identificação da biblioteca|Library ID|ID da biblioteca)\\s*[:#]?\\s*\\d+/gi;
  const all = document.querySelectorAll('div');
  const candidates = [];
  for (const el of all) {
    const r = el.getBoundingClientRect();
    if (r.width < 280 || r.height < 200) continue;
    const text = el.innerText || '';
    if (!RE.test(text)) continue;
    // descarta containers que englobam vários cards
    const matches = text.match(RE_GLOBAL);
    if (matches && matches.length > 1) continue;
    candidates.push(el);
  }
  // dedup: prefere o mais interno (se A está dentro de B, fica com A)
  const filtered = candidates.filter(c =>
    !candidates.some(other => other !== c && other.contains(c))
  );
  // marca pra Playwright achar depois
  filtered.forEach((el, i) => el.setAttribute('data-bravo-ad', String(i)));
  return filtered.length;
}
"""


# ─────────────────────────────────────────────────────────────────
# SCRAPE
# ─────────────────────────────────────────────────────────────────

def scrape_ads_library(url: str, max_ads: int = 20, headless: bool = True) -> list[dict[str, Any]]:
    """Abre a Ads Library, faz scroll e extrai os cards."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="pt-BR",
        )
        page = ctx.new_page()
        try:
            ads = _scrape_with_page(page, url, max_ads=max_ads)
        finally:
            ctx.close()
            browser.close()
        return ads


def _scrape_with_page(page: Page, url: str, *, max_ads: int) -> list[dict[str, Any]]:
    print(f"  · navegando ...")
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)

    # tenta dispensar cookie banner / modais
    _dismiss_overlays(page)

    # espera o primeiro Library ID aparecer no DOM (sinal de que cards carregaram)
    print(f"  · aguardando ad cards ...")
    if not _wait_for_library_ids(page, timeout=30_000):
        print("  · ✗ nenhum ad detectado após 30s")
        return []

    # scroll progressivo
    last_count = 0
    stagnant_rounds = 0
    max_stagnant = 4
    max_rounds = 60

    for round_idx in range(max_rounds):
        count = page.evaluate(FIND_AD_CARDS_JS)
        if count >= max_ads:
            print(f"  · {count} ads (atingiu max_ads={max_ads})")
            break

        if count == last_count:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0
        last_count = count

        if stagnant_rounds >= max_stagnant:
            print(f"  · {count} ads (parou de carregar)")
            break

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        try:
            page.wait_for_load_state("networkidle", timeout=4_000)
        except PWTimeout:
            pass
        time.sleep(1.2)

    # extrai dados (re-escaneia uma última vez antes pra garantir IDs frescos)
    final_count = page.evaluate(FIND_AD_CARDS_JS)
    print(f"  · extraindo {min(final_count, max_ads)} ads ...")

    ads: list[dict[str, Any]] = []
    real_idx = 0
    for i in range(min(final_count, max_ads * 2)):  # pega mais e filtra
        if real_idx >= max_ads:
            break
        card = page.query_selector(f'[data-bravo-ad="{i}"]')
        if not card:
            continue
        try:
            data = _extract_card(card)
            # validação: precisa ter library_id E (imagem ou vídeo)
            if not data["library_id"]:
                continue
            if not data["image_urls"] and not data["video_urls"]:
                continue
            real_idx += 1
            data["idx"] = real_idx
            ads.append(data)
        except Exception as e:
            print(f"  · ✗ erro extraindo ad: {e}")
            continue

    print(f"  · {len(ads)} ads válidos extraídos")
    return ads


def _wait_for_library_ids(page: Page, timeout: int) -> bool:
    """Espera até o DOM ter pelo menos 1 elemento com Library ID."""
    start = time.time()
    while (time.time() - start) * 1000 < timeout:
        try:
            count = page.evaluate(FIND_AD_CARDS_JS)
            if count >= 1:
                return True
        except Exception:
            pass
        time.sleep(0.8)
    return False


def _dismiss_overlays(page: Page) -> None:
    """Tenta clicar em botões comuns de fechar cookie/login modal."""
    candidates = [
        'div[aria-label="Permitir todos os cookies"]',
        'div[aria-label="Allow all cookies"]',
        'div[aria-label="Recusar cookies opcionais"]',
        'div[aria-label="Decline optional cookies"]',
        'div[aria-label="Fechar"]',
        'div[aria-label="Close"]',
        'button[title="Close"]',
    ]
    for sel in candidates:
        try:
            el = page.query_selector(sel)
            if el:
                el.click(timeout=1_000)
                time.sleep(0.5)
        except Exception:
            continue


def _extract_card(card) -> dict[str, Any]:
    """Extrai metadata + media URLs de um card."""
    text_full = (card.inner_text() or "").strip()

    # ID
    library_id = None
    m = LIBRARY_ID_RX.search(text_full)
    if m:
        library_id = m.group(1)

    # Active since
    active_since = None
    m = ACTIVE_SINCE_RX.search(text_full)
    if m:
        active_since = m.group(1)

    # textos: heurística — separa por linhas e remove lixo de UI
    lines = [ln.strip() for ln in text_full.splitlines() if ln.strip()]
    meta_keywords = (
        "library id",
        "identificação",
        "id da biblioteca",
        "veiculação",
        "started running",
        "active since",
        "ativo desde",
        "patrocinado",
        "sponsored",
        "saiba mais",
        "learn more",
        "cadastre-se",
        "sign up",
        "ver detalhes",
        "see ad details",
        "denunciar",
        "report",
        "classificar",
        "remover",
        "anúncios ativos",
        "status online",
        "ver resumo",
        "open in new tab",
        "abrir em nova aba",
    )
    # regex pra identificar lixo de player de vídeo ("0:00 / 1:16", "0:30/2:00")
    video_player_rx = re.compile(r"^\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}$")
    # números soltos (curtidas, comentários)
    pure_number_rx = re.compile(r"^[\d.,kKmM\s]+$")

    body_lines: list[str] = []
    for ln in lines:
        low = ln.lower()
        if any(k in low for k in meta_keywords):
            continue
        if video_player_rx.match(ln):
            continue
        if pure_number_rx.match(ln) and len(ln) < 8:
            continue
        # remove zero-width chars
        cleaned = re.sub(r"[​‌‍﻿]", "", ln).strip()
        if cleaned:
            body_lines.append(cleaned)

    # hook = primeira linha "longa" do corpo; copy = junção das demais
    hook = ""
    copy = ""
    if body_lines:
        for i, ln in enumerate(body_lines):
            if len(ln) >= 12:
                hook = ln
                copy = " ".join(body_lines[i + 1: i + 8]).strip()
                break
        if not hook:
            hook = body_lines[0]
            copy = " ".join(body_lines[1:6]).strip()

    # CTA — heurística: textos curtos que são botão clássico
    cta_text = _find_cta(card, text_full)

    # imagens — filtra avatares/thumbnails pequenas
    image_urls: list[str] = []
    for img in card.query_selector_all("img"):
        src = img.get_attribute("src") or ""
        if not src or not src.startswith("http"):
            continue
        if "static.xx.fbcdn" in src or "data:image" in src:
            continue
        # descarta thumbnails de avatar (s148x148, p148x148, p60x60, etc)
        if re.search(r"[sp]\d{2,3}x\d{2,3}", src):
            continue
        # descarta dimensões reportadas pequenas (avatar de página, ícones)
        try:
            w = int(img.get_attribute("width") or "0")
            h = int(img.get_attribute("height") or "0")
            if 0 < w < 200 and 0 < h < 200:
                continue
        except ValueError:
            pass
        if src not in image_urls:
            image_urls.append(src)

    # vídeos
    video_urls: list[str] = []
    for vid in card.query_selector_all("video"):
        src = vid.get_attribute("src") or ""
        if src and src.startswith("http"):
            video_urls.append(src)
        # alguns têm <source>
        for source in vid.query_selector_all("source"):
            ssrc = source.get_attribute("src") or ""
            if ssrc and ssrc.startswith("http") and ssrc not in video_urls:
                video_urls.append(ssrc)

    # tipo
    if video_urls:
        ad_type = "video"
    elif len(image_urls) > 1:
        ad_type = "carousel"
    elif image_urls:
        ad_type = "image"
    else:
        ad_type = "unknown"

    return {
        "library_id": library_id,
        "hook": hook[:280],
        "copy": copy[:1200],
        "cta_text": cta_text,
        "active_since": active_since,
        "type": ad_type,
        "image_urls": image_urls[:8],  # limita
        "video_urls": video_urls[:3],
        "raw_text": text_full[:4000],
    }


def _find_cta(card, text_full: str) -> str:
    """Tenta achar o texto do CTA — botão mais provável."""
    common_ctas = [
        "Saiba mais",
        "Learn more",
        "Cadastre-se",
        "Sign Up",
        "Inscreva-se",
        "Comprar",
        "Shop now",
        "Baixar",
        "Download",
        "Reservar",
        "Book now",
        "Assine",
        "Subscribe",
        "Quero entrar",
        "Quero saber mais",
        "Quero a vaga",
    ]
    # primeiro tenta divs com role=button
    for el in card.query_selector_all('div[role="button"], a[role="button"], a[role="link"]'):
        t = (el.inner_text() or "").strip()
        if 2 < len(t) < 40 and "\n" not in t:
            for c in common_ctas:
                if c.lower() in t.lower():
                    return t
    # fallback: procura no texto
    for c in common_ctas:
        if c.lower() in text_full.lower():
            return c
    return ""


# ─────────────────────────────────────────────────────────────────
# DOWNLOAD
# ─────────────────────────────────────────────────────────────────

def download_assets(ads: list[dict[str, Any]], out_dir: Path) -> list[dict[str, Any]]:
    """Baixa imagens e vídeos pra ad-{idx:03d}/. Atualiza ads com paths locais."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = httpx.Client(
        timeout=httpx.Timeout(30.0, connect=10.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )

    try:
        for ad in ads:
            ad_dir = out_dir / f"ad-{ad['idx']:03d}"
            ad_dir.mkdir(exist_ok=True)

            local_images: list[str] = []
            for n, u in enumerate(ad.get("image_urls", []), start=1):
                target = ad_dir / f"image-{n}.jpg"
                if _download(client, u, target):
                    local_images.append(str(target))

            local_videos: list[str] = []
            for n, u in enumerate(ad.get("video_urls", []), start=1):
                target = ad_dir / f"video-{n}.mp4"
                if _download(client, u, target):
                    local_videos.append(str(target))

            ad["local_images"] = local_images
            ad["local_videos"] = local_videos
            ad["dir"] = str(ad_dir)

            # salva meta inicial
            meta_path = ad_dir / "meta.json"
            with meta_path.open("w", encoding="utf-8") as f:
                json.dump(
                    {k: v for k, v in ad.items() if k not in ("raw_text",)},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            print(f"  · ad {ad['idx']:03d}: {len(local_images)} img · {len(local_videos)} vid")
    finally:
        client.close()

    return ads


def _download(client: httpx.Client, url: str, target: Path) -> bool:
    """Download atômico com 3 retries."""
    if target.exists() and target.stat().st_size > 0:
        return True
    part = target.with_suffix(target.suffix + ".part")
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with client.stream("GET", url) as r:
                r.raise_for_status()
                with part.open("wb") as f:
                    for chunk in r.iter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
            part.replace(target)
            return True
        except Exception as e:
            last_err = e
            time.sleep(0.7 * (attempt + 1))
    print(f"  · ✗ download falhou após 3 tentativas: {urlparse(url).netloc} :: {last_err}")
    if part.exists():
        try:
            part.unlink()
        except Exception:
            pass
    return False
