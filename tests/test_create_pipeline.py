"""End-to-end: `create` on a fake world, then the properties a real client relies on.

Not unit tests: the whole pipeline runs (App Store → Ad Library → strategy →
templates → images → guards → simulated feeds → campaign plan → report) with
the real model client, and we check the outputs as an auditor would.
"""

import json

import pytest
from PIL import Image

from strategy_fixture import APP
from whynot.agency.create import STAGES, CreateConfig, StageError, create
from whynot.create.composer import compose
from whynot.create.templates import Template
from whynot.models import BudgetExceeded
from whynot.run.autopilot import Level, Policy
from world import TOKEN, FakeMeta, Http, clients, default_reply

CFG = dict(app_ref="https://apps.apple.com/us/app/linguaapp/id1234567890", countries=["FR", "GB"], daily_cap_eur=20.0)


@pytest.fixture(scope="module")
def done(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    c, meta, http = clients(tmp)
    result = create(CreateConfig(**CFG), c, tmp / "run")
    return result, meta, http, tmp / "run"


def files(run):
    return [p for p in run.rglob("*") if p.is_file()]


def test_every_stage_ran_once_and_left_its_output(done):
    _result, _, _, run = done
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    assert [e["stage"] for e in events if e["status"] == "ok"] == list(STAGES)
    for name in ["app.json", "brand.json", "market.json", "market_ads.jsonl", "strategy.json", "variants.json",
                 "simulation.json", "plan.json", "meta_api_payloads.json", "launch.json", "report.md"]:
        assert (run / name).exists(), name
    # FR + GB: English templates for every persona reaching GB, French ones for personas reaching FR
    names = sorted(p.stem for p in (run / "templates").glob("*.yaml"))
    assert len([n for n in names if n.endswith("_en_v1")]) == 4 and len([n for n in names if n.endswith("_fr_v1")]) == 2


def test_the_plan_is_valid_within_the_cap_and_paused(done):
    result, _, _, run = done
    assert result.plan_errors == []
    assert 0 < result.plan.daily_total_eur <= 20.0
    assert {s.audience.persona for s in result.plan.ad_sets} == {"heritage_learner.en", "heritage_learner.fr",
                                                                  "busy_traveller.en"}
    assert all(s.name.startswith("Profile ") for s in result.plan.ad_sets)  # no persona labels in the ad account
    api = json.loads((run / "meta_api_payloads.json").read_text())
    assert {x["status"] for x in [api["campaign"], *api["ad_sets"], *api["ads"]]} == {"PAUSED"}
    assert sum(x["daily_budget"] for x in api["ad_sets"]) <= 2000


def test_every_planned_ad_is_real_reproducible_and_checked(done):
    """Each ad image exists, is exactly what the composer makes from its template and the real screenshot,
    and passed every guard."""
    result, _, _, run = done
    variants = {v["variant_id"]: v for v in json.loads((run / "variants.json").read_text())}
    templates = {t.id: t for t in (Template.load(p) for p in (run / "templates").glob("*.yaml"))}
    assert result.choices
    for ad in result.choices:
        v = variants[ad.variant_id]
        assert v["guards_passed"] and all(g["passed"] is True for g in v["guards"].values())
        saved = Image.open(run / ad.image_path)
        assert saved.size == (1080, 1080)
        t = templates[ad.template_id]
        again = compose(t, v["genome"], Image.open(run / "assets" / t.fixed["product"]["asset"]))
        assert again.image.tobytes() == saved.convert("RGB").tobytes()
        assert ad.persona == f"{t.persona}.{t.fixed['language']}"


def test_competitor_research_drops_noise_and_feeds_the_simulator(done):
    _, meta, _, run = done
    market = json.loads((run / "market.json").read_text())
    assert {c["page_id"] for c in market["competitors"]} == {"p1", "p2"}
    assert [r["page_id"] for r in market["rejected"]] == ["spam"]
    ads = (run / "market_ads.jsonl").read_text()
    assert "iPhone" not in ads and "900" in ads and "903" in ads  # inactive ads kept for longevity
    sim = json.loads((run / "simulation.json").read_text())
    assert sim["simulated"] and not sim["failures"] and sim["scores"]
    viewer_feeds = [r for r in meta.requests if r["messages"][0]["role"] == "system"]
    assert all("Rival Lingo" in r["messages"][1]["content"] or "Other App" in r["messages"][1]["content"]
               for r in viewer_feeds)


def test_no_token_and_no_reviewer_identity_leaks_into_the_run(done):
    _, _, _, run = done
    for p in files(run):
        if p.suffix in {".json", ".jsonl", ".md", ".yaml"}:
            text = p.read_text()
            assert TOKEN not in text and "access_token" not in text, p.name


def test_costs_are_logged_per_agent_and_match_the_report(done):
    result, meta, _, run = done
    ledger = [json.loads(line) for line in (run / "costs.jsonl").read_text().splitlines()]
    assert {e["module"] for e in ledger} == {"scout", "strategy", "director", "viewers", "evolver"}
    assert len(ledger) == len(meta.requests)
    assert result.usd == pytest.approx(sum(e["usd"] for e in ledger), abs=1e-3)
    assert {e["model"] for e in ledger if e["module"] == "strategy"} == {"muse-wonder-1.0"}
    assert f"${result.usd:.2f}" in (run / "report.md").read_text()


def test_report_is_honest_about_what_is_simulated_and_not_launched(done):
    _, _, _, run = done
    report = (run / "report.md").read_text()
    assert "Status: not launched" in report and "(SIMULATED)" in report
    assert "“The app doesn't hear you correctly” (review:101)" in report
    assert "Heritage learner (French)" in report and "€6.66/day" in report
    assert "Launch: **refused**" in report  # default policy: dry run with a €0 live cap
    for line in report.splitlines():
        if line.startswith("![") and "](" in line:
            assert (run / line.split("](")[1].rstrip(")")).exists()


def test_resume_reuses_every_stage_without_new_calls(done, tmp_path):
    result, _, _, run = done

    def no_calls(model, messages):
        raise AssertionError("resume must not call the model")

    c, meta, http = clients(tmp_path, meta=FakeMeta(no_calls))
    again = create(CreateConfig(**CFG), c, run)
    assert meta.requests == [] and http.calls == []
    assert again.plan.to_json() == result.plan.to_json()


def test_redo_from_creative_reuses_research_and_replaces_the_ads(done, tmp_path):
    import shutil

    _, _, _, original = done
    run = tmp_path / "copy"
    shutil.copytree(original, run)
    c, meta, http = clients(tmp_path)
    create(CreateConfig(**CFG), c, run, redo_from="creative")
    modules = {r["messages"][0]["role"] for r in meta.requests}
    assert http.calls == [] and modules  # no App Store / Ad Library calls
    assert not any(r["model"] == "muse-wonder-1.0" for r in meta.requests)  # strategy reused, not re-billed
    assert any("creative director" in str(r["messages"][0]["content"]) for r in meta.requests)
    pngs = {p.name for p in (run / "ads").glob("*.png")}
    listed = {v["image"].split("/")[1] for v in json.loads((run / "variants.json").read_text()) if v.get("image")}
    assert pngs == listed  # no stale images left from the previous set
    with pytest.raises(ValueError, match="unknown stage"):
        create(CreateConfig(**CFG), c, run, redo_from="everything")


# --- when things go wrong -------------------------------------------------------------

def test_hallucinating_strategist_stops_the_run_then_resume_finishes(tmp_path):
    def liar(model, messages):
        text = default_reply(model, messages)
        if "You are the strategist" in str(messages[-1]["content"]) or model == "muse-wonder-1.0":
            data = json.loads(text)
            data["claims"][0]["evidence"]["quote"] = "Used by 2 million learners"
            return json.dumps(data)
        return text

    c, meta, _http = clients(tmp_path, meta=FakeMeta(liar))
    with pytest.raises(StageError) as exc:
        create(CreateConfig(**CFG), c, tmp_path / "run")
    assert exc.value.stage == "strategy"
    assert sum(r["model"] == "muse-wonder-1.0" for r in meta.requests) == 4  # tried, repaired 3 times, refused
    events = (tmp_path / "run" / "events.jsonl").read_text()
    assert '"stage": "strategy", "status": "error"' in events and "not verbatim" in events
    assert not (tmp_path / "run" / "strategy.json").exists()

    c2, meta2, http2 = clients(tmp_path)
    result = create(CreateConfig(**CFG), c2, tmp_path / "run")
    assert result.plan_errors == []
    assert "itunes.apple.com" not in http2.calls and "graph.facebook.com" not in http2.calls  # app + market reused
    assert not any("search terms" in str(r["messages"][-1]["content"]) for r in meta2.requests)


def test_model_budget_stops_the_run_cleanly(tmp_path):
    c, meta, _ = clients(tmp_path, budget=0.0001)
    with pytest.raises(StageError) as exc:
        create(CreateConfig(**CFG), c, tmp_path / "run")
    assert isinstance(exc.value.cause, BudgetExceeded) and exc.value.stage == "market"
    assert len(meta.requests) == 1  # one call, then nothing


def test_without_competitor_ads_the_plan_says_it_was_not_simulated(tmp_path):
    def no_ad_evidence(model, messages):
        text = default_reply(model, messages)
        if model != "muse-wonder-1.0":
            return text
        data = json.loads(text)  # with no market ads, a valid strategy can only cite reviews and the store
        data["objections"][2]["evidence"] = [{"ref": "review:103", "quote": "Five minutes a day fits my commute"}]
        data["angles"][3]["evidence"] = [{"ref": "store", "quote": "Free to start"}]
        return json.dumps(data)

    c, _, _ = clients(tmp_path, meta=FakeMeta(no_ad_evidence), http=Http(ad_library={}))
    result = create(CreateConfig(**CFG), c, tmp_path / "run")
    sim = json.loads((tmp_path / "run" / "simulation.json").read_text())
    assert sim["simulated"] is False
    assert any("NOT simulated" in n for n in result.plan.notes)
    assert "Not simulated" in (tmp_path / "run" / "report.md").read_text()


def test_broken_viewers_are_counted_not_guessed(tmp_path):
    def broken_viewers(model, messages):
        if messages[0]["role"] == "system":
            return "I'd rather not say."
        return default_reply(model, messages)

    c, _, _ = clients(tmp_path, meta=FakeMeta(broken_viewers))
    result = create(CreateConfig(**CFG), c, tmp_path / "run")
    sim = json.loads((tmp_path / "run" / "simulation.json").read_text())
    assert sim["failures"] and sim["scores"] == {}
    assert result.plan_errors == []  # the plan still holds; ranking falls back to neutral


def test_us_campaign_researches_the_market_in_europe(tmp_path):
    """The partner case: ads target the US, the Ad Library only shows EU/UK, so research runs on GB."""
    import strategy_fixture

    def us_strategy(model, messages):
        text = default_reply(model, messages)
        if model == "muse-wonder-1.0":
            data = json.loads(text)
            for p in data["personas"]:
                p["countries"] = ["US"]
            return json.dumps(data)
        return text

    c, _, _http = clients(tmp_path, meta=FakeMeta(us_strategy))
    result = create(CreateConfig(**{**CFG, "countries": ["US"]}), c, tmp_path / "run")
    market = json.loads((tmp_path / "run" / "market.json").read_text())
    assert market["research_countries"] == ["GB"]
    assert all(s.audience.countries == ("US",) for s in result.plan.ad_sets)
    assert strategy_fixture.APP.name == APP.name


def test_app_without_screenshots_is_refused(tmp_path, monkeypatch):
    import world

    monkeypatch.setattr(world, "SHOTS", [])
    c, _, _ = clients(tmp_path)
    with pytest.raises(StageError, match="no screenshots"):
        create(CreateConfig(**CFG), c, tmp_path / "run")


def test_each_ad_set_speaks_the_language_of_its_countries(done):
    """Bug found on the Flighty run: French audiences got English ads."""
    from whynot.create.locale import language_of

    result, meta, _, run = done
    variants = {v["variant_id"]: v for v in json.loads((run / "variants.json").read_text())}
    for s in result.plan.ad_sets:
        langs = {language_of(c) for c in s.audience.countries}
        assert len(langs) == 1, s.audience.countries
        assert {variants[a.variant_id]["language"] for a in s.ads} == langs
    director_prompts = [r["messages"][0]["content"] for r in meta.requests
                        if "creative director" in str(r["messages"][0]["content"])]
    assert {p.split("- Language: ")[1].split(".")[0] for p in director_prompts} == {"English", "French"}


def test_forced_language_gives_one_set_for_all_countries(tmp_path):
    c, _, _ = clients(tmp_path)
    result = create(CreateConfig(**CFG, language="en"), c, tmp_path / "run")
    assert all(p.stem.endswith("_en_v1") for p in (tmp_path / "run" / "templates").glob("*.yaml"))
    assert {s.audience.persona for s in result.plan.ad_sets} == {"heritage_learner.en", "busy_traveller.en"}


def test_live_policy_turns_the_plan_into_approval_requests(tmp_path):
    c, _, _ = clients(tmp_path)
    cfg = CreateConfig(**CFG, policy=Policy(Level.AUTOPILOT, 20.0, first_live_approved=False))
    create(cfg, c, tmp_path / "run")
    launch = json.loads((tmp_path / "run" / "launch.json").read_text())
    assert {x["outcome"] for x in launch} == {"needs_approval"}


# --- the command a client runs ---------------------------------------------------------

def test_cli_create_end_to_end(tmp_path, monkeypatch, capsys):
    import whynot.agency.create as pipeline
    from whynot.cli import main

    c, _, _ = clients(tmp_path)
    monkeypatch.setattr(pipeline, "default_clients", lambda budget, run_dir: c)
    monkeypatch.setenv("AUTONOMY_LEVEL", "dry_run")
    monkeypatch.setenv("MAX_DAILY_AD_SPEND_EUR", "0")
    code = main(["create", CFG["app_ref"], "--countries", "FR", "GB", "--daily-cap", "20",
                 "--out", str(tmp_path / "runs")])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "3 ad set(s)" in out and "PAUSED, not launched" in out and "report.md" in out
    run_dir = next((tmp_path / "runs").iterdir())
    assert (run_dir / "report.md").exists()


def test_cli_reports_a_failed_stage_and_how_to_resume(tmp_path, monkeypatch, capsys):
    import whynot.agency.create as pipeline
    from whynot.cli import main

    c, _, _ = clients(tmp_path, budget=0.0001)
    monkeypatch.setattr(pipeline, "default_clients", lambda budget, run_dir: c)
    code = main(["create", CFG["app_ref"], "--countries", "FR", "--daily-cap", "20",
                 "--out", str(tmp_path / "runs")])
    err = capsys.readouterr().err
    assert code == 1 and "stage 'market' failed" in err and "--resume" in err


# --- simulator bias (found on real runs: the advertiser name alone won the feed) -----------

def test_fair_viewers_rank_by_content_and_placebos_stay_low(done):
    _, _, _, run = done
    sim = json.loads((run / "simulation.json").read_text())
    assert sim["brand"] == "LinguaApp"  # page-style name, not "LinguaApp: Learn Vietnamese"
    assert sim["groups"] and not any(g["biased"] for g in sim["groups"])
    variants = {v["variant_id"]: v for v in json.loads((run / "variants.json").read_text())}
    family = [s["lift_over_placebo"] for k, s in sim["scores"].items()
              if "famil" in variants[k]["texts"]["hook"].lower()]
    other = [s["lift_over_placebo"] for k, s in sim["scores"].items()
             if "famil" not in variants[k]["texts"]["hook"].lower()]
    assert family and other and min(family) > max(other)  # the ads that answer the need win, and only those


def test_viewers_are_never_handed_the_objections(done):
    _, meta, _, _ = done
    systems = [r["messages"][0]["content"] for r in meta.requests if r["messages"][0]["role"] == "system"]
    assert systems and not any("hesitates" in s or "Will it even understand me" in s for s in systems)


def test_a_name_biased_simulator_is_flagged_in_the_plan_and_report(tmp_path):
    from world import name_biased_viewer

    def biased(model, messages):
        if messages[0]["role"] == "system":
            return name_biased_viewer(messages[1]["content"])
        return default_reply(model, messages)

    c, _, _ = clients(tmp_path, meta=FakeMeta(biased))
    result = create(CreateConfig(**CFG), c, tmp_path / "run")
    sim = json.loads((tmp_path / "run" / "simulation.json").read_text())
    assert all(g["biased"] for g in sim["groups"])
    assert any("simulator bias" in n for n in result.plan.notes)
    report = (tmp_path / "run" / "report.md").read_text()
    assert "⚠ biased: rank within audience only" in report and "placebo also won here" in report


# --- evolution -----------------------------------------------------------------------------

def test_evolution_improves_the_ads_and_keeps_the_lineage(done):
    """In the fair world viewers want 'family': the evolver adds it, and the children must win their round."""
    result, _, _, run = done
    evo = json.loads((run / "evolution.json").read_text())
    variants = {v["variant_id"]: v for v in json.loads((run / "variants.json").read_text())}
    assert evo["groups"] and evo["usd"] > 0
    improved = 0
    for g in evo["groups"]:
        gens = [h for h in g["history"] if "scores" in h]
        assert gens[0]["generation"] == 0 and len(gens) >= 2
        for h in gens[1:]:
            for child in h["children"]:
                v = variants[child]
                assert v["generation"] == h["generation"] and v["parent_id"] in variants
                assert v["guards_passed"] and (run / v["image"]).exists()
                parent = variants[v["parent_id"]]
                diff = [k for k in parent["genome"] if parent["genome"][k] != v["genome"][k]]
                assert diff == [v["mutation"]["gene"]]  # exactly one element changed
        champ = variants[g["champion"]]
        if champ["generation"] > 0:
            improved += 1
            assert "famil" in champ["texts"]["hook"].lower()
    assert improved >= 1
    planned = {a.variant_id for a in result.choices}
    assert any(variants[k]["generation"] > 0 for k in planned)  # evolved ads reach the campaign


def test_evolved_templates_reproduce_their_children(done):
    from whynot.create.templates import Template, Variant

    _, _, _, run = done
    templates = {t.id: t for t in (Template.load(p) for p in (run / "templates").glob("*.yaml"))}
    for v in json.loads((run / "variants.json").read_text()):
        t = templates[v["template_id"]]
        t.check(v["genome"])
        assert Variant(t.id, v["genome"]).id == v["variant_id"]
    assert (run / "templates_gen0").is_dir()


def test_redo_evolve_starts_from_the_same_templates(done, tmp_path):
    import shutil

    _, _, _, original = done
    run = tmp_path / "copy"
    shutil.copytree(original, run)
    c, _, _ = clients(tmp_path)
    create(CreateConfig(**CFG), c, run, redo_from="evolve")
    rows = json.loads((run / "variants.json").read_text())
    assert len({r["variant_id"] for r in rows}) == len(rows)  # no duplicated children


def test_evolution_survives_a_stubborn_evolver(tmp_path):
    def stubborn(model, messages):
        text = default_reply(model, messages)
        if "You are improving a Meta app-install ad" in str(messages[0]["content"]):
            return json.dumps({"mutations": [{"gene": "hook", "text": "Join 3 million learners", "why": "x"}]})
        return text

    c, _, _ = clients(tmp_path, meta=FakeMeta(stubborn))
    result = create(CreateConfig(**CFG), c, tmp_path / "run")
    evo = json.loads((tmp_path / "run" / "evolution.json").read_text())
    assert all(g["history"][-1].get("stopped") == "no valid child" for g in evo["groups"])
    assert all("not in any verified claim" in str(g["history"][-1]["refused"]) for g in evo["groups"])
    assert result.plan_errors == []  # the campaign still ships with generation-0 ads


def test_generations_zero_skips_evolution(tmp_path):
    c, meta, _ = clients(tmp_path)
    create(CreateConfig(**CFG, generations=0), c, tmp_path / "run")
    assert json.loads((tmp_path / "run" / "evolution.json").read_text())["skipped"]
    assert not any("improving a Meta" in str(r["messages"][0]["content"]) for r in meta.requests)


def test_report_shows_the_evolution_with_images(done):
    _, _, _, run = done
    report = (run / "report.md").read_text()
    assert "## How the ads evolved (SIMULATED)" in report and "Lineage of the winning ad:" in report
    assert "changed **hook**" in report
    for line in report.splitlines():
        if "![" in line:
            path = line.split("](")[1].split(")")[0]
            assert (run / path).exists(), path
