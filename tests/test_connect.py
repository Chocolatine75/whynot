"""Connecting an owner's Meta login: find and check the ad account and Page, against a fake Graph API.

The fake answers like the real one where it matters: token check (error 190), paged edges whose next-page URL
embeds the token, account status codes, Page tasks."""

import json
import stat

import httpx
import pytest

from whynot.run.connect import ConnectError, MetaConnection, check, connect

TOKEN = "EAAownerLOGINtoken42"
PERMS = ["ads_management", "ads_read", "pages_show_list", "pages_read_engagement", "business_management"]


def account(n, status=1, currency="EUR", name=None):
    return {"account_id": str(n), "id": f"act_{n}", "name": name or f"Account {n}", "account_status": status,
            "currency": currency}


class Graph:
    def __init__(self, *, perms=PERMS, declined=(), accounts=None, pages=(("999", ["ADVERTISE"]),),
                 page_size=100, expired=False):
        self.perms = [{"permission": p, "status": "granted"} for p in perms]
        self.perms += [{"permission": p, "status": "declined"} for p in declined]
        self.accounts = list(accounts) if accounts is not None else [account(111)]
        self.page_size, self.expired = page_size, expired
        self.pages = [{"id": pid, "name": f"Page {pid}", "tasks": tasks} for pid, tasks in pages]
        self.urls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.urls.append(str(request.url))
        params = dict(request.url.params)
        if self.expired or params.get("access_token") != TOKEN:
            return httpx.Response(400, json={"error": {"code": 190, "message": f"Session expired for {TOKEN}"}})
        path = request.url.path.split("/", 2)[2]
        if path == "me":
            return httpx.Response(200, json={"id": "42", "name": "Owner"})
        rows = {"me/permissions": self.perms, "me/adaccounts": self.accounts, "me/accounts": self.pages}.get(path)
        if rows is None:  # one ad account read back
            acct = next((a for a in self.accounts if a["id"] == path), None)
            return httpx.Response(200, json=acct) if acct else httpx.Response(
                400, json={"error": {"code": 100, "message": "unknown"}})
        start = int(params.get("after", 0))
        body: dict = {"data": rows[start:start + self.page_size]}
        if start + self.page_size < len(rows):
            # like Meta: the next-page URL carries the token
            body["paging"] = {"next": f"https://graph.facebook.com/v26.0/{path}?access_token={TOKEN}"
                                      f"&limit={self.page_size}&after={start + self.page_size}"}
        return httpx.Response(200, json=body)


def http(graph: Graph) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(graph))


def go(tmp_path, graph=None, **kw):
    graph = graph or Graph()
    conn, path = connect(TOKEN, http=http(graph), folder=tmp_path, say=lambda m: None, **kw)
    return conn, path, graph


def test_one_account_one_page_connects_and_saves_privately(tmp_path):
    conn, path, _ = go(tmp_path)
    assert (conn.act, conn.page_id, conn.currency, conn.can_publish, conn.can_read) == (
        "act_111", "999", "EUR", True, True)
    assert conn.warnings == []
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and path.name == "act_111.json"
    assert MetaConnection.load(path).token == TOKEN
    assert TOKEN not in json.dumps(conn.public())


def test_paged_accounts_are_all_read_and_named_one_is_used(tmp_path):
    graph = Graph(accounts=[account(n) for n in range(1, 8)], page_size=3)
    conn, _, graph = go(tmp_path, graph, account_id="act_7")
    assert conn.account_id == "7"
    assert sum("me/adaccounts" in u for u in graph.urls) == 3  # three pages followed


def test_several_active_accounts_must_be_named(tmp_path):
    with pytest.raises(ConnectError, match=r"several ad accounts.*111.*222"):
        go(tmp_path, Graph(accounts=[account(111), account(222)]))


def test_an_unknown_account_lists_the_usable_ones(tmp_path):
    with pytest.raises(ConnectError, match=r"not one this login can use.*111"):
        go(tmp_path, account_id="555")


@pytest.mark.parametrize("status, words", [(2, "disabled"), (3, "unsettled"), (101, "closed")])
def test_an_unusable_account_says_why(tmp_path, status, words):
    with pytest.raises(ConnectError, match=words):
        go(tmp_path, Graph(accounts=[account(111, status=status)]))
    with pytest.raises(ConnectError, match=words):
        go(tmp_path, Graph(accounts=[account(111, status=status)]), account_id="111")


def test_without_ads_management_nothing_is_saved(tmp_path):
    with pytest.raises(ConnectError, match=r"cannot manage ads.*ads_management"):
        go(tmp_path, Graph(perms=["ads_read"], declined=["ads_management"]))
    assert not list(tmp_path.iterdir())


def test_warnings_for_currency_grace_period_and_missing_extras(tmp_path):
    conn, _, _ = go(tmp_path, Graph(accounts=[account(111, status=9, currency="USD")],
                                    perms=["ads_management", "ads_read"]))
    text = " ".join(conn.warnings)
    assert "bills in USD" in text and "grace period" in text and "pages_show_list" in text


def test_several_pages_or_none_means_no_publishing_yet(tmp_path):
    conn, _, _ = go(tmp_path, Graph(pages=[("1", ["ADVERTISE"]), ("2", ["MANAGE"])]))
    assert conn.page_id is None and not conn.can_publish and "several Pages" in " ".join(conn.warnings)
    conn, _, _ = go(tmp_path, Graph(pages=[("1", ["ANALYZE"])]))
    assert conn.page_id is None and "no Facebook Page" in " ".join(conn.warnings)
    conn, _, _ = go(tmp_path, Graph(pages=[("1", ["ADVERTISE"]), ("2", ["MANAGE"])]), page_id="2")
    assert conn.page_id == "2" and conn.can_publish
    with pytest.raises(ConnectError, match="Page 3 is not one"):
        go(tmp_path, page_id="3")


def test_an_expired_login_says_so_without_leaking_the_token(tmp_path):
    with pytest.raises(ConnectError) as exc:
        go(tmp_path, Graph(expired=True))
    assert "expired or was revoked" in str(exc.value) and TOKEN not in str(exc.value)


def test_no_token_is_refused_before_any_call(tmp_path):
    with pytest.raises(ConnectError, match="no Meta access token"):
        connect("  ", http=http(Graph()), folder=tmp_path, say=lambda m: None)


def test_check_reports_a_revoked_login_or_a_disabled_account(tmp_path):
    conn, _, _ = go(tmp_path)
    assert check(conn, http=http(Graph())) == []
    assert "now disabled" in check(conn, http=http(Graph(accounts=[account(111, status=2)])))[0]
    problems = check(conn, http=http(Graph(expired=True)))
    assert "expired" in problems[0] and TOKEN not in problems[0]


def test_loading_a_missing_connection_says_what_to_run(tmp_path):
    with pytest.raises(ConnectError, match="whynot connect"):
        MetaConnection.load(tmp_path / "nope.json")
