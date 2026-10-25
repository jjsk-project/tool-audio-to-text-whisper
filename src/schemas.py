"""Validated arguments for the local transcription tool."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import DEFAULT_MODEL
from .utils import validate_file_name


class FileProcessingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    file_name: str = Field(description="Audio filename directly inside input/.", examples=["meeting.wav"])
    generate_subtitles: bool = Field(default=True, description="Generate subtitle.srt alongside the transcript.")
    model: Literal["tiny", "base", "small", "medium", "large-v3", "turbo"] = Field(default=DEFAULT_MODEL)
    language: Optional[str] = Field(default=None, description="Language code such as en or ko; null detects automatically.")

    @field_validator("file_name")
    @classmethod
    def check_file_name(cls, value):
        return validate_file_name(value)

    @field_validator("language")
    @classmethod
    def check_language(cls, value):
        if value is not None and (not value.isascii() or not value.isalpha() or not 2 <= len(value) <= 3):
            raise ValueError("Use a two- or three-letter language code, or null for auto-detection.")
        return value.lower() if value else None
