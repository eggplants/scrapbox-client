"""Scrapbox API client."""

from typing import TYPE_CHECKING, Self
from urllib.parse import quote, urlparse

import httpx

from .models import GyazoOEmbedResponse, PageDetail, PageListResponse

if TYPE_CHECKING:
    from types import TracebackType


class ScrapboxClient:
    """Scrapbox API client.

    This client provides methods to interact with the Scrapbox API,
    including retrieving page lists, page details, page text, and files.
    """

    """Base URL for the Scrapbox API."""
    BASE_URL = "https://scrapbox.io/api"

    def __init__(self, connect_sid: str | None = None) -> None:
        """Initialize the Scrapbox API client.

        Args:
            connect_sid: Scrapbox authentication cookie (connect.sid).
        """
        self.connect_sid = connect_sid
        self.client = httpx.Client(
            cookies={"connect.sid": connect_sid} if connect_sid else None,
            follow_redirects=True,
        )

    def __enter__(self: Self) -> Self:
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, typ: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None, /) -> None:
        """Exit the runtime context related to this object."""
        self.client.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def get_pages(self, project_name: str, skip: int = 0, limit: int = 100) -> PageListResponse:
        """Get a list of pages from a project.

        Args:
            project_name: The name of the project.
            skip: Number of pages to skip (default: 0).
            limit: Number of pages to retrieve (default: 100).

        Returns:
            PageListResponse: The response containing the page list.
        """
        url = f"{self.BASE_URL}/pages/{project_name}"
        params = {"skip": skip, "limit": limit}

        response = self.client.get(url, params=params)
        response.raise_for_status()

        return PageListResponse.model_validate(response.json())

    def get_page(self, project_name: str, page_title: str) -> PageDetail:
        """Get detailed information about a specific page.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.

        Returns:
            PageDetail: The detailed information about the page.
        """
        encoded_title = quote(page_title, safe="")
        url = f"{self.BASE_URL}/pages/{project_name}/{encoded_title}"

        response = self.client.get(url)
        response.raise_for_status()

        return PageDetail.model_validate(response.json())

    def get_page_text(self, project_name: str, page_title: str) -> str:
        """Get the text content of a page.

        Args:
            project_name: The name of the project.
            page_title: The title of the page.

        Returns:
            str: The text content of the page.
        """
        encoded_title = quote(page_title, safe="")
        url = f"{self.BASE_URL}/pages/{project_name}/{encoded_title}/text"

        response = self.client.get(url)
        response.raise_for_status()

        return response.text

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

    def get_file(self, file_id: str) -> bytes:
        """Get a file uploaded to Scrapbox.

        Args:
            file_id: The file ID (e.g., "1a2b3c4d5e6f7g8h9i0j.JPG")
                or full URL (e.g., "https://scrapbox.io/files/1a2b3c4d5e6f7g8h9i0j.JPG"
                or "https://gyazo.com/1a2b3c4d5e6f7g8h9i0j1a2b3c4d5e6f").

        Returns:
            bytes: The binary data of the file.
        """
        url = file_id if file_id.startswith(("http://", "https://")) else f"https://scrapbox.io/files/{file_id}"

        parsed_url = urlparse(url)
        if parsed_url.hostname and "gyazo.com" in parsed_url.hostname:
            oembed_url = f"{self.BASE_URL}/oembed-proxy/gyazo"
            response = self.client.get(oembed_url, params={"url": url})
            response.raise_for_status()
            json = response.json()
            if oembed_type := json.get("type") != "photo":
                msg = f"Unsupported Gyazo oEmbed type: {oembed_type}"
                raise ValueError(msg)
            oembed_data = GyazoOEmbedResponse.model_validate(json)
            url = oembed_data.root.url
        response = self.client.get(url)
        response.raise_for_status()

        return response.content
