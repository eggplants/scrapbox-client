"""Tests for Scrapbox models."""

import pytest
from pydantic import ValidationError

from scrapbox.models import (
    GyazoOEmbedResponse,
    GyazoOEmbedResponsePhoto,
    GyazoOEmbedResponseVideo,
)


class TestGyazoOEmbedResponsePhoto:
    """Test GyazoOEmbedResponsePhoto model."""

    def test_valid_photo_response(self) -> None:
        """Test parsing valid photo response."""
        data = {
            "type": "photo",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "url": "https://i.gyazo.com/example.png",
            "width": 800,
            "height": 600,
            "scale": 1.0,
            "title": "Example Image",
        }
        photo = GyazoOEmbedResponsePhoto.model_validate(data)
        assert photo.type == "photo"
        assert photo.width == 800  # noqa: PLR2004
        assert photo.height == 600  # noqa: PLR2004
        assert photo.scale == 1.0
        assert photo.url == "https://i.gyazo.com/example.png"

    def test_photo_response_with_empty_strings(self) -> None:
        """Test parsing photo response with empty strings for numeric fields."""
        data = {
            "type": "photo",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "url": "https://i.gyazo.com/example.png",
            "width": "",
            "height": "",
            "scale": "",
            "title": "",
        }
        photo = GyazoOEmbedResponsePhoto.model_validate(data)
        assert photo.type == "photo"
        assert photo.width is None
        assert photo.height is None
        assert photo.scale is None
        assert photo.title == ""

    def test_photo_response_with_missing_optional_fields(self) -> None:
        """Test parsing photo response with missing optional fields."""
        data = {
            "type": "photo",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "url": "https://i.gyazo.com/example.png",
            "title": "Example",
        }
        photo = GyazoOEmbedResponsePhoto.model_validate(data)
        assert photo.type == "photo"
        assert photo.width is None
        assert photo.height is None
        assert photo.scale is None

    def test_photo_response_invalid_type(self) -> None:
        """Test validation error for invalid type."""
        data = {
            "type": "video",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "url": "https://i.gyazo.com/example.png",
            "width": 800,
            "height": 600,
            "scale": 1.0,
            "title": "Example Image",
        }
        with pytest.raises(ValidationError) as exc_info:
            GyazoOEmbedResponsePhoto.model_validate(data)
        assert "type" in str(exc_info.value)


class TestGyazoOEmbedResponseVideo:
    """Test GyazoOEmbedResponseVideo model."""

    def test_valid_video_response(self) -> None:
        """Test parsing valid video response."""
        data = {
            "type": "video",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "html": "<video></video>",
            "thumbnailUrl": "https://i.gyazo.com/thumb.png",
            "thumbnailWidth": 320,
            "thumbnailHeight": 240,
            "hasAudioTrack": True,
            "videoLengthMs": 5000,
            "width": 1920,
            "height": 1080,
            "scale": 1.0,
            "title": "Example Video",
        }
        video = GyazoOEmbedResponseVideo.model_validate(data)
        assert video.type == "video"
        assert video.width == 1920  # noqa: PLR2004
        assert video.height == 1080  # noqa: PLR2004
        assert video.scale == 1.0
        assert video.has_audio_track is True
        assert video.video_length_ms == 5000  # noqa: PLR2004

    def test_video_response_with_empty_strings(self) -> None:
        """Test parsing video response with empty strings for numeric fields."""
        data = {
            "type": "video",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "html": "<video></video>",
            "thumbnailUrl": "https://i.gyazo.com/thumb.png",
            "thumbnailWidth": 320,
            "thumbnailHeight": 240,
            "hasAudioTrack": False,
            "videoLengthMs": 5000,
            "width": "",
            "height": "",
            "scale": "",
            "title": "Example Video",
        }
        video = GyazoOEmbedResponseVideo.model_validate(data)
        assert video.type == "video"
        assert video.width is None
        assert video.height is None
        assert video.scale is None

    def test_video_response_missing_required_fields(self) -> None:
        """Test validation error for missing required fields."""
        data = {
            "type": "video",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "title": "Example Video",
        }
        with pytest.raises(ValidationError) as exc_info:
            GyazoOEmbedResponseVideo.model_validate(data)
        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "html" in error_fields
        assert "thumbnailUrl" in error_fields


class TestGyazoOEmbedResponse:
    """Test GyazoOEmbedResponse union model."""

    def test_parse_photo_response(self) -> None:
        """Test parsing photo type response."""
        data = {
            "type": "photo",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "url": "https://i.gyazo.com/example.png",
            "width": 800,
            "height": 600,
            "scale": 1.0,
            "title": "Example Image",
        }
        response = GyazoOEmbedResponse.model_validate(data)
        assert isinstance(response.root, GyazoOEmbedResponsePhoto)
        assert response.root.type == "photo"
        assert response.root.width == 800  # noqa: PLR2004

    def test_parse_video_response(self) -> None:
        """Test parsing video type response."""
        data = {
            "type": "video",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "html": "<video></video>",
            "thumbnailUrl": "https://i.gyazo.com/thumb.png",
            "thumbnailWidth": 320,
            "thumbnailHeight": 240,
            "hasAudioTrack": True,
            "videoLengthMs": 5000,
            "width": 1920,
            "height": 1080,
            "scale": 1.0,
            "title": "Example Video",
        }
        response = GyazoOEmbedResponse.model_validate(data)
        assert isinstance(response.root, GyazoOEmbedResponseVideo)
        assert response.root.type == "video"
        assert response.root.width == 1920  # noqa: PLR2004

    def test_parse_photo_with_empty_strings(self) -> None:
        """Test parsing photo response with empty strings (real-world case)."""
        data = {
            "type": "photo",
            "version": "1.0",
            "providerName": "Gyazo",
            "providerUrl": "https://gyazo.com",
            "url": "https://i.gyazo.com/example.png",
            "width": "",
            "height": "",
            "scale": "",
            "title": "",
        }
        response = GyazoOEmbedResponse.model_validate(data)
        assert isinstance(response.root, GyazoOEmbedResponsePhoto)
        assert response.root.width is None
        assert response.root.height is None
        assert response.root.scale is None

    def test_invalid_response_type(self) -> None:
        """Test validation error for invalid response."""
        data = {
            "type": "unknown",
            "version": "1.0",
        }
        with pytest.raises(ValidationError):
            GyazoOEmbedResponse.model_validate(data)
