"""D-1: `whynot reproduce` recomputes every demo number from the logs, says when a number is stale or missing."""

import json
import shutil
from pathlib import Path

from whynot.validate import reproduce as rp

REPO = Path(__file__).resolve().parents[1]


def test_the_committed_r3_result_reproduces_from_a_clean_clone(tmp_path):
    (tmp_path / "validate" / "results").mkdir(parents=True)
    shutil.copy(REPO / "validate" / "results" / "r3-v1-apps-gb-v1.json", tmp_path / "validate" / "results")
    claims = rp.reproduce(tmp_path, checks=[rp.r3])
    assert [c.status for c in claims] == ["ok", "ok", "ok"]
    assert claims[0].recomputed == "0.52 [0.44, 0.60]"


def test_a_stale_number_is_caught(tmp_path):
    (tmp_path / "validate" / "results").mkdir(parents=True)
    d = json.loads((REPO / "validate" / "results" / "r3-v1-apps-gb-v1.json").read_text())
    next(r for r in d["results"] if r["name"] == "viewers-text")["within_auc"] = 0.71  # the file says otherwise
    (tmp_path / "validate" / "results" / "r3-v1-apps-gb-v1.json").write_text(json.dumps(d))
    c = rp.reproduce(tmp_path, checks=[rp.r3])[0]
    assert c.status == "differs" and c.recomputed.startswith("0.71")


def test_sources_not_on_this_machine_are_said_missing_never_invented(tmp_path):
    claims = rp.reproduce(tmp_path, fast=True)
    assert claims and all(c.status == "missing" and c.recomputed is None for c in claims)
    assert "missing here" in rp.report(claims) and "$0" in rp.report(claims)


def test_evolution_verdicts_are_recomputed_from_the_logged_tournaments(tmp_path):
    src = REPO / "outputs" / "runs" / "20261102-e6-tournament-vietbuddy" / "evolution.json"
    if not src.exists():  # run folders are not in git
        return
    run = tmp_path / "outputs" / "runs" / "20261102-e6-tournament-vietbuddy"
    run.mkdir(parents=True)
    d = json.loads(src.read_text())
    run.joinpath("evolution.json").write_text(json.dumps(d))
    assert rp.reproduce(tmp_path, checks=[rp.evolution])[0].status == "ok"
    for g in d["groups"]:  # a retest that no longer clears the floor: the claim must fail
        g["retest"]["floor"] = 9.0
    run.joinpath("evolution.json").write_text(json.dumps(d))
    assert rp.reproduce(tmp_path, checks=[rp.evolution])[0].status == "differs"


def test_pixel_guard_counts_and_a_failed_guard_fails_the_claim(tmp_path):
    run = tmp_path / "outputs" / "runs" / "r1"
    run.mkdir(parents=True)
    rows = [{"guards": {"product_pixels_unchanged": {"passed": True}}} for _ in range(3)]
    run.joinpath("variants.json").write_text(json.dumps(rows))
    c = rp.reproduce(tmp_path, checks=[rp.pixel_guard])[0]
    assert (c.status, c.recomputed) == ("ok", "3/3")
    rows[1]["guards"]["product_pixels_unchanged"]["passed"] = False
    run.joinpath("variants.json").write_text(json.dumps(rows))
    assert rp.reproduce(tmp_path, checks=[rp.pixel_guard])[0].status == "differs"


def test_a_broken_source_is_reported_not_hidden(tmp_path):
    def broken(root):
        raise ValueError("bad file")
    c = rp.reproduce(tmp_path, checks=[broken])[0]
    assert c.status == "differs" and "bad file" in c.note


def test_cli_exit_code_says_whether_every_number_holds(monkeypatch, capsys):
    from whynot import cli
    monkeypatch.setattr(rp, "reproduce", lambda **kw: [rp.Claim("x", "X", "1", "1", "ok")])
    assert cli.main(["reproduce", "--json"]) == 0 and json.loads(capsys.readouterr().out)[0]["status"] == "ok"
    monkeypatch.setattr(rp, "reproduce", lambda **kw: [rp.Claim("x", "X", "1", "2", "differs")])
    assert cli.main(["reproduce"]) == 1
