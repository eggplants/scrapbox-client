""".. include:: ../README.md"""  # noqa: D415

import importlib.metadata

from .client import ScrapboxClient
from .models import Line, PageDetail, PageListItem, PageListResponse, User

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = (
    "Line",
    "PageDetail",
    "PageListItem",
    "PageListResponse",
    "ScrapboxClient",
    "User",
)
