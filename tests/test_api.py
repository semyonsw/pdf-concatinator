from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.app.main import app, store


client = TestClient(app)


def make_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_upload_list_merge_download_flow() -> None:
    store.reset()

    session_response = client.post("/api/session")
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    upload_response = client.post(
        f"/api/upload?session_id={session_id}",
        files=[
            ("files", ("Lecture 1.1.pdf", make_pdf_bytes(), "application/pdf")),
            ("files", ("Lecture 2.1.pdf", make_pdf_bytes(), "application/pdf")),
        ],
    )
    assert upload_response.status_code == 200
    uploaded = upload_response.json()["files"]
    assert len(uploaded) == 2

    queue_file_ids = [file_item["file_id"] for file_item in uploaded]
    merge_response = client.post(
        "/api/merge",
        json={
            "session_id": session_id,
            "queue_file_ids": queue_file_ids,
            "output_name": "result.pdf",
        },
    )
    assert merge_response.status_code == 200
    job_id = merge_response.json()["job_id"]

    status_response = client.get(f"/api/merge/{job_id}?session_id={session_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"

    download_response = client.get(
        f"/api/merge/{job_id}/download?session_id={session_id}"
    )
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("application/pdf")
