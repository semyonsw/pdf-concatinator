from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .core_logic import merge_pdf_paths
from .schemas import (
    FilesResponse,
    MergeJobStatus,
    MergeRequest,
    MergeStartResponse,
    SessionResponse,
)
from .storage import SessionStore


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / ".web_data"
MAX_FILE_SIZE_BYTES = 120 * 1024 * 1024

app = FastAPI(title="PDF Concatenator Web API", version="0.1.0")
store = SessionStore(DATA_ROOT)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _files_response(session_id: str, sort_mode: str) -> FilesResponse:
    return FilesResponse(files=store.list_files(session_id, sort_mode))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/session", response_model=SessionResponse)
def create_session() -> SessionResponse:
    session = store.create_session()
    return SessionResponse(session_id=session.session_id)


@app.post("/api/upload", response_model=FilesResponse)
async def upload_files(
    session_id: str = Query(..., min_length=8),
    files: list[UploadFile] = File(...),
) -> FilesResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    try:
        store.get_session(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Every file must have a name.")
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Not a PDF: {file.filename}")

        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413, detail=f"File too large: {file.filename}"
            )
        store.store_file(session_id, file.filename, content)

    return _files_response(session_id, "name")


@app.get("/api/files", response_model=FilesResponse)
def list_files(
    session_id: str = Query(..., min_length=8),
    sort_mode: str = Query("name", pattern="^(name|mtime_asc|mtime_desc)$"),
) -> FilesResponse:
    try:
        return _files_response(session_id, sort_mode)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _run_merge_job(
    session_id: str, job_id: str, queue_file_ids: list[str], output_name: str
) -> None:
    job = store.get_job(session_id, job_id)
    job.status = "running"
    try:
        input_paths = store.get_queue_paths(session_id, queue_file_ids)
        job.progress_total = len(input_paths)
        output_path = store.make_output_path(session_id, job_id, output_name)
        # Coarse progress for now: preparing files then complete write.
        job.progress_current = max(0, len(input_paths) - 1)
        merge_pdf_paths(input_paths, output_path)
        job.output_path = output_path
        job.output_name = output_path.name
        job.progress_current = len(input_paths)
        job.status = "completed"
    except Exception as error:  # noqa: BLE001
        job.status = "failed"
        job.error = str(error)


@app.post("/api/merge", response_model=MergeStartResponse)
def start_merge(
    request: MergeRequest, background_tasks: BackgroundTasks
) -> MergeStartResponse:
    try:
        store.get_session(request.session_id)
        store.get_queue_paths(request.session_id, request.queue_file_ids)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    job = store.create_job(request.session_id, request.output_name)
    background_tasks.add_task(
        _run_merge_job,
        request.session_id,
        job.job_id,
        request.queue_file_ids,
        request.output_name,
    )
    return MergeStartResponse(job_id=job.job_id)


@app.get("/api/merge/{job_id}", response_model=MergeJobStatus)
def get_merge_status(
    job_id: str, session_id: str = Query(..., min_length=8)
) -> MergeJobStatus:
    try:
        job = store.get_job(session_id, job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return MergeJobStatus(
        job_id=job.job_id,
        status=job.status,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        output_name=job.output_name,
        error=job.error,
    )


@app.get("/api/merge/{job_id}/download")
def download_merge(
    job_id: str, session_id: str = Query(..., min_length=8)
) -> FileResponse:
    try:
        job = store.get_job(session_id, job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    if (
        job.status != "completed"
        or job.output_path is None
        or not job.output_path.exists()
    ):
        raise HTTPException(status_code=409, detail="Merged file is not ready.")

    return FileResponse(
        job.output_path, media_type="application/pdf", filename=job.output_name
    )
