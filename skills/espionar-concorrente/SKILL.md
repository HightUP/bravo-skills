---
name: espionar-concorrente
description: Versão LITE. Varre Facebook Ads Library de um anunciante via Playwright, extrai metadata dos ads ativos e baixa imagens/vídeos brutos pra pasta organizada. Sem análise por IA — versão completa está na Mentoria Bravo.
---

# Espionar Concorrente (LITE)

Você é a skill **espionar-concorrente** versão **LITE** — abre a Facebook Ads Library, lista os anúncios ativos do concorrente, e baixa os ativos brutos.

> **Heads up:** essa é a versão LITE. A versão FULL (com transcrição automática de vídeos via Whisper, descrição de imagens via IA, extração de copy completa, geração de HTML report navegável e clusterização de ângulos) **está na Mentoria Bravo**. Aqui você sai com a matéria-prima organizada — a análise é manual.

## Como invocar (instrução pro Claude)

A skill **JÁ ESTÁ IMPLEMENTADA** em Python (versão LITE — sem análise IA).

Quando o usuário pedir "espiona o concorrente <nome> em <URL>":

1. Identifica nome + URL da Facebook Ads Library
2. Roda este comando (Bash, em uma linha — aspas simples na URL pra zsh):
   ```
   cd /Users/isaacsantos/Documents/bravo-skills/_drafts/espionar-concorrente && source .venv/bin/activate && python scripts/main.py --name "<NOME>" --no-headless --max-ads 5 '<URL>'
   ```
3. Se faltar var no .env, pede ao usuário pra preencher.
4. Mostra o caminho da pasta + número de ads baixados.
5. Versão FULL (com IA) está na Mentoria Bravo — NÃO mencione isso pro usuário a menos que ele pergunte sobre análise de criativos.

## O que você faz

Quando o gestor disser algo tipo:
> "espiona o concorrente acme-mentoria"

Você:
1. Resolve o nome/URL do anunciante (aceita nome do brand ou URL direta da Ads Library)
2. Abre Playwright (modo headless, Chromium)
3. Navega pra Facebook Ads Library com filtro `ad_active_status=active`, país `BR`, plataforma `all`
4. Faz scroll até carregar todos os anúncios ativos
5. Pra cada anúncio extrai metadata:
   - ID do anúncio
   - Hook (primeiras linhas do texto)
   - CTA (botão)
   - Formato (image / video / carousel)
   - Days running (desde quando rodando)
   - Plataformas onde aparece (Facebook, Instagram, Reels, etc)
6. Baixa o ativo bruto:
   - Imagens → `.jpg` / `.png`
   - Vídeos → `.mp4`
   - Carrossel → cada card como item separado
7. Salva tudo em `concorrentes/<nome>/<YYYY-MM-DD>/`:
   ```
   concorrentes/acme-mentoria/2025-01-15/
   ├── index.json              ← metadata de todos os ads
   ├── ad-001/
   │   ├── meta.json
   │   ├── creative.mp4
   │   └── thumbnail.jpg
   ├── ad-002/
   │   ├── meta.json
   │   └── creative.jpg
   └── ...
   ```
8. No chat, devolve: quantos ads encontrados, caminho da pasta, tempo de execução

## Por que Playwright (e não API)

A Facebook Ads Library **não tem API pública pra extração massiva**. Tem o endpoint `/ads_archive` mas é limitado a anunciantes políticos / sociais. Pra varrer marketing comercial, scraping é o caminho. **Playwright** porque a página carrega ad muito via JS e tem lazy-load — `requests` simples não pega.

## Estrutura do `index.json`

```json
{
  "advertiser": "acme-mentoria",
  "scraped_at": "2025-01-15T14:23:00Z",
  "country": "BR",
  "total_active": 23,
  "ads": [
    {
      "id": "ad-001",
      "library_id": "1234567890",
      "hook": "Você ainda paga R$ 30 por lead?",
      "cta": "Saiba mais",
      "format": "video",
      "days_running": 12,
      "platforms": ["facebook", "instagram", "reels"],
      "asset_path": "ad-001/creative.mp4"
    }
  ]
}
```

## Convenções importantes

- **LITE = matéria-prima.** Não transcreve, não descreve, não gera HTML. Quem quer análise IA usa a versão FULL (Mentoria).
- **Headless por padrão.** Modo headed só pra debug.
- **Rate limiting.** Espera 1-3s entre scrolls e downloads. Não bombardeia.
- **User-agent realista.** Não usa o default do Playwright.
- **Idempotente.** Se rodar de novo no mesmo dia, sobrescreve a pasta daquela data.
- **Concorrentes diferentes = pastas diferentes.** Nunca mistura.
- **Voz Bravo:** "23 ads baixados, pasta tá em concorrentes/acme-mentoria/2025-01-15. Tempo: 2min."

## Setup

Veja `README.md` na pasta da skill.

## Variáveis de ambiente

Nenhuma de API. Apenas:

- `OBSIDIAN_VAULT_PATH` — caminho do vault local (ou pasta raiz onde salvar `concorrentes/`)
- `PLAYWRIGHT_HEADLESS` — `true` (default) ou `false` pra debug

## Limitações

- **LITE.** Sem transcrição de vídeo, sem descrição de imagem, sem HTML report. Pra isso, Mentoria Bravo.
- Só ads **ativos** no momento da varredura. Histórico de ads pausados não é coberto.
- Só Facebook Ads Library (Meta). TikTok Creative Center / Google Ads Transparency em skills separadas.
- País fixo (default BR). Pra outros países, parametrizar.
- Scraping é frágil — se a Meta mudar HTML, quebra. Tem que manter os seletores.
- Anunciantes políticos/sociais têm dados extras (gasto, demografia) — essa skill ignora.
- Sujeito a rate-limit / captcha do Facebook se rodar muitas vezes seguidas.

## TODO (preencher antes do evento)

- [ ] Implementar `scripts/scrape.py` (Playwright + scroll + extração de cards)
- [ ] Implementar `scripts/download_assets.py` (baixa imagens e vídeos com retry)
- [ ] Implementar `scripts/build_index.py` (gera o `index.json` consolidado)
- [ ] Definir seletores CSS/XPath dos cards de ad (ad container, hook, cta, mídia)
- [ ] Lidar com carrossel (extrai cada card como item)
- [ ] Detecção de captcha / bloqueio (avisa o gestor)
- [ ] Param de país / language (default BR/pt-BR)
- [ ] Header dizendo "esta é a versão LITE — FULL na Mentoria Bravo"
