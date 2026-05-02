"""
analyze.py — Gemini transcreve vídeos, descreve imagens, extrai padrões.

Funções públicas:
    analyze_all(ads, api_key) -> (ads, insights, patterns, recommendations)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

# google-genai (lib nova)
try:
    from google import genai
    from google.genai import types as genai_types
except ImportError as e:
    raise ImportError(
        "google-genai não instalado. Roda: pip install google-genai"
    ) from e


GEMINI_MODEL = "gemini-2.5-flash"

# ─────────────────────────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────────────────────────

PROMPT_TRANSCRIBE = """Transcreva o áudio deste vídeo de anúncio publicitário em português brasileiro.
Inclua todas as falas, narração e qualquer texto importante que apareça na tela.
Retorne APENAS o texto transcrito, sem comentários ou marcações de timestamp."""

PROMPT_DESCRIBE_IMAGE = """Descreva esta imagem de anúncio publicitário de forma objetiva e estruturada, em português, em até 6 linhas:
- Composição visual (cores, layout, tipografia)
- Elementos principais (pessoa, produto, ambiente)
- Texto visível na imagem (se houver)
- Estilo / mood (UGC, produzido, minimalista, etc)

Não interprete sentimentos do espectador. Não faça recomendações. Só descreva."""

PROMPT_AGGREGATE = """Você é um analista sênior de mídia paga. Recebeu o conjunto completo de anúncios ativos de UM concorrente da Facebook Ads Library, com copies, transcrições de vídeos e descrições visuais.

Sua tarefa: produzir um relatório estratégico em JSON estruturado, em português brasileiro.

DADOS DO CONCORRENTE:
{dados}

Retorne EXCLUSIVAMENTE um JSON válido (sem ```json, sem comentário) com este schema:

{{
  "insights": [
    {{"icon": "A", "tag": "ângulo dominante", "text": "Texto com <strong>palavras-chave</strong> em strong. Máx 2 frases."}},
    {{"icon": "H", "tag": "hooks recorrentes", "text": "..."}},
    {{"icon": "C", "tag": "CTAs mais usados", "text": "..."}},
    {{"icon": "P", "tag": "público-alvo aparente", "text": "..."}},
    {{"icon": "F", "tag": "formato vencedor", "text": "..."}},
    {{"icon": "$", "tag": "spend tier estimado", "text": "..."}}
  ],
  "patterns": [
    {{"title": "Hook confessional", "freq": "18 / 47", "desc": "Descrição em até 2 frases.", "examples": ["exemplo curto 1", "exemplo curto 2", "exemplo curto 3"]}},
    {{"title": "...", "freq": "X / Y", "desc": "...", "examples": ["..."]}}
  ],
  "recommendations": [
    {{"what": "Título da recomendação tática", "why": "Por que faz sentido, baseado no que vimos. Até 3 frases.", "priority": "high"}},
    {{"what": "...", "why": "...", "priority": "med"}},
    {{"what": "...", "why": "...", "priority": "low"}}
  ]
}}

REGRAS:
- 6 insights (sempre nessa ordem: A, H, C, P, F, $)
- 6 padrões criativos com freq no formato "N / total"
- 5 recomendações com priority em ["high", "med", "low"]
- Nos textos de insights, marque palavras-chave fortes com <strong>...</strong>
- Não invente números — se não souber, escreva "não inferido" ou estime com qualificador ("estimado", "~")
- JSON puro. NADA fora dele."""


# ─────────────────────────────────────────────────────────────────
# API PRINCIPAL
# ─────────────────────────────────────────────────────────────────

def analyze_all(
    ads: list[dict[str, Any]],
    *,
    api_key: str,
    out_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list, list, list]:
    """
    Para cada ad: transcreve vídeos + descreve imagens.
    Depois agrega tudo num único call pra Gemini extrair insights+padrões+recs.
    """
    client = genai.Client(api_key=api_key)
    total = len(ads)

    for i, ad in enumerate(ads, start=1):
        print(f"  · analisando ad {i}/{total} (idx={ad['idx']}, type={ad['type']}) ...")
        ad_dir = Path(ad["dir"])

        # ── TRANSCRIÇÕES ──────────────────────────────────────
        transcriptions: list[str] = []
        for vpath in ad.get("local_videos", []):
            try:
                txt = _transcribe_video(client, Path(vpath))
                transcriptions.append(txt)
                (ad_dir / "transcription.txt").write_text(txt, encoding="utf-8")
            except Exception as e:
                print(f"    ✗ erro transcrevendo {Path(vpath).name}: {e}")

        ad["transcriptions"] = transcriptions

        # ── DESCRIÇÕES VISUAIS ────────────────────────────────
        descriptions: list[str] = []
        for ipath in ad.get("local_images", []):
            try:
                desc = _describe_image(client, Path(ipath))
                descriptions.append(desc)
            except Exception as e:
                print(f"    ✗ erro descrevendo {Path(ipath).name}: {e}")

        ad["descriptions"] = descriptions
        if descriptions:
            (ad_dir / "description.txt").write_text(
                "\n\n---\n\n".join(descriptions), encoding="utf-8"
            )

        # atualiza meta.json com dados de IA
        meta_path = ad_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                meta["transcriptions"] = transcriptions
                meta["descriptions"] = descriptions
                meta_path.write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass

    # ── AGREGAÇÃO ─────────────────────────────────────────────
    print("  · agregando padrões com Gemini ...")
    insights, patterns, recommendations = _aggregate(client, ads, out_dir=out_dir)

    return ads, insights, patterns, recommendations


# ─────────────────────────────────────────────────────────────────
# HELPERS — Gemini
# ─────────────────────────────────────────────────────────────────

def _transcribe_video(client, video_path: Path) -> str:
    """
    Sobe o vídeo via Files API (necessário pra arquivos > inline limit) e
    chama o modelo pra transcrever.
    """
    f = client.files.upload(file=str(video_path))
    # espera processar
    for _ in range(60):
        try:
            f = client.files.get(name=f.name)
        except Exception:
            break
        state = getattr(f, "state", None)
        state_name = getattr(state, "name", str(state)) if state else ""
        if state_name in ("ACTIVE", "SUCCEEDED"):
            break
        if state_name in ("FAILED", "ERROR"):
            raise RuntimeError(f"upload falhou: {state_name}")
        time.sleep(2.0)

    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[f, PROMPT_TRANSCRIBE],
    )
    text = (resp.text or "").strip()

    # cleanup
    try:
        client.files.delete(name=f.name)
    except Exception:
        pass
    return text


def _describe_image(client, image_path: Path) -> str:
    """Descrição visual estruturada de uma imagem."""
    data = image_path.read_bytes()
    mime = "image/jpeg"
    suffix = image_path.suffix.lower()
    if suffix == ".png":
        mime = "image/png"
    elif suffix in (".webp",):
        mime = "image/webp"

    part = genai_types.Part.from_bytes(data=data, mime_type=mime)
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[part, PROMPT_DESCRIBE_IMAGE],
    )
    return (resp.text or "").strip()


def _aggregate(client, ads: list[dict], *, out_dir: Path | None = None) -> tuple[list, list, list]:
    """Manda tudo num prompt agregador pra extrair insights+padrões+recs."""
    payload_lines: list[str] = []
    for ad in ads:
        block = []
        block.append(f"### ad {ad['idx']:03d} ({ad.get('type', 'unknown')})")
        if ad.get("library_id"):
            block.append(f"id: {ad['library_id']}")
        if ad.get("active_since"):
            block.append(f"ativo desde: {ad['active_since']}")
        if ad.get("hook"):
            block.append(f"hook: {ad['hook']}")
        if ad.get("copy"):
            block.append(f"copy: {ad['copy']}")
        if ad.get("cta_text"):
            block.append(f"cta: {ad['cta_text']}")
        for n, t in enumerate(ad.get("transcriptions", []), start=1):
            block.append(f"transcrição vídeo {n}: {t[:1500]}")
        for n, d in enumerate(ad.get("descriptions", []), start=1):
            block.append(f"descrição img {n}: {d[:600]}")
        payload_lines.append("\n".join(block))

    payload = "\n\n".join(payload_lines)
    prompt = PROMPT_AGGREGATE.format(dados=payload)

    raw = ""
    parsed: dict | None = None
    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.3,
    )

    # até 3 tentativas: a 1ª com JSON mode, a 2ª pedindo ainda mais explicitamente
    # JSON, a 3ª recuperando JSON loose do texto bruto da resposta anterior.
    for attempt in range(1, 4):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt],
                config=config,
            )
            raw = (resp.text or "").strip()
        except Exception as e:
            print(f"    ✗ erro na chamada do Gemini (tentativa {attempt}): {e}")
            time.sleep(1.2 * attempt)
            continue

        parsed = _parse_json_loose(raw)
        if parsed and isinstance(parsed, dict):
            break

        print(f"    ⚠ JSON inválido na tentativa {attempt}/3; tentando de novo ...")
        time.sleep(0.8 * attempt)

    if out_dir is not None:
        try:
            (Path(out_dir) / "_aggregate-raw.txt").write_text(raw, encoding="utf-8")
        except Exception:
            pass

    if not parsed:
        print("    ✗ Gemini retornou JSON inválido após 3 tentativas. Resultado vazio.")
        return [], [], []

    insights = parsed.get("insights") or []
    patterns = parsed.get("patterns") or []
    recommendations = parsed.get("recommendations") or []
    return insights, patterns, recommendations


def _parse_json_loose(text: str) -> dict | None:
    """Tenta parsear JSON mesmo com cercas de ``` ou texto antes/depois."""
    if not text:
        return None
    # tira fences
    cleaned = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # tenta extrair primeiro {...} balanceado de ponta-a-ponta
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    # tenta cortar último objeto incompleto e fechar — JSON truncado
    if start >= 0:
        truncated = cleaned[start:]
        # remove última vírgula pendente + fecha braces
        for closing in ("}", "]}", "}]}"):
            try:
                return json.loads(re.sub(r",\s*$", "", truncated.rstrip()) + closing)
            except Exception:
                continue
    return None
