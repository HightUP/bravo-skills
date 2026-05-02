# espionar-concorrente (LITE)

Skill que varre a Facebook Ads Library de um concorrente e baixa os ativos brutos.

> **Versão LITE.** Sem transcrição, sem descrição IA, sem HTML report. A versão FULL com tudo isso está na **Mentoria Bravo**.

## Instalação

1. Copia esta pasta pro seu diretório de skills do Claude Code:
   ```bash
   cp -r espionar-concorrente ~/.claude/skills/
   ```

2. Configura as variáveis no `.env` do seu projeto:
   ```env
   OBSIDIAN_VAULT_PATH=/Users/voce/Documents/obsidian-bravo
   PLAYWRIGHT_HEADLESS=true
   ```

3. Instala dependências:
   ```bash
   pip install playwright python-dotenv
   playwright install chromium
   ```

## Uso

No Claude Code:
```
espiona o concorrente acme-mentoria
```

Aceita também URL direta:
```
espiona https://www.facebook.com/ads/library/?...&view_all_page_id=123456
```

Saída:
```
concorrentes/acme-mentoria/2025-01-15/
├── index.json
├── ad-001/
├── ad-002/
└── ...
```

## Como funciona

Usa **Playwright** (Chromium headless) pra navegar na Ads Library porque a Meta não expõe API pública pra extração massiva de ads comerciais. Scraping com rate-limit baixo (1-3s entre ações) pra não tomar bloqueio.

## Roadmap (LITE → FULL)

A versão **FULL** (Mentoria Bravo) adiciona:

- [ ] Transcrição automática dos vídeos via Whisper
- [ ] Descrição de imagens via Claude Vision
- [ ] Extração de copy completa (não só hook)
- [ ] Clusterização automática por ângulo / promessa
- [ ] HTML report navegável com filtros
- [ ] Diff entre varreduras ("o que entrou / saiu desde a última semana")
- [ ] Suporte a TikTok Creative Center
- [ ] Suporte a Google Ads Transparency Center
- [ ] Modo "alerta": me avisa quando esse concorrente subir ad novo

## Notas importantes

- Scraper depende dos seletores HTML da Meta. Se a Meta mexer, a skill quebra — tem que atualizar.
- Roda em IP residencial, não datacenter, pra reduzir chance de bloqueio.
- Não use pra fins ilegais ou contra os ToS da Meta. É pesquisa de mercado, não pirataria.
