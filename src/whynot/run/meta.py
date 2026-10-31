"""Meta Marketing API client: the only code that writes to an ad account.

Creates ad images, campaigns, ad sets, creatives and ads (`POST /act_<id>/<edge>`), reads an object back,
and changes an object's status. It does not decide anything: `run/publish.py` decides what to create, after
the autopilot (`run/autopilot.py`) allowed it.

Security: the access token travels only in the request body; it is redacted from every error message and
never returned. Transient errors (network, 5xx, rate limits) are retried with backoff; validation errors are
raised with Meta's own message (`error_user_msg` when present), which says what to fix.
"""

import base64
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

GRAPH_URL = "https://graph.facebook.com"
TRANSIENT_CODES = {1, 2, 4, 17, 32, 341, 613, 80004}


class MetaError(RuntimeError):
    def __init__(self, message: str, code: int | None = None, subcode: int | None = None):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


@dataclass(frozen=True)
class Account:
    account_id: str  # without "act_"
    token: str
    page_id: str | None = None
    app_id: str | None = None
    sandbox: bool = False

    @property
    def act(self) -> str:
        return f"act_{self.account_id.removeprefix('act_')}"


def _form(fields: dict[str, Any]) -> dict[str, str]:
    """Graph API form encoding: objects and lists as JSON, booleans as true/false."""
    out = {}
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, bool):
            out[k] = "true" if v else "false"
        elif isinstance(v, (dict, list)):
            out[k] = json.dumps(v, separators=(",", ":"))
        else:
            out[k] = str(v)
    return out


class MarketingClient:
    def __init__(self, account: Account, *, version: str = "v26.0", http: httpx.Client | None = None,
                 base_url: str = GRAPH_URL, retries: int = 3, backoff_s: float = 2.0,
                 sleep: Callable[[float], None] = time.sleep):
        if not account.token:
            raise MetaError("no Marketing API token: set META_ACCESS_TOKEN (or META_SANDBOX_TOKEN) in .env")
        if not account.account_id:
            raise MetaError("no ad account: set META_AD_ACCOUNT_ID (or META_SANDBOX_AD_ACCOUNT_ID) in .env")
        self.account = account
        self.base = f"{base_url}/{version}"
        self.http = http or httpx.Client(timeout=60)
        self.retries = retries
        self.backoff_s = backoff_s
        self._sleep = sleep

    def _redact(self, text: str) -> str:
        return text.replace(self.account.token, "[REDACTED]")

    def _call(self, method: str, path: str, data: dict[str, Any] | None = None,
              params: dict[str, Any] | None = None, files: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base}/{path.lstrip('/')}"
        for attempt in range(self.retries + 1):
            last = attempt == self.retries
            try:
                if method == "GET":
                    response = self.http.get(url, params={**(params or {}), "access_token": self.account.token})
                else:
                    response = self.http.post(url, data={**_form(data or {}), "access_token": self.account.token},
                                              files=files)
            except httpx.HTTPError as exc:
                if last:
                    raise MetaError(self._redact(f"request failed: {exc}")) from None
                self._sleep(self.backoff_s * 2**attempt)
                continue
            try:
                body = response.json()
            except ValueError:
                if response.status_code >= 500 and not last:
                    self._sleep(self.backoff_s * 2**attempt)
                    continue
                raise MetaError(f"non-JSON response (HTTP {response.status_code})") from None
            err = body.get("error") if isinstance(body, dict) else None
            if err:
                code, sub = err.get("code"), err.get("error_subcode")
                if (err.get("is_transient") or code in TRANSIENT_CODES) and not last:
                    self._sleep(self.backoff_s * 2**attempt)
                    continue
                msg = err.get("error_user_msg") or err.get("message") or "unknown error"
                title = f"{err['error_user_title']}: " if err.get("error_user_title") else ""
                raise MetaError(self._redact(f"Meta error {code}/{sub}: {title}{msg}"), code, sub)
            if not isinstance(body, dict):
                raise MetaError("unexpected response shape")
            return body
        raise AssertionError("unreachable")

    def _create(self, edge: str, fields: dict[str, Any]) -> str:
        body = self._call("POST", f"{self.account.act}/{edge}", fields)
        if "id" not in body:
            raise MetaError(f"no id in the response to {edge}")
        return str(body["id"])

    # --- objects ------------------------------------------------------------------------------

    def upload_image(self, path: Path) -> str:
        """Upload an ad image; returns its hash (used by creatives)."""
        data = Path(path).read_bytes()
        body = self._call("POST", f"{self.account.act}/adimages",
                          {"bytes": base64.b64encode(data).decode(), "name": Path(path).name})
        images = body.get("images") or {}
        first = next(iter(images.values()), None)
        if not first or "hash" not in first:
            raise MetaError("no image hash in the response")
        return str(first["hash"])

    def upload_video(self, path: Path) -> str:
        """Upload an ad video (multipart); returns its video id. Meta processes it before a creative can use it."""
        path = Path(path)
        body = self._call("POST", f"{self.account.act}/advideos", {"name": path.name},
                          files={"source": (path.name, path.read_bytes(), "video/mp4")})
        if "id" not in body:
            raise MetaError("no video id in the response to advideos")
        return str(body["id"])

    def wait_video_ready(self, video_id: str, *, timeout_s: float = 300, every_s: float = 5) -> None:
        """Poll the video's processing status; a creative made before it is ready is refused by Meta."""
        waited = 0.0
        while True:
            status = (self.get(video_id, "status").get("status") or {}).get("video_status")
            if status == "ready":
                return
            if status == "error":
                raise MetaError(f"Meta could not process video {video_id}")
            if waited >= timeout_s:
                raise MetaError(f"video {video_id} still processing after {timeout_s:.0f} s ({status})")
            self._sleep(every_s)
            waited += every_s

    def create_campaign(self, fields: dict[str, Any]) -> str:
        return self._create("campaigns", fields)

    def create_adset(self, fields: dict[str, Any]) -> str:
        return self._create("adsets", fields)

    def create_creative(self, fields: dict[str, Any]) -> str:
        return self._create("adcreatives", fields)

    def create_ad(self, fields: dict[str, Any]) -> str:
        return self._create("ads", fields)

    def get(self, object_id: str, fields: str = "id,name,status,effective_status") -> dict[str, Any]:
        return self._call("GET", object_id, params={"fields": fields})

    def set_status(self, object_id: str, status: str) -> None:
        if status not in {"ACTIVE", "PAUSED", "ARCHIVED", "DELETED"}:
            raise ValueError(f"bad status {status!r}")
        self._call("POST", object_id, {"status": status})

    def ads_manager_url(self, campaign_id: str) -> str:
        return (f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={self.account.account_id}"
                f"&selected_campaign_ids={campaign_id}")
