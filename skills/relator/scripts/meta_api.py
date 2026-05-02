"""
meta_api — Meta Marketing API (Graph) insights.

Endpoint: GET /act_<id>/insights
Doc: https://developers.facebook.com/docs/marketing-api/insights

Retorna métricas agregadas dos últimos N dias da conta de anúncios.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx

GRAPH_URL = "https://graph.facebook.com/v21.0"

_ACTIVITY_EVENT_LABELS = {
    "create_campaign": "Campanha criada",
    "update_campaign_budget": "Budget de campanha alterado",
    "update_campaign_run_status": "Status de campanha alterado",
    "update_campaign_name": "Campanha renomeada",
    "create_ad_set": "Conjunto criado",
    "update_ad_set_budget": "Budget de conjunto alterado",
    "update_ad_set_run_status": "Status de conjunto alterado",
    "update_ad_set_targeting": "Público de conjunto alterado",
    "update_ad_set_name": "Conjunto renomeado",
    "create_ad": "Anúncio criado",
    "update_ad_run_status": "Status de anúncio alterado",
    "update_ad_creative": "Criativo atualizado",
    "update_ad_name": "Anúncio renomeado",
    "create_audience": "Público personalizado criado",
    "update_audience": "Público personalizado atualizado",
}


class MetaAPIError(RuntimeError):
    pass


def _date_range(days: int) -> tuple[str, str]:
    today = date.today()
    since = today - timedelta(days=days)
    until = today - timedelta(days=1)  # ontem (último dia fechado)
    return since.isoformat(), until.isoformat()


def fetch_insights(
    access_token: str,
    ad_account_id: str,
    days: int = 7,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Pega insights agregados da conta nos últimos N dias.

    Retorna dict com:
        spend, impressions, clicks, ctr, cpm, cpc,
        purchases, purchase_value, cpa, roas,
        leads, registrations,
        days, since, until, raw
    """
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    since, until = _date_range(days)

    params = {
        "access_token": access_token,
        "time_range": f'{{"since":"{since}","until":"{until}"}}',
        "fields": ",".join([
            "spend",
            "impressions",
            "clicks",
            "ctr",
            "cpm",
            "cpc",
            "actions",
            "action_values",
        ]),
        "level": "account",
    }

    url = f"{GRAPH_URL}/{ad_account_id}/insights"

    try:
        resp = httpx.get(url, params=params, timeout=timeout)
    except httpx.HTTPError as e:
        raise MetaAPIError(f"falha de rede ao chamar Meta API: {e}") from e

    if resp.status_code != 200:
        try:
            payload = resp.json()
            err = payload.get("error", {})
            msg = err.get("message", resp.text)
        except Exception:
            msg = resp.text
        raise MetaAPIError(f"Meta API {resp.status_code}: {msg}")

    payload = resp.json()
    rows = payload.get("data", [])

    metrics = {
        "spend": 0.0,
        "impressions": 0,
        "clicks": 0,
        "ctr": 0.0,
        "cpm": 0.0,
        "cpc": 0.0,
        "purchases": 0,
        "purchase_value": 0.0,
        "leads": 0,
        "registrations": 0,
        "days": days,
        "since": since,
        "until": until,
        "raw": rows,
        "has_data": False,
    }

    if not rows:
        return metrics

    row = rows[0]
    metrics["has_data"] = True
    metrics["spend"] = _to_float(row.get("spend"))
    metrics["impressions"] = _to_int(row.get("impressions"))
    metrics["clicks"] = _to_int(row.get("clicks"))
    metrics["ctr"] = _to_float(row.get("ctr"))
    metrics["cpm"] = _to_float(row.get("cpm"))
    metrics["cpc"] = _to_float(row.get("cpc"))

    actions = row.get("actions") or []
    action_values = row.get("action_values") or []

    metrics["purchases"] = _sum_action(actions, [
        "purchase",
        "offsite_conversion.fb_pixel_purchase",
        "omni_purchase",
    ])
    metrics["leads"] = _sum_action(actions, [
        "lead",
        "offsite_conversion.fb_pixel_lead",
        "onsite_conversion.lead_grouped",
    ])
    metrics["registrations"] = _sum_action(actions, [
        "complete_registration",
        "offsite_conversion.fb_pixel_complete_registration",
    ])
    metrics["purchase_value"] = _sum_action(action_values, [
        "purchase",
        "offsite_conversion.fb_pixel_purchase",
        "omni_purchase",
    ])

    # derivadas
    if metrics["purchases"] > 0:
        metrics["cpa"] = metrics["spend"] / metrics["purchases"]
    elif metrics["leads"] > 0:
        metrics["cpa"] = metrics["spend"] / metrics["leads"]
    else:
        metrics["cpa"] = 0.0

    if metrics["spend"] > 0 and metrics["purchase_value"] > 0:
        metrics["roas"] = metrics["purchase_value"] / metrics["spend"]
    else:
        metrics["roas"] = 0.0

    return metrics


def fetch_activity(
    access_token: str,
    ad_account_id: str,
    days: int = 7,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """
    Busca o log de atividade da conta nos últimos N dias via /activities.
    Retorna lista de eventos ordenados do mais recente pro mais antigo.
    """
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    since, until = _date_range(days)

    params = {
        "access_token": access_token,
        "fields": "event_type,event_time,object_id,object_name,extra_data",
        "since": since,
        "until": until,
        "limit": 100,
    }

    url = f"{GRAPH_URL}/{ad_account_id}/activities"

    try:
        resp = httpx.get(url, params=params, timeout=timeout)
    except httpx.HTTPError as e:
        return []

    if resp.status_code != 200:
        return []

    rows = resp.json().get("data", [])

    events = []
    for row in rows:
        event_type = row.get("event_type", "")
        label = _ACTIVITY_EVENT_LABELS.get(event_type)
        if not label:
            continue

        name = row.get("object_name") or row.get("object_id") or ""
        extra = row.get("extra_data") or {}

        detail = ""
        if event_type in ("update_campaign_budget", "update_ad_set_budget"):
            new_val = extra.get("new_value") or extra.get("budget")
            if new_val:
                detail = f"→ R$ {float(new_val) / 100:.2f}" if str(new_val).isdigit() else f"→ {new_val}"
        elif event_type in ("update_campaign_run_status", "update_ad_set_run_status", "update_ad_run_status"):
            new_val = extra.get("new_value") or extra.get("status")
            if new_val:
                detail = f"→ {new_val}"

        event_time = row.get("event_time", "")
        date_str = event_time[:10] if event_time else ""

        events.append({
            "date": date_str,
            "label": label,
            "name": name,
            "detail": detail,
        })

    return events


def format_activity_text(events: list[dict[str, Any]]) -> str:
    """Formata a lista de eventos como texto curto pro relatório."""
    if not events:
        return ""
    lines = []
    for e in events[:15]:
        parts = [f"- {e['date']} — {e['label']}"]
        if e["name"]:
            parts.append(f": {e['name']}")
        if e["detail"]:
            parts.append(f" {e['detail']}")
        lines.append("".join(parts))
    return "\n".join(lines)


def _to_float(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_int(v: Any) -> int:
    try:
        return int(float(v)) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _sum_action(actions: list[dict], action_types: list[str]) -> float:
    """
    Soma o valor das ações que batem com algum dos action_types.
    Pega o MAIOR valor entre os types (não soma — Meta repete o mesmo evento
    em vários action_types, somar dá double-count).
    """
    best = 0.0
    for a in actions:
        t = a.get("action_type", "")
        if t in action_types:
            v = _to_float(a.get("value"))
            if v > best:
                best = v
    return best
