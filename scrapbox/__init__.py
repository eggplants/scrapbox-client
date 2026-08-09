""".. include:: ../README.md"""  # noqa: D415

import importlib.metadata

from .client import ScrapboxClient
from .edits import changes_from_ops, new_line_id
from .exceptions import (
    NotAuthenticatedError,
    PersonalAccessTokenRequiredError,
    ScrapboxError,
    SearchServerUpdatingError,
)
from .models import (
    Commit,
    CommitsResponse,
    EditPreviewResponse,
    EditSubmitResponse,
    FileInfo,
    GyazoOEmbedResponse,
    Line,
    LinkPage,
    Links1hopResponse,
    Links2hopResponse,
    Me,
    PageDetail,
    PageDetailV2,
    PageListItem,
    PageListResponse,
    Project,
    ProjectDetail,
    ProjectsResponse,
    ProjectUsersResponse,
    SearchResponse,
    User,
    VectorSearchResponse,
)

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = (
    "Commit",
    "CommitsResponse",
    "EditPreviewResponse",
    "EditSubmitResponse",
    "FileInfo",
    "GyazoOEmbedResponse",
    "Line",
    "LinkPage",
    "Links1hopResponse",
    "Links2hopResponse",
    "Me",
    "NotAuthenticatedError",
    "PageDetail",
    "PageDetailV2",
    "PageListItem",
    "PageListResponse",
    "PersonalAccessTokenRequiredError",
    "Project",
    "ProjectDetail",
    "ProjectUsersResponse",
    "ProjectsResponse",
    "ScrapboxClient",
    "ScrapboxError",
    "SearchResponse",
    "SearchServerUpdatingError",
    "User",
    "VectorSearchResponse",
    "changes_from_ops",
    "new_line_id",
)
