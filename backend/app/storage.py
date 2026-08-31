from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from .core_logic import PDFItem, decode_unicode_escapes_for_display, sort_items
from .schemas import FileItem


@dataclass
class StoredFile:
    file_id: str
    filename: str
    path: Path


@dataclass
class MergeJob:
    job_id: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    progress_current: int = 0
    progress_total: int = 0
    output_path: Path | None = None
    output_name: str | None = None
    error: str | None = None


@dataclass
class SessionState:
    session_id: str
    folder: Path
    files: dict[str, StoredFile] = field(default_factory=dict)
    jobs: dict[str, MergeJob] = field(default_factory=dict)


class SessionStore:
    def __init__(self, root_folder: Path) -> None:
        self.root_folder = root_folder
        self.root_folder.mkdir(parents=True, exist_ok=True)
        self.sessions: dict[str, SessionState] = {}
        self.lock = Lock()

    def create_session(self) -> SessionState:
        session_id = uuid4().hex
        session_folder = self.root_folder / session_id
        uploads = session_folder / "uploads"
        outputs = session_folder / "outputs"
        uploads.mkdir(parents=True, exist_ok=True)
        outputs.mkdir(parents=True, exist_ok=True)
        state = SessionState(session_id=session_id, folder=session_folder)
        with self.lock:
            self.sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> SessionState:
        with self.lock:
            state = self.sessions.get(session_id)
        if state is None:
            raise KeyError("Session not found")
        return state

    def list_files(self, session_id: str, mode: str) -> list[FileItem]:
        state = self.get_session(session_id)
        items = sort_items(
            [PDFItem(path=entry.path) for entry in state.files.values()], mode
        )
        id_by_path = {entry.path: entry.file_id for entry in state.files.values()}
        response: list[FileItem] = []
        for item in items:
            file_id = id_by_path[item.path]
            response.append(
                FileItem(
                    file_id=file_id,
                    filename=item.path.name,
                    display_name=decode_unicode_escapes_for_display(item.path.name),
                    mtime=item.mtime,
                    mtime_label=item.mtime_label,
                    size_bytes=item.size_bytes,
                )
            )
        return response

    def store_file(self, session_id: str, source_name: str, content: bytes) -> str:
        state = self.get_session(session_id)
        file_id = uuid4().hex
        safe_name = Path(source_name).name
        file_path = state.folder / "uploads" / f"{file_id}_{safe_name}"
        file_path.write_bytes(content)
        state.files[file_id] = StoredFile(
            file_id=file_id, filename=safe_name, path=file_path
        )
        return file_id

    def create_job(self, session_id: str, output_name: str) -> MergeJob:
        state = self.get_session(session_id)
        job = MergeJob(job_id=uuid4().hex, output_name=output_name)
        state.jobs[job.job_id] = job
        return job

    def get_job(self, session_id: str, job_id: str) -> MergeJob:
        state = self.get_session(session_id)
        job = state.jobs.get(job_id)
        if job is None:
            raise KeyError("Merge job not found")
        return job

    def get_queue_paths(self, session_id: str, queue_file_ids: list[str]) -> list[Path]:
        state = self.get_session(session_id)
        paths: list[Path] = []
        for file_id in queue_file_ids:
            entry = state.files.get(file_id)
            if entry is None:
                raise KeyError(f"Unknown file id: {file_id}")
            paths.append(entry.path)
        return paths

    def make_output_path(self, session_id: str, job_id: str, output_name: str) -> Path:
        safe_name = Path(output_name).name
        if not safe_name.lower().endswith(".pdf"):
            safe_name = f"{safe_name}.pdf"
        return self.get_session(session_id).folder / "outputs" / f"{job_id}_{safe_name}"

    def reset(self) -> None:
        with self.lock:
            for state in self.sessions.values():
                shutil.rmtree(state.folder, ignore_errors=True)
            self.sessions.clear()
