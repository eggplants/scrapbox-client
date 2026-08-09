"""Tests for Scrapbox client."""

from typing import TYPE_CHECKING

import pytest

from scrapbox.client import PAT_HEADER, ScrapboxClient

if TYPE_CHECKING:
    import httpx


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
            assert page.lines_count > 0
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
