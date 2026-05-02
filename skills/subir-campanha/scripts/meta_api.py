"""
meta_api — wrapper minimal da Meta Marketing API (Graph API v19.0).

Cobre o que a skill precisa:
  - criar campanha (ABO ou CBO)
  - criar adset
  - criar ad (precisa de creative_id existente)
  - traduzir erro de API em mensagem humana

Sempre cria com status PAUSED. Nunca ATIVO.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import requests


GRAPH_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


# Mapa objetivo → ODAX (objetivos novos do Meta) + optimization_goal sugerido
OBJECTIVE_MAP = {
    "CONVERSIONS": {
        "objective": "OUTCOME_SALES",
        "optimization_goal": "OFFSITE_CONVERSIONS",
        "billing_event": "IMPRESSIONS",
    },
    "TRAFFIC": {
        "objective": "OUTCOME_TRAFFIC",
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
    },
    "LEADS": {
        "objective": "OUTCOME_LEADS",
        "optimization_goal": "LEAD_GENERATION",
        "billing_event": "IMPRESSIONS",
    },
}


class MetaApiError(Exception):
    """Erro da Meta Marketing API com mensagem amigável."""

    def __init__(self, message: str, code: Optional[int] = None, raw: Any = None):
        super().__init__(message)
        self.code = code
        self.raw = raw


def _humanize_error(payload: dict) -> str:
    """
    Converte JSON de erro da Meta numa frase humana.
    Ver https://developers.facebook.com/docs/marketing-api/error-reference
    """
    err = payload.get("error", {}) if isinstance(payload, dict) else {}
    code = err.get("code")
    msg = err.get("message", "Erro desconhecido")
    sub = err.get("error_subcode")
    uti = err.get("error_user_title")
    umsg = err.get("error_user_msg")

    hints = {
        190: "Token expirado ou inválido — gere um novo long-lived token em developers.facebook.com.",
        200: "Conta sem permissão pra essa ação — verifique se o token tem `ads_management` e se o usuário é admin da conta.",
        100: "Parâmetro inválido — revise os campos enviados.",
        17: "Limite de requisição atingido (rate limit) — espere alguns minutos e tente de novo.",
        2635: "Conta de anúncios desabilitada ou bloqueada.",
        368: "Ação bloqueada por política da Meta — verifique o status da conta.",
    }
    hint = hints.get(code)

    parts = [f"Meta API erro {code}: {msg}"]
    if sub:
        parts.append(f"(subcode {sub})")
    if uti or umsg:
        parts.append(f"— {uti or ''}: {umsg or ''}".strip())
    if hint:
        parts.append(f"\n  Dica: {hint}")
    return " ".join(parts)


def _request(method: str, path: str, access_token: str, **kwargs) -> dict:
    """Executa request, levanta MetaApiError com mensagem humana se falhar."""
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    params = kwargs.pop("params", {}) or {}
    params["access_token"] = access_token

    try:
        resp = requests.request(method, url, params=params, timeout=30, **kwargs)
    except requests.RequestException as e:
        raise MetaApiError(f"Falha de rede ao chamar {path}: {e}") from e

    try:
        payload = resp.json()
    except json.JSONDecodeError:
        payload = {"raw": resp.text}

    if resp.status_code >= 400 or (isinstance(payload, dict) and payload.get("error")):
        msg = _humanize_error(payload) if isinstance(payload, dict) else f"HTTP {resp.status_code}"
        code = None
        if isinstance(payload, dict):
            code = payload.get("error", {}).get("code")
        raise MetaApiError(msg, code=code, raw=payload)

    return payload


def create_campaign(
    access_token: str,
    ad_account_id: str,
    name: str,
    objective: str,
    cbo: bool = False,
    daily_budget_cents: Optional[int] = None,
    special_ad_categories: Optional[list[str]] = None,
) -> dict:
    """
    Cria campanha (sempre PAUSED).

    objective: chave de OBJECTIVE_MAP (CONVERSIONS, TRAFFIC, LEADS).
    cbo=True: orçamento na campanha (CBO). Precisa de daily_budget_cents.
    cbo=False: orçamento no adset (ABO). daily_budget_cents é ignorado aqui.
    """
    if objective not in OBJECTIVE_MAP:
        raise MetaApiError(f"Objetivo inválido: {objective!r}. Use {list(OBJECTIVE_MAP)}.")

    data: dict[str, Any] = {
        "name": name,
        "objective": OBJECTIVE_MAP[objective]["objective"],
        "status": "PAUSED",
        "special_ad_categories": json.dumps(special_ad_categories or []),
        # política de aceitação obrigatória pra criação por API
        "buying_type": "AUCTION",
    }
    if cbo:
        if not daily_budget_cents or daily_budget_cents <= 0:
            raise MetaApiError("CBO precisa de daily_budget_cents > 0.")
        data["daily_budget"] = daily_budget_cents

    return _request("POST", f"{ad_account_id}/campaigns", access_token, data=data)


def create_adset(
    access_token: str,
    ad_account_id: str,
    campaign_id: str,
    name: str,
    objective: str,
    targeting: dict,
    daily_budget_cents: Optional[int] = None,
    cbo: bool = False,
    promoted_pixel_id: Optional[str] = None,
    promoted_page_id: Optional[str] = None,
) -> dict:
    """
    Cria adset (sempre PAUSED).
    Em ABO: daily_budget_cents > 0 obrigatório.
    Em CBO: orçamento já está na campanha.
    """
    obj = OBJECTIVE_MAP.get(objective)
    if not obj:
        raise MetaApiError(f"Objetivo inválido: {objective!r}.")

    data: dict[str, Any] = {
        "name": name,
        "campaign_id": campaign_id,
        "status": "PAUSED",
        "billing_event": obj["billing_event"],
        "optimization_goal": obj["optimization_goal"],
        "targeting": json.dumps(targeting),
    }

    if not cbo:
        if not daily_budget_cents or daily_budget_cents <= 0:
            raise MetaApiError("ABO precisa de daily_budget_cents > 0 no adset.")
        data["daily_budget"] = daily_budget_cents

    # promoted_object — depende do objetivo
    if objective == "CONVERSIONS" and promoted_pixel_id:
        data["promoted_object"] = json.dumps({
            "pixel_id": promoted_pixel_id,
            "custom_event_type": "PURCHASE",
        })
    elif objective == "LEADS" and promoted_page_id:
        data["promoted_object"] = json.dumps({"page_id": promoted_page_id})

    return _request("POST", f"{ad_account_id}/adsets", access_token, data=data)


def create_ad(
    access_token: str,
    ad_account_id: str,
    adset_id: str,
    name: str,
    creative_id: str,
) -> dict:
    """Cria ad apontando pra creative existente. Sempre PAUSED."""
    data = {
        "name": name,
        "adset_id": adset_id,
        "status": "PAUSED",
        "creative": json.dumps({"creative_id": creative_id}),
    }
    return _request("POST", f"{ad_account_id}/ads", access_token, data=data)


def ads_manager_url(ad_account_id: str, campaign_id: Optional[str] = None) -> str:
    """URL pro Ads Manager filtrando pela campanha (se passada)."""
    act = ad_account_id.replace("act_", "")
    base = f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={act}"
    if campaign_id:
        base += f"&selected_campaign_ids={campaign_id}"
    return base
