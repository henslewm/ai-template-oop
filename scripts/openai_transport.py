"""One text-only Responses request. No tools, redirects, or transport retries."""

from __future__ import annotations

import os
from decimal import Decimal
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from scripts import workflow_budget as budget
from scripts import workflow_state as ws
from scripts.pilot_authority import PROVIDER

# Standard short-context USD / million tokens, verified 2026-10-15.
# https://developers.openai.com/api/docs/pricing
RATES = {
    "gpt-6-luna": {
        "input": 0.10,
        "cached_input": 0.01,
        "cache_write": 0.125,
        "output": 0.50,
    },
    "gpt-6.1-sol": {
        "input": 2.0,
        "cached_input": 0.10,
        "cache_write": 2.50,
        "output": 10.0,
    },
}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenAITransport:
    def send(self, request: dict) -> dict:
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key.strip():
            raise ValueError("OPENAI_API_KEY missing")
        raw = ws.approval.canonical(request)
        message = Request(
            PROVIDER["endpoint"],
            data=raw,
            method="POST",
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
        )
        # Do not forward proxy credentials, custom endpoints, or secrets to a redirect.
        opener = build_opener(ProxyHandler({}), _NoRedirect())
        with opener.open(message, timeout=180) as response:
            content = response.read(ws.MAX_EVENT + 1)
        return ws._json(content)


def request_for(model: str, prompt: str, schema: dict) -> dict:
    if model not in RATES:
        raise ValueError("Unapproved provider model")
    return {
        "model": model,
        "input": prompt,
        "store": False,
        "service_tier": "default",
        "reasoning": {"effort": "medium"},
        "max_output_tokens": 8192,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "pilot_result",
                "strict": True,
                "schema": schema,
            }
        },
    }


def ceiling(request: dict, rates: dict) -> float:
    # One UTF-8 byte per input token plus a fixed protocol reserve; cache writes
    # use the highest input rate. No cache savings are assumed in a reservation.
    tokens = len(ws.approval.canonical(request)) + 2048
    return budget.upward(
        (
            Decimal(str(max(rates["input"], rates["cache_write"]))) * tokens
            + Decimal(str(rates["output"])) * request["max_output_tokens"]
        )
        / 1000000
    )


def usage_cost(response: dict, model: str, rates: dict) -> tuple[dict, float]:
    usage = response.get("usage")
    if not isinstance(usage, dict) or not isinstance(response.get("id"), str):
        raise ValueError("Provider usage or response identity unavailable")
    actual = response.get("model", "")
    if actual != model and not actual.startswith(model + "-"):
        raise ValueError(
            "Provider returned a different model; cost reconciliation required"
        )
    details = usage.get("input_tokens_details")
    if not isinstance(details, dict) or not {
        "cached_tokens",
        "cache_write_tokens",
    } <= set(details):
        raise ValueError("Provider cache breakdown unavailable; cost remains unknown")
    counts = {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cached_input_tokens": details["cached_tokens"],
        "cache_write_tokens": details["cache_write_tokens"],
    }
    if any(type(v) is not int or v < 0 for v in counts.values()):
        raise ValueError("Provider usage must contain nonnegative integer counts")
    normal = (
        counts["input_tokens"]
        - counts["cached_input_tokens"]
        - counts["cache_write_tokens"]
    )
    if normal < 0:
        raise ValueError("Provider cache usage exceeds input")
    cost = (
        Decimal(normal) * Decimal(str(rates["input"]))
        + Decimal(counts["cached_input_tokens"]) * Decimal(str(rates["cached_input"]))
        + Decimal(counts["cache_write_tokens"]) * Decimal(str(rates["cache_write"]))
        + Decimal(counts["output_tokens"]) * Decimal(str(rates["output"]))
    ) / 1000000
    return {
        **counts,
        "provider_response_id": response["id"],
        "model": actual,
    }, budget.upward(cost)


def structured(response: dict, schema: dict) -> dict:
    from scripts import work_packet as wp

    if response.get("status") != "completed":
        raise ValueError("Provider response incomplete; known usage was settled")
    text = []
    for item in response.get("output", []):
        if item.get("type") == "reasoning":
            continue
        if item.get("type") != "message":
            raise ValueError("Unexpected provider output type")
        for part in item.get("content", []):
            if part.get("type") != "output_text":
                raise ValueError("Provider refused or returned non-text output")
            text.append(part["text"])
    value = ws._json("".join(text).encode())
    if list(wp.Draft202012Validator(schema).iter_errors(value)):
        raise ValueError("Provider output does not match the structured contract")
    return value
