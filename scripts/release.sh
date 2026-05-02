#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────
# release.sh — move 1 skill de _drafts/ pra skills/, commita e pusha
# ────────────────────────────────────────────────────────────
# uso: ./scripts/release.sh <nome-da-skill>
# ex:  ./scripts/release.sh subir-campanha
# ────────────────────────────────────────────────────────────

set -e

if [ -z "$1" ]; then
  echo "uso: $0 <nome-da-skill>"
  echo ""
  echo "skills em _drafts/:"
  ls -1 _drafts/ 2>/dev/null | sed 's/^/  - /' || echo "  (nenhuma)"
  exit 1
fi

SKILL="$1"
SRC="_drafts/$SKILL"
DEST="skills/$SKILL"

# valida
if [ ! -d "$SRC" ]; then
  echo "✗ skill não encontrada em $SRC"
  echo ""
  echo "skills disponíveis em _drafts/:"
  ls -1 _drafts/ 2>/dev/null | sed 's/^/  - /' || echo "  (nenhuma)"
  exit 1
fi

if [ -d "$DEST" ]; then
  echo "✗ $DEST já existe — skill já foi liberada"
  exit 1
fi

# move
echo "→ movendo $SRC → $DEST"
mv "$SRC" "$DEST"

# commit + push
echo "→ commit + push"
git add "$DEST"
git commit -m "release: $SKILL"
git push origin main

echo ""
echo "✓ skill '$SKILL' liberada"
echo "  https://github.com/euisaacsantos/bravo-skills/tree/main/skills/$SKILL"
