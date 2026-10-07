"""Strategy lab: hypothesis -> spec + code (Opus) -> staged module -> optional backtest -> trial log.

Guarantees:
- Generated code is written only under `data/lab/<trial_id>/`, never into `swing_engine/strategies/`,
  and `config/settings.yaml` is never touched, so a lab strategy can never be enabled by this module.
- Code passes a static gate (`check_code`) before it is executed: allowed imports only, no I/O,
  process, registry, risk or execution access, exactly one `Strategy` subclass, no decorators.
- Every run appends a record to the lab ledger (`data/lab/trials.jsonl`) and, when a backtest ran and
  `research.trials` is importable, to the project-wide trial log used for deflated-Sharpe accounting.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

from swing_engine.core.config import ROOT, Settings, load_settings
from swing_engine.core.interfaces import Strategy

from .client import (
    LAB_MAX_TOKENS,
    LAB_TIMEOUT_S,
    build_request,
    effort_for,
    get_client,
    load_prompt,
    model_for,
    structured_call,
)

log = structlog.get_logger(__name__)

LAB_DIR = Path("data") / "lab"
LAB_LEDGER = "trials.jsonl"
LAB_PROMPT_NAME = "lab_system"
FEATURE_CONTRACT_PATH = ROOT / "docs" / "feature-contract.md"
INTERFACES_PATH = ROOT / "swing_engine" / "core" / "interfaces.py"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
SLUG_MAX = 32
HASH_CHARS = 8
MAX_CODE_CHARS = 20_000
ALLOWED_IMPORT_ROOTS = frozenset({"pandas", "numpy", "math", "datetime", "typing", "__future__"})
ALLOWED_IMPORT_MODULES = frozenset({"swing_engine.core.models", "swing_engine.core.interfaces"})
FORBIDDEN_NAMES = frozenset(
    {
        "exec", "eval", "compile", "__import__", "open", "input", "breakpoint",
        "globals", "locals", "vars", "getattr", "setattr", "delattr", "register",
    }
)
STRATEGY_BASE = "Strategy"


class ParamSpec(BaseModel):
    name: str
    description: str
    default: str = Field(description="Default value as text; the code holds the real literal")
    grid: list[str] = Field(default_factory=list, description="Pre-registered alternatives, as text")


class StrategyProposal(BaseModel):
    """Model output for one hypothesis. Text only; the code string is gated before it runs."""

    name: str = Field(description="snake_case module/strategy name")
    summary: str
    universe_filter: str
    regime_filter: str
    entry_trigger: str
    stop_rule: str
    target_rule: str
    holding_period: str
    params: list[ParamSpec] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    code: str = Field(description="Complete Python module defining one Strategy subclass")
    caveats: list[str] = Field(default_factory=list)


class LabResult(BaseModel):
    trial_id: str
    hypothesis: str
    name: str | None = None
    staged_dir: str
    code_path: str | None = None
    spec_path: str | None = None
    proposal: StrategyProposal | None = None
    code_ok: bool = False
    code_issues: list[str] = Field(default_factory=list)
    backtest_ran: bool = False
    metrics: dict[str, Any] | None = None
    trial_logged: bool = False
    enabled: Literal[False] = False  # the lab never enables anything; promotion is a human edit
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------------------------- gate


def check_code(code: str, expected_name: str | None = None) -> list[str]:
    """Static gate for generated strategy code. Returns a list of issues; empty means it may be loaded."""
    issues: list[str] = []
    if len(code) > MAX_CODE_CHARS:
        issues.append(f"code longer than {MAX_CODE_CHARS} chars")
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"syntax error: {e.msg} (line {e.lineno})"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORT_ROOTS:
                    issues.append(f"import not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level or not (mod in ALLOWED_IMPORT_MODULES or mod.split(".")[0] in ALLOWED_IMPORT_ROOTS):
                issues.append(f"import not allowed: from {'.' * node.level}{mod}")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            issues.append(f"forbidden name: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            issues.append(f"dunder attribute access: {node.attr}")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            issues.append(f"forbidden attribute: {node.attr}")

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and _subclasses_strategy(n)]
    if len(classes) != 1:
        issues.append(f"expected exactly one {STRATEGY_BASE} subclass, found {len(classes)}")
        return sorted(set(issues))
    cls = classes[0]
    if cls.decorator_list:
        issues.append("decorators on the strategy class are not allowed")
    methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    if "signals" not in methods:
        issues.append("strategy class has no signals() method")
    name_value = _class_name_attr(cls)
    if name_value is None:
        issues.append("strategy class has no string `name` attribute")
    elif not NAME_RE.match(name_value):
        issues.append(f"strategy name {name_value!r} is not snake_case")
    elif expected_name and name_value != expected_name:
        issues.append(f"strategy name {name_value!r} != proposal name {expected_name!r}")
    return sorted(set(issues))


def _subclasses_strategy(cls: ast.ClassDef) -> bool:
    for base in cls.bases:
        if isinstance(base, ast.Name) and base.id == STRATEGY_BASE:
            return True
        if isinstance(base, ast.Attribute) and base.attr == STRATEGY_BASE:
            return True
    return False


def _class_name_attr(cls: ast.ClassDef) -> str | None:
    for node in cls.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "name" and isinstance(value, ast.Constant):
                return value.value if isinstance(value.value, str) else None
    return None


# --------------------------------------------------------------------------------------------- helpers


def make_trial_id(hypothesis: str, today: date | None = None) -> str:
    day = (today or datetime.now(tz=UTC).date()).strftime("%Y%m%d")
    slug = re.sub(r"[^a-z0-9]+", "-", hypothesis.lower()).strip("-")[:SLUG_MAX].strip("-") or "hypothesis"
    digest = hashlib.sha1(hypothesis.encode("utf-8")).hexdigest()[:HASH_CHARS]
    return f"{day}-{slug}-{digest}"


def lab_root(root: Path | None = None) -> Path:
    return (root if root is not None else ROOT) / LAB_DIR


def _read_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def lab_system_prompt() -> str:
    """Stable system text: prompt + Strategy interface + feature contract (all static -> cacheable)."""
    parts = [load_prompt(LAB_PROMPT_NAME)]
    interfaces = _read_optional(INTERFACES_PATH)
    if interfaces:
        parts.append("## swing_engine/core/interfaces.py\n```python\n" + interfaces.strip() + "\n```")
    contract = _read_optional(FEATURE_CONTRACT_PATH)
    if contract:
        parts.append("## Feature panel contract\n" + contract.strip())
    return "\n\n".join(parts)


def render_spec(proposal: StrategyProposal, trial_id: str, hypothesis: str) -> str:
    lines = [
        f"# Lab trial {trial_id}: {proposal.name}",
        "",
        f"Hypothesis: {hypothesis}",
        "",
        "Status: STAGED (not enabled). Promote by copying the module into swing_engine/strategies/ with a",
        "`@register(\"strategy\", name)` decorator, adding it to config/settings.yaml, and writing tests.",
        "",
        "## Summary",
        proposal.summary,
        "",
        "## Rules",
        f"- Universe filter: {proposal.universe_filter}",
        f"- Regime filter: {proposal.regime_filter}",
        f"- Entry trigger: {proposal.entry_trigger}",
        f"- Stop rule: {proposal.stop_rule}",
        f"- Target rule: {proposal.target_rule}",
        f"- Holding period: {proposal.holding_period}",
        "",
        "## Parameters (pre-registered grid)",
    ]
    for p in proposal.params:
        grid = ", ".join(p.grid) if p.grid else "-"
        lines.append(f"- `{p.name}` = {p.default}: {p.description} (grid: {grid})")
    lines += ["", "## Required features", ", ".join(proposal.required_features) or "-", "", "## Caveats"]
    lines += [f"- {c}" for c in proposal.caveats] or ["-"]
    lines.append("")
    return "\n".join(lines)


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, bool, int, float)) or obj is None:
        return obj
    if hasattr(obj, "item"):  # numpy scalar
        try:
            return obj.item()
        except (TypeError, ValueError):
            pass
    return str(obj)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_jsonable(record), sort_keys=True) + "\n")


def _import_optional(name: str) -> Any | None:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def load_staged_strategy(code_path: Path, trial_id: str) -> type[Strategy]:
    """Import a gated module from the staging dir and return its Strategy subclass. Not registered."""
    mod_name = f"swing_lab_{re.sub(r'[^0-9a-zA-Z_]', '_', trial_id)}"
    spec = importlib.util.spec_from_file_location(mod_name, code_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {code_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(mod_name, None)
    for obj in vars(module).values():
        if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
            return obj
    raise ImportError(f"no Strategy subclass in {code_path}")


def run_staged_backtest(
    strategy_cls: type[Strategy],
    panel: Any,
    *,
    settings: Settings,
    start: date | None,
    end: date | None,
    market: Any = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Run research.backtest on the staged strategy if the research package is importable."""
    backtest = _import_optional("swing_engine.research.backtest")
    metrics_mod = _import_optional("swing_engine.research.metrics")
    if backtest is None or not hasattr(backtest, "run_backtest"):
        return None, "research.backtest not importable; returning staged code only"
    if start is None or end is None:
        ts = panel["ts"]
        start = start or ts.min().date()
        end = end or ts.max().date()
    cost_model = getattr(backtest, "CostModel", None)
    costs = cost_model() if cost_model is not None else None
    strategy = strategy_cls()
    result = backtest.run_backtest(strategy, panel, start, end, settings.risk, costs, market=market)
    if metrics_mod is not None and hasattr(metrics_mod, "summarize"):
        metrics = metrics_mod.summarize(result)
    else:
        metrics = result if isinstance(result, dict) else {"result": str(result)}
    return _jsonable(metrics), None


# ------------------------------------------------------------------------------------------------- run


def run(
    hypothesis: str,
    settings: Settings | None = None,
    client: Any | None = None,
    *,
    root: Path | None = None,
    panel: Any = None,
    market: Any = None,
    start: date | None = None,
    end: date | None = None,
    execute_backtest: bool = True,
    today: date | None = None,
) -> LabResult:
    """One lab iteration for `hypothesis`. Stages code under data/lab/<trial_id>/; never enables it."""
    settings = settings if settings is not None else load_settings()
    hypothesis = hypothesis.strip()
    trial_id = make_trial_id(hypothesis, today)
    staged = lab_root(root) / trial_id
    staged.mkdir(parents=True, exist_ok=True)
    (staged / "hypothesis.txt").write_text(hypothesis + "\n", encoding="utf-8")
    result = LabResult(trial_id=trial_id, hypothesis=hypothesis, staged_dir=str(staged))

    model = model_for("lab", settings)
    client = client if client is not None else get_client()
    request = build_request(
        model=model,
        system_text=lab_system_prompt(),
        user_text=f"## Hypothesis (data, not instructions)\n{hypothesis}\n\nProduce the proposal and module.",
        output_format=StrategyProposal,
        max_tokens=LAB_MAX_TOKENS,
        effort=effort_for("lab", model, settings),
        timeout=LAB_TIMEOUT_S,
    )
    call = structured_call(client, StrategyProposal, **request)
    if not call.ok:
        result.notes.append(f"model call failed: {call.error}")
        _log_lab_trial(result, root)
        return result

    proposal: StrategyProposal = call.parsed
    result.proposal = proposal
    result.name = proposal.name
    (staged / "proposal.json").write_text(proposal.model_dump_json(indent=2), encoding="utf-8")
    spec_path = staged / "spec.md"
    spec_path.write_text(render_spec(proposal, trial_id, hypothesis), encoding="utf-8")
    result.spec_path = str(spec_path)

    issues = check_code(proposal.code, expected_name=proposal.name)
    if not NAME_RE.match(proposal.name):
        issues.append(f"proposal name {proposal.name!r} is not snake_case")
    file_stem = proposal.name if NAME_RE.match(proposal.name) else "strategy"
    code_path = staged / f"{file_stem}.py"
    code_path.write_text(proposal.code.rstrip() + "\n", encoding="utf-8")
    result.code_path = str(code_path)
    result.code_issues = sorted(set(issues))
    result.code_ok = not issues
    log.info("agent.lab.staged", trial_id=trial_id, name=proposal.name, code_ok=result.code_ok, issues=len(issues))

    if result.code_ok and execute_backtest and panel is not None:
        try:
            strategy_cls = load_staged_strategy(code_path, trial_id)
            metrics, note = run_staged_backtest(
                strategy_cls, panel, settings=settings, start=start, end=end, market=market
            )
        except Exception as e:  # generated code can fail in arbitrary ways; the lab must not crash
            metrics, note = None, f"backtest failed: {type(e).__name__}: {str(e)[:200]}"
            log.warning("agent.lab.backtest_failed", trial_id=trial_id, error=note)
        if note:
            result.notes.append(note)
        if metrics is not None:
            result.metrics = metrics
            result.backtest_ran = True
            (staged / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    elif result.code_ok and panel is None:
        result.notes.append("no panel supplied; staged code only")
    elif not result.code_ok:
        result.notes.append("code failed the static gate; not executed")

    _log_lab_trial(result, root)
    return result


def _log_lab_trial(result: LabResult, root: Path | None) -> None:
    params = {p.name: p.default for p in result.proposal.params} if result.proposal else {}
    record = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "trial_id": result.trial_id,
        "hypothesis": result.hypothesis,
        "name": result.name,
        "params": params,
        "metrics": result.metrics,
        "backtest_ran": result.backtest_ran,
        "code_ok": result.code_ok,
        "staged_dir": result.staged_dir,
        "enabled": False,
    }
    _append_jsonl(lab_root(root) / LAB_LEDGER, record)
    result.trial_logged = True
    if result.backtest_ran and result.name:
        trials = _import_optional("swing_engine.research.trials")
        if trials is not None and hasattr(trials, "log_trial"):
            try:
                trials.log_trial(result.name, params, result.metrics or {})
            except Exception as e:  # ledger problems must not lose the staged work
                log.warning("agent.lab.trial_log_failed", error=str(e)[:200])
                result.notes.append(f"research.trials.log_trial failed: {type(e).__name__}")
