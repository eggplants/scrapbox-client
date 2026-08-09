"""Tests for the endpoints that cannot be reached without a credential.

These use an `httpx.MockTransport` rather than the real API, so the request the
client builds is still assembled by the real code path: headers, the personal
access token hook and the JSON body are all exercised.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

import httpx
import pytest

from scrapbox.client import (
    MAX_PAGE_SIZE,
    PAT_HEADER,
    SCRAPBOX_ORIGIN,
    SERVICE_ACCOUNT_HEADER,
    ScrapboxClient,
    bare_file_id,
    page_url,
)
from scrapbox.edits import changes_from_ops
from scrapbox.exceptions import (
    NotAuthenticatedError,
    PersonalAccessTokenRequiredError,
    SearchServerUpdatingError,
)
from scrapbox.models import TitleChange, UpdateChange

PAT = "pat_test"


def build_client(
    handler: Any,  # noqa: ANN401
    pat: str | None = PAT,
    connect_sid: str | None = None,
    service_account_key: str | None = None,
) -> ScrapboxClient:
    """Build a client whose requests are answered by a handler.

    Args:
        handler: Callable taking an `httpx.Request` and returning an `httpx.Response`.
        pat: Personal access token to authenticate with.
        connect_sid: Cookie to authenticate with.
        service_account_key: Service account access key to authenticate with.

    Returns:
        The client.
    """
    return ScrapboxClient(
        connect_sid=connect_sid,
        pat=pat,
        service_account_key=service_account_key,
        transport=httpx.MockTransport(handler),
    )


def json_handler(payload: Any, recorder: list[httpx.Request] | None = None) -> Any:  # noqa: ANN401
    """Build a handler answering every request with the same JSON payload.

    Args:
        payload: The JSON body to answer with.
        recorder: List the received requests are appended to, if given.

    Returns:
        The handler.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        return httpx.Response(200, json=payload)

    return handler


class TestAuthenticatedReads:
    """Test the read endpoints that require a credential."""

    def test_get_me(self) -> None:
        """Test getting the authenticated user."""
        payload = {
            "id": "5724627723541f110097c291",
            "name": "shokai",
            "displayName": "Sho Hashimoto",
            "email": "shokai@example.com",
            "provider": "google",
            "pageFilters": [{"type": "icon", "value": "shokai"}],
            "created": 1654254216,
            "updated": 1786255768,
            "isGuest": False,
            "config": {},
        }
        requests: list[httpx.Request] = []
        with build_client(json_handler(payload, requests)) as client:
            me = client.get_me()

        assert me.name == "shokai"
        assert me.page_filters[0].value == "shokai"
        assert str(requests[0].url) == f"{SCRAPBOX_ORIGIN}/api/users/me"
        assert requests[0].headers[PAT_HEADER] == PAT

    def test_get_me_without_a_credential(self) -> None:
        """Test that being logged out becomes an exception rather than a parse error.

        This endpoint does not answer 401: without a credential it answers 200 with
        `{"isGuest": true}` and no user at all.
        """
        requests: list[httpx.Request] = []
        with (
            build_client(json_handler({"isGuest": True}, requests), pat=None) as client,
            pytest.raises(NotAuthenticatedError, match="Not authenticated"),
        ):
            client.get_me()

        assert str(requests[0].url) == f"{SCRAPBOX_ORIGIN}/api/users/me"

    def test_get_projects(self) -> None:
        """Test getting the projects the user belongs to."""
        payload = {
            "projects": [
                {
                    "id": "57b3fe09ec2b330f00f15382",
                    "name": "icons",
                    "displayName": "Icons",
                    "publicVisible": True,
                    "loginStrategies": [],
                    "additionalPlans": {},
                    "created": 1471413769,
                    "updated": 1784260784,
                    "usersCount": 288,
                    "isMember": True,
                    "isOwner": False,
                    "isAdmin": False,
                    "adminsCount": 0,
                }
            ]
        }
        with build_client(json_handler(payload)) as client:
            projects = client.get_projects()

        assert projects.projects[0].name == "icons"
        assert projects.projects[0].public_visible

    def test_get_commits(self) -> None:
        """Test getting the edit history of a page."""
        payload = {
            "commits": [
                {
                    "id": "6a78192e2c5aac9b66e0859d",
                    "kind": "page",
                    "changes": [
                        {"_update": "6a78192b3a6ddc39bdf42b47", "lines": {"text": "hey", "origText": "hello"}},
                        {"linesCount": 1},
                        {"title": "hey", "titleLc": "hey"},
                    ],
                    "parentId": None,
                    "pageId": "6a78192b3a6ddc39bdf42b47",
                    "userId": "6299ea8890dfc9002310f0e4",
                    "created": 1786255662,
                }
            ]
        }
        requests: list[httpx.Request] = []
        with build_client(json_handler(payload, requests)) as client:
            commits = client.get_commits("my-project", "6a78192b3a6ddc39bdf42b47", since="abc123")

        edit, metadata, rename = commits.commits[0].changes
        # The body edit and the rename get their own models; the derived metadata
        # change has none and stays a plain dict.
        assert isinstance(edit, UpdateChange)
        assert edit.update == "6a78192b3a6ddc39bdf42b47"
        assert edit.lines.orig_text == "hello"
        assert metadata == {"linesCount": 1}
        assert isinstance(rename, TitleChange)
        assert rename.title == "hey"
        assert requests[0].url.params["head"] == "abc123"

    def test_get_file_info(self) -> None:
        """Test getting the metadata of an uploaded file."""
        payload = {
            "id": "5f151efbacbb17001a58f120",
            "projectName": "my-project",
            "text": "extracted text",
            "originalname": "shot.png",
            "contentType": "image/png",
            "size": 242180,
        }
        requests: list[httpx.Request] = []
        with build_client(json_handler(payload, requests)) as client:
            info = client.get_file_info("https://scrapbox.io/files/5f151efbacbb17001a58f120.png")

        assert info.content_type == "image/png"
        assert info.text == "extracted text"
        assert str(requests[0].url) == f"{SCRAPBOX_ORIGIN}/api/gcs/5f151efbacbb17001a58f120/info"

    def test_search_server_updating_is_typed(self) -> None:
        """Test that the non-standard 490 status becomes a dedicated exception."""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                490,
                json={"name": "UpdatingSearchServerError", "message": "Updating search server."},
            )

        with build_client(handler) as client, pytest.raises(SearchServerUpdatingError, match="Updating search server"):
            client.search_titles_by_vector("my-project", "query")


class TestErrorMessages:
    """Test that the explanation in an error body survives into the exception.

    The status code on its own is often uninformative: a service account pointed at
    the wrong project gets a bare 400.
    """

    def test_named_error_is_reported(self) -> None:
        """Test that both the name and the message of an API error are reported."""
        payload = {"name": "BadRequestError", "message": "Service account is not available for this project."}

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json=payload)

        with build_client(handler) as client, pytest.raises(httpx.HTTPStatusError) as excinfo:
            client.get_pages("other-project")

        assert "BadRequestError: Service account is not available for this project." in str(excinfo.value)
        assert excinfo.value.response.status_code == httpx.codes.BAD_REQUEST

    def test_message_only_error_is_reported(self) -> None:
        """Test an error body carrying no name, as the edit endpoints send."""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"message": "preview not found or expired"})

        with build_client(handler) as client, pytest.raises(httpx.HTTPStatusError, match="preview not found"):
            client.submit_page_edit("my-project", "000000000000000000000000")

    def test_a_body_without_an_explanation_is_left_alone(self) -> None:
        """Test that a non-JSON error body still raises the plain httpx error."""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(500, content=b"<html>oops</html>")

        with build_client(handler) as client, pytest.raises(httpx.HTTPStatusError) as excinfo:
            client.get_pages("my-project")

        assert "oops" not in str(excinfo.value)


class TestPageEdit:
    """Test the page edit endpoints."""

    PAGE_ID = "6a78192b3a6ddc39bdf42b47"

    PREVIEW_PAYLOAD: ClassVar[dict[str, Any]] = {
        "previewId": "6a78216d0b154dadc8dcd414",
        "expireAt": "2026-08-09T06:47:53.590Z",
        "pagePreview": {
            "title": "test",
            "persistent": True,
            "lines": [{"id": "6a78192b3a6ddc39bdf42b47", "text": "test"}],
        },
    }

    def test_preview_sends_changes_and_page_id(self) -> None:
        """Test the request body of a preview for an existing page."""
        requests: list[httpx.Request] = []
        changes = changes_from_ops([{"insertBefore": "_end", "text": "one\ntwo"}])
        with build_client(json_handler(self.PREVIEW_PAYLOAD, requests)) as client:
            preview = client.preview_page_edit("my-project", changes, page_id=self.PAGE_ID)

        assert preview.preview_id == "6a78216d0b154dadc8dcd414"
        body = json.loads(requests[0].content)
        assert body["pageId"] == self.PAGE_ID
        # A two-line text becomes two insertions, each with a client-generated id.
        assert [change["_insert"] for change in body["changes"]] == ["_end", "_end"]
        assert [change["lines"]["text"] for change in body["changes"]] == ["one", "two"]
        assert all(len(change["lines"]["id"]) == 24 for change in body["changes"])  # noqa: PLR2004

    def test_preview_without_page_id_omits_it(self) -> None:
        """Test that creating a page sends no pageId at all."""
        requests: list[httpx.Request] = []
        changes = changes_from_ops([{"insertBefore": "_end", "text": "new page"}])
        with build_client(json_handler(self.PREVIEW_PAYLOAD, requests)) as client:
            client.preview_page_edit("my-project", changes)

        assert "pageId" not in json.loads(requests[0].content)

    def test_write_requests_authenticate_with_the_token(self) -> None:
        """Test that a write is authenticated by the token alone.

        The API's `CrossOriginWriteNotAllowedError` guards cookie authentication
        only: a token-authenticated write is accepted whatever `Origin` says, so
        none is sent.
        """
        requests: list[httpx.Request] = []
        with build_client(json_handler(self.PREVIEW_PAYLOAD, requests)) as client:
            client.preview_page_edit("my-project", [])

        assert requests[0].headers[PAT_HEADER] == PAT
        assert "Origin" not in requests[0].headers

    def test_submit(self) -> None:
        """Test committing a previewed edit.

        `page` arrives as a whole v2 page; only the id and the title are read out of
        it, and the fields with no model must not get in the way.
        """
        payload = {
            "commitId": "6a7821775ef194e8f89322cc",
            "page": {
                "id": self.PAGE_ID,
                "title": "test",
                "persistent": True,
                "commitId": "6a7821775ef194e8f89322cc",
                "lines": [{"id": self.PAGE_ID, "text": "test", "userId": "u1", "created": 1, "updated": 2}],
                "linesCount": 1,
                "charsCount": 4,
            },
        }
        requests: list[httpx.Request] = []
        with build_client(json_handler(payload, requests)) as client:
            result = client.submit_page_edit("my-project", "6a78216d0b154dadc8dcd414")

        assert result.commit_id == "6a7821775ef194e8f89322cc"
        assert result.page is not None
        assert result.page.id == self.PAGE_ID
        assert result.page.title == "test"
        assert json.loads(requests[0].content) == {"previewId": "6a78216d0b154dadc8dcd414"}

    def test_submit_of_a_creation_reports_the_title_the_page_got(self) -> None:
        """Test the response to a submit that created a page.

        A title already taken gets a suffix and the first line is rewritten to match,
        so the requested title and the resulting one differ. The page takes the id of
        the line the first `_insert` carried.
        """
        line_id = "2b049d90fb091d365760e1c6"
        payload = {
            "commitId": "6a7847d78d06daa629829b15",
            "page": {
                "id": line_id,
                "title": "sbc-create-test_2",
                "persistent": True,
                "lines": [{"id": line_id, "text": "sbc-create-test_2", "userId": "u1", "created": 1, "updated": 1}],
            },
        }
        with build_client(json_handler(payload)) as client:
            result = client.submit_page_edit("my-project", "6a78216d0b154dadc8dcd414")

        assert result.page is not None
        assert result.page.id == line_id
        assert result.page.title == "sbc-create-test_2"

    def test_submit_without_a_page_id(self) -> None:
        """Test a submit response that names no id, so the id stays optional."""
        payload = {"commitId": "6a7821775ef194e8f89322cc", "page": {"title": "test"}}
        with build_client(json_handler(payload)) as client:
            result = client.submit_page_edit("my-project", "6a78216d0b154dadc8dcd414")

        assert result.page is not None
        assert result.page.id is None
        assert result.page.title == "test"

    def test_a_service_account_may_write(self) -> None:
        """Test that a service account access key is accepted for a write.

        The API takes either header credential here; only a cookie is refused. An
        edit submitted this way is attributed to the service account.
        """
        requests: list[httpx.Request] = []
        with build_client(json_handler(self.PREVIEW_PAYLOAD, requests), pat=None, service_account_key="cs_test") as c:
            preview = c.preview_page_edit("my-project", [], page_id=self.PAGE_ID)

        assert preview.preview_id == "6a78216d0b154dadc8dcd414"
        assert requests[0].headers[SERVICE_ACCOUNT_HEADER] == "cs_test"
        assert PAT_HEADER not in requests[0].headers

    @pytest.mark.parametrize(
        "credentials",
        [
            {"pat": None},
            {"pat": None, "connect_sid": "s%3Atest"},
        ],
    )
    def test_edit_without_pat_never_reaches_the_network(self, credentials: dict[str, Any]) -> None:
        """Test that editing without a header credential fails before a request is sent.

        The API rejects cookie authentication for these endpoints, so there is no
        point in sending the request.
        """
        requests: list[httpx.Request] = []
        with (
            build_client(json_handler({}, requests), **credentials) as client,
            pytest.raises(PersonalAccessTokenRequiredError, match="personal access token"),
        ):
            client.preview_page_edit("my-project", [])

        assert requests == []

    def test_submit_without_pat_never_reaches_the_network(self) -> None:
        """Test that submitting without a token fails before a request is sent."""
        requests: list[httpx.Request] = []
        with (
            build_client(json_handler({}, requests), pat=None) as client,
            pytest.raises(PersonalAccessTokenRequiredError),
        ):
            client.submit_page_edit("my-project", "preview-id")

        assert requests == []


class TestPageSizeValidation:
    """Test that a page size the API would silently replace is refused.

    The API answers 200 for an out-of-range size, serving a different number of
    entries than asked for, so these must fail before a request is sent.
    """

    OUT_OF_RANGE: ClassVar[list[int]] = [0, -1, MAX_PAGE_SIZE + 1, 5000]

    @pytest.mark.parametrize("limit", OUT_OF_RANGE)
    def test_get_pages_refuses_an_out_of_range_limit(self, limit: int) -> None:
        """Test that the page list refuses a limit outside the accepted range."""
        requests: list[httpx.Request] = []
        with (
            build_client(json_handler({}, requests)) as client,
            pytest.raises(ValueError, match=rf"limit must be between 1 and {MAX_PAGE_SIZE}, got {limit}"),
        ):
            client.get_pages("my-project", limit=limit)

        assert requests == []

    @pytest.mark.parametrize("limit", [1, 100, MAX_PAGE_SIZE])
    def test_get_pages_accepts_the_range(self, limit: int) -> None:
        """Test that the ends of the accepted range are sent as given."""
        requests: list[httpx.Request] = []
        payload = {"projectName": "my-project", "skip": 0, "limit": limit, "count": 0, "pages": []}
        with build_client(json_handler(payload, requests)) as client:
            client.get_pages("my-project", limit=limit)

        assert requests[0].url.params["limit"] == str(limit)

    @pytest.mark.parametrize("per_page", OUT_OF_RANGE)
    @pytest.mark.parametrize("method", ["get_links_1hop", "get_links_2hop"])
    def test_get_links_refuses_an_out_of_range_per_page(self, method: str, per_page: int) -> None:
        """Test that both related pages endpoints refuse an out-of-range page size."""
        requests: list[httpx.Request] = []
        with (
            build_client(json_handler({}, requests)) as client,
            pytest.raises(ValueError, match=rf"per_page must be between 1 and {MAX_PAGE_SIZE}"),
        ):
            getattr(client, method)("my-project", "title", per_page=per_page)

        assert requests == []

    @pytest.mark.parametrize("method", ["iter_links_1hop", "iter_links_2hop"])
    def test_iter_links_refuses_before_it_is_iterated(self, method: str) -> None:
        """Test that the iterators check the page size when they are called.

        A generator function would defer the check to the first `next()`, which
        would surface the mistake far from the call that made it.
        """
        requests: list[httpx.Request] = []
        with (
            build_client(json_handler({}, requests)) as client,
            pytest.raises(ValueError, match="per_page must be between"),
        ):
            getattr(client, method)("my-project", "title", per_page=MAX_PAGE_SIZE + 1)

        assert requests == []


class TestRelatedPagesPagination:
    """Test walking the cursor of the related pages endpoints.

    The public project used elsewhere has a neighbourhood small enough to fit in one
    response, so the multi-page cases are served by a handler here.
    """

    @staticmethod
    def paged_handler(pages: list[dict[str, Any]]) -> Any:  # noqa: ANN401
        """Build a handler serving a fixed sequence of pages, keyed by the cursor.

        Args:
            pages: One payload per response, served in order.

        Returns:
            The handler.
        """
        by_cursor = {None if index == 0 else f"cursor{index}": page for index, page in enumerate(pages)}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=by_cursor[request.url.params.get("nextId")])

        return handler

    @staticmethod
    def page(entries: list[str], next_id: str | None) -> dict[str, Any]:
        """Build one response of the 1-hop endpoint.

        Args:
            entries: Ids of the entries on this page. Titles are derived from them.
            next_id: Cursor of the next page, or None for the last one.

        Returns:
            The payload.
        """
        return {
            "links1hop": [{"id": entry, "title": f"page {entry}"} for entry in entries],
            "pagination": {"perPage": 2, "total": 5, "hasNext": next_id is not None, "nextId": next_id},
        }

    def test_iter_walks_every_page(self) -> None:
        """Test that the iterator concatenates the pages the cursor leads to."""
        requests: list[httpx.Request] = []
        pages = [
            self.page(["a", "b"], "cursor1"),
            self.page(["c", "d"], "cursor2"),
            self.page(["e"], None),
        ]
        handler = self.paged_handler(pages)

        def recording(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return handler(request)

        with build_client(recording) as client:
            found = list(client.iter_links_1hop("my-project", "title", per_page=2))

        assert [entry.id for entry in found] == ["a", "b", "c", "d", "e"]
        # The first request carries no cursor; each later one carries the previous nextId.
        assert [request.url.params.get("nextId") for request in requests] == [None, "cursor1", "cursor2"]
        assert all(request.url.params["perPage"] == "2" for request in requests)

    def test_iter_is_lazy(self) -> None:
        """Test that pages are fetched only as their entries are consumed."""
        requests: list[httpx.Request] = []
        handler = self.paged_handler([self.page(["a", "b"], "cursor1"), self.page(["c"], None)])

        def recording(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return handler(request)

        with build_client(recording) as client:
            first = next(iter(client.iter_links_1hop("my-project", "title", per_page=2)))

        assert first.id == "a"
        assert len(requests) == 1

    def test_iter_stops_on_an_empty_page_that_still_has_a_cursor(self) -> None:
        """Test that a page emptied by `search` does not end the walk.

        A search filters within a page rather than across the neighbourhood, so a page
        can come back empty while entries remain further along the cursor.
        """
        pages = [self.page([], "cursor1"), self.page(["c", "d"], None)]
        with build_client(self.paged_handler(pages)) as client:
            found = list(client.iter_links_1hop("my-project", "title", "query", per_page=2))

        assert [entry.id for entry in found] == ["c", "d"]

    def test_iter_stops_when_the_cursor_stops_advancing(self) -> None:
        """Test that a cursor pointing at itself does not loop forever."""

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=self.page(["a"], "cursor1"))

        with build_client(handler) as client:
            found = list(client.iter_links_1hop("my-project", "title"))

        # Two requests: the first without a cursor, the second with `cursor1`, which
        # answers with `cursor1` again.
        assert [entry.id for entry in found] == ["a", "a"]

    def test_iter_stops_without_pagination(self) -> None:
        """Test that a response carrying no pagination ends the walk."""
        payload = {"links2hop": [{"id": "a", "title": "page a"}]}
        with build_client(json_handler(payload)) as client:
            found = list(client.iter_links_2hop("my-project", "title"))

        assert [entry.id for entry in found] == ["a"]


class TestUrlHelpers:
    """Test the URL helpers."""

    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("5f151efbacbb17001a58f120", "5f151efbacbb17001a58f120"),
            ("5f151efbacbb17001a58f120.png", "5f151efbacbb17001a58f120"),
            ("https://scrapbox.io/files/5f151efbacbb17001a58f120.tar.gz", "5f151efbacbb17001a58f120"),
        ],
    )
    def test_bare_file_id(self, given: str, expected: str) -> None:
        """Test reducing a file reference to its id."""
        assert bare_file_id(given) == expected

    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("simple", "simple"),
            ("with space", "with_space"),
            ("a/b", "a%2Fb"),
            ("100%", "100%25"),
            ("what?", "what%3F"),
            ("tag#1", "tag%231"),
        ],
    )
    def test_page_url(self, title: str, expected: str) -> None:
        """Test building a page URL from a title."""
        assert page_url("my-project", title) == f"{SCRAPBOX_ORIGIN}/my-project/{expected}"


class TestThumbnail:
    """Test the thumbnail option of file downloads."""

    def test_thumbnail_adds_the_query_parameter(self) -> None:
        """Test that the scaled down version is requested explicitly."""
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, content=b"binary")

        with build_client(handler, pat=None) as client:
            client.get_file("5f151efbacbb17001a58f120.png", thumbnail=True)

        assert requests[0].url.params["type"] == "thumbnail"

    def test_no_thumbnail_parameter_by_default(self) -> None:
        """Test that a plain download asks for the original."""
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, content=b"binary")

        with build_client(handler, pat=None) as client:
            client.get_file("5f151efbacbb17001a58f120.png")

        assert "type" not in requests[0].url.params
