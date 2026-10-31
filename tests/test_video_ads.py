"""Video ads to Meta (E14-10): upload, processing, one ad set per ad, PAUSED then ACTIVE, never twice."""

import json
from datetime import date

import httpx
import pytest

from test_daily import AUTOPILOT, STRATEGY, Producer
from whynot.agency.daily import DailyConfig, MetaLauncher, run_day
from whynot.agency.memory import Memory
from whynot.run.campaign import Audience
from whynot.run.insights import SimulatedAccount
from whynot.run.killswitch import stop
from whynot.run.meta import Account, MarketingClient, MetaError
from whynot.run.video_ads import VideoAd, VideoPublisher

TOKEN = "EAAvideoSECRET77"
STORE = "https://apps.apple.com/us/app/x/id1234567890"
AUDIENCE = Audience("heritage_learner", "Heritage learners", ("US",), 18, 34, "female")


class VideoGraph:
    """An ad account that processes videos and refuses creatives on unknown or unready videos."""

    def __init__(self, processing_polls: int = 1, fail_once_on: str | None = None, video_error: bool = False):
        self.objects: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        self.polls_left = processing_polls
        self.fail_once_on = fail_once_on
        self.video_error = video_error
        self.n = 0

    def _new(self, kind: str, fields: dict) -> str:
        self.n += 1
        oid = f"{kind}_{self.n}"
        self.objects[oid] = {"kind": kind, **fields}
        return oid

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.split("/", 2)[2]
        edge = path.split("/")[-1]
        self.calls.append((request.method, edge))
        multipart = request.headers.get("content-type", "").startswith("multipart/")
        if multipart:
            fields = {"access_token": TOKEN} if TOKEN.encode() in request.content else {}
        elif request.method == "POST":
            fields = dict(httpx.QueryParams(request.content.decode()))
        else:
            fields = dict(request.url.params)
        if fields.get("access_token") != TOKEN:
            return httpx.Response(400, json={"error": {"code": 190, "message": "Invalid OAuth access token."}})
        if self.fail_once_on == edge:
            self.fail_once_on = None
            return httpx.Response(400, json={"error": {"code": 100, "message": "boom"}})
        if request.method == "GET":
            obj = self.objects.get(path, {})
            if obj.get("kind") == "advideos":
                status = "error" if self.video_error else ("processing" if self.polls_left > 0 else "ready")
                self.polls_left -= 1
                obj["video_status"] = status
                return httpx.Response(200, json={"id": path, "status": {"video_status": status}})
            return httpx.Response(200, json={"id": path, **obj})
        if edge == "advideos":
            assert b"ftypisom" in request.content  # the real bytes were sent
            return httpx.Response(200, json={"id": self._new("advideos", {})})
        if edge == "adimages":
            return httpx.Response(200, json={"images": {fields["name"]: {"hash": f"hash_{self._new('img', {})}"}}})
        if edge == "adsets":
            assert fields["campaign_id"] in self.objects
        if edge == "adcreatives":
            video = json.loads(fields["object_story_spec"])["video_data"]["video_id"]
            if self.objects.get(video, {}).get("video_status") != "ready":
                return httpx.Response(400, json={"error": {"code": 100, "message": "video not ready"}})
        if edge == "ads":
            assert fields["adset_id"] in self.objects
            assert json.loads(fields["creative"])["creative_id"] in self.objects
        if edge in ("campaigns", "adsets", "adcreatives", "ads"):
            return httpx.Response(200, json={"id": self._new(edge, fields)})
        if path in self.objects:
            self.objects[path]["status"] = fields["status"]
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404, json={"error": {"code": 803, "message": "unknown path"}})


def client(graph: VideoGraph, *, page: str | None = "999", account: str = "42") -> MarketingClient:
    http = httpx.Client(transport=httpx.MockTransport(graph))
    return MarketingClient(Account(account, TOKEN, page_id=page), http=http, sleep=lambda s: None, retries=0)


def files(folder, name="day-1-pov"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.mp4").write_bytes(b"\x00\x00\x00\x18ftypisom fake mp4")
    (folder / f"{name}.poster.jpg").write_bytes(b"\xff\xd8 fake jpeg")
    return folder / f"{name}.mp4", folder / f"{name}.poster.jpg"


def ad(tmp_path, key="day-1-pov"):
    video, poster = files(tmp_path / "videos", key)
    return VideoAd(key, video, poster, "so i said cà phê", "VietBuddy", AUDIENCE, 5.0)


def publisher(graph, tmp_path, **kw):
    return VideoPublisher(client(graph, **kw), tmp_path, store_url=STORE, campaign_name="whynot daily · VietBuddy")


def test_a_video_ad_is_created_paused_in_order_then_activated(tmp_path):
    graph = VideoGraph()
    ad_id = publisher(graph, tmp_path).publish(ad(tmp_path), activate=True)
    creates = [e for m, e in graph.calls if m == "POST" and not e.startswith(("ads_", "adsets_", "campaigns_"))]
    assert creates == ["campaigns", "advideos", "adimages", "adsets", "adcreatives", "ads"]
    adset = next(o for o in graph.objects.values() if o["kind"] == "adsets")
    assert adset["daily_budget"] == "500" and json.loads(adset["targeting"])["geo_locations"] == {"countries": ["US"]}
    spec = json.loads(next(o for o in graph.objects.values() if o["kind"] == "adcreatives")["object_story_spec"])
    assert spec["page_id"] == "999" and spec["video_data"]["image_hash"].startswith("hash_")
    assert spec["video_data"]["call_to_action"] == {"type": "LEARN_MORE", "value": {"link": STORE}}
    activations = [e for m, e in graph.calls if m == "POST" and e.startswith(("ads_", "adsets_", "campaigns_"))]
    assert activations[0] == ad_id and activations[-1].startswith("campaigns_")  # children first
    assert all(o["status"] == "ACTIVE" for o in graph.objects.values() if o["kind"] in ("campaigns", "adsets", "ads"))


def test_without_activation_everything_stays_paused(tmp_path):
    graph = VideoGraph()
    publisher(graph, tmp_path).publish(ad(tmp_path), activate=False)
    assert all(o["status"] == "PAUSED" for o in graph.objects.values() if o["kind"] in ("campaigns", "adsets", "ads"))


def test_it_waits_for_meta_to_process_the_video(tmp_path):
    graph = VideoGraph(processing_polls=3)
    publisher(graph, tmp_path).publish(ad(tmp_path), activate=False)
    assert sum(1 for m, e in graph.calls if m == "GET") == 4


def test_a_video_meta_cannot_process_is_an_error(tmp_path):
    with pytest.raises(MetaError, match="could not process"):
        publisher(VideoGraph(video_error=True), tmp_path).publish(ad(tmp_path), activate=False)


def test_a_crash_midway_resumes_without_uploading_or_creating_twice(tmp_path):
    graph = VideoGraph(fail_once_on="adcreatives")
    with pytest.raises(MetaError):
        publisher(graph, tmp_path).publish(ad(tmp_path), activate=True)
    publisher(graph, tmp_path).publish(ad(tmp_path), activate=True)  # a new process reads agency/meta.json
    kinds = [o["kind"] for o in graph.objects.values()]
    assert kinds.count("advideos") == kinds.count("adsets") == kinds.count("campaigns") == kinds.count("ads") == 1


def test_the_campaign_is_shared_by_every_daily_ad(tmp_path):
    graph = VideoGraph()
    pub = publisher(graph, tmp_path)
    pub.publish(ad(tmp_path, "a"), activate=False)
    pub.publish(ad(tmp_path, "b"), activate=False)
    kinds = [o["kind"] for o in graph.objects.values()]
    assert kinds.count("campaigns") == 1 and kinds.count("adsets") == 2


def test_a_page_is_required_and_accounts_are_never_mixed(tmp_path):
    with pytest.raises(MetaError, match="META_PAGE_ID"):
        publisher(VideoGraph(), tmp_path, page=None)
    publisher(VideoGraph(), tmp_path).publish(ad(tmp_path), activate=False)
    with pytest.raises(MetaError, match="act_42"):
        publisher(VideoGraph(), tmp_path, account="7")


# --- the daily loop on a real-shaped account ---------------------------------------------------

class VideoProducer(Producer):
    """The fake studio, writing a real-looking video and poster where the studio would."""

    def __init__(self, videos):
        super().__init__()
        self.videos = videos

    def make(self, p, name_prefix, *, avoid=None):
        out = super().make(p, name_prefix, avoid=avoid)
        files(self.videos, out["file"]["path"].removesuffix(".mp4"))
        return out


def test_the_daily_loop_publishes_its_videos_and_the_kill_switch_stops_them(tmp_path):
    graph = VideoGraph()
    c = client(graph)
    pub = VideoPublisher(c, tmp_path, store_url=STORE, campaign_name="whynot daily")
    audiences = {p.id: AUDIENCE for p in STRATEGY.personas}
    launcher = MetaLauncher(c, pub, audiences=audiences, videos=tmp_path / "videos", title="VietBuddy")
    rep = run_day(tmp_path, date(2026, 11, 2), source=SimulatedAccount(), producer=VideoProducer(tmp_path / "videos"),
                  launcher=launcher, policy=AUTOPILOT, strategy=STRATEGY,
                  cfg=DailyConfig(target_live=2, max_new=2), say=lambda s: None)
    assert len(rep.live) == 2 and not rep.failures
    memory = Memory(tmp_path / "agency" / "memory.json")
    live_ids = {r.meta_ad_id for r in memory.by_status("live")}
    assert all(i and i.startswith("ads_") for i in live_ids)
    report = stop([tmp_path], c, by="Tom")
    assert {t.meta_id for t in report.paused} == live_ids
    assert all(graph.objects[i]["status"] == "PAUSED" for i in live_ids)


def test_a_persona_without_an_audience_stays_waiting_with_the_reason(tmp_path):
    c = client(VideoGraph())
    launcher = MetaLauncher(c, VideoPublisher(c, tmp_path, store_url=STORE, campaign_name="x"), audiences={},
                            videos=tmp_path / "videos")
    rep = run_day(tmp_path, date(2026, 11, 2), source=SimulatedAccount(), producer=VideoProducer(tmp_path / "videos"),
                  launcher=launcher, policy=AUTOPILOT, strategy=STRATEGY, cfg=DailyConfig(target_live=1, max_new=1),
                  say=lambda s: None)
    assert not rep.live and rep.waiting_approval and "no audience" in rep.failures[0]
