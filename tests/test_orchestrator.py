"""The agency end to end: from an App Store link and a Meta connection to a running, reported campaign.

Runs the real orchestrator, the real `create` (fake App Store, Ad Library and models), the real publish and daily
loop, against a fake Graph API and a fake video studio. Checks what an owner relies on: nothing is sent in dry run,
approvals are needed and remembered, the account's cap holds for everything together, finished steps are never
paid twice, a failure stops the chain and resume continues it, no token is written anywhere.
"""

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fakes import make_settings
from test_daily import Producer
from test_publish import TOKEN, FakeGraph
from whynot.agency.orchestrator import (
    STEPS,
    AgencyConfig,
    Orchestrator,
    Services,
    StepContext,
    load_state,
)
from whynot.events import EventLog, total_usd
from whynot.models import ModelClient
from whynot.run.connect import MetaConnection
from whynot.run.meta import Account, MarketingClient
from world import clients

APP = "https://apps.apple.com/us/app/linguaapp/id1234567890"
DAY = date(2026, 11, 2)


class Launcher:
    """Records video ad launches on the real account (the fake Graph has no video endpoint)."""

    simulated = False
    paused_only = False

    def __init__(self):
        self.launched: list[tuple[str, float]] = []
        self.paused: list[str] = []

    def launch(self, rec, budget_eur):
        self.launched.append((rec.key, budget_eur))
        return f"ad-{rec.key}"

    def pause(self, rec):
        self.paused.append(rec.key)


class World:
    """Fake outside world for the orchestrator, with what each service was asked."""

    def __init__(self, tmp: Path, *, broken_studio: bool = False):
        self.tmp = tmp
        self.graph = FakeGraph()
        self.launcher = Launcher()
        self.producer = Producer()
        self.broken_studio = broken_studio
        self.checks = 0
        self.budgets: dict[str, float] = {}
        self.settings = make_settings(tmp)

    def create_clients(self, budget, run_dir):
        self.budgets["create"] = budget
        c, _, _ = clients(self.tmp, budget=budget)
        return c

    def model(self, budget, run_dir):
        self.budgets["daily"] = budget
        return ModelClient(self.settings, budget_usd=budget)

    def marketing(self, conn: MetaConnection):
        return MarketingClient(Account(conn.account_id, conn.token, page_id=conn.page_id, app_id=conn.app_id,
                                       sandbox=conn.sandbox),
                               http=httpx.Client(transport=httpx.MockTransport(self.graph)), sleep=lambda s: None)

    def studio(self, run_dir, model):
        if self.broken_studio:
            raise RuntimeError("trend videos need Remotion: run `cd video && npm install`")
        return self.producer

    def check(self, conn):
        self.checks += 1
        return []

    def services(self) -> Services:
        return Services(self.settings, self.create_clients, self.model, self.marketing, self.studio, self.check,
                        launcher=self.make_launcher)

    def make_launcher(self, client, run_dir, *, objective, say, paused_only=False, link=None):
        self.launcher.paused_only = paused_only
        self.launcher.objective, self.launcher.link = objective, link
        return self.launcher


def connection(tmp: Path, *, sandbox=False, page="999", perms=("ads_management", "ads_read"), app_id="777",
               expires_at=None) -> str:
    # app_id: the app registered with Meta (App Store links need the app_promotion objective)
    conn = MetaConnection(TOKEN, "123456", "Owner's account", "EUR", page, "Page" if page else None, app_id, "Owner",
                          list(perms), sandbox, [] if page else ["no Facebook Page you can advertise with"],
                          expires_at=expires_at)
    return str(conn.save(tmp / "connections"))


def cfg(**kw) -> AgencyConfig:
    base = dict(app_ref=APP, countries=["FR", "GB"], daily_cap_eur=20.0, budget_usd=10.0, objective="app_promotion")
    return AgencyConfig(**{**base, **kw})


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """One simulated-account agency run (the expensive `create` runs once for the whole module)."""
    tmp = tmp_path_factory.mktemp("agency")
    world = World(tmp)
    orch = Orchestrator(tmp / "run", cfg(simulated_account=True), world.services())
    result = orch.run(today=DAY, say=lambda m: None)
    return tmp, world, orch, result


def fork(base, tmp_path: Path) -> Path:
    """A copy of the base run's `create` outputs, without the agency's state: a fresh agency over them."""
    src = base[0] / "run"
    dst = tmp_path / "run"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("agency", "events.jsonl"))
    return dst


def quiet(orch, **kw):
    return orch.run(say=lambda m: None, **kw)


# --- simulated account: the whole chain in one command ------------------------------------------

def test_one_command_runs_every_step_on_the_simulated_account(base):
    _tmp, world, orch, result = base
    assert result.status == "done", result.error
    assert [k for k in result.steps] == ["connect", "create", "publish", f"daily {DAY}"]
    assert [r["status"] for r in result.steps.values()] == ["skipped", "ok", "skipped", "ok"]
    daily = result.steps[f"daily {DAY}"]["outputs"]
    assert daily["simulated"] and daily["new"] == 2 and daily["live"] == 2
    report = (orch.run_dir / daily["report"]).read_text()
    assert "SIMULATED account" in report
    state = load_state(orch.run_dir)
    assert state["steps"]["create"]["status"] == "ok" and str(DAY) in state["days"]
    assert world.graph.calls == [] and world.checks == 0  # nothing sent to Meta, no login needed


def test_every_agent_step_is_in_one_event_log_with_its_parent(base):
    _, _, orch, _ = base
    rows = EventLog(orch.run_dir / "events.jsonl").rows()
    starts = {r["stage"]: r for r in rows if r["status"] == "start" and r.get("agent") in
              ("connector", "agency", "publisher", "media_buyer")}
    assert set(starts) == set(STEPS)
    stages = [r for r in rows if r.get("parent") == starts["create"]["id"]]
    assert {r["agent"] for r in stages} >= {"scout", "strategist", "director", "composer", "viewers", "planner"}
    produce = next(r for r in stages if r["stage"] == "produce" and r["status"] == "ok")
    assert produce["guards"]["passed"] > 0 and "variants.json" in produce["outputs"]
    # the create step's own end event is a roll-up: total spend counts each dollar once
    create_end = next(r for r in rows if r["stage"] == "create" and r["status"] == "ok" and r.get("rollup"))
    inner = sum(float(r.get("usd") or 0) for r in stages if r["status"] in ("ok", "error"))
    assert create_end["usd"] == pytest.approx(inner, abs=1e-3)
    assert total_usd(rows) == pytest.approx(inner + sum(
        float(r.get("usd") or 0) for r in rows if r["stage"] == "daily" and r["status"] == "ok"), abs=1e-3)


def test_resume_the_same_day_redoes_and_pays_nothing(base, tmp_path):
    _tmp, world, orch, _first = base
    again = Orchestrator.resume(orch.run_dir, world.services())
    calls = len(world.producer.calls)
    result = quiet(again, today=DAY)
    assert result.usd == 0 and result.status == "done"
    assert result.steps["create"]["status"] == "cached" and result.steps[f"daily {DAY}"]["status"] == "cached"
    assert len(world.producer.calls) == calls


def test_the_next_day_only_runs_the_daily_loop(base, tmp_path):
    _, world, _, _ = base
    run = tmp_path / "copy"
    shutil.copytree(base[2].run_dir, run)
    orch = Orchestrator.resume(run, world.services())
    result = quiet(orch, today=DAY + timedelta(days=1))
    assert result.steps["create"]["status"] == "cached"
    assert result.steps[f"daily {DAY + timedelta(days=1)}"]["status"] == "ok"
    assert len(load_state(run)["days"]) == 2


def test_a_simulated_week_keeps_every_day_under_the_cap(base, tmp_path):
    world = World(tmp_path)
    orch = Orchestrator(fork(base, tmp_path), cfg(simulated_account=True, daily_cap_eur=15.0), world.services())
    result = quiet(orch, today=DAY, days=5)
    days = [r["outputs"] for k, r in result.steps.items() if k.startswith("daily")]
    assert len(days) == 5 and all(d["committed_eur"] <= 15.0 for d in days)
    assert any(d["paused"] for d in days) or days[-1]["live"] <= 3


# --- the real account: dry run, approvals, the cap -----------------------------------------------

def test_dry_run_on_a_real_account_sends_nothing_to_meta(base, tmp_path):
    world = World(tmp_path)
    orch = Orchestrator(fork(base, tmp_path), cfg(connection=connection(tmp_path)), world.services())
    result = quiet(orch, today=DAY)
    assert result.status == "done" and world.checks == 1
    assert result.steps["publish"]["status"] == "skipped" and "dry run" in result.steps["publish"]["detail"]
    daily = result.steps[f"daily {DAY}"]["outputs"]
    assert daily["live"] == 0 and daily["waiting_approval"] == 2
    assert world.graph.calls == [] and world.launcher.launched == []


def test_autopilot_waits_for_the_first_approval_then_remembers_it(base, tmp_path):
    world = World(tmp_path)
    conn = connection(tmp_path)
    orch = Orchestrator(fork(base, tmp_path), cfg(connection=conn, level="autopilot"), world.services())
    first = quiet(orch, today=DAY)
    assert first.status == "waiting"
    assert first.steps["publish"]["status"] == "waiting" and "--approve" in first.steps["publish"]["detail"]
    assert first.steps[f"daily {DAY}"]["outputs"]["waiting_approval"] == 2  # the day still ran: ads proposed
    assert world.graph.objects == {} and world.launcher.launched == []

    # the owner approves: static campaign published and activated, the waiting video ads launched
    second = Orchestrator.resume(orch.run_dir, world.services())
    result = quiet(second, today=DAY, approved_by="Matteo")
    assert result.status == "done", result.error
    pub = result.steps["publish"]["outputs"]
    assert pub["status"] == "active" and pub["campaign"] in world.graph.objects
    state = load_state(orch.run_dir)
    assert state["first_live_approved_by"] == "Matteo"
    # the day was already done; its waiting ads launch on the next day, now without asking again
    nxt = quiet(Orchestrator.resume(orch.run_dir, world.services()), today=DAY + timedelta(days=1))
    assert nxt.status == "done" and world.launcher.launched
    static = state["static_committed_eur"]
    video = sum(b for _, b in world.launcher.launched)
    assert 0 < static <= 10.0 and static + video <= 20.0 + 1e-9  # the account's cap holds for both together


def test_propose_mode_needs_an_approval_for_every_day(base, tmp_path):
    world = World(tmp_path)
    orch = Orchestrator(fork(base, tmp_path), cfg(connection=connection(tmp_path), level="propose",
                                                  publish_static=False), world.services())
    result = quiet(orch, today=DAY, approved_by="Matteo")
    assert result.steps["publish"]["status"] == "skipped"  # video ads only
    assert len(world.launcher.launched) == 2 and all(b == 5.0 for _, b in world.launcher.launched)
    nxt = quiet(Orchestrator.resume(orch.run_dir, world.services()), today=DAY + timedelta(days=1))
    assert nxt.steps[f"daily {DAY + timedelta(days=1)}"]["outputs"]["waiting_approval"] >= 1
    assert len(world.launcher.launched) == 2  # no approval today: nothing new launched


def test_a_connection_without_a_page_cannot_publish(base, tmp_path):
    world = World(tmp_path)
    orch = Orchestrator(fork(base, tmp_path), cfg(connection=connection(tmp_path, page=None), level="autopilot"),
                        world.services())
    result = quiet(orch, today=DAY, approved_by="Matteo")
    assert result.status == "error" and "cannot publish" in result.error
    assert f"daily {DAY}" not in result.steps  # an error stops the chain


def test_a_revoked_login_stops_everything_before_any_spend(base, tmp_path):
    world = World(tmp_path)
    world.check = lambda conn: ["Meta error 190: the login expired or was revoked"]
    orch = Orchestrator(fork(base, tmp_path), cfg(connection=connection(tmp_path)), world.services())
    result = quiet(orch, today=DAY)
    assert result.status == "error" and "reconnect" in result.error and list(result.steps) == ["connect"]


# --- failures, resume, budgets -------------------------------------------------------------------

def test_a_failed_step_is_recorded_and_resume_continues_after_the_fix(base, tmp_path):
    world = World(tmp_path, broken_studio=True)
    run = fork(base, tmp_path)
    result = quiet(Orchestrator(run, cfg(simulated_account=True), world.services()), today=DAY)
    assert result.status == "error" and "Remotion" in result.error
    assert load_state(run)["days"][str(DAY)]["status"] == "error"
    world.broken_studio = False
    again = quiet(Orchestrator.resume(run, world.services()), today=DAY)
    assert again.status == "done" and again.steps["create"]["status"] == "cached"
    assert again.steps[f"daily {DAY}"]["status"] == "ok"


def test_create_failing_on_its_budget_names_the_stage(tmp_path):
    world = World(tmp_path)
    orch = Orchestrator(tmp_path / "run", cfg(simulated_account=True, budget_usd=0.0), world.services())
    result = quiet(orch, today=DAY)
    assert result.status == "error" and "BudgetExceeded" in result.error
    assert load_state(orch.run_dir)["steps"]["create"]["stage"] == "market"  # the first stage calling a model


def fake_steps(spend: dict[str, float], seen: dict[str, float]):
    def make(name):
        def run(ctx: StepContext):
            seen[name] = ctx.budget_usd
            ctx.spent_usd = min(spend.get(name, 0.0), ctx.budget_usd)
            return {"ok": name}
        return run
    return {s: make(s) for s in STEPS}


@settings(max_examples=40, deadline=None)
@given(total=st.floats(0, 10), caps=st.dictionaries(st.sampled_from(["create", "daily"]), st.floats(0, 10)),
       spend=st.dictionaries(st.sampled_from(list(STEPS)), st.floats(0, 10)))
def test_property_no_step_gets_more_than_its_cap_or_what_is_left(tmp_path_factory, total, caps, spend):
    tmp = tmp_path_factory.mktemp("budget")
    seen: dict[str, float] = {}
    c = cfg(simulated_account=True, budget_usd=total, step_budgets_usd=caps)
    result = Orchestrator(tmp / "run", c, World(tmp).services(), steps=fake_steps(spend, seen)).run(
        today=DAY, say=lambda m: None)
    left = total
    for step in STEPS:
        assert seen[step] <= caps.get(step, total) + 1e-9 and seen[step] <= left + 1e-9
        left -= min(spend.get(step, 0.0), seen[step])
    assert result.usd <= round(total, 4) + 1e-4  # the result is rounded to 4 decimals


# --- config and secrets --------------------------------------------------------------------------

def test_bad_configs_are_refused_before_anything_runs(tmp_path):
    with pytest.raises(ValueError, match="needs a Meta connection"):
        cfg()
    with pytest.raises(ValueError):
        cfg(simulated_account=True, level="yolo")
    with pytest.raises(ValueError, match="static_share"):
        cfg(simulated_account=True, static_share=1.5)
    orch = Orchestrator(tmp_path / "run", cfg(connection=connection(tmp_path)), World(tmp_path).services())
    with pytest.raises(ValueError, match="simulated account only"):
        orch.run(days=3, say=lambda m: None)


def test_the_meta_token_is_written_nowhere_in_the_run(base, tmp_path):
    world = World(tmp_path)
    run = fork(base, tmp_path)
    orch = Orchestrator(run, cfg(connection=connection(tmp_path), level="autopilot"), world.services())
    quiet(orch, today=DAY, approved_by="Matteo")
    state = load_state(run)
    assert state["account"]["act"] == "act_123456" and "token" not in state["account"]
    for f in run.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".jsonl", ".md", ".yaml"):
            assert TOKEN not in f.read_text(errors="ignore"), f
    assert json.loads(Path(connection(tmp_path)).read_text())["token"] == TOKEN  # only in the private file


# --- the commands ------------------------------------------------------------------------------

def test_cli_agency_runs_resumes_and_says_what_next(base, tmp_path, monkeypatch, capsys):
    from whynot import cli
    from whynot.agency import orchestrator

    world = World(tmp_path)
    monkeypatch.setattr(orchestrator, "default_services", lambda s, silent=False: world.services())
    run = fork(base, tmp_path)
    Orchestrator(run, cfg(simulated_account=True), world.services()).save()
    assert cli.main(["agency", "--resume", str(run), "--start", str(DAY)]) == 0
    out = capsys.readouterr().out
    assert "SIMULATED" in out and "agency done" in out and f"--resume {run}" in out
    assert cli.main(["agency", "--sim"]) == 1  # a new run needs the link, countries and cap
    assert "needs: the App Store link" in capsys.readouterr().err


def test_cli_connect_reads_the_token_from_stdin_never_argv(tmp_path, monkeypatch, capsys):
    import io

    from whynot import cli
    from whynot.run import connect as connect_mod

    seen = {}

    def fake_connect(token, **kw):
        seen["token"] = token
        conn = MetaConnection(token, "123456", "Acct", "EUR", "999", "Page", None, "Owner",
                              ["ads_management", "ads_read"])
        return conn, conn.save(tmp_path)

    monkeypatch.setattr(connect_mod, "connect", fake_connect)
    monkeypatch.setattr("sys.stdin", io.StringIO(TOKEN + "\n"))
    assert cli.main(["connect", "--token-stdin"]) == 0
    out = capsys.readouterr().out
    assert seen["token"] == TOKEN and TOKEN not in out and "act_123456" in out and "whynot agency" in out


def test_the_simulated_account_plans_with_the_whole_cap_and_says_autopilot():
    sim = cfg(simulated_account=True, level="dry_run")
    assert sim.static_cap_eur == 20.0 and sim.effective_level == "autopilot"
    real = cfg(connection="x.json", level="dry_run")
    assert real.static_cap_eur == 10.0 and real.effective_level == "dry_run"
    assert cfg(connection="x.json", publish_static=False).static_cap_eur == 20.0



def test_paused_test_mode_creates_everything_on_meta_and_activates_nothing(base, tmp_path):
    """The first test on a real ad account: objects exist in Ads Manager, all PAUSED, nothing can spend."""
    world = World(tmp_path)
    run = fork(base, tmp_path)
    orch = Orchestrator(run, cfg(connection=connection(tmp_path), level="autopilot", paused_only=True),
                        world.services())
    result = quiet(orch, today=DAY, approved_by="Matteo")
    assert result.status == "done", result.error
    pub = result.steps["publish"]["outputs"]
    assert pub["status"] == "published" and pub["committed_eur"] == 0.0 and pub["paused_only"]
    statuses = {o.get("status") for o in world.graph.objects.values() if o["kind"] in ("campaigns", "adsets", "ads")}
    assert statuses == {"PAUSED"}  # created PAUSED ...
    assert not any(f.get("status") == "ACTIVE" for _, _, f in world.graph.calls)  # ... and never switched on
    daily = result.steps[f"daily {DAY}"]["outputs"]
    assert daily["live"] == 0 and daily["published_paused"] == 2 and daily["committed_eur"] == 0
    assert len(world.launcher.launched) == 2 and world.launcher.paused_only
    state = load_state(run)
    assert "first_live_approved_by" not in state  # a paused test is not the owner's first live launch
    report = (run / "agency" / "reports" / f"{DAY}.md").read_text()
    assert "Published PAUSED (test mode" in report



# --- Meta, automatically: the right objective, the login renewed ----------------------------------

def test_auto_uses_app_installs_when_the_app_is_registered_with_meta(base, tmp_path):
    world = World(tmp_path)
    orch = Orchestrator(fork(base, tmp_path), cfg(connection=connection(tmp_path), level="autopilot", objective="auto",
                                                  paused_only=True), world.services())
    result = quiet(orch, today=DAY, approved_by="Matteo")
    assert result.status == "done", result.error
    assert result.steps["connect"]["outputs"]["objective"] == "app_promotion"
    camp = next(o for o in world.graph.objects.values() if o["kind"] == "campaigns")
    assert camp["objective"] == "OUTCOME_APP_PROMOTION"


def test_auto_without_an_app_id_sends_traffic_to_the_website(base, tmp_path):
    """Meta refuses App Store links outside app installs (error 1487810, seen on a real account)."""
    world = World(tmp_path)
    orch = Orchestrator(fork(base, tmp_path), cfg(connection=connection(tmp_path, app_id=None), level="autopilot",
                                                  objective="auto", landing_url="https://linguaapp.example",
                                                  paused_only=True), world.services())
    result = quiet(orch, today=DAY, approved_by="Matteo")
    assert result.status == "done", result.error
    camp = next(o for o in world.graph.objects.values() if o["kind"] == "campaigns")
    assert camp["objective"] == "OUTCOME_TRAFFIC"
    links = {json.loads(o["object_story_spec"])["link_data"]["link"] for o in world.graph.objects.values()
             if o["kind"] == "adcreatives"}
    assert links == {"https://linguaapp.example"}
    assert world.launcher.objective == "traffic" and world.launcher.link == "https://linguaapp.example"


def test_no_app_id_and_no_website_stops_before_paying_for_research(tmp_path):
    world = World(tmp_path)
    orch = Orchestrator(tmp_path / "run", cfg(connection=connection(tmp_path, app_id=None), objective="auto"),
                        world.services())
    result = quiet(orch, today=DAY)
    assert result.status == "error" and "--landing-url" in result.error
    assert list(result.steps) == ["connect"] and "create" not in world.budgets  # nothing spent


def test_a_login_close_to_its_end_is_renewed_before_acting(base, tmp_path):
    from datetime import UTC, datetime, timedelta

    world = World(tmp_path)
    soon = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    renewed = []

    def refresh(conn):
        conn.expires_at = (datetime.now(UTC) + timedelta(days=60)).isoformat()
        renewed.append(conn.act)
        return conn

    services = world.services()
    services.refresh_connection = refresh
    orch = Orchestrator(fork(base, tmp_path), cfg(connection=connection(tmp_path, expires_at=soon)), services)
    result = quiet(orch, today=DAY)
    assert renewed == ["act_123456"] and result.steps["connect"]["outputs"]["renewed"]
    assert not any("ends in" in w for w in result.steps["connect"]["outputs"]["warnings"])


def test_an_expired_login_stops_everything(tmp_path):
    from datetime import UTC, datetime, timedelta

    world = World(tmp_path)
    world.check = lambda conn: ["the Meta login has expired: connect again"] if conn.days_left() < 0 else []
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    orch = Orchestrator(tmp_path / "run", cfg(connection=connection(tmp_path, expires_at=past)), world.services())
    result = quiet(orch, today=DAY)
    assert result.status == "error" and "expired" in result.error


def test_cli_status_and_agency_speak_json_for_the_site(base, tmp_path, monkeypatch, capsys):
    from whynot import cli
    from whynot.agency import orchestrator

    world = World(tmp_path)
    monkeypatch.setattr(orchestrator, "default_services", lambda s, silent=False: world.services())
    run = fork(base, tmp_path)
    Orchestrator(run, cfg(simulated_account=True), world.services()).save()
    assert cli.main(["agency", "--resume", str(run), "--start", str(DAY), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["status"] == "done" and f"daily {DAY}" in out["steps"]
    assert cli.main(["status", str(run), "--json"]) == 0
    state = json.loads(capsys.readouterr().out)
    assert state["ok"] and str(DAY) in state["days"] and TOKEN not in json.dumps(state)
