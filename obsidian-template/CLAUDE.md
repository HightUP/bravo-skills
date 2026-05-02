# Vault Bravo — Memória da Operação

Este vault Obsidian é a **memória viva** da operação de tráfego pago.
Cada cliente, criativo, relatório e decisão vira nota linkada.

O Claude Code lê este arquivo automaticamente quando aberto na pasta. Use como índice mestre.

## Estrutura

```
obsidian-vault/
├── CLAUDE.md                       (este arquivo — índice mestre)
├── clientes/                       (uma subpasta por cliente)
│   ├── CLAUDE.md                   (índice de clientes)
│   ├── _template-cliente/          (template — duplique pra criar novo)
│   └── exemplo-acme/               (cliente preenchido como referência)
├── operacao/                       (notas gerais — playbooks, padrões)
│   └── CLAUDE.md
└── skills-referencia.md            (referência rápida das skills)
```

## Estrutura interna de cada cliente

```
nome-do-cliente/
├── CLAUDE.md          (status atual + avisos antes de agir)
├── contexto.md        (negócio — estático)
├── historico.md       (log append-only: subidas, ajustes, decisões, alertas)
├── criativos/         (um arquivo por criativo)
└── relatorios/        (um arquivo por envio)
```

**Importante:** não existe pasta `campanhas/`. Toda mudança operacional (subida, ajuste, pausa, decisão) é registrada como entrada cronológica em `historico.md`. Skills devem **sempre** registrar no histórico ao agir.

## Convenções

- **Nomes de arquivo:** kebab-case (`relatorio-cliente-acme.md`).
- **Datas:** ISO `YYYY-MM-DD` (`2026-04-30.md`).
- **Links:** wiki-links do Obsidian `[[clientes/exemplo-acme/CLAUDE]]`.
- **Cada pasta tem seu próprio `CLAUDE.md`** explicando o que vai dentro.

## Regra de ouro pras skills

**Antes de agir** em qualquer cliente:
1. Leia o `CLAUDE.md` da pasta dele (status + avisos).
2. Leia o `contexto.md` raiz (sobre o negócio).
3. Leia as últimas 5–10 entradas do `historico.md`.

**Depois de agir** em qualquer cliente:
- Registra nova entrada no `historico.md` no topo, com data/hora/tipo/descrição.
- Atualize o snapshot do `CLAUDE.md` se mudou status (CPA, ROAS, campanhas ativas).

Nunca aja às cegas. Nunca esqueça de registrar.
