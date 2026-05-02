#!/usr/bin/env python3
"""
relator — orquestrador CLI

Uso:
    python main.py --client acme --to joao
    python main.py --client acme --to 5511999998888 --days 14
    python main.py --client acme --to 120363XXXXXXXXXX@g.us   (grupo WhatsApp)
    python main.py --client acme --to joao --preview
    python main.py --all-clients --to joao                    (todos os clientes)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import meta_api  # noqa: E402
import narrative  # noqa: E402
import vault  # noqa: E402
import evo_go  # noqa: E402


REQUIRED_ENV = {
    "META_ACCESS_TOKEN": "Token Meta com ads_read (developers.facebook.com)",
    "META_AD_ACCOUNT_ID": "Conta de anúncios (act_XXXX)",
    "OBSIDIAN_VAULT_PATH": "Caminho absoluto do vault (sem / no final)",
    "EVO_API_URL": "URL da Evo Go com https://, sem / no final",
    "EVO_API_KEY": "apikey da instância Evo Go (UUID)",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="relator",
        description="Gera relatório narrativo dos últimos N dias e manda no WhatsApp via Evo Go.",
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--client", help="Nome do cliente (pasta em clientes/)")
    group.add_argument("--all-clients", action="store_true", help="Roda para todos os clientes em clientes/")
    p.add_argument("--to", required=True, help="Destinatário: nome, número, ID de grupo (@g.us) ou 'grupo'")
    p.add_argument("--days", type=int, default=7, help="Janela em dias (default: 7)")
    p.add_argument("--preview", action="store_true", help="Imprime no terminal sem mandar nem salvar")
    return p.parse_args()


def check_env(env_path: Path) -> bool:
    missing = []
    for key, desc in REQUIRED_ENV.items():
        v = os.getenv(key, "").strip()
        if not v or v.startswith(("act_$", "/Users/voce")):
            missing.append((key, desc))
        if key == "META_AD_ACCOUNT_ID" and v == "act_":
            missing.append((key, desc))

    seen = set()
    missing = [(k, d) for k, d in missing if not (k in seen or seen.add(k))]

    if not missing:
        return True

    print("\n✗ Variáveis ausentes no .env:")
    for k, d in missing:
        print(f"  - {k}  ({d})")
    print(f"\n→ edita: {env_path}")
    print("→ depois roda o comando de novo.\n")
    return False


def run_client(
    client_name: str,
    to: str,
    days: int,
    preview: bool,
    vault_path: Path,
) -> int:
    print(f"\n{'='*60}")
    print(f"→ cliente: {client_name}")
    print(f"→ janela: {days}d")

    try:
        client_path = vault.client_dir(vault_path, client_name)
    except vault.VaultError as e:
        print(f"✗ {e}")
        return 1

    contexto = vault.read_contexto(client_path)

    # resolve destinatário — suporta grupo (@g.us) diretamente
    try:
        recipient_label, recipient_number = vault.resolve_recipient(
            target=to,
            client_path=client_path,
            contexto_fm=contexto.get("frontmatter") or {},
        )
    except vault.VaultError as e:
        print(f"✗ {e}")
        return 1

    is_group = recipient_number.endswith("@g.us")
    dest_type = "grupo" if is_group else "contato"
    print(f"→ destinatário ({dest_type}): {recipient_label} ({_mask(recipient_number)})")

    # métricas
    print(f"→ buscando métricas dos últimos {days}d na Meta...")
    try:
        metrics = meta_api.fetch_insights(
            access_token=os.environ["META_ACCESS_TOKEN"],
            ad_account_id=os.environ["META_AD_ACCOUNT_ID"],
            days=days,
        )
    except meta_api.MetaAPIError as e:
        print(f"✗ {e}")
        return 1

    if metrics.get("has_data"):
        print(
            f"  spend R$ {metrics['spend']:.2f} · "
            f"purchases {metrics['purchases']:.0f} · "
            f"cpa R$ {metrics.get('cpa', 0):.2f} · "
            f"roas {metrics.get('roas', 0):.2f}"
        )
    else:
        print("  conta sem dados na janela.")

    # atividade automática via API do Meta (sem histórico manual)
    activity = []
    print("→ buscando atividade da conta na Meta API...")
    try:
        activity = meta_api.fetch_activity(
            access_token=os.environ["META_ACCESS_TOKEN"],
            ad_account_id=os.environ["META_AD_ACCOUNT_ID"],
            days=days,
        )
        print(f"  {len(activity)} evento(s) encontrado(s).")
    except Exception as e:
        print(f"  aviso: não consegui buscar atividade ({e})")

    # narrativa
    text = narrative.build_narrative(
        client_name=client_name,
        metrics=metrics,
        historico={},
        contexto=contexto,
        days=days,
        activity=activity,
    )

    print("\n" + "─" * 60)
    print(text)
    print("─" * 60 + "\n")

    if preview:
        print("→ modo preview — nada foi enviado nem salvo.")
        return 0

    print(f"→ enviando para {recipient_label} via Evo Go...")
    try:
        evo_go.send_text(
            api_url=os.environ["EVO_API_URL"],
            api_key=os.environ["EVO_API_KEY"],
            number=recipient_number,
            text=text,
        )
    except evo_go.EvoGoError as e:
        print(f"✗ {e}")
        return 1
    print("✓ mensagem enviada.")

    saved = vault.save_relatorio(client_path, recipient_label, text)
    print(f"✓ relatório salvo em: {saved}")

    vault.append_historico(
        client_path,
        f"relatório de {days}d enviado pro {recipient_label}",
    )
    return 0


def list_clients(vault_path: Path) -> list[str]:
    clientes_dir = vault_path / "clientes"
    if not clientes_dir.is_dir():
        return []
    return sorted(p.name for p in clientes_dir.iterdir() if p.is_dir())


def main() -> int:
    env_path = (SCRIPT_DIR.parent / ".env").resolve()
    load_dotenv(env_path)
    load_dotenv()

    args = parse_args()

    if not check_env(env_path):
        return 2

    vault_path = Path(os.environ["OBSIDIAN_VAULT_PATH"]).expanduser().resolve()
    if not vault_path.is_dir():
        print(f"✗ OBSIDIAN_VAULT_PATH não existe: {vault_path}")
        return 2

    if args.all_clients:
        clients = list_clients(vault_path)
        if not clients:
            print("✗ Nenhum cliente encontrado em clientes/")
            return 1

        print(f"→ {len(clients)} cliente(s) encontrado(s): {', '.join(clients)}")
        results = {}
        for client in clients:
            code = run_client(client, args.to, args.days, args.preview, vault_path)
            results[client] = "✓" if code == 0 else "✗"

        print(f"\n{'='*60}")
        print("Resumo:")
        for client, status in results.items():
            print(f"  {status} {client}")
        return 0

    return run_client(args.client, args.to, args.days, args.preview, vault_path)


def _mask(number: str) -> str:
    if "@g.us" in number:
        return number[:8] + "****@g.us"
    if len(number) < 6:
        return number
    return number[:4] + "*" * (len(number) - 8) + number[-4:]


if __name__ == "__main__":
    raise SystemExit(main())
