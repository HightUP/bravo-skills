---
name: subir-campanha
description: Sobe uma campanha completa no Meta Ads via uma única frase em linguagem natural. Cria estrutura, conjunto, anúncio, configura segmentação e orçamento.
---

# Subir Campanha

Você é a skill **subir-campanha**. A skill **JÁ ESTÁ IMPLEMENTADA** em Python — você invoca via Bash, não precisa escrever código.

## Como invocar (instrução pro Claude)

Quando o usuário pedir algo como "sobe campanha do <cliente> com <budget>" ou similar:

1. **Identifica os 4 inputs** com o usuário (peça os que faltarem):
   - **Cliente** (nome da pasta em `clientes/<nome>/`, ex: `acme`, `joao-silva`)
   - **Budget** diário em reais (ex: `500`)
   - **Objetivo** — `CONVERSIONS`, `TRAFFIC` ou `LEADS` (aceita `CONV`/`TRAF` como atalho)
   - **Modo** — `--abo` (orçamento por conjunto, default) ou `--cbo` (orçamento na campanha)

2. **Sempre roda primeiro com `--dry-run`** pra mostrar a estrutura. Comando único (Bash, em uma linha):
   ```bash
   cd /Users/isaacsantos/Documents/bravo-skills/_drafts/subir-campanha && source .venv/bin/activate && python scripts/main.py --client "<nome>" --budget <valor> --objetivo <CONVERSIONS|TRAFFIC|LEADS> --abo --dry-run
   ```

3. **Se imprimir "✗ Variáveis ausentes no .env"**, peça ao usuário pra preencher e tenta de novo. O .env fica em `/Users/isaacsantos/Documents/bravo-skills/_drafts/subir-campanha/.env`.

4. **Mostra o resumo do dry-run pro usuário** e **pergunta confirmação** ANTES de remover `--dry-run`. Algo como: "vou criar essa campanha PAUSED, posso seguir?"

5. **Após confirmação**, roda o mesmo comando **sem `--dry-run`**. A campanha sai PAUSED — usuário ativa manualmente no Ads Manager.

6. **Mostra o link do Ads Manager** (impresso no final) pro usuário revisar.

## O que você faz

Quando o gestor disser algo tipo:
> "sobe campanha do acme com 500 reais em ABO"

Você:
1. Identifica o cliente (`acme`) no vault Obsidian (`clientes/acme/`)
2. Lê o histórico do cliente (criativos que rodaram, públicos, ângulos)
3. Pergunta o que falta: objetivo (CONVERSIONS / TRAFFIC / LEADS), público (frio/morno/quente), criativos (quais usar)
4. Monta a estrutura: 1 campanha (ABO ou CBO) + 1-3 conjuntos + 1-3 anúncios
5. Sobe via Meta Marketing API (modo `PAUSED` por segurança)
6. Confirma com link da Ads Manager
7. Atualiza `historico.md` do cliente

## Convenções importantes

- **Sempre subir PAUSED** — gestor revisa e ativa manualmente
- **Nomenclatura padrão Bravo:**
  ```
  Campanha: [Cliente] · [Objetivo] · [Data]
  Conjunto: [Público] · [Idade] · [Localização]
  Anúncio: [Criativo-ID] · [Hook]
  ```
- **Sempre confirmar antes de gastar:** mostrar resumo (orçamento total, públicos, criativos) antes de subir
- **Modo dry-run primeiro:** se for primeira vez, mostrar JSON da estrutura sem subir

## Setup

Veja `README.md` na pasta da skill.

## Variáveis de ambiente

- `META_ACCESS_TOKEN` — token long-lived com `ads_management`
- `META_AD_ACCOUNT_ID` — conta de anúncios (formato `act_XXX`)
- `OBSIDIAN_VAULT_PATH` — caminho do vault local

## Limitações

- Só Meta Ads por enquanto (Google Ads em outra skill futura)
- Não cria criativos novos — usa os que já existem no vault do cliente (precisa do `creative_id`)
- Validação de público é feita via Audience Insights, não cria custom audience
- Targeting default é genérico (BR, 25-55, feed/story) — gestor refina no Ads Manager ou edita o JSON antes de subir
- Sem `creative_id` preenchido, o anúncio é pulado mas a campanha + conjunto sobem (gestor anexa criativo no Ads Manager)

## TODO (preencher antes do evento)

- [x] Implementar `scripts/main.py` com chamadas à Marketing API
- [x] Ler `clientes/<nome>/contexto.md` pra puxar contexto do cliente
- [x] Atualização automática do `historico.md`
- [x] Modo `--dry-run` com preview JSON
- [x] Backup do JSON da estrutura em `clientes/<nome>/campanhas/`
- [ ] Templates de campanha por objetivo (`templates/conversions.json`, etc)
- [ ] Validação de criativos (formato, dimensões, política)
- [ ] Resolução automática de `creative_id` a partir do contexto.md
