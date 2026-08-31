from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SortMode = Literal["name", "mtime_asc", "mtime_desc"]


class SessionResponse(BaseModel):
    session_id: str


class FileItem(BaseModel):
    file_id: str
    filename: str
    display_name: str
    mtime: float
    mtime_label: str
    size_bytes: int


class FilesResponse(BaseModel):
    files: list[FileItem]


class MergeRequest(BaseModel):
    session_id: str
    queue_file_ids: list[str] = Field(min_length=1)
    output_name: str = Field(
        default="merged_lectures.pdf", min_length=1, max_length=120
    )


class MergeStartResponse(BaseModel):
    job_id: str


class MergeJobStatus(BaseModel):
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    progress_current: int = 0
    progress_total: int = 0
    output_name: str | None = None
    error: str | None = None
