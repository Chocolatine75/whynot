"""Connect an owner's Meta login to the agency: from one access token to a checked, saved connection.

The owner logs in with Facebook (the web app's "Connect Meta" button, or a token from Graph API Explorer).
From that user token alone this module finds what the agency needs and says plainly what is missing:

- who logged in (`/me`) and which permissions they granted (`/me/permissions`);
- their ad accounts (`/me/adaccounts`): status, currency; the one to use (the only active one, or the one named);
- their Facebook Pages (`/me/accounts`) the ads are published as (a Page where they can advertise);
- whether the agency can publish (ads_management), read results (ads_read) and use the Page.

The connection is saved in `data/private/connections/<act_id>.json` (gitignored, file mode 600), with the token,
so later runs (`whynot agency`) and the daily loop can use it. The token is never printed, logged or returned in
an error message; paging URLs (which embed it) are followed, never stored.
"""

import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from whynot.config import REPO_ROOT
from whynot.run.meta import GRAPH_URL, Account

CONNECTIONS = REPO_ROOT / "data" / "private" / "connections"

REQUIRED = {"ads_management": "create, pause and change ads", "ads_read": "read each ad's results"}
RECOMMENDED = {"pages_show_list": "find your Facebook Pages",
               "pages_read_engagement": "publish ads as your Page",
               "business_management": "use ad accounts owned by a Business Manager"}
# Meta's ad account status codes (AdAccount.account_status)
ACCOUNT_STATUS = {1: "active", 2: "disabled", 3: "unsettled (unpaid balance)", 7: "pending risk review",
                  8: "pending settlement", 9: "in grace period", 100: "pending closure", 101: "closed",
                  201: "any active", 202: "any closed"}
USABLE_STATUS = {1, 9}
MAX_PAGES = 5  # paging guard: an owner with more than ~500 accounts names the one to use


class ConnectError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdAccountInfo:
    account_id: str  # without act_
    name: str
    status: int
    currency: str
    business: str = ""

    @property
    def usable(self) -> bool:
        return self.status in USABLE_STATUS

    @property
    def status_text(self) -> str:
        return ACCOUNT_STATUS.get(self.status, f"status {self.status}")


@dataclass(frozen=True)
class PageInfo:
    page_id: str
    name: str
    can_advertise: bool


@dataclass
class Discovery:
    user_id: str
    user_name: str
    granted: list[str]
    declined: list[str]
    accounts: list[AdAccountInfo]
    pages: list[PageInfo]


@dataclass
class MetaConnection:
    """What a run needs to act on the owner's account. `token` stays in the private file only."""

    token: str
    account_id: str
    account_name: str
    currency: str
    page_id: str | None
    page_name: str | None
    app_id: str | None
    user_name: str
    granted: list[str]
    sandbox: bool = False
    warnings: list[str] = field(default_factory=list)
    connected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def act(self) -> str:
        return f"act_{self.account_id.removeprefix('act_')}"

    @property
    def can_publish(self) -> bool:
        return "ads_management" in self.granted and self.page_id is not None

    @property
    def can_read(self) -> bool:
        return "ads_read" in self.granted or "ads_management" in self.granted

    def account(self) -> Account:
        return Account(self.account_id, self.token, page_id=self.page_id, app_id=self.app_id, sandbox=self.sandbox)

    def public(self) -> dict[str, Any]:
        """Everything but the token: safe to print, log, or store in a run folder."""
        d = asdict(self)
        d.pop("token")
        return {**d, "act": self.act, "can_publish": self.can_publish, "can_read": self.can_read}

    def save(self, folder: Path = CONNECTIONS) -> Path:
        """Private file, mode 600, written atomically (never world-readable, even for an instant)."""
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self.act}.json"
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=1)
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, path: Path) -> "MetaConnection":
        path = Path(path)
        if not path.exists():
            raise ConnectError(f"no Meta connection at {path}: run `whynot connect` first")
        return cls(**json.loads(path.read_text(encoding="utf-8")))


class GraphReader:
    """Read-only Graph API calls with the owner's token (redacted from every error)."""

    def __init__(self, token: str, *, version: str = "v26.0", http: httpx.Client | None = None,
                 base_url: str = GRAPH_URL):
        if not token or not token.strip():
            raise ConnectError("no Meta access token: log in with Facebook (Connect Meta) or paste a token")
        self.token = token.strip()
        self.base = f"{base_url}/{version}"
        self.http = http or httpx.Client(timeout=30)

    def _redact(self, text: str) -> str:
        return text.replace(self.token, "[REDACTED]")

    def _get_url(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            r = self.http.get(url, params={**(params or {}), "access_token": self.token})
        except httpx.HTTPError as exc:
            raise ConnectError(self._redact(f"Meta did not answer: {exc}")) from None
        try:
            body = r.json()
        except ValueError:
            raise ConnectError(f"Meta sent a non-JSON answer (HTTP {r.status_code})") from None
        err = body.get("error") if isinstance(body, dict) else None
        if err:
            code = err.get("code")
            hint = (" — the login expired or was revoked: log in with Facebook again" if code == 190
                    else " — a permission is missing: log in again and accept every permission" if code in (10, 200)
                    else "")
            raise ConnectError(self._redact(f"Meta error {code}: {err.get('message', 'unknown')}{hint}"))
        if not isinstance(body, dict):
            raise ConnectError("unexpected answer from Meta")
        return body

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        return self._get_url(f"{self.base}/{path.lstrip('/')}", params)

    def all(self, path: str, **params: Any) -> list[dict[str, Any]]:
        """Every row of a paged edge (at most MAX_PAGES pages); next-page URLs are used, never kept."""
        body = self.get(path, limit=100, **params)
        rows = list(body.get("data") or [])
        for _ in range(MAX_PAGES - 1):
            nxt = (body.get("paging") or {}).get("next")
            if not nxt:
                break
            body = self._get_url(nxt.split("?")[0], _query(nxt))
            rows += body.get("data") or []
        return rows


def _query(url: str) -> dict[str, str]:
    """A next-page URL's query, without its access_token (ours is added again by the reader)."""
    from urllib.parse import parse_qsl, urlsplit

    return {k: v for k, v in parse_qsl(urlsplit(url).query) if k != "access_token"}


def discover(reader: GraphReader) -> Discovery:
    me = reader.get("me", fields="id,name")
    perms = reader.all("me/permissions")
    accounts = [AdAccountInfo(str(a.get("account_id") or str(a.get("id", "")).removeprefix("act_")),
                              str(a.get("name") or ""), int(a.get("account_status") or 0),
                              str(a.get("currency") or ""), str(a.get("business_name") or ""))
                for a in reader.all("me/adaccounts", fields="account_id,name,account_status,currency,business_name")]
    pages = [PageInfo(str(p["id"]), str(p.get("name") or ""),
                      "ADVERTISE" in (p.get("tasks") or []) or "MANAGE" in (p.get("tasks") or []))
             for p in reader.all("me/accounts", fields="id,name,tasks") if p.get("id")]
    return Discovery(str(me.get("id", "")), str(me.get("name", "")),
                     sorted(p["permission"] for p in perms if p.get("status") == "granted"),
                     sorted(p["permission"] for p in perms if p.get("status") == "declined"), accounts, pages)


def choose(d: Discovery, token: str, *, account_id: str | None = None, page_id: str | None = None,
           app_id: str | None = None, sandbox: bool = False) -> MetaConnection:
    """Pick the ad account and the Page; refuse with a plain reason when the agency could not work."""
    missing = [f"{p} (to {why})" for p, why in REQUIRED.items() if p not in d.granted]
    if "ads_management" not in d.granted:
        raise ConnectError("this login cannot manage ads. Missing: " + "; ".join(missing)
                           + ". Log in again and accept every permission.")
    if account_id:
        want = account_id.removeprefix("act_")
        acct = next((a for a in d.accounts if a.account_id == want), None)
        if acct is None:
            raise ConnectError(f"ad account {account_id} is not one this login can use; it can use: "
                               + (", ".join(f"{a.account_id} ({a.name})" for a in d.accounts) or "none"))
    else:
        usable = [a for a in d.accounts if a.usable]
        if not usable:
            raise ConnectError("no active ad account on this login"
                               + (": " + ", ".join(f"{a.name} is {a.status_text}" for a in d.accounts)
                                  if d.accounts else ": create one in Ads Manager first"))
        if len(usable) > 1:
            raise ConnectError("several ad accounts: name the one to use with --account. "
                               + ", ".join(f"{a.account_id} ({a.name}, {a.currency})" for a in usable))
        acct = usable[0]
    if not acct.usable:
        raise ConnectError(f"ad account {acct.account_id} ({acct.name}) is {acct.status_text}: "
                           "fix it in Ads Manager, then connect again")

    warnings = [f"permission {p} not granted: the agency cannot {why}" for p, why in RECOMMENDED.items()
                if p not in d.granted]
    warnings += [f"permission {p} not granted: the agency cannot {why}" for p, why in REQUIRED.items()
                 if p not in d.granted]
    if acct.status == 9:
        warnings.append("the ad account is in its grace period: pay the balance or ads will stop")
    if acct.currency and acct.currency != "EUR":
        warnings.append(f"the ad account bills in {acct.currency}: whynot's caps and budgets are written in EUR "
                        f"and sent as {acct.currency} amounts (1 EUR of cap = 1 {acct.currency})")

    page: PageInfo | None
    if page_id:
        page = next((p for p in d.pages if p.page_id == page_id), None)
        if page is None:
            raise ConnectError(f"Page {page_id} is not one this login manages; it manages: "
                               + (", ".join(f"{p.page_id} ({p.name})" for p in d.pages) or "none"))
    else:
        ads_pages = [p for p in d.pages if p.can_advertise]
        page = ads_pages[0] if len(ads_pages) == 1 else None
        if len(ads_pages) > 1:
            warnings.append("several Pages: name the one the ads speak as with --page ("
                            + ", ".join(f"{p.page_id} {p.name}" for p in ads_pages) + "); until then nothing "
                            "is published")
        elif not ads_pages:
            warnings.append("no Facebook Page you can advertise with: ads need one (create it, or ask its admin "
                            "for the Advertise task); until then nothing is published")
    return MetaConnection(token, acct.account_id, acct.name, acct.currency, page.page_id if page else None,
                          page.name if page else None, app_id, d.user_name, d.granted, sandbox, warnings)


def connect(token: str, *, account_id: str | None = None, page_id: str | None = None, app_id: str | None = None,
            sandbox: bool = False, version: str = "v26.0", http: httpx.Client | None = None,
            folder: Path = CONNECTIONS, say: Callable[[str], None] = print) -> tuple[MetaConnection, Path]:
    """From a Meta login token to a saved connection (or a ConnectError saying what to fix)."""
    reader = GraphReader(token, version=version, http=http)
    d = discover(reader)
    say(f"logged in as {d.user_name or d.user_id}: {len(d.accounts)} ad account(s), {len(d.pages)} Page(s), "
        f"permissions: {', '.join(d.granted) or 'none'}")
    conn = choose(d, reader.token, account_id=account_id, page_id=page_id, app_id=app_id, sandbox=sandbox)
    return conn, conn.save(folder)


def check(conn: MetaConnection, *, version: str = "v26.0", http: httpx.Client | None = None) -> list[str]:
    """Before acting: is the login still valid and the account still usable? Returns problems (empty = fine)."""
    reader = GraphReader(conn.token, version=version, http=http)
    try:
        acct = reader.get(conn.act, fields="account_status,currency,name")
    except ConnectError as exc:
        return [str(exc)]
    status = int(acct.get("account_status") or 0)
    if status not in USABLE_STATUS:
        return [f"ad account {conn.account_id} is now {ACCOUNT_STATUS.get(status, status)}"]
    return []
