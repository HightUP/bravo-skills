#!/usr/bin/env python3
"""
subir-campanha — orquestrador CLI

Sobe uma campanha completa no Meta Ads (Facebook/Instagram) com 1 comando.
Sempre cria PAUSED. Gestor revisa e ativa manual.

Uso:
    python main.py --client acme --budget 500 --objetivo CONVERSIONS --abo
    python main.py --client acme --budget 1500 --objetivo TRAFFIC --cbo --dry-run
    python main.py --client "João da Silva" --budget 300 --objetivo LEADS --abo --dry-run

Fluxo:
    1. Lê .env da skill (META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, OBSIDIAN_VAULT_PATH)
    2. Acha pasta clientes/<nome>/ no vault
    3. Lê contexto.md e historico.md (informativo)
    4. Monta estrutura (campanha + N conjuntos + N anúncios)
    5. Mostra resumo
    6. --dry-run: imprime JSON e sai
       senão: salva backup, chama Graph API, atualiza historico.md, imprime URL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# permite importar módulos irmãos de qualquer cwd
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import meta_api  # noqa: E402
import vault  # noqa: E402


# ── env validation ──────────────────────────────────────────────────────
REQUIRED_ENV = {
    "META_ACCESS_TOKEN": "Token Meta long-lived com `ads_management` (developers.facebook.com)",
    "META_AD_ACCOUNT_ID": "Conta de anúncios (formato act_XXXXXX, do adsmanager.facebook.com)",
    "OBSIDIAN_VAULT_PATH": "Caminho absoluto do vault Obsidian (sem / no final)",
}


def check_env() -> None:
    missing = [(k, desc) for k, desc in REQUIRED_ENV.items() if not os.getenv(k, "").strip()]
    if missing:
        print("✗ Variáveis ausentes no .env desta skill:")
        for k, desc in missing:
            print(f"  - {k}")
            print(f"    {desc}")
        print()
        print("Edita o .env em:")
        print(f"  {Path(__file__).resolve().parent.parent / '.env'}")
        print()
        print("Veja .env.example pra detalhes. Roda de novo depois de preencher.")
        sys.exit(2)


# ── parsing ─────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="subir-campanha",
        description="Sobe campanha completa no Meta Ads (sempre PAUSED).",
    )
    p.add_argument("--client", required=True, help="Nome do cliente (pasta em clientes/<nome>/)")
    p.add_argument("--budget", required=True, type=float, help="Orçamento DIÁRIO em R$ (ex: 500)")
    p.add_argument(
        "--objetivo",
        required=True,
        choices=["CONVERSIONS", "TRAFFIC", "LEADS", "CONV", "TRAF"],
        help="Objetivo da campanha",
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--abo", dest="cbo", action="store_false", help="Orçamento por conjunto (default)")
    mode.add_argument("--cbo", dest="cbo", action="store_true", help="Orçamento na campanha")
    p.set_defaults(cbo=False)

    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Não chama API. Imprime JSON da estrutura e sai.",
    )
    p.add_argument(
        "--num-adsets",
        type=int,
        default=1,
        help="Quantidade de conjuntos a criar (default: 1)",
    )
    return p.parse_args()


def normalize_objetivo(raw: str) -> str:
    """CONV → CONVERSIONS, TRAF → TRAFFIC, LEADS → LEADS."""
    mapping = {"CONV": "CONVERSIONS", "TRAF": "TRAFFIC"}
    return mapping.get(raw.upper(), raw.upper())


# ── estrutura ───────────────────────────────────────────────────────────
def build_structure(
    client_name: str,
    objetivo: str,
    budget_brl: float,
    cbo: bool,
    num_adsets: int,
    ad_account_id: str,
) -> dict:
    """
    Monta a estrutura da campanha (campanha + conjuntos + anúncios).
    Não chama API — apenas dicts.

    Nomenclatura padrão Bravo:
      Campanha: [Cliente] · [Objetivo] · [Data]
      Conjunto: [Público] · [Idade] · [Localização]
      Anúncio:  [Criativo-ID] · [Hook]
    """
    today = datetime.now().strftime("%Y-%m-%d")
    cliente_label = client_name.title()

    # orçamento total → cents
    budget_cents = int(round(budget_brl * 100))
    # ABO: divide o budget entre conjuntos
    per_adset_cents = budget_cents // max(num_adsets, 1)

    campaign = {
        "name": f"{cliente_label} · {objetivo} · {today}",
        "objective": objetivo,
        "cbo": cbo,
        "daily_budget_cents": budget_cents if cbo else None,
        "status": "PAUSED",
    }

    # targeting placeholder — gestor edita depois no Ads Manager
    # (ou a skill é chamada de novo com targeting customizado)
    default_targeting = {
        "geo_locations": {"countries": ["BR"]},
        "age_min": 25,
        "age_max": 55,
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed"],
        "instagram_positions": ["stream", "story"],
        "device_platforms": ["mobile", "desktop"],
    }

    publicos = ["Frio · Lookalike", "Morno · Engajadores", "Quente · Visitantes"]
    adsets = []
    for i in range(num_adsets):
        publico = publicos[i % len(publicos)]
        adsets.append({
            "name": f"{publico} · 25-55 · BR",
            "daily_budget_cents": None if cbo else per_adset_cents,
            "targeting": default_targeting,
            "status": "PAUSED",
            "ads": [
                {
                    "name": f"Criativo-001 · Hook principal",
                    "creative_id": None,  # gestor preenche, ou a skill busca depois
                    "status": "PAUSED",
                }
            ],
        })

    return {
        "ad_account_id": ad_account_id,
        "client": client_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "campaign": campaign,
        "adsets": adsets,
    }


def print_summary(structure: dict, budget_brl: float) -> None:
    """Resumo humano do que vai ser criado."""
    c = structure["campaign"]
    n_adsets = len(structure["adsets"])
    n_ads = sum(len(a["ads"]) for a in structure["adsets"])
    mode = "CBO" if c["cbo"] else "ABO"
    print()
    print("━" * 60)
    print(f"  Cliente:      {structure['client']}")
    print(f"  Conta:        {structure['ad_account_id']}")
    print(f"  Modo:         {mode}")
    print(f"  Objetivo:     {c['objective']}")
    print(f"  Orçamento:    R$ {budget_brl:.2f}/dia")
    print(f"  Estrutura:    1 campanha + {n_adsets} conjunto(s) + {n_ads} anúncio(s)")
    print(f"  Status:       PAUSED (você revisa e ativa)")
    print("━" * 60)
    print()


# ── upload ──────────────────────────────────────────────────────────────
def upload_structure(
    structure: dict,
    access_token: str,
) -> dict:
    """
    Chama a Graph API de fato. Retorna o mesmo dict enriquecido com IDs.
    Levanta meta_api.MetaApiError em caso de falha.
    """
    ad_account_id = structure["ad_account_id"]
    c = structure["campaign"]

    print(f"→ criando campanha '{c['name']}' ...")
    camp_resp = meta_api.create_campaign(
        access_token=access_token,
        ad_account_id=ad_account_id,
        name=c["name"],
        objective=c["objective"],
        cbo=c["cbo"],
        daily_budget_cents=c.get("daily_budget_cents"),
    )
    campaign_id = camp_resp.get("id")
    structure["campaign"]["id"] = campaign_id
    print(f"  ✓ campaign_id = {campaign_id}")

    for adset in structure["adsets"]:
        print(f"→ criando conjunto '{adset['name']}' ...")
        adset_resp = meta_api.create_adset(
            access_token=access_token,
            ad_account_id=ad_account_id,
            campaign_id=campaign_id,
            name=adset["name"],
            objective=c["objective"],
            targeting=adset["targeting"],
            daily_budget_cents=adset.get("daily_budget_cents"),
            cbo=c["cbo"],
        )
        adset_id = adset_resp.get("id")
        adset["id"] = adset_id
        print(f"  ✓ adset_id = {adset_id}")

        for ad in adset["ads"]:
            if not ad.get("creative_id"):
                print(f"  ⚠ anúncio '{ad['name']}' sem creative_id — pulando.")
                print(f"    (preencha no Ads Manager ou rode de novo com creative_id)")
                continue
            print(f"→ criando anúncio '{ad['name']}' ...")
            ad_resp = meta_api.create_ad(
                access_token=access_token,
                ad_account_id=ad_account_id,
                adset_id=adset_id,
                name=ad["name"],
                creative_id=ad["creative_id"],
            )
            ad["id"] = ad_resp.get("id")
            print(f"  ✓ ad_id = {ad['id']}")

    return structure


# ── main ────────────────────────────────────────────────────────────────
def main() -> int:
    # carrega .env da pasta da skill (.. relativo a scripts/)
    load_dotenv(SCRIPT_DIR.parent / ".env")
    # e .env do cwd, sem sobrescrever
    load_dotenv()

    args = parse_args()

    if not args.dry_run:
        check_env()
    else:
        # mesmo em dry-run precisamos de OBSIDIAN_VAULT_PATH pra ler contexto
        if not os.getenv("OBSIDIAN_VAULT_PATH", "").strip():
            print("✗ OBSIDIAN_VAULT_PATH ausente — necessário pra ler clientes/<nome>/")
            print(f"  Configure em: {SCRIPT_DIR.parent / '.env'}")
            return 2

    objetivo = normalize_objetivo(args.objetivo)
    vault_path = Path(os.environ["OBSIDIAN_VAULT_PATH"]).expanduser().resolve()

    # ── 1. localizar cliente ────────────────────────────────────────
    client_dir = vault.find_client_dir(vault_path, args.client)
    if not client_dir:
        print(f"✗ Cliente '{args.client}' não encontrado em {vault_path / 'clientes'}")
        print(f"  Verifique se a pasta existe: {vault_path / 'clientes' / args.client}")
        return 1

    print(f"→ cliente: {client_dir}")

    # ── 2. ler contexto + histórico ─────────────────────────────────
    contexto = vault.read_context(client_dir)
    historico = vault.read_historico(client_dir)
    if contexto:
        print(f"→ contexto.md: {len(contexto)} chars")
    else:
        print("⚠ contexto.md não encontrado — seguindo com defaults")
    if historico:
        print(f"→ historico.md: {len(historico)} chars")

    # ── 3. montar estrutura ─────────────────────────────────────────
    ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "act_PLACEHOLDER").strip()
    structure = build_structure(
        client_name=args.client,
        objetivo=objetivo,
        budget_brl=args.budget,
        cbo=args.cbo,
        num_adsets=args.num_adsets,
        ad_account_id=ad_account_id,
    )

    print_summary(structure, args.budget)

    # ── 4. dry-run ──────────────────────────────────────────────────
    if args.dry_run:
        print("→ DRY-RUN — JSON da estrutura (nada foi enviado pra Meta):")
        print()
        print(json.dumps(structure, indent=2, ensure_ascii=False))
        print()
        print("✓ pra subir de verdade, rode de novo SEM --dry-run")
        return 0

    # ── 5. backup ───────────────────────────────────────────────────
    backup = vault.save_structure_backup(client_dir, structure)
    print(f"→ backup salvo: {backup}")

    # ── 6. upload via Graph API ─────────────────────────────────────
    access_token = os.environ["META_ACCESS_TOKEN"].strip()
    try:
        structure = upload_structure(structure, access_token)
    except meta_api.MetaApiError as e:
        print(f"✗ {e}")
        # re-salva o backup com o erro pra debug
        structure["error"] = str(e)
        backup.write_text(
            json.dumps(structure, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return 1

    # ── 7. atualiza histórico ───────────────────────────────────────
    campaign_id = structure["campaign"].get("id")
    url = meta_api.ads_manager_url(ad_account_id, campaign_id)
    n_adsets = len(structure["adsets"])
    n_ads = sum(1 for a in structure["adsets"] for ad in a["ads"] if ad.get("id"))

    entry = (
        f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} — campanha criada (PAUSED)\n\n"
        f"- **Nome:** {structure['campaign']['name']}\n"
        f"- **Objetivo:** {structure['campaign']['objective']}\n"
        f"- **Modo:** {'CBO' if structure['campaign']['cbo'] else 'ABO'}\n"
        f"- **Budget diário:** R$ {args.budget:.2f}\n"
        f"- **Estrutura:** {n_adsets} conjunto(s), {n_ads} anúncio(s)\n"
        f"- **Campaign ID:** `{campaign_id}`\n"
        f"- **Ads Manager:** {url}\n"
        f"- **Backup:** `{backup.relative_to(client_dir)}`\n"
    )
    vault.append_historico(client_dir, entry)
    print(f"→ historico.md atualizado")

    print()
    print("━" * 60)
    print(f"✓ campanha criada com sucesso (PAUSED)")
    print(f"  abrir Ads Manager: {url}")
    print("━" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
