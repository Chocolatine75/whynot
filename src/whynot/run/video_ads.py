"""Publish the daily loop's video ads to Meta, one ad set per ad (E14-10).

Each new video becomes its own ad set (its own daily budget, the persona's targeting from the run's plan) in one
campaign kept for the client's daily ads. Order, everything created PAUSED:
video upload → wait until Meta has processed it → poster as thumbnail → ad set → creative → ad;
then, only when `activate` is asked (the autopilot said EXECUTE), ad, ad set and campaign go ACTIVE.

Resumable: every id is written to `<run>/agency/meta.json` the moment it exists, so a crash or a retry
never uploads or creates anything twice. The autopilot decides before this module is called; this module
never decides anything.
"""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whynot.run.campaign import APP_ONLY_CTAS, Audience, adset_fields
from whynot.run.meta import MarketingClient, MetaError


@dataclass(frozen=True)
class VideoAd:
    key: str  # the daily loop's id for the ad (video file stem)
    video: Path
    poster: Path
    message: str  # primary text
    title: str  # headline under the video
    audience: Audience
    daily_budget_eur: float
    cta: str = "LEARN_MORE"


class VideoPublisher:
    def __init__(self, client: MarketingClient, run_dir: Path, *, store_url: str, campaign_name: str,
                 objective: str = "traffic", wait_s: float = 300):
        if not client.account.page_id:
            raise MetaError("video ads are published as a Facebook Page: set META_PAGE_ID in .env")
        if objective == "app_promotion" and not client.account.app_id:
            raise MetaError("app_promotion needs META_APP_ID (or use objective traffic)")
        self.client = client
        self.path = Path(run_dir) / "agency" / "meta.json"
        self.store_url = store_url
        self.campaign_name = campaign_name
        self.objective = objective
        self.wait_s = wait_s
        self.state: dict[str, Any] = (json.loads(self.path.read_text()) if self.path.exists()
                                      else {"account": client.account.act, "campaign": None, "ads": {}})
        if self.state["account"] != client.account.act:
            raise MetaError(f"this client's daily ads live on {self.state['account']}, not {client.account.act}")

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".meta-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=1)
        os.replace(tmp, self.path)

    def _step(self, record: dict[str, str], name: str, make: Any) -> str:
        """The id of step `name`: reused when it already exists, else created and saved at once."""
        if not record.get(name):
            record[name] = make()
            self._save()
        return record[name]

    def campaign(self) -> str:
        if not self.state["campaign"]:
            objective = "OUTCOME_APP_PROMOTION" if self.objective == "app_promotion" else "OUTCOME_TRAFFIC"
            self.state["campaign"] = self.client.create_campaign({
                "name": self.campaign_name, "objective": objective, "status": "PAUSED", "buying_type": "AUCTION",
                "special_ad_categories": [], "is_adset_budget_sharing_enabled": False})
            self._save()
        return str(self.state["campaign"])

    def publish(self, ad: VideoAd, *, activate: bool) -> str:
        """Create the ad (or finish creating it) and return its Meta ad id; ACTIVE only if `activate`."""
        campaign = self.campaign()
        rec: dict[str, str] = self.state["ads"].setdefault(ad.key, {})
        self._save()
        video = self._step(rec, "video", lambda: self.client.upload_video(ad.video))
        if not rec.get("video_ready"):
            self.client.wait_video_ready(video, timeout_s=self.wait_s)
            rec["video_ready"] = "yes"
            self._save()
        thumb = self._step(rec, "thumbnail", lambda: self.client.upload_image(ad.poster))
        body = adset_fields(f"whynot · {ad.key}", ad.audience, ad.daily_budget_eur, objective=self.objective,
                            store_url=self.store_url, campaign_id=campaign)
        if "promoted_object" in body:
            body["promoted_object"]["application_id"] = self.client.account.app_id
        adset = self._step(rec, "adset", lambda: self.client.create_adset(body))
        cta = ad.cta if self.objective == "app_promotion" or ad.cta not in APP_ONLY_CTAS else "LEARN_MORE"
        creative = self._step(rec, "creative", lambda: self.client.create_creative({
            "name": ad.key, "object_story_spec": {"page_id": self.client.account.page_id, "video_data": {
                "video_id": video, "image_hash": thumb, "message": ad.message, "title": ad.title,
                "call_to_action": {"type": cta, "value": {"link": self.store_url}}}}}))
        ad_id = self._step(rec, "ad", lambda: self.client.create_ad({
            "name": ad.key, "adset_id": adset, "creative": {"creative_id": creative}, "status": "PAUSED"}))
        if activate and rec.get("active") != "yes":
            for object_id in (ad_id, adset, campaign):  # children first: nothing delivers half-configured
                self.client.set_status(object_id, "ACTIVE")
            rec["active"] = "yes"
            self._save()
        return ad_id
