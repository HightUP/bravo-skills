"""
vault — leitura do vault Obsidian (clientes/<nome>/).

Responsável por:
  - localizar a pasta do cliente
  - ler contexto.md e historico.md
  - escrever backup do JSON da estrutura antes de subir
  - acrescentar entrada em historico.md depois de subir

Não faz nenhuma chamada de API. Apenas filesystem.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional


def slugify(text: str) -> str:
    """Normaliza pra slug seguro (lowercase, hífen, sem acento)."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")[:60]


def find_client_dir(vault_path: Path, client_name: str) -> Optional[Path]:
    """
    Procura a pasta do cliente em <vault>/clientes/.

    Tenta nessa ordem:
      1. match exato pelo nome dado
      2. match exato pelo slug
      3. match case-insensitive
      4. match por slug case-insensitive

    Retorna o Path se achar, None se não.
    """
    clients_root = vault_path / "clientes"
    if not clients_root.is_dir():
        return None

    target = client_name.strip()
    target_slug = slugify(target)

    # 1. exato
    direct = clients_root / target
    if direct.is_dir():
        return direct

    # 2. slug exato
    slug_path = clients_root / target_slug
    if slug_path.is_dir():
        return slug_path

    # 3 + 4. varre e compara case-insensitive
    target_lower = target.lower()
    for child in clients_root.iterdir():
        if not child.is_dir():
            continue
        if child.name.lower() == target_lower:
            return child
        if slugify(child.name) == target_slug:
            return child

    return None


def read_context(client_dir: Path) -> str:
    """Lê contexto.md do cliente. Retorna string vazia se não existir."""
    p = client_dir / "contexto.md"
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def read_historico(client_dir: Path) -> str:
    """Lê historico.md do cliente. Retorna string vazia se não existir."""
    p = client_dir / "historico.md"
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def save_structure_backup(client_dir: Path, structure: dict) -> Path:
    """
    Salva o JSON da estrutura em clientes/<nome>/campanhas/YYYY-MM-DD-HH-MM.json
    antes de subir. Retorna o Path do arquivo criado.
    """
    campanhas_dir = client_dir / "campanhas"
    campanhas_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    out = campanhas_dir / f"{stamp}.json"
    # se já existir (rodou 2x no mesmo minuto), adiciona segundos
    if out.exists():
        stamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        out = campanhas_dir / f"{stamp}.json"
    out.write_text(
        json.dumps(structure, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out


def append_historico(client_dir: Path, entry: str) -> Path:
    """
    Acrescenta uma entrada no historico.md do cliente.
    Cria o arquivo se não existir. Retorna o Path do arquivo.
    """
    p = client_dir / "historico.md"
    header_needed = not p.is_file()
    with p.open("a", encoding="utf-8") as f:
        if header_needed:
            f.write("# Histórico\n\n")
        f.write(entry)
        if not entry.endswith("\n"):
            f.write("\n")
    return p
