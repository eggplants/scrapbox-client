"""Tests for Scrapbox client."""

import httpx
import pytest

from scrapbox.client import PAT_HEADER, ScrapboxClient
from scrapbox.exceptions import SearchServerUpdatingError


class TestScrapboxClient:
    """Test ScrapboxClient class."""

    PROJECT_NAME = "help-jp"
    PAGE_TITLE = "ブラケティング"

    def test_get_pages(self) -> None:
        """Test getting page list from a public project."""
        limit = 5
        with ScrapboxClient() as client:
            pages = client.get_pages(self.PROJECT_NAME, skip=0, limit=limit)

            assert pages.project_name == self.PROJECT_NAME
            assert pages.count > 0
            assert len(pages.pages) <= limit
            assert pages.skip == 0
            assert pages.limit == limit

            if pages.pages:
                page = pages.pages[0]
                assert hasattr(page, "title")
                assert hasattr(page, "views")
                assert isinstance(page.title, str)
                assert isinstance(page.views, int)

    def test_get_pages_pagination(self) -> None:
        """Test pagination with skip parameter."""
        limit = 3
        with ScrapboxClient() as client:
            pages1 = client.get_pages(self.PROJECT_NAME, skip=0, limit=limit)
            pages2 = client.get_pages(self.PROJECT_NAME, skip=3, limit=limit)

            assert pages1.project_name == pages2.project_name
            assert pages1.skip == 0
            assert pages2.skip == limit

            # Ensure we got different pages (if there are enough pages)
            if len(pages1.pages) == limit and len(pages2.pages) > 0:
                assert pages1.pages[0].title != pages2.pages[0].title

    def test_get_page(self) -> None:
        """Test getting individual page details."""
        with ScrapboxClient() as client:
            page = client.get_page(self.PROJECT_NAME, self.PAGE_TITLE)

            assert page.title == self.PAGE_TITLE
            assert page.id is not None
            # A page with substance carries its counts; one without leaves them out.
            assert page.lines_count is not None
            assert page.lines_count > 0
            assert page.chars_count is not None
            assert page.chars_count > 0
            assert hasattr(page, "created")
            assert hasattr(page, "updated")
            assert hasattr(page, "views")
            assert len(page.lines) > 0

            # Check line structure
            line = page.lines[0]
            assert hasattr(line, "text")
            assert isinstance(line.text, str)

    def test_get_page_text(self) -> None:
        """Test getting page text content."""
        with ScrapboxClient() as client:
            text = client.get_page_text(self.PROJECT_NAME, self.PAGE_TITLE)

            assert isinstance(text, str)
            assert len(text) > 0
            # First line should be the page title
            assert text.startswith(self.PAGE_TITLE)

    def test_get_page_icon_url(self) -> None:
        """Test getting page icon URL."""
        with ScrapboxClient() as client:
            icon_url = client.get_page_icon_url(self.PROJECT_NAME, self.PAGE_TITLE)

            assert isinstance(icon_url, str)
            assert icon_url.startswith("http")

    def test_get_file_with_file_id(self) -> None:
        """Test getting file with file ID."""
        file_id = "60190edf1176d9001c13f8e8.png"

        with ScrapboxClient() as client:
            image_data = client.get_file(file_id)
            assert isinstance(image_data, bytes)
            assert len(image_data) > 0

    def test_get_file_with_scrapbox_url(self) -> None:
        """Test getting file with full Scrapbox URL."""
        file_url = "https://scrapbox.io/files/60190edf1176d9001c13f8e8.png"

        with ScrapboxClient() as client:
            image_data = client.get_file(file_url)
            assert isinstance(image_data, bytes)
            assert len(image_data) > 0

    def test_get_file_with_gyazo_url(self) -> None:
        """Test getting file with Gyazo URL."""
        gyazo_url = "https://gyazo.com/da78df293f9e83a74b5402411e2f2e01"

        with ScrapboxClient() as client:
            image_data = client.get_file(gyazo_url)
            assert isinstance(image_data, bytes)
            assert len(image_data) > 0

    def test_context_manager(self) -> None:
        """Test using client as context manager."""
        with ScrapboxClient() as client:
            pages = client.get_pages(self.PROJECT_NAME, limit=1)
            assert pages.project_name == self.PROJECT_NAME

    def test_client_close(self) -> None:
        """Test manually closing client."""
        client = ScrapboxClient()
        try:
            pages = client.get_pages(self.PROJECT_NAME, limit=1)
            assert pages.project_name == self.PROJECT_NAME
        finally:
            client.close()

    def test_page_with_special_characters(self) -> None:
        """Test getting page with special characters in title."""
        # Testing URL encoding
        special_page = "API"

        with ScrapboxClient() as client:
            page = client.get_page(self.PROJECT_NAME, special_page)
            assert page.title == special_page

    def test_nonexistent_page(self) -> None:
        """Test error handling for non-existent page."""
        nonexistent_title = "this-page-definitely-does-not-exist-12345"

        with ScrapboxClient() as client, pytest.raises(Exception):  # noqa: B017, PT011
            client.get_page(self.PROJECT_NAME, nonexistent_title)

    def test_invalid_project(self) -> None:
        """Test error handling for invalid project."""
        invalid_project = "this-project-definitely-does-not-exist-12345"

        with ScrapboxClient() as client, pytest.raises(Exception):  # noqa: B017, PT011
            client.get_pages(invalid_project)


class TestAuthentication:
    """Test how credentials are attached to outgoing requests."""

    API_URL = "https://scrapbox.io/api/pages/help-jp"
    GYAZO_URL = "https://i.gyazo.com/1a2b3c4d5e6f7g8h9i0j.png"

    @staticmethod
    def _build_request(client: ScrapboxClient, url: str) -> httpx.Request:
        """Build a request through the client so its hooks and cookies apply."""
        request = client.client.build_request("GET", url)
        for hook in client.client.event_hooks["request"]:
            hook(request)
        return request

    def test_no_credentials(self) -> None:
        """Test that no credential is attached when none is given."""
        with ScrapboxClient() as client:
            request = self._build_request(client, self.API_URL)
            assert PAT_HEADER not in request.headers
            assert "cookie" not in request.headers

    def test_connect_sid_is_sent_as_cookie(self) -> None:
        """Test that connect.sid is sent as a cookie."""
        with ScrapboxClient(connect_sid="test-sid") as client:
            request = self._build_request(client, self.API_URL)
            assert PAT_HEADER not in request.headers
            assert "connect.sid=test-sid" in request.headers["cookie"]

    def test_pat_is_sent_as_header(self) -> None:
        """Test that the personal access token is sent as a header."""
        with ScrapboxClient(pat="test-pat") as client:
            request = self._build_request(client, self.API_URL)
            assert request.headers[PAT_HEADER] == "test-pat"

    def test_pat_takes_precedence_over_connect_sid(self) -> None:
        """Test that the cookie is dropped when a personal access token is given."""
        with ScrapboxClient(connect_sid="test-sid", pat="test-pat") as client:
            assert client.connect_sid is None
            request = self._build_request(client, self.API_URL)
            assert request.headers[PAT_HEADER] == "test-pat"
            assert "cookie" not in request.headers

    def test_pat_is_not_sent_to_other_hosts(self) -> None:
        """Test that the personal access token is not leaked to third-party hosts."""
        with ScrapboxClient(pat="test-pat") as client:
            request = self._build_request(client, self.GYAZO_URL)
            assert PAT_HEADER not in request.headers


class TestReadEndpoints:
    """Test the read-only endpoints against a public project.

    These endpoints answer without authentication, so they are exercised for real
    rather than mocked. The ones that do need a credential live in
    `test_client_mock.py`.
    """

    PROJECT_NAME = "help-jp"
    PAGE_TITLE = "ブラケティング"
    LINKED_ONLY_TITLE = "リンク"
    """A title other pages link to, with no page of its own behind it."""

    def test_get_page_without_substance(self) -> None:
        """Test a page that only exists as a link target.

        The API answers 200 rather than 404 for one of these, and leaves
        `commitId`, `linesCount` and `charsCount` out of the response entirely
        instead of sending them as null.
        """
        with ScrapboxClient() as client:
            page = client.get_page(self.PROJECT_NAME, self.LINKED_ONLY_TITLE)

        if page.persistent:
            pytest.skip(f"{self.LINKED_ONLY_TITLE} is now a real page")

        assert page.commit_id is None
        assert page.lines_count is None
        assert page.chars_count is None

    def test_get_page_v2(self) -> None:
        """Test getting page details from the v2 endpoint."""
        with ScrapboxClient() as client:
            page = client.get_page_v2(self.PROJECT_NAME, self.PAGE_TITLE)

            assert page.title == self.PAGE_TITLE
            assert page.persistent
            assert len(page.lines) > 0
            # The normalized variants are what v2 adds over v1.
            assert page.links_lc == [link.replace(" ", "_").lower() for link in page.links]

    def test_get_links_1hop(self) -> None:
        """Test getting the 1-hop neighbourhood of a page."""
        with ScrapboxClient() as client:
            result = client.get_links_1hop(self.PROJECT_NAME, self.PAGE_TITLE)

            assert len(result.links1hop) > 0
            assert result.pagination is not None
            assert all(page.title for page in result.links1hop)

    def test_get_links_1hop_with_search(self) -> None:
        """Test that a search query narrows the 1-hop neighbourhood."""
        with ScrapboxClient() as client:
            everything = client.get_links_1hop(self.PROJECT_NAME, self.PAGE_TITLE)
            filtered = client.get_links_1hop(self.PROJECT_NAME, self.PAGE_TITLE, search="リンク")

            assert len(filtered.links1hop) <= len(everything.links1hop)

    def test_get_links_2hop(self) -> None:
        """Test getting the 2-hop neighbourhood of a page."""
        with ScrapboxClient() as client:
            result = client.get_links_2hop(self.PROJECT_NAME, self.PAGE_TITLE)

            assert result.pagination is not None
            assert all(page.title for page in result.links2hop)

    def test_get_links_paginates(self) -> None:
        """Test that a page size and a cursor reach the API."""
        per_page = 2
        with ScrapboxClient() as client:
            first = client.get_links_1hop(self.PROJECT_NAME, self.PAGE_TITLE, per_page=per_page)

            assert first.pagination is not None
            assert first.pagination.per_page == per_page
            assert len(first.links1hop) <= per_page
            assert first.pagination.has_next
            assert first.pagination.next_id is not None

            second = client.get_links_1hop(
                self.PROJECT_NAME, self.PAGE_TITLE, per_page=per_page, next_id=first.pagination.next_id
            )

            # The cursor moves past the entries already seen.
            assert {page.id for page in first.links1hop}.isdisjoint(page.id for page in second.links1hop)

    def test_iter_links_1hop_matches_a_single_page(self) -> None:
        """Test that walking the cursor yields the same neighbourhood in one go.

        The page used here has few enough neighbours to fit in one default response,
        so a small `per_page` is what forces the walk over several requests.
        """
        with ScrapboxClient() as client:
            single = client.get_links_1hop(self.PROJECT_NAME, self.PAGE_TITLE)
            walked = list(client.iter_links_1hop(self.PROJECT_NAME, self.PAGE_TITLE, per_page=2))

            assert [page.id for page in walked] == [page.id for page in single.links1hop]
            assert len({page.id for page in walked}) == len(walked)

    def test_iter_links_2hop_matches_a_single_page(self) -> None:
        """Test the same for the 2-hop neighbourhood."""
        with ScrapboxClient() as client:
            single = client.get_links_2hop(self.PROJECT_NAME, self.PAGE_TITLE)
            walked = list(client.iter_links_2hop(self.PROJECT_NAME, self.PAGE_TITLE, per_page=2))

            assert [page.id for page in walked] == [page.id for page in single.links2hop]

    def test_iter_links_with_search(self) -> None:
        """Test that a search narrows the walk without ending it early.

        The API filters within a page rather than across the neighbourhood, so an
        intermediate page can come back empty while entries remain.
        """
        with ScrapboxClient() as client:
            everything = list(client.iter_links_1hop(self.PROJECT_NAME, self.PAGE_TITLE, per_page=2))
            filtered = list(client.iter_links_1hop(self.PROJECT_NAME, self.PAGE_TITLE, "リンク", per_page=2))

            assert len(filtered) <= len(everything)
            assert {page.id for page in filtered} <= {page.id for page in everything}

    def test_search_pages(self) -> None:
        """Test searching the full text of a project."""
        with ScrapboxClient() as client:
            result = client.search_pages(self.PROJECT_NAME, "リンク")

            assert result.project_name == self.PROJECT_NAME
            assert result.count is not None
            assert result.count > 0
            assert all(page.title for page in result.pages)

    def test_search_pages_keeps_the_thumbnail(self) -> None:
        """Test that the thumbnail of a search hit survives model validation."""
        with ScrapboxClient() as client:
            result = client.search_pages(self.PROJECT_NAME, "リンク")

            with_image = [page for page in result.pages if page.image]
            assert with_image
            assert with_image[0].model_dump(by_alias=True)["image"] == with_image[0].image

    def test_get_project(self) -> None:
        """Test getting a single project by name."""
        with ScrapboxClient() as client:
            project = client.get_project(self.PROJECT_NAME)

            assert project.name == self.PROJECT_NAME
            assert project.public_visible
            assert project.display_name
            assert project.users
            assert all(member.id for member in project.users)

    def test_get_project_not_found(self) -> None:
        """Test that an unknown project name is an error."""
        with ScrapboxClient() as client, pytest.raises(httpx.HTTPStatusError):
            client.get_project("this-project-definitely-does-not-exist-12345")

    def test_search_pages_match_any(self) -> None:
        """Test that matching any word finds at least as much as matching all."""
        with ScrapboxClient() as client:
            all_words = client.search_pages(self.PROJECT_NAME, "リンク 検索")
            any_word = client.search_pages(self.PROJECT_NAME, "リンク 検索", match_any=True)

            assert all_words.count is not None
            assert any_word.count is not None
            assert any_word.count >= all_words.count

    def test_search_titles_by_vector(self) -> None:
        """Test searching pages by vector similarity."""
        with ScrapboxClient() as client:
            try:
                result = client.search_titles_by_vector(self.PROJECT_NAME, "リンク")
            except SearchServerUpdatingError:  # pragma: no cover - depends on the server
                pytest.skip("search backend is updating")

            assert len(result.pages) > 0
            # Results come back most similar first.
            scores = [page.score for page in result.pages]
            assert scores == sorted(scores, reverse=True)

    def test_get_project_users(self) -> None:
        """Test getting the members of a project."""
        with ScrapboxClient() as client:
            result = client.get_project_users(self.PROJECT_NAME)

            assert len(result.users) > 0
            assert all(member.id for member in result.users)

    def test_get_pages_with_sort(self) -> None:
        """Test that the sort order reaches the API and changes the result.

        The exact order is not asserted: pinned pages always come first and the API
        collates titles its own way, neither of which this client decides.
        """
        with ScrapboxClient() as client:
            by_title = client.get_pages(self.PROJECT_NAME, limit=10, sort="title")
            by_linked = client.get_pages(self.PROJECT_NAME, limit=10, sort="linked")

            assert len(by_title.pages) == len(by_linked.pages)
            assert [page.title for page in by_title.pages] != [page.title for page in by_linked.pages]

    def test_get_pages_with_filter(self) -> None:
        """Test that filtering narrows the page list."""
        with ScrapboxClient() as client:
            everything = client.get_pages(self.PROJECT_NAME, limit=1)
            filtered = client.get_pages(self.PROJECT_NAME, limit=1, filter_value="no-such-user-12345")

            assert filtered.count <= everything.count
