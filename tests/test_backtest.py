"""R1 backtest on partner-shaped fake data: exports read, pairs inside the noise skipped, blind, anonymised."""

import json
import random
import re
import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from whynot.config import REPO_ROOT
from whynot.sim.personas import Persona
from whynot.validate.backtest import (
    HistoryError,
    PastAd,
    R1Report,
    _number,
    eligible,
    evaluate,
    fetch_history,
    load_csv,
    load_history,
    run,
    save_history,
    separable,
    separable_pairs,
)

EN = """Reporting starts,Reporting ends,Ad name,Ad ID,Amount spent (EUR),Impressions,Link clicks,Results,Body
2026-09-01,2026-10-01,Grandma POV,120001,"1,234.50","48,213",612,30,Finally talk to grandma
2026-09-01,2026-10-01,Grandma POV,120001,10.00,1000,10,1,Finally talk to grandma
2026-09-05,2026-10-01,Tones meme,120002,80.00,9000,45,2,Six tones in one word
,,,,"1,324.50","58,213",667,33,
"""

FR = ("Début des rapports;Nom de la publicité;Identifiant de la publicité;Montant dépensé (EUR);Impressions;"
      "Clics sur un lien;Résultats\n") + """01/09/2026;Grand-mère;130001;1 234,56;12 000;150;7
05/09/2026;Accent du Sud;130002;0,5;800;3;0
"""


def write(tmp_path, text, name="export.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def ad(i, impressions, clicks, body="", started=None):
    return PastAd(str(i), f"ad {i}", body, "", started, 10.0, impressions, clicks, 0)


# --- loading ----------------------------------------------------------------------------------

def test_english_export_skips_the_total_line_and_sums_duplicate_ids(tmp_path):
    ads = {a.id: a for a in load_csv(write(tmp_path, EN))}
    assert set(ads) == {"120001", "120002"}
    a = ads["120001"]
    assert (a.spend, a.impressions, a.link_clicks, a.conversions) == (1244.5, 49213, 622, 31)
    assert a.body == "Finally talk to grandma" and a.started == date(2026, 9, 1)


def test_french_export_with_semicolons_and_decimal_commas(tmp_path):
    ads = {a.id: a for a in load_csv(write(tmp_path, FR))}
    assert ads["130001"].spend == 1234.56 and ads["130001"].impressions == 12000
    assert ads["130002"].spend == 0.5 and ads["130002"].started == date(2026, 9, 5)


def test_missing_columns_are_named(tmp_path):
    with pytest.raises(HistoryError, match="link_clicks"):
        load_csv(write(tmp_path, "Ad ID,Amount spent,Impressions\n1,2,3\n"))


@pytest.mark.parametrize(("raw", "value"), [("1,234.50", 1234.5), ("1 234,56 €", 1234.56), ("12,5", 12.5),
                                            ("0,123", 0.123), ("1,234", 1234.0), ("1,234,567", 1234567.0),
                                            ("", 0.0), ("-", 0.0), ("€ 7", 7.0)])
def test_numbers(raw, value):
    assert _number(raw) == pytest.approx(value)


def test_junk_numbers_are_refused():
    with pytest.raises(HistoryError):
        _number("1.2.3")


def test_partner_data_only_under_private(tmp_path):
    ads = [ad(1, 1000, 10, started=date(2026, 9, 1))]
    with pytest.raises(HistoryError, match="data/private"):
        save_history(ads, tmp_path / "history.json")
    path = save_history(ads, tmp_path / "private" / "partner" / "history.json")
    assert load_history(path) == ads


def test_macos_system_private_folder_does_not_count():
    """Regression: on macOS every temp dir is under /private/var/..., so any path passed the guard."""
    with pytest.raises(HistoryError, match="data/private"):
        save_history([ad(1, 1000, 10)], Path("/private/var/folders/x/history.json"))


def test_the_private_folder_is_never_tracked_by_git():
    out = subprocess.run(["git", "check-ignore", "-q", "data/private/partner/history.json"], cwd=REPO_ROOT)
    assert out.returncode == 0


def test_api_history_follows_cursors_never_the_next_url():
    pages = {
        "act_9/ads": [{"data": [{"id": "1", "name": "a", "created_time": "2026-09-01T10:00:00+0000",
                                 "creative": {"body": "hello", "title": "t", "thumbnail_url": "https://cdn/x.jpg"}}],
                       "paging": {"cursors": {"after": "C1"}, "next": "https://graph.facebook.com/?access_token=S"}},
                      {"data": [{"id": "2", "name": "b", "creative": {}}, {"id": "3", "name": "never shown"}],
                       "paging": {"cursors": {"after": "C2"}}}],
        "act_9/insights": [{"data": [
            {"ad_id": "1", "spend": "12.5", "impressions": "3000", "inline_link_clicks": "40",
             "actions": [{"action_type": "mobile_app_install", "value": "3"}, {"action_type": "link_click",
                                                                               "value": "40"}]},
            {"ad_id": "2", "spend": "1", "impressions": "100", "inline_link_clicks": "1"}]}],
    }
    calls = []

    def call(path, params):
        calls.append((path, dict(params)))
        page = sum(1 for p, _ in calls if p == path) - 1
        return pages[path][page]

    ads, thumbs = fetch_history(call, "act_9")
    assert [a.id for a in ads] == ["1", "2"]  # ad 3 never delivered
    assert ads[0].conversions == 3 and ads[0].link_clicks == 40 and ads[0].started == date(2026, 9, 1)
    assert thumbs == {"1": "https://cdn/x.jpg"}
    assert calls[1][1]["after"] == "C1" and all("access_token" not in json.dumps(p) for _, p in calls)


# --- pairs and accuracy -----------------------------------------------------------------------

def test_only_pairs_outside_the_noise_count():
    a, b, c = ad(1, 10_000, 200), ad(2, 10_000, 205), ad(3, 10_000, 400)
    assert not separable(a, b) and separable(a, c) and separable(b, c)
    assert not separable(ad(4, 50, 5), ad(5, 50, 1))  # 10 % vs 2 % on 50 impressions: could be luck
    result = evaluate("x", {"1": 1.0, "2": 0.0, "3": 2.0}, [a, b, c])
    assert result.pairs == 2 and result.accuracy == 1.0


def test_accuracy_reversed_and_ties():
    ads = [ad(i, 10_000, 100 * (i + 1)) for i in range(4)]
    assert evaluate("good", {a.id: a.ctr for a in ads}, ads).accuracy == 1.0
    assert evaluate("bad", {a.id: -a.ctr for a in ads}, ads).accuracy == 0.0
    assert evaluate("flat", dict.fromkeys((a.id for a in ads), 1.0), ads).accuracy == 0.5
    with pytest.raises(ValueError, match="clearly different"):
        evaluate("x", {"1": 1.0, "2": 2.0}, [ad(1, 10_000, 200), ad(2, 10_000, 201)])


ads_strategy = st.lists(st.tuples(st.integers(100, 50_000), st.floats(0, 0.05)), min_size=2, max_size=12)


@settings(max_examples=150, deadline=None)
@given(ads_strategy, st.randoms())
def test_every_counted_pair_is_outside_the_noise(rows, rng):
    ads = [ad(i, n, int(n * p)) for i, (n, p) in enumerate(rows)]
    scores = {a.id: rng.random() for a in ads}
    if separable_pairs(ads) == 0:
        return
    result = evaluate("x", scores, ads)
    assert result.pairs == separable_pairs(ads) and 0 <= result.accuracy <= 1
    assert result.ci[0] <= result.ci[1]


def test_eligibility_threshold():
    assert [a.id for a in eligible([ad(1, 999, 9), ad(2, 1000, 9)])] == ["2"]


# --- the whole backtest on a fake partner --------------------------------------------------------

def partner(n=14, seed=0):
    """Ads whose real CTR follows a hidden quality Q written in the copy, plus binomial noise."""
    rng = random.Random(seed)
    ads = []
    for i in range(n):
        q = rng.uniform(0.5, 3.0)
        imp = rng.randint(4_000, 20_000)
        clicks = sum(rng.random() < q / 100 for _ in range(imp))
        ads.append(PastAd(f"9{i:04d}", f"ad {i}", f"Q={q:.2f} learn with grandma", "", date(2026, 9, 1 + i),
                          round(rng.uniform(20, 90), 2), imp, clicks, rng.randint(0, 5)))
    return ads


class TasteModel:
    """Viewers and judge that see only the creative and like a high Q; records every prompt."""

    def __init__(self):
        self.prompts, self.spent_usd = [], 0.0

    def viewer_chat(self, messages, **kwargs):
        text = json.dumps(messages, ensure_ascii=False)
        self.prompts.append(text)
        self.spent_usd += 0.001
        if kwargs.get("module") == "judge":
            q = float(re.search(r"Q=([\d.]+)", text)[1])
            return NS(text=json.dumps({"score": max(1, min(10, round(q * 3))), "why": "x"}), cost=NS(usd=0.001))
        rng = random.Random(text)
        blocks = re.findall(r"\[(A\d+)\] Sponsored · .*?Q=([\d.]+)", messages[1]["content"], re.S)
        best = max(blocks, key=lambda b: float(b[1]) + rng.gauss(0, 0.4))[0]
        return NS(text=json.dumps({"reactions": [{"ad": lab, "stopped": lab == best, "understood": True,
                                                  "believed": True, "why_not": "", "intent": "",
                                                  "intent_score": 3} for lab, _ in blocks],
                                   "preferred": best}), cost=NS(usd=0.001))


PERSONAS = [Persona(f"p{i}", "FR", "25-34", "female" if i % 2 else "male") for i in range(6)]


def test_a_simulator_with_the_right_taste_scores_high_and_baselines_are_reported():
    ads = partner()
    model = TasteModel()
    report, _ = run(model, ads, advertiser="VietBuddy", personas=PERSONAS,
                    conditions=["viewers-text", "judge-text"], appearances=4)
    by = {r.name: r for r in report.results}
    assert by["viewers-text"].accuracy >= 0.75 and by["judge-text"].accuracy >= 0.8
    assert {"shorter_copy", "longer_copy", "most_recent"} <= set(by)
    assert report.usd == pytest.approx(model.spent_usd) and report.separable_pairs > 10
    assert all(r.pairs <= report.separable_pairs for r in report.results)


def test_predictions_are_blind_to_results():
    ads = partner()
    model = TasteModel()
    run(model, ads, advertiser="VietBuddy", personas=PERSONAS, conditions=["viewers-text", "judge-text"])
    prompts = " ".join(model.prompts)
    for a in ads:  # no impression, click or spend figure ever reaches a model
        for number in (str(a.impressions), f"{a.spend:.2f}"):
            assert number not in prompts
        assert a.name not in prompts  # internal ad names can describe results ("winner", "best CTR")


def test_image_conditions_need_images_and_unknown_conditions_are_refused():
    with pytest.raises(ValueError, match="images"):
        run(TasteModel(), partner(), advertiser="V", personas=PERSONAS, conditions=["viewers-image"])
    with pytest.raises(ValueError, match="unknown"):
        run(TasteModel(), partner(), advertiser="V", personas=PERSONAS, conditions=["vibes"])


def test_the_summary_carries_numbers_only():
    ads = partner()
    report, _ = run(TasteModel(), ads, advertiser="VietBuddy", personas=PERSONAS, conditions=["judge-text"])
    text = json.dumps(report.summary("partner-app-2026-11"))
    assert "VietBuddy" not in text and "grandma" not in text
    assert not any(a.id in text for a in ads)
    assert json.loads(text)["simulated_scores"] is True


def test_empty_report_summary():
    assert R1Report().summary("x")["results"] == []
