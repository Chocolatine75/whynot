"""Publish a `create` run's campaign plan to a Meta ad account (sandbox first).

Order of operations, each step refusing early rather than half-publishing:
1. the plan must be valid (`campaign.validate`) and every id it needs must be configured (page, app);
2. every ad set goes through the autopilot (`autopilot.decide`): the owner's cap, autonomy level and approval.
   Only ad sets the autopilot lets through are created; the others are recorded with the reason;
3. objects are created in dependency order — images, campaign, ad sets, creatives, ads — all PAUSED;
4. activation is a separate, explicit step (`activate=True`), never implied by publishing.

Resumable: every created object's id is written to `publish.json` immediately, and a re-run reuses it, so a
failure halfway never creates duplicates. Each decision is appended to `actions.jsonl` (`autopilot.ActionLog`).

Sandbox: a Meta sandbox ad account creates real objects that never deliver and never spend. The publisher
uses the plan's own cap and still requires the owner's approval, so the flow is exactly the live one.
"""

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from whynot.run.autopilot import AccountState, Action, ActionLog, Kind, Level, Outcome, Policy, decide
from whynot.run.campaign import CampaignPlan, to_api, validate
from whynot.run.meta import MarketingClient

PLACEHOLDER_KEYS = ("{PAGE_ID}", "{META_APP_ID}")


class PublishError(RuntimeError):
    pass


@dataclass
class PublishState:
    mode: str  # sandbox | live
    account: str
    objective: str
    objects: dict[str, str] = field(default_factory=dict)  # ref -> Meta id
    images: dict[str, str] = field(default_factory=dict)  # image path -> hash
    decisions: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "started"  # started | partial | published | refused | active
    campaign_url: str | None = None
    approved_by: str | None = None

    @classmethod
    def load(cls, path: Path) -> "PublishState | None":
        return cls(**json.loads(path.read_text())) if path.exists() else None

    def save(self, path: Path) -> None:
        """Atomic write: a crash never leaves a half-written state file."""
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".publish-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)


def _fill(value: Any, mapping: dict[str, str]) -> Any:
    """Replace "{placeholder}" strings (exact matches) recursively; drop the local "ref" keys."""
    if isinstance(value, dict):
        return {k: _fill(v, mapping) for k, v in value.items() if k != "ref"}
    if isinstance(value, list):
        return [_fill(v, mapping) for v in value]
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        if value not in mapping:
            raise PublishError(f"unresolved placeholder {value}")
        return mapping[value]
    return value


def _unresolved(value: Any, known: set[str]) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_unresolved(v, known) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_unresolved(v, known) for v in value)) if value else set()
    if isinstance(value, str) and value in PLACEHOLDER_KEYS and value not in known:
        return {value}
    return set()


def policy_for(mode: str, plan: CampaignPlan, owner_policy: Policy) -> Policy:
    """Sandbox: the live flow with the plan's own cap (nothing can spend). Live: exactly the owner's policy."""
    if mode == "sandbox":
        return Policy(Level.AUTOPILOT, plan.daily_cap_eur, first_live_approved=False)
    return owner_policy


def publish(plan: CampaignPlan, run_dir: Path, client: MarketingClient, owner_policy: Policy, *,
            objective: str, approved_by: str | None, activate: bool = False,
            now: datetime | None = None) -> PublishState:
    mode = "sandbox" if client.account.sandbox else "live"
    errors = validate(plan)
    if errors:
        raise PublishError("the plan is not valid: " + "; ".join(errors))
    payloads = to_api(plan, objective=objective)
    known = {k for k, v in (("{PAGE_ID}", client.account.page_id), ("{META_APP_ID}", client.account.app_id)) if v}
    missing = _unresolved(payloads, known)
    if missing:
        names = {"{PAGE_ID}": "META_PAGE_ID", "{META_APP_ID}": "META_APP_ID"}
        raise PublishError(f"missing ids for {sorted(missing)}: set {sorted(names[m] for m in missing)} in .env"
                           + (" (or publish with objective=traffic)" if "{META_APP_ID}" in missing else ""))

    state_path = run_dir / "publish.json"
    state = PublishState.load(state_path) or PublishState(mode, client.account.act, objective)
    if state.mode != mode or state.account != client.account.act or state.objective != objective:
        raise PublishError(f"this run was already published to {state.mode} {state.account} ({state.objective}); "
                           "refusing to mix accounts or objectives")
    stamp = (now or datetime.now(UTC)).isoformat()
    log = ActionLog(run_dir / "actions.jsonl")

    # 1. the autopilot decides, ad set by ad set
    policy = policy_for(mode, plan, owner_policy)
    running: dict[str, float] = {}
    allowed: set[int] = set()
    state.decisions = []
    for i, s in enumerate(plan.ad_sets):
        action = Action(Kind.PUBLISH, s.name, f"publish to {mode} {client.account.act}", s.daily_budget_eur,
                        all(a.guards_passed for a in s.ads))
        decision = decide(action, policy, AccountState(dict(running)), approved_by=approved_by)
        log.record(action, policy, decision, approved_by=approved_by)
        state.decisions.append({"ad_set": s.name, "outcome": decision.outcome.value, "why": decision.why})
        if decision.outcome is Outcome.EXECUTE:
            allowed.add(i)
            running[s.name] = s.daily_budget_eur
    state.approved_by = approved_by
    if not allowed:
        state.status = "refused"
        state.save(state_path)
        return state

    # 2. create, in dependency order, reusing anything already created
    mapping = {"{PAGE_ID}": client.account.page_id or "", "{META_APP_ID}": client.account.app_id or ""}

    def created(ref: str, object_id: str, kind: str) -> None:
        state.objects[ref] = object_id
        state.events.append({"ts": stamp, "ref": ref, "kind": kind, "id": object_id})
        state.save(state_path)

    try:
        for ad_set_index in sorted(allowed):
            for ad in plan.ad_sets[ad_set_index].ads:
                if ad.image_path not in state.images:
                    state.images[ad.image_path] = client.upload_image(run_dir / ad.image_path)
                    state.save(state_path)
        mapping |= {f"{{image:{p}}}": h for p, h in state.images.items()}

        if "campaign" not in state.objects:
            created("campaign", client.create_campaign(_fill(payloads["campaign"], mapping)), "campaign")
        mapping["{campaign}"] = state.objects["campaign"]
        state.campaign_url = client.ads_manager_url(state.objects["campaign"])

        allowed_refs = {f"adset_{i}" for i in allowed}
        for body in payloads["ad_sets"]:
            if body["ref"] in allowed_refs and body["ref"] not in state.objects:
                created(body["ref"], client.create_adset(_fill(body, mapping)), "adset")
        mapping |= {f"{{{r}}}": i for r, i in state.objects.items() if r.startswith("adset_")}

        for creative, ad in zip(payloads["creatives"], payloads["ads"], strict=True):
            if ad["adset_id"].strip("{}") not in allowed_refs:
                continue
            if creative["ref"] not in state.objects:
                created(creative["ref"], client.create_creative(_fill(creative, mapping)), "creative")
            mapping[f"{{{creative['ref']}}}"] = state.objects[creative["ref"]]
            if ad["ref"] not in state.objects:
                created(ad["ref"], client.create_ad(_fill(ad, mapping)), "ad")
    except Exception:
        state.status = "partial"
        state.save(state_path)
        raise

    state.status = "published"
    state.save(state_path)
    if activate:
        activate_published(state, client, run_dir)
    return state


def activate_published(state: PublishState, client: MarketingClient, run_dir: Path) -> PublishState:
    """Switch everything that was published to ACTIVE (ads, ad sets, then the campaign last)."""
    if state.status not in ("published", "active"):
        raise PublishError(f"nothing complete to activate (status: {state.status})")
    order = sorted(state.objects, key=lambda r: (r.startswith("campaign"), r.startswith("adset_")))
    for ref in order:
        if ref.startswith(("ad_", "adset_", "campaign")):
            client.set_status(state.objects[ref], "ACTIVE")
    state.status = "active"
    state.save(run_dir / "publish.json")
    return state
