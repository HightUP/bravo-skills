# subir-campanha

Skill que sobe campanha no Meta Ads via 1 frase no Claude Code.

## Instalação

1. Copia esta pasta pro seu diretório de skills do Claude Code:
   ```bash
   cp -r subir-campanha ~/.claude/skills/
   ```

2. Configura as variáveis no `.env` do seu projeto:
   ```env
   META_ACCESS_TOKEN=EAAxxxx...
   META_AD_ACCOUNT_ID=act_1234567890
   OBSIDIAN_VAULT_PATH=/Users/voce/Documents/obsidian-bravo
   ```

3. Instala dependências Python (se for usar `scripts/upload.py`):
   ```bash
   pip install requests python-dotenv
   ```

## Uso

No Claude Code:
```
sobe campanha do acme com 500 reais em ABO
```

A skill vai puxar o contexto do cliente `acme`, perguntar o que falta e montar a campanha.

## Como obter o token Meta

1. [developers.facebook.com](https://developers.facebook.com) → criar app
2. Marketing API → gerar token long-lived com permissão `ads_management`
3. Pega o `act_id` em [adsmanager.facebook.com](https://adsmanager.facebook.com)

## Roadmap

- [ ] Suporte a CBO além de ABO
- [ ] Modo dry-run com preview
- [ ] Geração automática de variações de conjunto
