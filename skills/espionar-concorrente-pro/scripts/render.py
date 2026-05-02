"""
render.py — Jinja2 → report.html + insights.md + index.json.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


# ─────────────────────────────────────────────────────────────────
# API PRINCIPAL
# ─────────────────────────────────────────────────────────────────

def render_all(
    *,
    out_dir: Path,
    ads: list[dict[str, Any]],
    page_meta: dict[str, Any],
    insights: list[dict],
    patterns: list[dict],
    recommendations: list[dict],
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Pre-process ads pra template (embed thumbs como base64 + paths relativos pra vídeos)
    view_ads = [_prepare_ad_view(ad, idx=i, out_dir=out_dir) for i, ad in enumerate(ads, start=1)]

    # 1.5) Normaliza markdown **bold** -> <strong> nos textos vindos do Gemini (que costuma ignorar instrução de HTML)
    insights = [_normalize_insight(ins) for ins in (insights or [])]

    # 2) Render HTML
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["nl2br"] = lambda s: (s or "").replace("\n", "<br>")
    template = env.get_template("report.html.j2")
    html = template.render(
        page=page_meta,
        ads=view_ads,
        insights=insights or [],
        patterns=patterns or [],
        recommendations=recommendations or [],
        generated_at=datetime.now(),
    )
    (out_dir / "report.html").write_text(html, encoding="utf-8")

    # 3) insights.md
    md = _render_markdown(page_meta, view_ads, insights, patterns, recommendations)
    (out_dir / "insights.md").write_text(md, encoding="utf-8")

    # 4) index.json
    index_payload = {
        "page": page_meta,
        "ads": [
            {k: v for k, v in ad.items() if k not in ("raw_text", "thumb_data_uri")}
            for ad in view_ads
        ],
        "insights": insights,
        "patterns": patterns,
        "recommendations": recommendations,
    }
    (out_dir / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def _prepare_ad_view(ad: dict[str, Any], *, idx: int, out_dir: Path | None = None) -> dict[str, Any]:
    """Adiciona campos prontos pra template (thumb embed, format label, theme, vídeo player)."""
    out = dict(ad)
    out["theme"] = f"t{((idx - 1) % 8) + 1}"
    type_label_map = {
        "video": "Vídeo",
        "image": "Imagem",
        "carousel": "Carrossel",
        "unknown": "Anúncio",
    }
    out["type_label"] = type_label_map.get(ad.get("type", "unknown"), "Anúncio")

    # thumb: primeira imagem local OU placeholder
    thumb = None
    images = ad.get("local_images") or []
    if images:
        thumb = _embed_image(Path(images[0]))
    out["thumb_data_uri"] = thumb

    # vídeo: caminho RELATIVO ao report.html (não embed em base64 pra não pesar)
    # report.html mora em out_dir/, vídeo em out_dir/ad-XXX/video-N.mp4
    out["video_relpath"] = None
    out["video_mime"] = None
    videos = ad.get("local_videos") or []
    if videos and out_dir is not None:
        try:
            video_path = Path(videos[0])
            rel = video_path.relative_to(out_dir)
            out["video_relpath"] = str(rel)
            mime, _ = mimetypes.guess_type(video_path.name)
            out["video_mime"] = mime or "video/mp4"
        except (ValueError, Exception):
            pass

    # mock label do thumb
    if ad.get("type") == "video":
        n_videos = len(ad.get("local_videos", []))
        out["thumb_label"] = f"vídeo · {n_videos} arquivo(s)" if n_videos else "vídeo"
    elif ad.get("type") == "carousel":
        out["thumb_label"] = f"carrossel · {len(images)} cards"
    elif ad.get("type") == "image":
        out["thumb_label"] = "imagem · estática"
    else:
        out["thumb_label"] = "anúncio"

    # rodando = active_since em "X dias" approximation (best-effort)
    out["running_days"] = _running_days(ad.get("active_since"))

    return out


def _normalize_insight(ins: dict) -> dict:
    """Converte **markdown bold** em <strong>HTML</strong> nos campos de texto."""
    out = dict(ins)
    text = out.get("text") or ""
    # **algo** -> <strong>algo</strong>
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    out["text"] = text
    return out


def _embed_image(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        mime, _ = mimetypes.guess_type(path.name)
        mime = mime or "image/jpeg"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


_PT_MONTHS = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}


def _running_days(active_since: str | None) -> str:
    """Tenta calcular dias rodando a partir do texto 'ativo desde'."""
    if not active_since:
        return ""
    cleaned = active_since.strip()

    # formato BR escrito por extenso: "25 de set. de 2025" / "25 de setembro de 2025"
    m = re.match(
        r"(\d{1,2})\s+de\s+([a-zçãáéíóú]+)\.?\s+de\s+(\d{4})",
        cleaned,
        flags=re.IGNORECASE,
    )
    if m:
        day, mon_word, year = m.group(1), m.group(2).lower()[:3], m.group(3)
        mon = _PT_MONTHS.get(mon_word)
        if mon:
            try:
                dt = datetime(int(year), mon, int(day))
                delta = (datetime.now() - dt).days
                if delta >= 0:
                    return f"{delta} dias"
            except Exception:
                pass

    # formatos numéricos
    formats = ["%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y"]
    m = re.search(r"\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}", cleaned)
    candidate = m.group(0) if m else cleaned
    for fmt in formats:
        try:
            dt = datetime.strptime(candidate, fmt)
            delta = (datetime.now() - dt).days
            if delta >= 0:
                return f"{delta} dias"
        except Exception:
            continue
    return cleaned


# ─────────────────────────────────────────────────────────────────
# MARKDOWN
# ─────────────────────────────────────────────────────────────────

def _render_markdown(page, ads, insights, patterns, recommendations) -> str:
    lines: list[str] = []
    lines.append(f"# Inteligência competitiva — {page.get('slug', '')}")
    lines.append("")
    lines.append(f"- URL: {page.get('url', '')}")
    lines.append(f"- Varredura: {page.get('scraped_at', '')}")
    lines.append(f"- Anúncios analisados: {page.get('total_ads', len(ads))}")
    lines.append("")

    if insights:
        lines.append("## Resumo executivo")
        lines.append("")
        for ins in insights:
            tag = ins.get("tag", "")
            text = re.sub(r"</?strong>", "**", ins.get("text", ""))
            lines.append(f"- **{tag}** — {text}")
        lines.append("")

    if patterns:
        lines.append("## Padrões criativos")
        lines.append("")
        for p in patterns:
            lines.append(f"### {p.get('title', '')}  ·  {p.get('freq', '')}")
            lines.append("")
            lines.append(p.get("desc", ""))
            lines.append("")
            for ex in p.get("examples", []):
                lines.append(f"- {ex}")
            lines.append("")

    if recommendations:
        lines.append("## Recomendações táticas")
        lines.append("")
        for i, r in enumerate(recommendations, start=1):
            prio = {"high": "alta", "med": "média", "low": "baixa"}.get(
                r.get("priority", ""), r.get("priority", "")
            )
            lines.append(f"### {i:02d}. {r.get('what', '')}  ·  prioridade {prio}")
            lines.append("")
            lines.append(r.get("why", ""))
            lines.append("")

    lines.append("## Anúncios")
    lines.append("")
    for ad in ads:
        lines.append(f"### ad {ad['idx']:03d} ({ad.get('type_label', '')})")
        if ad.get("library_id"):
            lines.append(f"- id: `{ad['library_id']}`")
        if ad.get("active_since"):
            lines.append(f"- ativo desde: {ad['active_since']}")
        if ad.get("hook"):
            lines.append(f"- hook: **{ad['hook']}**")
        if ad.get("copy"):
            lines.append(f"- copy: {ad['copy']}")
        if ad.get("cta_text"):
            lines.append(f"- CTA: {ad['cta_text']}")
        lines.append("")

    return "\n".join(lines)
