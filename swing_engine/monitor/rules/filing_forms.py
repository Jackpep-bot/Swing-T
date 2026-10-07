"""Non-8-K filing forms: NT 10-K/10-Q, SC 13D, Form 144, S-1/S-3/F-1/F-3/424B dilution documents."""
from __future__ import annotations

from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import DILUTION_FORM_PREFIXES, FILING_FORM_SEVERITY
from ._common import P0, P1, P2, P3, form_type, tiered


def is_dilution_form(form: str) -> bool:
    f = form.upper().strip()
    return any(f.startswith(p) for p in DILUTION_FORM_PREFIXES)


@register("rule", "filing_forms")
class FilingForms(Rule):
    name = "filing_forms"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind != "filing":
            return None
        form = form_type(event)
        if not form or form.startswith("8-K") or form in {"4", "4/A"}:
            return None
        sev = FILING_FORM_SEVERITY.get(form)
        if sev is None and is_dilution_form(form):
            sev = "dilution"
        if sev is None:
            return None
        event.meta["filing_severity"] = sev
        hit = f"filing:{form}"
        if sev == "severe":
            return hit, tiered(event, ctx, P3, P2, P1)
        if sev == "dilution":
            event.meta["dilution"] = True
            return hit, tiered(event, ctx, P2, P2, P1)
        if sev == "major":
            return hit, tiered(event, ctx, P2, P2, P1)
        return hit, tiered(event, ctx, P1, P0, P0)
