"""Scrapbox API response models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator
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
    commit_id: str | None = Field(None, alias="commitId")
    created: int
    updated: int
    accessed: int
    snapshot_created: int | None = Field(None, alias="snapshotCreated")
    page_rank: float = Field(alias="pageRank")
    last_accessed: int | None = Field(None, alias="lastAccessed")
    lines_count: int = Field(alias="linesCount")
    chars_count: int = Field(alias="charsCount")
    helpfeels: list[str]
    persistent: bool
    lines: list[Line]


class GyazoOEmbedResponsePhoto(BaseModel):
    """Photo information in the Gyazo oEmbed response."""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    type: Literal["photo"]
    version: Literal["1.0"]
    provider_name: str
    provider_url: str
    url: str
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


class GyazoOEmbedResponseVideo(BaseModel):
    """Video information in the Gyazo oEmbed response."""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    type: Literal["video"]
    version: Literal["1.0"]
    provider_name: str
    provider_url: str
    html: str
    thumbnail_url: str
    thumbnail_width: int
    thumbnail_height: int
    has_audio_track: bool
    video_length_ms: int
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


class GyazoOEmbedResponse(RootModel[GyazoOEmbedResponsePhoto | GyazoOEmbedResponseVideo]):
    """Response from the Gyazo oEmbed API.

    See: https://gyazo.com/api/docs/image#oembed
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)
