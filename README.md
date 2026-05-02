# Bravo Skills

Skills de **Claude Code** pra gestores de tráfego. Distribuídas durante a **Imersão Bravo**.

> Este repo **cresce ao vivo durante o evento** — cada skill é liberada após o bloco que a apresentou.

## O que é

Cada pasta em `skills/` é uma skill pronta pra usar com o Claude Code. Você instala e roda comandos no seu terminal pra automatizar tarefas do dia a dia: subir campanha, gerar relatório, monitorar conta, diagnosticar performance, espionar concorrente.

## Como instalar uma skill

```bash
git clone https://github.com/euisaacsantos/bravo-skills.git
cd bravo-skills/skills/<nome-da-skill>
# leia o README dentro de cada skill
```

Cada skill tem seu próprio `README.md` com instruções específicas.

## Skills disponíveis

| Skill | O que faz | Status |
|---|---|---|
| `subir-campanha` | Sobe campanha completa no Meta Ads via 1 frase | 🔒 |
| `relator` | Gera relatório narrativo no WhatsApp do cliente | 🔒 |
| `vigia-24h` | Monitora contas 24/7 e alerta no WhatsApp | 🔒 |
| `diagnostico-conta` | Auditoria automatizada da conta | 🔒 |
| `espionar-concorrente` | Baixa ativos da Facebook Ads Library de concorrentes | 🔒 |

🔒 = ainda não liberada · ✓ = disponível no repo

## Versão Pro (Mentoria Bravo)

Quem entra na **[Mentoria Bravo](https://areadebravo.com.br/mentoria)** ganha acesso a:
- `master` — skill orquestradora que roda a rotina semanal completa
- `jarvis` — interface WhatsApp via Evolution API (comanda tudo por voz/texto)
- `espionar-concorrente-full` — versão completa: transcreve vídeos, descreve imagens, gera HTML report

## Licença

Uso livre pra os participantes da imersão. Não redistribuir o conteúdo desse repo sem permissão.
