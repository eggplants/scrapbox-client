"""Scrapbox API client."""

from typing import TYPE_CHECKING, Any, Literal, Self
from urllib.parse import quote, urlparse

import httpx

from .exceptions import NotAuthenticatedError, PersonalAccessTokenRequiredError, SearchServerUpdatingError
from .models import (
    CommitsResponse,
    EditPreviewResponse,
    EditSubmitResponse,
    FileInfo,
    GyazoOEmbedResponse,
    GyazoOEmbedResponsePhoto,
    Links1hopResponse,
    Links2hopResponse,
    Me,
    PageDetail,
    PageDetailV2,
    PageListResponse,
    ProjectDetail,
    ProjectsResponse,
    ProjectUsersResponse,
    SearchResponse,
    VectorSearchResponse,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence
    from types import TracebackType

    from .models import LinkPage, PageChange

PAT_HEADER = "x-personal-access-token"
"""Header carrying the personal access token."""

SERVICE_ACCOUNT_HEADER = "x-service-account-access-key"
"""Header carrying the service account access key."""

SCRAPBOX_HOST = "scrapbox.io"
"""Host a header credential may be sent to."""

SCRAPBOX_ORIGIN = f"https://{SCRAPBOX_HOST}"
"""Origin every URL is built from."""


MAX_PAGE_SIZE = 1000
"""Most entries the paginated endpoints return in one response.

The API neither errors nor reports that a request asked for more: it silently
serves 1000, and a page size below 1 silently becomes something else again. A
caller reading `len(...)` has no way to tell that from a short final page, so this
client refuses an out-of-range size instead of passing it on.
"""


PageSort = Literal["updated", "created", "accessed", "linked", "views", "title"]
"""Orders the page list API accepts. Pinned pages always come first."""

SearchSort = Literal["pageRank", "updated"]
"""Orders the full-text search API accepts."""


def bare_file_id(file_id: str) -> str:
    """Strip a file id down to the form the metadata endpoint expects.

    Args:
        file_id: A file id, a file id with an extension, or a full file URL.

    Returns:
        The file id on its own.
    """
    tail = urlparse(file_id).path if file_id.startswith(("http://", "https://")) else file_id
    return tail.rsplit("/", 1)[-1].split(".", 1)[0]


def check_page_size(value: int, name: str = "page size") -> int:
    """Reject a page size the API would silently replace with another.

    Args:
        value: The page size to check.
        name: How the message refers to the value. Callers that have an argument
            name pass it so that the message names it.

    Returns:
        The page size, unchanged.

    Raises:
        ValueError: If the page size is outside 1 to `MAX_PAGE_SIZE`.
    """
    if not 1 <= value <= MAX_PAGE_SIZE:
        msg = f"{name} must be between 1 and {MAX_PAGE_SIZE}, got {value}"
        raise ValueError(msg)
    return value


def page_url(project_name: str, title: str) -> str:
    """Build the URL of a page from its title.

    A title is part of the URL, so `/`, `%`, `?` and `#` are percent-encoded and
    spaces become underscores, matching how Cosense writes readable links.

    Args:
        project_name: The name of the project.
        title: The page title.

    Returns:
        The URL of the page.
    """
    encoded = title.replace("%", "%25").replace("/", "%2F").replace("?", "%3F").replace("#", "%23").replace(" ", "_")
    return f"{SCRAPBOX_ORIGIN}/{project_name}/{encoded}"


class ScrapboxClient:
    """Scrapbox API client.

    This client provides methods to interact with the Scrapbox API,
    including retrieving page lists, page details, page text, and files.
    """

    """Base URL for the Scrapbox API."""
    BASE_URL = f"{SCRAPBOX_ORIGIN}/api"

    def __init__(
        self,
        connect_sid: str | None = None,
        pat: str | None = None,
        service_account_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Initialize the Scrapbox API client.

        Authentication is optional for public projects. Only one credential is ever
        sent: given more than one, a personal access token wins over a service
        account key, which in turn wins over a cookie.

        Args:
            connect_sid: Scrapbox authentication cookie (connect.sid).
            pat: Scrapbox personal access token, sent as the `x-personal-access-token`
                header.
            service_account_key: Access key of a service account, sent as the
                `x-service-account-access-key` header. A service account is registered
                on one project of a Business plan and can read and write only that
                one: any other project, even a public one, answers 400. It stands for
                no user, so `get_me` and `get_projects` are out of its reach, and
                `get_project` refuses it as well.
            transport: Transport used by the underlying HTTP client. Intended for
                tests, which pass an `httpx.MockTransport` so that header handling
                is still exercised.
        """
        self.pat = pat
        self.service_account_key = None if pat else service_account_key
        self.connect_sid = None if pat or service_account_key else connect_sid
        self.client = httpx.Client(
            cookies={"connect.sid": self.connect_sid} if self.connect_sid else None,
            follow_redirects=True,
            transport=transport,
        )
        if self.pat or self.service_account_key:
            # Attach the credential per request instead of as a default header:
            # get_file() follows redirects to third-party hosts (Gyazo), which must
            # not receive it.
            self.client.event_hooks["request"].append(self._attach_credential)

    def _attach_credential(self, request: httpx.Request) -> None:
        """Attach the header credential to requests sent to Scrapbox.

        Args:
            request: The outgoing request.
        """
        if request.url.host != SCRAPBOX_HOST:
            return
        if self.pat:
            request.headers[PAT_HEADER] = self.pat
        elif self.service_account_key:
            request.headers[SERVICE_ACCOUNT_HEADER] = self.service_account_key

    def __enter__(self: Self) -> Self:
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, typ: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None, /) -> None:
        """Exit the runtime context related to this object."""
        self.client.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    @staticmethod
    def _error_detail(response: httpx.Response) -> str | None:
        """Read the explanation the API put in an error body.

        Most of `/api/` answers `{"name": ..., "message": ...}`; the oEmbed proxy and
        the edit endpoints answer with `message` alone.

        Args:
            response: The error response to read.

        Returns:
            The explanation, or None if the body carries none.
        """
        try:
            body = response.json()
        except ValueError:
            return None
        if not isinstance(body, dict):
            return None
        message = body.get("message") or body.get("error")
        if not message:
            return None
        name = body.get("name")
        return f"{name}: {message}" if name else str(message)

    @classmethod
    def _raise_for_status(cls, response: httpx.Response) -> None:
        """Turn an error response into an exception.

        The status code alone rarely says what went wrong -- a service account asked
        for the wrong project gets a bare 400 -- so the API's own explanation is
        carried into the error message.

        Args:
            response: The response to inspect.

        Raises:
            SearchServerUpdatingError: If the search backend is being updated.
            httpx.HTTPStatusError: If the response carries any other error status.
        """
        if response.status_code == SearchServerUpdatingError.STATUS_CODE:
            # The name adds nothing here: the exception class already carries it.
            try:
                message = response.json().get("message")
            except ValueError:
                message = None
            raise SearchServerUpdatingError(message)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = cls._error_detail(response)
            if detail is None:
                raise
            msg = f"{e}\n{detail}"
            raise httpx.HTTPStatusError(msg, request=e.request, response=e.response) from None

    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> httpx.Response:
        """Send a GET request to a path under `BASE_URL`.

        Args:
            path: Path below `BASE_URL`, starting with a slash.
            params: Query parameters. Entries are sent as given.

        Returns:
            The successful response.
        """
        response = self.client.get(f"{self.BASE_URL}{path}", params=params)
        self._raise_for_status(response)
        return response

    def _get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:  # noqa: ANN401
        """Send a GET request and decode the JSON body.

        Args:
            path: Path below `BASE_URL`, starting with a slash.
            params: Query parameters. Entries are sent as given.

        Returns:
            The decoded JSON body.
        """
        return self._get(path, params).json()

    def _post_json(self, path: str, payload: Mapping[str, Any]) -> Any:  # noqa: ANN401
        """Send a POST request and decode the JSON body.

        Write endpoints take a header credential -- a personal access token or a
        service account access key -- and refuse a cookie with HTTP 403, so the
        request is not even sent without one.

        Args:
            path: Path below `BASE_URL`, starting with a slash.
            payload: JSON body to send.

        Returns:
            The decoded JSON body.

        Raises:
            PersonalAccessTokenRequiredError: If neither a personal access token nor a
                service account access key is set.
        """
        if not (self.pat or self.service_account_key):
            raise PersonalAccessTokenRequiredError(path)
        response = self.client.post(f"{self.BASE_URL}{path}", json=dict(payload))
        self._raise_for_status(response)
        return response.json()

    def get_pages(
        self,
        project_name: str,
        skip: int = 0,
        limit: int = 100,
        sort: PageSort | None = None,
        filter_value: str | None = None,
    ) -> PageListResponse:
        """Get a list of pages from a project.

        The page bodies are not included. At most 1000 pages come back per request,
        so `skip` is how a whole project is walked.

        Args:
            project_name: The name of the project.
            skip: Number of pages to skip (default: 0).
            limit: Number of pages to retrieve (default: 100, max: 1000).
            sort: Order of the returned pages (default: the API's own, `updated`).
            filter_value: Keep only the pages carrying a `[<value>.icon]` reference,
                plus the pages that user has edited. Use the login name, not the
                display name.

        Returns:
            PageListResponse: The response containing the page list.

        Raises:
            ValueError: If `limit` is outside 1 to `MAX_PAGE_SIZE`.
        """
        check_page_size(limit, "limit")
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if sort is not None:
            params["sort"] = sort
        if filter_value is not None:
            params["filterType"] = "icon"
            params["filterValue"] = filter_value
        return PageListResponse.model_validate(self._get_json(f"/pages/{project_name}", params))

    def get_page(self, project_name: str, page_title: str) -> PageDetail:
        """Get detailed information about a specific page.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.

        Returns:
            PageDetail: The detailed information about the page.
        """
        encoded_title = quote(page_title, safe="")
        return PageDetail.model_validate(self._get_json(f"/pages/{project_name}/{encoded_title}"))

    def get_page_v2(self, project_name: str, page_title: str) -> PageDetailV2:
        """Get detailed information about a page from the v2 endpoint.

        Compared with `get_page`, this carries the normalized `links_lc` /`icons_lc` /
        `project_links_lc` fields but no embedded related pages; use `get_links_1hop`
        and `get_links_2hop` for those.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.

        Returns:
            PageDetailV2: The detailed information about the page.
        """
        encoded_title = quote(page_title, safe="")
        return PageDetailV2.model_validate(self._get_json(f"/pages/v2/{project_name}/{encoded_title}"))

    def get_links_1hop(  # noqa: PLR0913 - one parameter per query parameter the endpoint takes
        self,
        project_name: str,
        page_title: str,
        search: str | None = None,
        *,
        match_any: bool = False,
        per_page: int | None = None,
        next_id: str | None = None,
    ) -> Links1hopResponse:
        """Get one page of the 1-hop neighbourhood of a page.

        Use `iter_links_1hop` to walk a neighbourhood larger than one page.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.
            search: Keep only the neighbours whose body matches this query.
            match_any: Match pages containing any of the words in `search` instead of
                all of them.
            per_page: Number of neighbours per page (default: the API's own, 1000).
                Must be between 1 and `MAX_PAGE_SIZE`.
            next_id: Continue after this entry, as reported by `pagination.next_id`
                of the previous page.

        Returns:
            Links1hopResponse: The neighbouring pages.

        Raises:
            ValueError: If `per_page` is outside 1 to `MAX_PAGE_SIZE`.
        """
        encoded_title = quote(page_title, safe="")
        return Links1hopResponse.model_validate(
            self._get_json(
                f"/pages/v2/{project_name}/{encoded_title}/links1hop",
                self._related_params(search, match_any=match_any, per_page=per_page, next_id=next_id),
            )
        )

    def get_links_2hop(  # noqa: PLR0913 - one parameter per query parameter the endpoint takes
        self,
        project_name: str,
        page_title: str,
        search: str | None = None,
        *,
        match_any: bool = False,
        per_page: int | None = None,
        next_id: str | None = None,
    ) -> Links2hopResponse:
        """Get one page of the 2-hop neighbourhood of a page.

        The direct 1-hop neighbours are not included. Use `iter_links_2hop` to walk a
        neighbourhood larger than one page.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.
            search: Keep only the neighbours whose body matches this query.
            match_any: Match pages containing any of the words in `search` instead of
                all of them.
            per_page: Number of neighbours per page (default: the API's own, 1000).
                Must be between 1 and `MAX_PAGE_SIZE`.
            next_id: Continue after this entry, as reported by `pagination.next_id`
                of the previous page.

        Returns:
            Links2hopResponse: The neighbouring pages.

        Raises:
            ValueError: If `per_page` is outside 1 to `MAX_PAGE_SIZE`.
        """
        encoded_title = quote(page_title, safe="")
        return Links2hopResponse.model_validate(
            self._get_json(
                f"/pages/v2/{project_name}/{encoded_title}/links2hop",
                self._related_params(search, match_any=match_any, per_page=per_page, next_id=next_id),
            )
        )

    def iter_links_1hop(
        self,
        project_name: str,
        page_title: str,
        search: str | None = None,
        *,
        match_any: bool = False,
        per_page: int | None = None,
    ) -> Iterator[LinkPage]:
        """Iterate over the whole 1-hop neighbourhood of a page.

        A single response holds at most 1000 neighbours, so a larger neighbourhood is
        walked with the cursor the API reports. Pages are fetched as they are consumed.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.
            search: Keep only the neighbours whose body matches this query.
            match_any: Match pages containing any of the words in `search` instead of
                all of them.
            per_page: Number of neighbours fetched per request (default: the API's
                own, 1000). Must be between 1 and `MAX_PAGE_SIZE`.

        Returns:
            An iterator over each neighbouring page, in the order the API returns
            them.

        Raises:
            ValueError: If `per_page` is outside 1 to `MAX_PAGE_SIZE`.
        """
        if per_page is not None:
            check_page_size(per_page, "per_page")
        return self._iter_links(
            lambda next_id: self.get_links_1hop(
                project_name, page_title, search, match_any=match_any, per_page=per_page, next_id=next_id
            ),
            lambda response: response.links1hop,
        )

    def iter_links_2hop(
        self,
        project_name: str,
        page_title: str,
        search: str | None = None,
        *,
        match_any: bool = False,
        per_page: int | None = None,
    ) -> Iterator[LinkPage]:
        """Iterate over the whole 2-hop neighbourhood of a page.

        The direct 1-hop neighbours are not included.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.
            search: Keep only the neighbours whose body matches this query.
            match_any: Match pages containing any of the words in `search` instead of
                all of them.
            per_page: Number of neighbours fetched per request (default: the API's
                own, 1000). Must be between 1 and `MAX_PAGE_SIZE`.

        Returns:
            An iterator over each neighbouring page, in the order the API returns
            them.

        Raises:
            ValueError: If `per_page` is outside 1 to `MAX_PAGE_SIZE`.
        """
        if per_page is not None:
            check_page_size(per_page, "per_page")
        return self._iter_links(
            lambda next_id: self.get_links_2hop(
                project_name, page_title, search, match_any=match_any, per_page=per_page, next_id=next_id
            ),
            lambda response: response.links2hop,
        )

    @staticmethod
    def _iter_links[T: Links1hopResponse | Links2hopResponse](
        fetch: Callable[[str | None], T],
        entries: Callable[[T], list[LinkPage]],
    ) -> Iterator[LinkPage]:
        """Walk a related pages endpoint until its cursor runs out.

        A page narrowed by `search` can come back with fewer entries than asked for,
        or none at all, while the cursor still points further on: the filter applies
        within a page rather than to the whole neighbourhood. Only `has_next` decides
        whether to stop.

        Args:
            fetch: Fetches one page, given the cursor to continue from.
            entries: Reads the neighbours out of a fetched page.

        Yields:
            LinkPage: Each neighbouring page.
        """
        next_id: str | None = None
        while True:
            response = fetch(next_id)
            yield from entries(response)
            pagination = response.pagination
            if pagination is None or not pagination.has_next or pagination.next_id is None:
                return
            if pagination.next_id == next_id:
                # The cursor has stopped advancing; continuing would loop forever.
                return
            next_id = pagination.next_id

    @staticmethod
    def _related_params(
        search: str | None,
        *,
        match_any: bool,
        per_page: int | None = None,
        next_id: str | None = None,
    ) -> dict[str, Any]:
        """Build the query parameters shared by the related pages endpoints.

        Args:
            search: Full-text query to filter the neighbours with.
            match_any: Whether to match any word instead of all of them.
            per_page: Number of neighbours per page.
            next_id: Cursor to continue from.

        Returns:
            The query parameters to send.

        Raises:
            ValueError: If `per_page` is outside 1 to `MAX_PAGE_SIZE`.
        """
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        if match_any:
            params["op"] = "or"
        if per_page is not None:
            params["perPage"] = check_page_size(per_page, "per_page")
        if next_id is not None:
            params["nextId"] = next_id
        return params

    def search_pages(
        self,
        project_name: str,
        query: str,
        *,
        match_any: bool = False,
        sort: SearchSort | None = None,
    ) -> SearchResponse:
        """Search the full text of the pages in a project.

        Args:
            project_name: The name of the project.
            query: The search query.
            match_any: Match pages containing any of the words instead of all of them.
            sort: Order of the results (default: the API's own, `pageRank`).

        Returns:
            SearchResponse: The matching pages.
        """
        params: dict[str, Any] = {"q": query}
        if match_any:
            params["op"] = "or"
        if sort is not None:
            params["sort"] = sort
        return SearchResponse.model_validate(self._get_json(f"/pages/{project_name}/search/query", params))

    def search_titles_by_vector(self, project_name: str, query: str) -> VectorSearchResponse:
        """Search pages by vector similarity.

        Only page titles and the link notations in page bodies are searched; ordinary
        body text is not.

        Args:
            project_name: The name of the project.
            query: The search query.

        Returns:
            VectorSearchResponse: The matching pages, most similar first.

        Raises:
            SearchServerUpdatingError: If the search backend is temporarily updating.
                Retrying later usually succeeds.
        """
        return VectorSearchResponse.model_validate(
            self._get_json(f"/pages/{project_name}/search/vector/titles", {"q": query})
        )

    def get_commits(self, project_name: str, page_id: str, since: str | None = None) -> CommitsResponse:
        """Get the edit history of a page.

        The history is keyed by page id rather than title, so it can be followed
        across renames.

        Args:
            project_name: The name of the project.
            page_id: The immutable id of the page.
            since: Return only the commits after this commit id. Omit for the whole
                history.

        Returns:
            CommitsResponse: The commits, oldest first.
        """
        params = {"head": since} if since is not None else None
        return CommitsResponse.model_validate(self._get_json(f"/commits/{project_name}/{page_id}", params))

    def get_project_users(self, project_name: str) -> ProjectUsersResponse:
        """Get the members of a project.

        Args:
            project_name: The name of the project.

        Returns:
            ProjectUsersResponse: Current members, departed members and service accounts.
        """
        return ProjectUsersResponse.model_validate(self._get_json(f"/projects/{project_name}/users"))

    def get_projects(self) -> ProjectsResponse:
        """Get the projects the authenticated user belongs to.

        Requires authentication.

        Returns:
            ProjectsResponse: The projects.
        """
        return ProjectsResponse.model_validate(self._get_json("/projects"))

    def get_project(self, project_name: str) -> ProjectDetail:
        """Get a single project by name.

        Unlike `get_projects`, this needs no authentication for a public project, and
        carries the project's settings and member list rather than the counters.

        A service account is refused here with HTTP 401, even for the project it
        belongs to, though `get_project_users` on that same project works.

        Args:
            project_name: The name of the project.

        Returns:
            ProjectDetail: The project.
        """
        return ProjectDetail.model_validate(self._get_json(f"/projects/{project_name}"))

    def get_me(self) -> Me:
        """Get the authenticated user.

        Requires authentication. The `name` shown here, not `display_name`, is what
        `get_pages(filter_value=...)` expects.

        Returns:
            Me: The authenticated user.

        Raises:
            NotAuthenticatedError: If no credential was accepted. This endpoint does
                not answer 401: without one it answers 200 with `{"isGuest": true}`,
                which carries no user to return.
        """
        payload = self._get_json("/users/me")
        if "id" not in payload:
            raise NotAuthenticatedError
        return Me.model_validate(payload)

    def get_file_info(self, file_id: str) -> FileInfo:
        """Get the metadata of a file uploaded to a project.

        Args:
            file_id: The file id, optionally with an extension, or the full file URL.

        Returns:
            FileInfo: The metadata, including any text extracted from the file.
        """
        return FileInfo.model_validate(self._get_json(f"/gcs/{bare_file_id(file_id)}/info"))

    def preview_page_edit(
        self,
        project_name: str,
        changes: Sequence[PageChange],
        page_id: str | None = None,
    ) -> EditPreviewResponse:
        """Dry-run an edit and get a preview id for it.

        Nothing is written until the returned preview id is passed to
        `submit_page_edit`, and the preview expires a few minutes after it is issued.
        Use `scrapbox.edits.changes_from_ops` to build `changes`.

        Args:
            project_name: The name of the project.
            changes: The changes to apply, in order.
            page_id: The id of the page to edit. Omit to create a new page.

        Returns:
            EditPreviewResponse: The preview id and the resulting page.

        Raises:
            PersonalAccessTokenRequiredError: If neither a personal access token nor a
                service account access key is set.
        """
        payload: dict[str, Any] = {
            "changes": [
                change if isinstance(change, dict) else change.model_dump(by_alias=True, exclude_none=True)
                for change in changes
            ]
        }
        if page_id is not None:
            payload["pageId"] = page_id
        return EditPreviewResponse.model_validate(
            self._post_json(f"/pages/v2/{project_name}/page-edit-for-ai/preview", payload)
        )

    def submit_page_edit(self, project_name: str, preview_id: str) -> EditSubmitResponse:
        """Commit an edit that was previewed earlier.

        A preview id can only be submitted once, and the project must be the one the
        preview was created for.

        Args:
            project_name: The name of the project.
            preview_id: The preview id returned by `preview_page_edit`.

        Returns:
            EditSubmitResponse: The created commit and the page written to.

        Raises:
            PersonalAccessTokenRequiredError: If neither a personal access token nor a
                service account access key is set.
        """
        return EditSubmitResponse.model_validate(
            self._post_json(f"/pages/v2/{project_name}/page-edit-for-ai/submit", {"previewId": preview_id})
        )

    def get_page_text(self, project_name: str, page_title: str) -> str:
        """Get the text content of a page.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.

        Returns:
            str: The text content of the page.
        """
        encoded_title = quote(page_title, safe="")
        return self._get(f"/pages/{project_name}/{encoded_title}/text").text

    def get_page_icon_url(self, project_name: str, page_title: str) -> str:
        """Get the icon image URL for a page.

        This method returns the redirect destination URL of the page icon.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.

        Returns:
            str: The URL of the icon image.
        """
        encoded_title = quote(page_title, safe="")
        url = f"{self.BASE_URL}/pages/{project_name}/{encoded_title}/icon"

        response = self.client.get(url, follow_redirects=False)

        if response.status_code == httpx.codes.FOUND:
            return response.headers.get("location", "")
        if response.status_code == httpx.codes.OK:
            return url
        response.raise_for_status()
        return url

    def get_file(self, file_id: str, *, thumbnail: bool = False) -> bytes:
        """Get a file uploaded to Scrapbox.

        Args:
            file_id: The file ID (e.g., "1a2b3c4d5e6f7g8h9i0j.JPG")
                or full URL (e.g., "https://scrapbox.io/files/1a2b3c4d5e6f7g8h9i0j.JPG"
                or "https://gyazo.com/1a2b3c4d5e6f7g8h9i0j1a2b3c4d5e6f").
            thumbnail: Fetch the scaled down version. Files that have no thumbnail
                (anything but JPEG and PNG) come back at full size. Ignored for Gyazo
                URLs, which are resolved through oEmbed instead.

        Returns:
            bytes: The binary data of the file.
        """
        url = file_id if file_id.startswith(("http://", "https://")) else f"https://scrapbox.io/files/{file_id}"

        parsed_url = urlparse(url)
        is_gyazo = "gyazo.com" in (parsed_url.hostname or "")
        params = {"type": "thumbnail"} if thumbnail and not is_gyazo else None
        if is_gyazo:
            # If URL already has a file extension (e.g., .mp4, .jpg), directly convert to i.gyazo.com
            path = parsed_url.path.strip("/")
            if "." in path.split("/")[-1]:  # Check if last path segment has extension
                url = f"https://i.gyazo.com/{path}"
            else:
                # Use oEmbed API to get the actual file URL
                json = self._get_json("/oembed-proxy/gyazo", {"url": url})
                if (oembed_type := json.get("type")) not in ("photo", "video"):
                    msg = f"Unsupported Gyazo oEmbed type: {oembed_type}"
                    raise ValueError(msg)
                oembed_data = GyazoOEmbedResponse.model_validate(json)
                if isinstance(oembed_data.root, GyazoOEmbedResponsePhoto):
                    url = oembed_data.root.url
                else:  # video
                    # Extract Gyazo ID from the original URL and construct direct video URL
                    gyazo_id = parsed_url.path.strip("/")
                    url = f"https://i.gyazo.com/{gyazo_id}.mp4"
        response = self.client.get(url, params=params)
        response.raise_for_status()

        return response.content
