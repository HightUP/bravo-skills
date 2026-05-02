# Clientes

Cada subpasta = um cliente. Nome em kebab-case (ex: `acme-ecommerce`).

## Estrutura por cliente

```
nome-do-cliente/
├── CLAUDE.md          (índice rápido + status atual + avisos)
├── contexto.md        (negócio, público, objetivos — estático, muda raro)
├── historico.md       (log append-only: tudo que rolou — subidas, ajustes, decisões)
├── criativos/         (criativos versionados, um arquivo por criativo)
│   └── CLAUDE.md
└── relatorios/        (relatórios enviados, um arquivo por envio)
    └── CLAUDE.md
```

**Importante:** não existe pasta `campanhas/`. Subidas, pausas, mudanças de orçamento, decisões — tudo vai pro `historico.md` como entrada cronológica. Mais simples, menos burocracia.

## Como achar um cliente

Procure pela pasta com nome em kebab-case do cliente. Se não encontrar, pergunte ao usuário antes de criar.

## Para criar novo cliente

Duplique `_template-cliente/`, renomeie e preencha:
1. `contexto.md` (sobre o negócio)
2. `CLAUDE.md` raiz do cliente (status atual)
3. `historico.md` começa vazio — vai sendo populado a cada ação.

## Cliente exemplo

`exemplo-acme/` está populado como referência. Use pra entender o padrão.
