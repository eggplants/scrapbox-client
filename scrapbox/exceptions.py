"""Exceptions raised by the Scrapbox client."""


class ScrapboxError(Exception):
    """Base class for every error raised by this package."""


class PersonalAccessTokenRequiredError(ScrapboxError):
    """Raised when an endpoint that only accepts a personal access token is called without one.

    The page editing endpoints (`page-edit-for-ai/preview` and
    `page-edit-for-ai/submit`) reject `connect.sid` cookie authentication with
    HTTP 403, so the client refuses to send the request in the first place.
    """

    def __init__(self, endpoint: str) -> None:
        """Initialize the error.

        Args:
            endpoint: Path of the endpoint that requires a personal access token.
        """
        super().__init__(f"{endpoint} is only available via a personal access token. Pass pat= to ScrapboxClient.")
        self.endpoint = endpoint


class NotAuthenticatedError(ScrapboxError):
    """Raised when an endpoint answers as if no one is logged in.

    `users/me` does not answer 401 without a credential: it answers 200 with
    `{"isGuest": true}` and nothing else, so the absence of a credential has to be
    read out of the body rather than the status code.
    """

    def __init__(self) -> None:
        """Initialize the error."""
        super().__init__(
            "Not authenticated. Pass pat= or connect_sid= to ScrapboxClient.",
        )


class SearchServerUpdatingError(ScrapboxError):
    """Raised when the search backend is being updated and cannot serve the request.

    The vector search endpoint answers with the non-standard status code 490 while
    its backend is updating. This is transient: the same request usually succeeds
    on a later attempt. No retry is performed automatically, because the wait is
    unbounded; deciding when to retry is left to the caller.
    """

    STATUS_CODE = 490
    """Non-standard HTTP status code used for this condition."""

    def __init__(self, message: str | None = None) -> None:
        """Initialize the error.

        Args:
            message: Message returned by the API, if any.
        """
        super().__init__(message or "Search server is updating. Please try again later.")
