"""Scrapbox API response models."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator
from pydantic.alias_generators import to_camel


class ScrapboxModel(BaseModel):
    """Base model shared by every Scrapbox payload.

    The API speaks camelCase while this package exposes snake_case attributes, so
    aliases are generated instead of being spelled out on each field.
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class User(ScrapboxModel):
    """User information.

    Only `id` is always present: a public project answers with `id` and `name` alone.
    """

    id: str
    name: str | None = None
    display_name: str | None = None
    photo: str | None = None
    email: str | None = None


class PageFilter(ScrapboxModel):
    """A page list filter configured by a user."""

    type: str
    value: str


class ProjectMember(User):
    """A current member of a project."""

    provider: str | None = None
    created: int | None = None
    updated: int | None = None


class Me(User):
    """The authenticated user, as returned by the `users/me` endpoint."""

    provider: str | None = None
    page_filters: list[PageFilter] = Field(default_factory=list)
    created: int | None = None
    updated: int | None = None
    is_guest: bool | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class MemberSnapshot(ScrapboxModel):
    """A record of a user who has left or been deleted from a project."""

    id: str
    reason: str | None = None
    created: int | None = None
    updated: int | None = None
    data: User | None = None


class ServiceAccount(ScrapboxModel):
    """A service account of a project.

    `usage` is a free-form label, so it is not a person's name even though it is
    what identifies the author of a page or a line edited by this account.
    """

    id: str
    usage: str | None = None


class ProjectUsersResponse(ScrapboxModel):
    """Response from the project members API.

    A page or line author may be a current member, a departed one or a service
    account, so all four lists are needed to resolve an author id to a name.
    """

    users: list[ProjectMember] = Field(default_factory=list)
    member_snapshots: list[MemberSnapshot] = Field(default_factory=list)
    service_accounts: list[ServiceAccount] = Field(default_factory=list)
    service_account_snapshots: list[ServiceAccount] = Field(default_factory=list)


class Project(ScrapboxModel):
    """A project the authenticated user belongs to."""

    id: str
    name: str
    display_name: str | None = None
    public_visible: bool | None = None
    login_strategies: list[str] = Field(default_factory=list)
    plan: str | None = None
    additional_plans: dict[str, bool] = Field(default_factory=dict)
    alert: dict[str, Any] | None = None
    users_count: int | None = None
    is_member: bool | None = None
    billing_id: str | None = None
    created: int | None = None
    updated: int | None = None
    is_owner: bool | None = None
    is_admin: bool | None = None
    admins_count: int | None = None


class ProjectsResponse(ScrapboxModel):
    """Response from the project list API."""

    projects: list[Project] = Field(default_factory=list)


class ProjectDetail(Project):
    """A single project, as returned by the project detail API.

    Compared with the entries of the project list, this carries the project's own
    settings and its member list, but not the counters (`users_count`,
    `admins_count`) that only the list fills in.
    """

    theme: str | None = None
    image: str | None = None
    gyazo_teams_name: str | None = None
    translation: bool | None = None
    infobox: bool | None = None
    disable_realtime_collaboration: bool | None = None
    users: list[User] = Field(default_factory=list)
    """Members of the project. A public project answers with `id` and `name` alone."""


class InfoboxResult(ScrapboxModel):
    """An Infobox extracted from a page body.

    A result flagged as `hallucination` (uncertain value filled in by the extractor)
    or `truncated` (extraction cut short) should not be trusted.
    """

    title: str | None = None
    infobox: dict[str, Any] = Field(default_factory=dict)
    hallucination: bool | None = None
    truncated: bool | None = None


class PageListItem(ScrapboxModel):
    """An item in the page list."""

    id: str
    title: str
    image: str | None = None
    descriptions: list[str]
    user: User
    last_update_user: User | None = None
    pin: int
    views: int
    linked: int
    created: int
    updated: int
    accessed: int
    lines_count: int = Field(alias="linesCount")
    chars_count: int = Field(alias="charsCount")
    helpfeels: list[str]


class PageListResponse(ScrapboxModel):
    """Response from the page list API."""

    project_name: str = Field(alias="projectName")
    skip: int
    limit: int
    count: int
    pages: list[PageListItem]


class Line(ScrapboxModel):
    """Line data in a page."""

    id: str
    text: str
    user_id: str = Field(alias="userId")
    created: int
    updated: int


class LinkPage(ScrapboxModel):
    """A page in the 1-hop or 2-hop neighbourhood of another page.

    Which fields the API fills in varies between entries, so nearly everything is
    optional here.
    """

    id: str
    title: str
    title_lc: str | None = None
    image: str | None = None
    descriptions: list[str] = Field(default_factory=list)
    links_lc: list[str] = Field(default_factory=list)
    linked: int | None = None
    page_rank: float | None = None
    views: int | None = None
    lines_count: int | None = None
    chars_count: int | None = None
    created: int | None = None
    updated: int | None = None
    accessed: int | None = None
    last_accessed: int | None = None
    user: User | None = None
    last_update_user: User | None = None
    users: list[User] = Field(default_factory=list)
    infobox_definition: list[str] | None = None
    infobox_disable_links: list[str] | None = None
    infobox_result: list[InfoboxResult] | None = None
    search: Any = None
    """Search highlight information, present only when the request carried a query."""


class Pagination(ScrapboxModel):
    """Pagination state of a related-pages response."""

    per_page: int | None = None
    """Page size actually applied, clamped by the API to between 1 and 1000."""
    total: int | None = None
    """Size of the whole neighbourhood. A `search` narrows the entries returned but
    not this count."""
    has_next: bool | None = None
    next_id: str | None = None
    """Id of the last entry of this page. Send it back as `next_id` to get the
    entries after it."""


class Links1hopResponse(ScrapboxModel):
    """Response from the 1-hop related pages API."""

    links1hop: list[LinkPage] = Field(default_factory=list, alias="links1hop")
    chars_count: int | None = None
    has_back_links_or_icons: bool | None = None
    kcs_control_tags_lc: list[str] = Field(default_factory=list)
    synonyms: list[Any] = Field(default_factory=list)
    search_backend: str | None = None
    pagination: Pagination | None = None


class Links2hopResponse(ScrapboxModel):
    """Response from the 2-hop related pages API.

    The direct 1-hop neighbourhood is not included.
    """

    links2hop: list[LinkPage] = Field(default_factory=list, alias="links2hop")
    hidden_headwords_lc: list[str] = Field(default_factory=list)
    synonyms: list[Any] = Field(default_factory=list)
    search_backend: str | None = None
    pagination: Pagination | None = None


class RelatedPages(ScrapboxModel):
    """Related pages embedded in the v1 page response.

    The v2 page endpoint drops this field; use the `links1hop` / `links2hop`
    endpoints there instead.
    """

    links1hop: list[LinkPage] = Field(default_factory=list, alias="links1hop")
    links2hop: list[LinkPage] = Field(default_factory=list, alias="links2hop")
    project_links1hop: list[Any] = Field(default_factory=list)
    chars_count: dict[str, int] | int | None = None
    """Character count per hop, e.g. `{"links1hop": 12294, "links2hop": 7618}`."""
    has_back_links_or_icons: bool | None = None
    hidden_headwords_lc: list[str] = Field(default_factory=list)
    fat_headwords_lc: list[str] = Field(default_factory=list)
    search: Any = None
    search_backend: str | None = None


class PageBase(ScrapboxModel):
    """Fields shared by the v1 and v2 page detail responses.

    A page that is only linked to and has no substance still answers 200, with
    `persistent` false. Such a response leaves out `commit_id`, `lines_count` and
    `chars_count` entirely rather than sending them as null.
    """

    id: str
    title: str
    image: str | None = None
    descriptions: list[str]
    user: User
    last_update_user: User | None = None
    users: list[User] = Field(default_factory=list)
    pin: int
    views: int
    linked: int
    commit_id: str | None = Field(None, alias="commitId")
    """Latest commit id. Absent from a page that has no substance."""
    created: int
    updated: int
    accessed: int
    snapshot_created: int | None = Field(None, alias="snapshotCreated")
    snapshot_count: int | None = None
    page_rank: float = Field(alias="pageRank")
    last_accessed: int | None = Field(None, alias="lastAccessed")
    lines_count: int | None = Field(None, alias="linesCount")
    """Number of lines. Absent from a page that has no substance."""
    chars_count: int | None = Field(None, alias="charsCount")
    """Number of characters. Absent from a page that has no substance."""
    helpfeels: list[str]
    persistent: bool
    lines: list[Line]
    links: list[str] = Field(default_factory=list)
    icons: list[str] = Field(default_factory=list)
    project_links: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    infobox_definition: list[str] = Field(default_factory=list)
    infobox_disable_links: list[str] = Field(default_factory=list)
    infobox_result: list[InfoboxResult] = Field(default_factory=list)


class PageDetail(PageBase):
    """Detailed information about a page, from the v1 endpoint."""

    related_pages: RelatedPages | None = None


class PageDetailV2(PageBase):
    """Detailed information about a page, from the v2 endpoint.

    Compared with `PageDetail` this carries the normalized `*_lc` variants but no
    embedded related pages.
    """

    links_lc: list[str] = Field(default_factory=list)
    icons_lc: list[str] = Field(default_factory=list)
    project_links_lc: list[str] = Field(default_factory=list)


class SearchResultPage(ScrapboxModel):
    """A page matched by the full-text search API."""

    id: str
    title: str
    image: str | None = None
    user: User | None = None
    last_update_user: User | None = None
    users: list[User] = Field(default_factory=list)
    views: int | None = None
    linked: int | None = None
    created: int | None = None
    updated: int | None = None
    page_rank: float | None = None
    lines_count: int | None = None
    chars_count: int | None = None
    words: list[str] = Field(default_factory=list)
    lines: list[str] = Field(default_factory=list)


class SearchResponse(ScrapboxModel):
    """Response from the full-text search API."""

    project_name: str | None = None
    search_query: str | None = None
    query: Any = None
    field: str | None = None
    backend: str | None = None
    count: int | None = None
    limit: int | None = None
    exists_exact_title_match: bool | None = None
    pages: list[SearchResultPage] = Field(default_factory=list)


class VectorSearchPage(ScrapboxModel):
    """A page matched by the vector search API.

    `exists` is false for a page that only appears as a link in some body, in which
    case the fields describing a real page are absent.
    """

    title: str
    score: float
    exists: bool | None = None
    image: str | None = None
    linked: int | None = None
    id: str | None = None
    user: User | None = None
    last_update_user: User | None = None
    users: list[User] = Field(default_factory=list)
    views: int | None = None
    created: int | None = None
    updated: int | None = None
    page_rank: float | None = None
    lines_count: int | None = None
    chars_count: int | None = None


class VectorSearchResponse(ScrapboxModel):
    """Response from the vector search API."""

    pages: list[VectorSearchPage] = Field(default_factory=list)


class ChangeLines(ScrapboxModel):
    """The line a commit change applies to."""

    id: str | None = None
    text: str | None = None
    orig_text: str | None = None


class InsertChange(ScrapboxModel):
    """Insertion of a line before another one.

    The anchor is the id of the line to insert before, or `_end` for the end of the
    page.
    """

    insert: str = Field(alias="_insert")
    lines: ChangeLines


class UpdateChange(ScrapboxModel):
    """Replacement of the text of a single line."""

    update: str = Field(alias="_update")
    lines: ChangeLines


class DeleteChange(ScrapboxModel):
    """Removal of a line."""

    delete: str = Field(alias="_delete")
    lines: ChangeLines | None = None


class TitleChange(ScrapboxModel):
    """Renaming of a page."""

    title: str
    title_lc: str | None = None


PageChange = InsertChange | UpdateChange | DeleteChange | TitleChange | dict[str, Any]
"""A single change inside a commit.

Alongside the body edits, a commit also carries derived metadata changes such as
`{"linesCount": 3}`. Those have no dedicated model and fall back to a plain dict so
that an unknown change never fails validation.
"""


class Commit(ScrapboxModel):
    """A commit in the history of a page."""

    id: str
    kind: str | None = None
    changes: list[PageChange] = Field(default_factory=list)
    parent_id: str | None = None
    page_id: str | None = None
    user_id: str | None = None
    created: int | None = None


class CommitsResponse(ScrapboxModel):
    """Response from the commit history API."""

    commits: list[Commit] = Field(default_factory=list)


class FileInfo(ScrapboxModel):
    """Metadata of a file uploaded to a project."""

    id: str
    project_name: str | None = None
    text: str | None = None
    """Text extracted from the file (OCR of an image, body of a PDF), truncated by the API."""
    originalname: str | None = None
    content_type: str | None = None
    size: int | None = None


class PreviewLine(ScrapboxModel):
    """A line of the page as it would look after an edit is applied."""

    id: str
    text: str


class PagePreview(ScrapboxModel):
    """The page as it would look after an edit is applied.

    `persistent` is false when the edit would create the page rather than update it.
    """

    title: str | None = None
    persistent: bool | None = None
    lines: list[PreviewLine] = Field(default_factory=list)


class EditPreviewResponse(ScrapboxModel):
    """Response from the page edit preview API.

    The preview is a dry run: nothing is written until `preview_id` is submitted,
    and it expires a few minutes after it is issued.
    """

    preview_id: str
    expire_at: str | None = None
    page_preview: PagePreview | None = None


class SubmittedPage(ScrapboxModel):
    """The page a submitted edit ended up writing to.

    The title can differ from the requested one: creating a page whose title is
    already taken makes the server append a suffix.
    """

    title: str | None = None


class EditSubmitResponse(ScrapboxModel):
    """Response from the page edit submit API."""

    commit_id: str
    page: SubmittedPage | None = None


class GyazoOEmbedBase(ScrapboxModel):
    """Fields shared by the Gyazo oEmbed responses.

    Gyazo answers with an empty string instead of a number for an image it will not
    serve, so the numeric fields are normalized to None.
    """

    version: Literal["1.0"]
    provider_name: str
    provider_url: str
    width: int | None = None
    height: int | None = None
    scale: float | None = None
    title: str

    @field_validator("width", "height", mode="before")
    @classmethod
    def empty_int_to_none(cls, v: str | int | None) -> int | None:
        """Convert empty string to None for int fields."""
        if v == "":
            return None
        if isinstance(v, str):
            return int(v)
        return v

    @field_validator("scale", mode="before")
    @classmethod
    def empty_float_to_none(cls, v: str | float | None) -> float | None:
        """Convert empty string to None for float fields."""
        if v == "":
            return None
        if isinstance(v, str):
            return float(v)
        return v


class GyazoOEmbedResponsePhoto(GyazoOEmbedBase):
    """Photo information in the Gyazo oEmbed response."""

    type: Literal["photo"]
    url: str


class GyazoOEmbedResponseVideo(GyazoOEmbedBase):
    """Video information in the Gyazo oEmbed response."""

    type: Literal["video"]
    html: str
    thumbnail_url: str
    thumbnail_width: int
    thumbnail_height: int
    has_audio_track: bool
    video_length_ms: int


class GyazoOEmbedResponse(RootModel[GyazoOEmbedResponsePhoto | GyazoOEmbedResponseVideo]):
    """Response from the Gyazo oEmbed API.

    See: https://gyazo.com/api/docs/image#oembed
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)
