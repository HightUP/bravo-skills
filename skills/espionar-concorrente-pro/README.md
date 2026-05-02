# espionar-concorrente-full

Versão Mentoria da `espionar-concorrente`. Faz tudo da LITE (scrape + download dos ativos da Facebook Ads Library) **e adiciona análise IA** — transcreve vídeos, descreve imagens, detecta padrões e gera HTML report navegável.

> A versão LITE do repo público para de scrape. A FULL pega o output da varredura, manda pra Gemini, **interpreta** e devolve um relatório estratégico.

---

## Pré-requisitos

- **Python 3.11+**
- **Chromium** via Playwright (passo do setup abaixo)
- **GEMINI_API_KEY** — pega em [aistudio.google.com](https://aistudio.google.com/) (free tier serve)
- **OBSIDIAN_VAULT_PATH** — caminho absoluto onde a skill vai cuspir o output

---

## Setup

```bash
cd <pasta-da-skill>

# 1. dependências Python
pip install -r scripts/requirements.txt

# 2. browser do Playwright
playwright install chromium

# 3. variáveis de ambiente
cp .env.example .env
# edita .env e preenche GEMINI_API_KEY + OBSIDIAN_VAULT_PATH
```

---

## Como rodar

A skill é um script Python. Você passa a URL da Ads Library do concorrente:

```bash
python scripts/main.py "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=BR&is_targeted_country=false&media_type=all&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&source=fb-logo&view_all_page_id=113789661710458"
```

### Flags úteis

```bash
# debugar com browser visível
python scripts/main.py "<url>" --no-headless

# limitar a 5 anúncios (mais rápido / mais barato)
python scripts/main.py "<url>" --max-ads 5

# pular a parte de IA (só baixa os ativos)
python scripts/main.py "<url>" --skip-analyze

# sobrescrever pasta de saída sem mexer no .env
python scripts/main.py "<url>" --output-base /tmp/teste

# nomear o concorrente (vira o título do report e o slug da pasta)
python scripts/main.py --name "Pedro Sobral" "<url>"
```

### Re-execução (sem rebaixar tudo)

Se a análise IA deu errado (ex: Gemini retornou JSON ruim) ou você quer re-renderizar com prompt diferente:

```bash
# Reusa transcrições + descrições já feitas; só refaz a agregação Gemini + render.
# Mais barato e mais rápido (≈30s). Use isso em 90% dos retries.
python scripts/main.py --name "<NOME>" --rerun-only-aggregate "<url>"

# Reusa só os assets baixados (vídeos/imagens). Refaz transcrição + descrição + agregação + render.
# Útil quando você muda os prompts de transcrição/descrição.
python scripts/main.py --name "<NOME>" --rerun-only-analyze "<url>"
```

A pasta detectada é a do dia atual (`YYYY-MM-DD`); se não existir, cai pra mais recente do mesmo slug.

---

## O que sai

```
{OBSIDIAN_VAULT_PATH}/concorrentes/{slug}/{YYYY-MM-DD}/
├── report.html              ← navegável, abre no browser, self-contained (CSS inline)
├── insights.md              ← versão markdown pra Obsidian
├── index.json               ← metadata estruturada (todos os ads + insights)
├── ad-001/
│   ├── meta.json            ← hook, copy, cta, library_id, urls
│   ├── image-1.jpg
│   ├── image-2.jpg
│   ├── video-1.mp4
│   ├── transcription.txt    ← se vídeo
│   └── description.txt      ← descrição visual da Gemini
├── ad-002/...
└── ad-NNN/...
```

O `slug` é derivado da URL:
- `view_all_page_id=XXX` → `page-XXX`
- `search_terms=foo` → `term-foo`
- fallback → `intel-YYYYMMDD-HHMMSS`

---

## Variáveis de ambiente

| nome | obrigatório | default | descrição |
|---|---|---|---|
| `GEMINI_API_KEY` | sim (pra IA) | — | API key do Google AI Studio |
| `OBSIDIAN_VAULT_PATH` | sim | — | pasta base de saída |
| `PLAYWRIGHT_HEADLESS` | não | `true` | `false` mostra o browser |
| `MAX_ADS` | não | `20` | limite de cards processados |

---

## Custo aproximado

Gemini 2.5 Flash, ~20 anúncios mistos (com vídeos curtos e imagens):

| chamada | preço aprox |
|---|---|
| Transcrição de vídeos | US$ 0,05 – 0,30 |
| Descrição de imagens | US$ 0,02 – 0,10 |
| Agregação final | US$ 0,01 – 0,05 |
| **Total** | **~ US$ 0,10 – 0,50** |

Use `--max-ads N` se quiser limitar mais.

---

## Limitações conhecidas

- **Selectors da Ads Library mudam:** o Facebook redesenha esse produto com frequência. Se o scrape vier vazio, atualize `AD_CARD_SELECTORS` em `scripts/scrape.py` e/ou as regex de "active_since" / "library_id".
- **Login wall:** em algumas regiões/horários a Ads Library exige login mesmo pra biblioteca pública. Sem login automático — rode com `--no-headless` e logue manualmente uma vez.
- **Vídeos longos:** Gemini Files API aceita vídeo grande mas tem timeout no upload. Vídeos > 100MB podem falhar (raro em ads).
- **Detecção de padrão funciona melhor com 10+ anúncios.** Com poucos ativos os "padrões" detectados são ruído.
- **Stealth básico:** sem `playwright-stealth`. Se o Facebook bloquear, considere adicionar.
- **Self-contained = arquivo grande:** o `report.html` embute as imagens em base64 — pode ficar 5-30 MB dependendo do nº de ads.

---

## Estrutura do código

```
scripts/
├── main.py                  ← CLI orquestrador
├── scrape.py                ← Playwright + httpx
├── analyze.py               ← google-genai (Gemini 2.5 Flash)
├── render.py                ← Jinja2 → HTML/MD/JSON
├── templates/
│   └── report.html.j2       ← template do report (design idêntico ao espionar-html-report)
└── requirements.txt
```

---

## Roadmap

- [ ] Cache por hash de arquivo (não retranscrever vídeo já processado)
- [x] Modo `--rerun-only-aggregate` (reaproveita transcrições, refaz só agregação)
- [x] Modo `--rerun-only-analyze` (reaproveita assets, refaz transcrição + agregação)
- [ ] Comparação cross-concorrente (qual ângulo é exclusivo de cada um)
- [ ] Modo cron: roda 1x por semana, gera diff dos ativos novos
- [ ] Fallback OpenAI (Whisper + GPT-4o vision)
