"""Publishing to Meta, against a fake Graph API that behaves like the real one where it matters:
it checks the token, refuses references to objects that don't exist, and can fail on demand."""

import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from whynot.run.autopilot import Level, Policy
from whynot.run.campaign import AdChoice, Audience, build_plan
from whynot.run.meta import Account, MarketingClient, MetaError
from whynot.run.publish import PublishError, PublishState, activate_published, publish

TOKEN = "EAAsandboxSECRET99"
STORE = "https://apps.apple.com/us/app/x/id1234567890"


class FakeGraph:
    """In-memory ad account. `fail_on` = edge name (e.g. 'adsets') to fail once with a given error."""

    def __init__(self, fail_on: str | None = None, error: dict | None = None, fail_times: int = 1):
        self.objects: dict[str, dict] = {}
        self.images: dict[str, str] = {}
        self.calls: list[tuple[str, str, dict]] = []
        self.fail_on, self.error, self.fail_times = fail_on, error, fail_times
        self.n = 0

    def _new(self, kind: str, fields: dict) -> str:
        self.n += 1
        oid = f"{kind}_{self.n}"
        self.objects[oid] = {"kind": kind, **fields}
        return oid

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.split("/", 2)[2]  # drop /v26.0/
        post = request.method == "POST"
        fields = dict(httpx.QueryParams(request.content.decode())) if post else dict(request.url.params)
        self.calls.append((request.method, path, fields))
        if fields.get("access_token") != TOKEN:
            return httpx.Response(400, json={"error": {"code": 190, "message": "Invalid OAuth access token."}})
        edge = path.split("/")[-1]
        if self.fail_on == edge and self.fail_times > 0:
            self.fail_times -= 1
            return httpx.Response(400, json={"error": self.error or {"code": 100, "message": "Invalid parameter",
                                                                      "error_user_msg": "Budget too low"}})
        if request.method == "GET":
            return httpx.Response(200, json={"id": path, **self.objects.get(path, {})})
        if edge == "adimages":
            h = f"hash_{len(self.images) + 1}"
            self.images[h] = fields["name"]
            return httpx.Response(200, json={"images": {fields["name"]: {"hash": h}}})
        for ref_field in ("campaign_id", "adset_id"):
            if ref_field in fields and fields[ref_field] not in self.objects:
                return httpx.Response(400, json={"error": {"code": 100, "message": f"unknown {ref_field}"}})
        if edge == "adcreatives":
            spec = json.loads(fields["object_story_spec"])
            assert spec["link_data"]["image_hash"] in self.images
        if edge == "ads":
            assert json.loads(fields["creative"])["creative_id"] in self.objects
        if edge in ("campaigns", "adsets", "adcreatives", "ads"):
            return httpx.Response(200, json={"id": self._new(edge, fields)})
        if edge not in ("campaigns",) and path in self.objects:  # status update on an object
            self.objects[path]["status"] = fields["status"]
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404, json={"error": {"code": 803, "message": "unknown path"}})


def client(graph: FakeGraph, *, sandbox=True, token=TOKEN, page="999", app=None) -> MarketingClient:
    return MarketingClient(Account("123456", token, page_id=page, app_id=app, sandbox=sandbox),
                           http=httpx.Client(transport=httpx.MockTransport(graph)), sleep=lambda s: None)


@pytest.fixture
def run(tmp_path: Path):
    (tmp_path / "ads").mkdir()
    choices = []
    for p, persona in enumerate(("a.en", "b.en")):
        for i in range(2):
            img = f"ads/{persona}-{i}.png"
            Image.new("RGB", (40, 40), (p * 80, i * 80, 100)).save(tmp_path / img)
            choices.append(AdChoice(f"{persona}-{i}", f"t{p}{i}", persona, img, "Hook", "Body text", "Title",
                                    "INSTALL_MOBILE_APP", True, 1.0 + i))
    audiences = [Audience("a.en", "A", ("US",), 18, 34, "all"), Audience("b.en", "B", ("US",), 25, 54, "female")]
    return build_plan("App", STORE, audiences, choices, daily_cap_eur=20), tmp_path


OWNER_DRY = Policy()  # the default: dry run, €0


# --- the happy path ------------------------------------------------------------------------

def test_sandbox_publish_creates_everything_paused_in_order(run):
    plan, d = run
    g = FakeGraph()
    state = publish(plan, d, client(g), OWNER_DRY, objective="traffic", approved_by="Matteo")
    assert state.status == "published" and state.mode == "sandbox"
    kinds = [path.split("/")[-1] for m, path, _ in g.calls if m == "POST"]
    assert kinds == ["adimages"] * 4 + ["campaigns", "adsets", "adsets"] + ["adcreatives", "ads"] * 4
    assert all(o.get("status") == "PAUSED" for o in g.objects.values() if o["kind"] in ("campaigns", "adsets", "ads"))
    camp = next(o for o in g.objects.values() if o["kind"] == "campaigns")
    assert camp["objective"] == "OUTCOME_TRAFFIC" and camp["is_adset_budget_sharing_enabled"] == "false"
    adsets = [o for o in g.objects.values() if o["kind"] == "adsets"]
    assert sum(int(a["daily_budget"]) for a in adsets) <= 2000
    assert all(a["optimization_goal"] == "LINK_CLICKS" for a in adsets)
    creative = json.loads(next(o for o in g.objects.values() if o["kind"] == "adcreatives")["object_story_spec"])
    assert creative["page_id"] == "999" and creative["link_data"]["call_to_action"]["type"] == "LEARN_MORE"
    saved = json.loads((d / "publish.json").read_text())
    assert saved["status"] == "published" and len(saved["objects"]) == 1 + 2 + 4 + 4
    assert "adsmanager.facebook.com" in saved["campaign_url"]


def test_activation_is_separate_and_ends_with_the_campaign(run):
    plan, d = run
    g = FakeGraph()
    state = publish(plan, d, client(g), OWNER_DRY, objective="traffic", approved_by="Matteo")
    assert not any(f.get("status") == "ACTIVE" for _, _, f in g.calls)
    activate_published(state, client(g), d)
    activated = [path for m, path, f in g.calls if f.get("status") == "ACTIVE"]
    assert activated[-1] == state.objects["campaign"] and len(activated) == 4 + 2 + 1
    assert json.loads((d / "publish.json").read_text())["status"] == "active"


# --- the autopilot decides -----------------------------------------------------------------

def test_without_the_owners_approval_nothing_is_created(run):
    plan, d = run
    g = FakeGraph()
    state = publish(plan, d, client(g), OWNER_DRY, objective="traffic", approved_by=None)
    assert state.status == "refused" and g.calls == []
    assert {x["outcome"] for x in state.decisions} == {"needs_approval"}
    actions = [json.loads(line) for line in (d / "actions.jsonl").read_text().splitlines()]
    assert len(actions) == 2 and all(a["outcome"] == "needs_approval" for a in actions)


def test_live_follows_the_owners_policy_exactly(run):
    plan, d = run
    g = FakeGraph()
    state = publish(plan, d, client(g, sandbox=False), OWNER_DRY, objective="traffic", approved_by="Matteo")
    assert state.status == "refused" and g.calls == []  # dry run with a €0 cap: refused, nothing sent
    assert "above the cap of €0.00" in state.decisions[0]["why"]
    tight = Policy(Level.AUTOPILOT, 12.0, first_live_approved=True)
    d2 = d / "second"
    d2.mkdir()
    (d2 / "ads").symlink_to(d / "ads")
    state = publish(plan, d2, client(g, sandbox=False), tight, objective="traffic", approved_by="Matteo")
    assert [x["outcome"] for x in state.decisions] == ["execute", "refused"]  # the second set would pass the cap
    assert sum(1 for o in g.objects.values() if o["kind"] == "adsets") == 1


# --- refusing early -------------------------------------------------------------------------

def test_missing_ids_are_refused_before_any_call(run):
    plan, d = run
    g = FakeGraph()
    with pytest.raises(PublishError, match="META_PAGE_ID"):
        publish(plan, d, client(g, page=None), OWNER_DRY, objective="traffic", approved_by="Matteo")
    with pytest.raises(PublishError, match="META_APP_ID"):
        publish(plan, d, client(g), OWNER_DRY, objective="app_promotion", approved_by="Matteo")
    assert g.calls == []


def test_an_invalid_plan_is_refused(run):
    plan, d = run
    plan.ad_sets[0].daily_budget_eur = 50  # above the cap
    with pytest.raises(PublishError, match="exceeds the cap"):
        publish(plan, d, client(FakeGraph()), OWNER_DRY, objective="traffic", approved_by="Matteo")


def test_no_mixing_accounts_or_objectives_in_one_run(run):
    plan, d = run
    publish(plan, d, client(FakeGraph()), OWNER_DRY, objective="traffic", approved_by="Matteo")
    with pytest.raises(PublishError, match="refusing to mix"):
        publish(plan, d, client(FakeGraph(), sandbox=False), Policy(Level.AUTOPILOT, 20, True), objective="traffic",
                approved_by="Matteo")


# --- failures and resume ---------------------------------------------------------------------

def test_failure_halfway_then_resume_without_duplicates(run):
    plan, d = run
    g = FakeGraph(fail_on="ads", error={"code": 100, "message": "Invalid parameter", "error_user_title": "Ad issue",
                                         "error_user_msg": "The image is too small"})
    with pytest.raises(MetaError, match="Ad issue: The image is too small"):
        publish(plan, d, client(g), OWNER_DRY, objective="traffic", approved_by="Matteo")
    partial = PublishState.load(d / "publish.json")
    assert partial.status == "partial" and "campaign" in partial.objects
    state = publish(plan, d, client(g), OWNER_DRY, objective="traffic", approved_by="Matteo")
    assert state.status == "published"
    kinds = ("campaigns", "adsets", "adcreatives", "ads")
    counts = {k: sum(1 for o in g.objects.values() if o["kind"] == k) for k in kinds}
    assert counts == {"campaigns": 1, "adsets": 2, "adcreatives": 4, "ads": 4}  # nothing created twice
    assert len(g.images) == 4


def test_rate_limits_are_retried(run):
    plan, d = run
    g = FakeGraph(fail_on="campaigns", error={"code": 17, "message": "User request limit reached"}, fail_times=2)
    assert publish(plan, d, client(g), OWNER_DRY, objective="traffic", approved_by="Matteo").status == "published"
    assert sum(1 for _, path, _ in g.calls if path.endswith("/campaigns")) == 3  # two refusals, then success


def test_token_errors_are_not_retried(run):
    plan, d = run
    g = FakeGraph()
    with pytest.raises(MetaError, match="190"):
        publish(plan, d, client(g, token="wrong-token"), OWNER_DRY, objective="traffic", approved_by="Matteo")
    assert len(g.calls) == 1  # the first upload failed on the token: no retry, nothing else sent
    assert PublishState.load(d / "publish.json").status == "partial"


def test_the_token_never_leaks(run):
    plan, d = run

    def network_down(request):
        raise httpx.ConnectError(f"cannot reach {request.url}?access_token={TOKEN}")

    c = MarketingClient(Account("123456", TOKEN, page_id="999", sandbox=True),
                        http=httpx.Client(transport=httpx.MockTransport(network_down)), retries=1, sleep=lambda s: None)
    with pytest.raises(MetaError) as exc:
        publish(plan, d, c, OWNER_DRY, objective="traffic", approved_by="Matteo")
    assert TOKEN not in str(exc.value)
    for f in d.rglob("*.json*"):
        assert TOKEN not in f.read_text()


def test_client_needs_a_token_and_an_account():
    with pytest.raises(MetaError, match="token"):
        MarketingClient(Account("1", ""))
    with pytest.raises(MetaError, match="ad account"):
        MarketingClient(Account("", "t"))
