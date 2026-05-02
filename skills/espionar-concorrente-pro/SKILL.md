---
name: espionar-concorrente-full
description: Versão Mentoria da espionar-concorrente. Pega tudo da LITE (ativos da Facebook Ads Library) e adiciona análise IA — transcreve vídeos, descreve imagens, detecta padrões e gera HTML report navegável.
---

# Espionar Concorrente Full

Você é a skill **espionar-concorrente-full**. A skill **JÁ ESTÁ IMPLEMENTADA** em Python — você invoca via Bash, não precisa escrever código.

## Como invocar (instrução pro Claude)

Quando o usuário pedir algo como "espiona o concorrente X" ou "roda a skill espionar":

1. **Confirma 2 inputs** com o usuário se faltarem:
   - **Nome** (display label, ex: `Hyeser`, `Pedro Sobral`)
   - **URL da Facebook Ads Library** (precisa começar com `https://www.facebook.com/ads/library/...`)

2. **Roda este comando único** (Bash tool, em uma linha):
   ```bash
   cd /Users/isaacsantos/Documents/bravo-skills-pro/_drafts/espionar-concorrente-full && source .venv/bin/activate && python scripts/main.py --name "<NOME>" --no-headless --max-ads 10 '<URL>'
   ```

   Substitui `<NOME>` e `<URL>`. Aspas **simples** na URL (não duplas — `[ ]` quebram em zsh).
   Use `--max-ads 5` pra teste rápido, `--max-ads 10` default, `--max-ads 20` pra varredura completa.

3. **Aguarda o output** — o script imprime "✓ pronto em Xs" e o caminho do report.html. Pode demorar de 2 a 8 minutos dependendo do número de anúncios e dos vídeos. Considere rodar em background (Bash `run_in_background=true`) e usar Monitor pra detectar "✓ pronto" ou "✗" / "Traceback".

4. **Mostra ao usuário** o caminho final + sugere `open` pra abrir no navegador:
   ```
   open "<caminho>/report.html"
   ```

## Modos de re-execução (rerun)

Se algo deu errado na análise mas o scrape funcionou (ex: Gemini retornou JSON inválido, ou você quer re-rodar com prompt diferente), **não precisa rebaixar tudo**:

```bash
# Reaproveita transcriptions + descriptions já feitas, só refaz agregação Gemini + render.
# Custa centavos e leva 30s. É a opção certa em 90% dos retries.
python scripts/main.py --name "<NOME>" --rerun-only-aggregate --max-ads 10 '<URL>'

# Reaproveita só os assets baixados (vídeos/imagens). Refaz transcrição + descrição + agregação.
# Útil se trocou o prompt de transcrição/descrição. Custa o mesmo que análise nova.
python scripts/main.py --name "<NOME>" --rerun-only-analyze --max-ads 10 '<URL>'
```

A pasta de saída é detectada automaticamente do dia (`YYYY-MM-DD`); se não existe, cai pra mais recente do mesmo slug.

## O que a skill faz por baixo

A LITE baixa os ativos. A FULL **interpreta** os ativos.

> Esta skill **complementa** a LITE — não substitui. A LITE faz o scraping. A FULL roda a análise IA em cima do output da LITE.

A pipeline:
1. **Scrape** (`scrape.py`, Playwright) — varre a Ads Library, extrai metadata + URLs de mídia.
2. **Download** (`scrape.py`, httpx) — baixa imagens e vídeos pra `ad-XXX/`.
3. **Análise** (`analyze.py`, Gemini 2.5 Flash):
   - Transcreve cada vídeo via Files API → `ad-XXX/transcription.txt`
   - Descreve cada imagem via Vision → `ad-XXX/description.txt`
   - Agrega tudo num call estruturado (JSON mode) pra extrair insights / patterns / recommendations.
4. **Render** (`render.py`, Jinja2) — gera `report.html` (design self-contained), `insights.md` e `index.json`.

## Convenções importantes

- **Output:** `{OBSIDIAN_VAULT_PATH}/concorrentes/{slug}/{YYYY-MM-DD}/`
- **HTML report é self-contained:** CSS inline, vídeos referenciados localmente. Não precisa de internet pra abrir.
- **Insights.md:** resumo executivo pro gestor ler em 2 minutos no Obsidian. O `report.html` é pro deep dive.
- **Detecção de padrão funciona melhor com 10+ anúncios.** Com poucos ativos, os "padrões" detectados são ruído.
- **Estrutura idêntica entre concorrentes:** sempre `concorrentes/<slug>/<data>/` — facilita o `master` orquestrar.

## Setup

Veja `README.md` na pasta da skill.

Pré-requisito: nenhum (não depende mais da skill LITE estar instalada — o scrape é independente).

## Variáveis de ambiente

- `GEMINI_API_KEY` (obrigatório pra análise IA) — Gemini 2.5 Flash, audio + vision + agregação
- `OBSIDIAN_VAULT_PATH` (obrigatório) — pasta base de saída
- `PLAYWRIGHT_HEADLESS` (opcional, default `true`)
- `MAX_ADS` (opcional, default `20`)

## Limitações

- **Selectors da Ads Library mudam:** se o scrape vier vazio, atualize `FIND_AD_CARDS_JS` em `scripts/scrape.py` e/ou as regex de `LIBRARY_ID_RX` / `ACTIVE_SINCE_RX`.
- **Login wall:** em algumas regiões/horários a Ads Library exige login. Rode com `--no-headless` e logue manualmente.
- **Custo escala com ativos:** concorrente com 100 vídeos pode custar US$ 1–3 com Gemini Flash. Use `--max-ads N` pra limitar.
- **Não roda sem ads:** se a Ads Library não retornar nada (concorrente sem ads ativos), a FULL não tem o que analisar.
