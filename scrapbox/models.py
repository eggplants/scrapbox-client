"""Scrapbox API response models."""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class User(BaseModel):
    """User information."""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    id: str
    name: str | None = None
    display_name: str | None = None
    photo: str | None = None


class PageListItem(BaseModel):
    """An item in the page list."""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    id: str
    title: str
    image: str | None = None
    descriptions: list[str]
    user: User
    last_update_user: User = Field(alias="lastUpdateUser")
    pin: int
    views: int
    linked: int
    created: int
    updated: int
    accessed: int
    lines_count: int = Field(alias="linesCount")
    chars_count: int = Field(alias="charsCount")
    helpfeels: list[str]


class PageListResponse(BaseModel):
    """Response from the page list API."""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    project_name: str = Field(alias="projectName")
    skip: int
    limit: int
    count: int
    pages: list[PageListItem]


class Line(BaseModel):
    """Line data in a page."""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    id: str
    text: str
    user_id: str = Field(alias="userId")
    created: int
    updated: int


class PageDetail(BaseModel):
    """Detailed information about a page."""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    id: str
    title: str
    image: str | None = None
    descriptions: list[str]
    user: User
    last_update_user: User = Field(alias="lastUpdateUser")
    pin: int
    views: int
    linked: int
    commit_id: str = Field(alias="commitId")
    created: int
    updated: int
    accessed: int
    snapshot_created: int = Field(alias="snapshotCreated")
    page_rank: float = Field(alias="pageRank")
    last_accessed: int | None = Field(None, alias="lastAccessed")
    lines_count: int = Field(alias="linesCount")
    chars_count: int = Field(alias="charsCount")
    helpfeels: list[str]
    persistent: bool
    lines: list[Line]
