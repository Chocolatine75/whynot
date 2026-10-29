"""A fake world for end-to-end tests: App Store, Ad Library, image CDN and Meta models.

The pipeline runs unchanged against it: real `ModelClient` (cost ledger, budget),
real `AppStoreClient` and `AdLibraryClient` over `httpx.MockTransport`.
Model answers are routed by prompt and can be swapped per test to misbehave.
"""

import io
import json
import re
from pathlib import Path
from types import SimpleNamespace as NS

import httpx
from PIL import Image, ImageDraw

from director_fixture import director_json, director_json_fr
from fakes import make_settings
from strategy_fixture import APP, REVIEWS, strategy_json
from whynot.agency.create import Clients
from whynot.costs import CostLedger
from whynot.ingest.adlibrary import AdLibraryClient
from whynot.ingest.appstore import AppStoreClient
from whynot.models import ModelClient

TOKEN = "EAAsecretTOKEN42"
SHOTS = [f"https://is1-ssl.mzstatic.com/image/thumb/P/v4/{i}/screen{i}.png/392x696bb.jpg" for i in range(3)]
ICON = "https://is1-ssl.mzstatic.com/image/thumb/P/v4/icon/AppIcon.png/512x512bb.jpg"

AD_LIBRARY = {  # page_id -> ads (raw Graph API rows)
    "p1": [("900", "Speak Vietnamese in 10 minutes a day. Start free.", "2026-05-01", None),
           ("902", "Your first Vietnamese conversation this week.", "2026-04-01", None),
           ("903", "Old promo that stopped fast.", "2026-09-01", "2026-09-03")],
    "p2": [("901", "Tired of textbooks? Learn with native speakers.", "2026-09-01", "2026-09-04"),
           ("904", "Learn the Southern accent with real people.", "2026-03-01", None)],
    "spam": [("990", "Win a free iPhone now", "2026-10-01", None)],
}
PAGE_NAMES = {"p1": "Rival Lingo", "p2": "Other App", "spam": "Crurdfotcra Drismecluki"}


def png(size, colour) -> bytes:
    img = Image.new("RGB", size, colour)
    d = ImageDraw.Draw(img)
    for y in range(0, size[1], max(1, size[1] // 10)):
        d.rectangle((size[0] // 10, y, size[0] * 9 // 10, y + size[1] // 30), fill=(250, 250, 250))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def lookup_json() -> dict:
    return {"resultCount": 1, "results": [{
        "kind": "software", "trackId": int(APP.app_id), "trackName": APP.name, "sellerName": APP.seller,
        "bundleId": APP.bundle_id, "trackViewUrl": APP.store_url + "?uo=4", "description": APP.description,
        "genres": APP.genres, "price": 0.0, "currency": "USD", "averageUserRating": APP.rating,
        "userRatingCount": APP.rating_count, "screenshotUrls": SHOTS, "artworkUrl512": ICON}]}


def reviews_json() -> dict:
    return {"feed": {"entry": [{"im:rating": {"label": str(r.rating)}, "id": {"label": r.id},
                                "title": {"label": r.title}, "content": {"label": r.text},
                                "im:version": {"label": r.version}, "updated": {"label": r.date + "T00:00:00"}}
                               for r in REVIEWS]}}


def ad_row(page, ad_id, body, start, stop):
    return {"id": ad_id, "page_id": page, "page_name": PAGE_NAMES[page], "ad_creative_bodies": [body],
            "ad_delivery_start_time": start, "ad_delivery_stop_time": stop,
            "ad_snapshot_url": f"https://www.facebook.com/ads/archive/render_ad/?id={ad_id}&access_token={TOKEN}",
            "age_country_gender_reach_breakdown": [
                {"country": "FR", "age_gender_breakdowns": [{"age_range": "25-34", "male": 100, "female": 150}]}]}


class Http:
    """One transport for every outside service; counts requests per host."""

    def __init__(self, ad_library=None):
        self.ad_library = AD_LIBRARY if ad_library is None else ad_library
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(request.url.host)
        if "itunes.apple.com/lookup" in url:
            return httpx.Response(200, json=lookup_json())
        if "customerreviews/page=1/" in url:
            return httpx.Response(200, json=reviews_json())
        if "customerreviews" in url:
            return httpx.Response(200, json={"feed": {}})
        if "mzstatic.com" in url:
            body = png((512, 512), (220, 38, 38)) if "AppIcon" in url else png((1290, 2796), (30, 111, 217))
            return httpx.Response(200, content=body, headers={"content-type": "image/png"})
        if "graph.facebook.com" in url:
            q = dict(request.url.params)
            assert q.get("access_token") == TOKEN
            if "search_terms" in q:
                rows = [ad_row(p, *a) for p, ads in self.ad_library.items() for a in ads if a[3] is None]
            else:
                status = q["ad_active_status"]
                rows = [ad_row(p, *a) for p in json.loads(q["search_page_ids"]) for a in self.ad_library.get(p, [])
                        if (a[3] is None) == (status == "ACTIVE")]
            return httpx.Response(200, json={"data": rows, "paging": {}})
        return httpx.Response(404)


def _viewer_answer(labels: list[str], preferred: str) -> str:
    return json.dumps({"reactions": [{"ad": lab, "stopped": lab == preferred, "understood": True, "believed": True,
                                      "why_not": "" if lab == preferred else "Not for me", "intent": "maybe",
                                      "intent_score": 4 if lab == preferred else 2} for lab in labels],
                       "preferred": preferred})


def _blocks(feed_text: str) -> list[tuple[str, str, str]]:
    """(label, advertiser, block text) for each ad in a viewer prompt."""
    parts = re.split(r"(?=\[A\d+\] Sponsored · )", feed_text)
    out = []
    for part in parts:
        m = re.match(r"\[(A\d+)\] Sponsored · (.*)", part)
        if m:
            out.append((m.group(1), m.group(2).strip(), part))
    return out


def fair_viewer(feed_text: str) -> str:
    """Judges content: prefers the first ad that talks about family, whoever the advertiser."""
    blocks = _blocks(feed_text)
    liked = [lab for lab, _, body in blocks if "famil" in body.lower()]  # family, famille
    return _viewer_answer([b[0] for b in blocks], liked[0] if liked else blocks[-1][0])


def name_biased_viewer(feed_text: str) -> str:
    """Judges the name: prefers anything shown under the app's brand (what the real model did)."""
    blocks = _blocks(feed_text)
    ours = [lab for lab, adv, _ in blocks if adv == "LinguaApp"]
    return _viewer_answer([b[0] for b in blocks], ours[0] if ours else blocks[-1][0])


def default_reply(model: str, messages: list[dict]) -> str:
    system = messages[0]["content"] if messages[0]["role"] == "system" else ""
    user = next(m["content"] for m in messages if m["role"] == "user")  # the original prompt, also on repairs
    text = user if isinstance(user, str) else user[0]["text"]
    if "You simulate one specific person" in system:
        return fair_viewer(text)
    if "Keyword search is noisy" in text:
        ids = re.findall(r"page_id (\S+):", text)
        return json.dumps({"advertisers": [{"page_id": i, "competitor": i != "spam", "why": "test"} for i in ids]})
    if "search terms" in text:
        return json.dumps({"category": "Vietnamese learning app", "terms": ["learn vietnamese", "language app",
                                                                           "speak vietnamese"]})
    if "You are the strategist" in text:
        return json.dumps(strategy_json())
    if "creative director" in text:
        angles = re.findall(r"^- (\w+) \(persona", text, flags=re.M)
        if "- Language: French." in text:
            return json.dumps(director_json_fr(tuple(angles)))
        return json.dumps(director_json(tuple(angles)))
    raise AssertionError(f"unrouted prompt: {text[:120]}")


class FakeMeta:
    """OpenAI-compatible fake: `reply(model, messages) -> str`, with usage so costs are real numbers."""

    def __init__(self, reply=default_reply):
        self.reply = reply
        self.requests: list[dict] = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, *, model, messages, **kwargs):
        self.requests.append({"model": model, "messages": messages, **kwargs})
        text = self.reply(model, messages)
        prompt = sum(len(json.dumps(m)) for m in messages) // 4
        return NS(choices=[NS(message=NS(content=text), finish_reason="stop")],
                  usage=NS(prompt_tokens=prompt, completion_tokens=len(text) // 4 + 300,
                           prompt_tokens_details=NS(cached_tokens=0),
                           completion_tokens_details=NS(reasoning_tokens=300)))


def clients(tmp: Path, *, meta: FakeMeta | None = None, http: Http | None = None, budget: float = 5.0):
    meta = meta or FakeMeta()
    http = http or Http()
    transport = httpx.MockTransport(http)
    settings = make_settings(tmp)
    model = ModelClient(settings, CostLedger(tmp / "run" / "costs.jsonl"), meta=meta, budget_usd=budget)
    return Clients(model, AppStoreClient(httpx.Client(transport=transport), sleep=lambda s: None),
                   AdLibraryClient(TOKEN, http=httpx.Client(transport=transport), sleep=lambda s: None)), meta, http
