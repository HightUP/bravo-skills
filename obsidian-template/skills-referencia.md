# Referência rápida — Skills

Cola este arquivo aberto no Obsidian. Consulta enquanto comanda.

## Regra de ouro

Toda skill que age num cliente:
1. **Lê** `CLAUDE.md` + `contexto.md` + últimas 5-10 entradas de `historico.md` do cliente.
2. **Age** (sobe campanha, manda relatório, etc).
3. **Registra** nova entrada no `historico.md` do cliente.
4. **Atualiza** o `CLAUDE.md` do cliente se status mudou.

---

## subir-campanha
Sobe campanha via Meta Ads API a partir de um briefing.

```
sobe a campanha do cliente <nome> com o criativo <nome ou path> e orçamento R$<valor>
```

- **Lê:** `clientes/<nome>/CLAUDE.md`, `contexto.md`, `historico.md`, `criativos/<criativo>.md`
- **Age:** chama Meta Ads API, cria campanha + conjunto + anúncio
- **Registra no histórico:** `[data] — Subida de campanha: <objetivo>` com público, orçamento, criativo
- **Atualiza CLAUDE.md** se for primeira campanha ativa

## relatorio-cliente
Gera relatório narrativo e envia via WhatsApp.

```
manda o relatório de hoje do <cliente> pro <destinatário>
```

- **Lê:** contexto + histórico + dados Meta API últimos 7d
- **Cria:** `clientes/<nome>/relatorios/<data>.md` (texto enviado + resposta quando vier)
- **Envia:** WhatsApp via Evolution Go (skill jarvis)
- **Registra no histórico:** `[data] — Relatório enviado` com link pro arquivo

## vigia-24h
Watcher de background. Avisa quando métrica passa do limite.

```
vigia a conta da <cliente>, me avisa se o cpa passar de R$<valor>
```

- Roda em loop (cron job ou processo background)
- Notifica via Evolution Go (WhatsApp do gestor)
- **Registra no histórico** quando dispara: `[data] — Alerta: CPA passou R$X`

## diagnostico-conta
Análise estruturada com olho de sênior.

```
diagnóstico da conta do <cliente>
```

- **Lê:** tudo do cliente (CLAUDE, contexto, histórico inteiro, criativos, relatórios) + dados Meta API
- **Cria:** `clientes/<nome>/diagnosticos/<data>.md`
- **Registra no histórico:** `[data] — Diagnóstico gerado`

## espionar-concorrente
Baixa criativos da Library do FB e organiza em pasta dedicada.

```
espiona os criativos do <concorrente>
```

- **Cria:** `concorrentes/<nome>/` com criativos baixados (separados por formato)
- **Gera HTML report** mostrando criativos, formato, frequência (quando FB mostra)

## skill-master
Interpreta linguagem natural e roteia pra skill certa.

```
qualquer comando em português — ele decide o que rodar
```

## jarvis
Mensagem WhatsApp via Evolution Go a partir do terminal.

```
manda no whatsapp do <pessoa>: <mensagem>
```

Útil dentro de outras skills (notificação, relatório, alerta).
