import { useEffect, useMemo, useState } from "react";

const DEFAULT_API_BASE =
  window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : "http://127.0.0.1:8000";
const API_BASE = import.meta.env.VITE_API_URL ?? DEFAULT_API_BASE;
const API_FALLBACK_BASE = API_BASE.includes("localhost")
  ? API_BASE.replace("localhost", "127.0.0.1")
  : API_BASE.includes("127.0.0.1")
    ? API_BASE.replace("127.0.0.1", "localhost")
    : null;

let activeApiBase = API_BASE;

const SORT_OPTIONS = [
  { value: "name", label: "By name" },
  { value: "mtime_asc", label: "By modified time (oldest first)" },
  { value: "mtime_desc", label: "By modified time (newest first)" },
];

async function apiRequest(path, options = {}) {
  let response;
  let usedBase = activeApiBase;
  try {
    response = await fetch(`${activeApiBase}${path}`, options);
  } catch {
    if (API_FALLBACK_BASE && activeApiBase !== API_FALLBACK_BASE) {
      usedBase = API_FALLBACK_BASE;
      try {
        response = await fetch(`${usedBase}${path}`, options);
      } catch {
        throw new Error(
          `Cannot reach backend at ${API_BASE}. Start the API server and reload.`,
        );
      }
    } else {
      throw new Error(
        `Cannot reach backend at ${API_BASE}. Start the API server and reload.`,
      );
    }
  }

  activeApiBase = usedBase;

  if (!response) {
    throw new Error(
      `Cannot reach backend at ${API_BASE}. Start the API server and reload.`,
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  return response;
}

function prettyBytes(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function App() {
  const [sessionId, setSessionId] = useState("");
  const [files, setFiles] = useState([]);
  const [sortMode, setSortMode] = useState("name");
  const [selectedAvailable, setSelectedAvailable] = useState(new Set());
  const [queueIds, setQueueIds] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [statusText, setStatusText] = useState("Create a session to begin.");
  const [mergeJob, setMergeJob] = useState(null);

  useEffect(() => {
    let mounted = true;
    apiRequest("/api/session", { method: "POST" })
      .then((response) => response.json())
      .then((data) => {
        if (!mounted) return;
        setSessionId(data.session_id);
        setStatusText("Session ready. Upload PDFs to begin.");
      })
      .catch((error) => setStatusText(error.message));
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    apiRequest(`/api/files?session_id=${sessionId}&sort_mode=${sortMode}`)
      .then((response) => response.json())
      .then((data) => setFiles(data.files))
      .catch((error) => setStatusText(error.message));
  }, [sessionId, sortMode]);

  useEffect(() => {
    if (
      !mergeJob ||
      mergeJob.status === "completed" ||
      mergeJob.status === "failed"
    ) {
      return;
    }

    const timer = window.setInterval(() => {
      apiRequest(`/api/merge/${mergeJob.job_id}?session_id=${sessionId}`)
        .then((response) => response.json())
        .then((data) => {
          setMergeJob(data);
          if (data.status === "completed") {
            setStatusText("Merge complete. Download is ready.");
            window.clearInterval(timer);
          }
          if (data.status === "failed") {
            setStatusText(`Merge failed: ${data.error || "Unknown error"}`);
            window.clearInterval(timer);
          }
        })
        .catch((error) => {
          setStatusText(error.message);
          window.clearInterval(timer);
        });
    }, 700);

    return () => window.clearInterval(timer);
  }, [mergeJob, sessionId]);

  const availableById = useMemo(() => {
    const map = new Map();
    for (const item of files) {
      map.set(item.file_id, item);
    }
    return map;
  }, [files]);

  const queueItems = useMemo(
    () => queueIds.map((id) => availableById.get(id)).filter(Boolean),
    [queueIds, availableById],
  );

  async function refreshFiles() {
    if (!sessionId) return;
    const response = await apiRequest(
      `/api/files?session_id=${sessionId}&sort_mode=${sortMode}`,
    );
    const payload = await response.json();
    setFiles(payload.files);
  }

  async function handleUpload(fileList) {
    if (!sessionId || !fileList?.length) {
      return;
    }

    const formData = new FormData();
    for (const file of fileList) {
      formData.append("files", file);
    }

    setStatusText(`Uploading ${fileList.length} file(s)...`);
    try {
      const response = await apiRequest(`/api/upload?session_id=${sessionId}`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      setFiles(payload.files);
      setStatusText(`Uploaded ${fileList.length} file(s).`);
    } catch (error) {
      setStatusText(error.message);
    }
  }

  function addSelectedToQueue() {
    const next = [...queueIds];
    for (const fileId of selectedAvailable) {
      if (!next.includes(fileId)) {
        next.push(fileId);
      }
    }
    setQueueIds(next);
  }

  function addAllToQueue() {
    const allIds = files.map((f) => f.file_id);
    const next = [...queueIds];
    for (const id of allIds) {
      if (!next.includes(id)) {
        next.push(id);
      }
    }
    setQueueIds(next);
  }

  function removeFromQueue(fileId) {
    setQueueIds((prev) => prev.filter((id) => id !== fileId));
  }

  function moveQueueItem(fromIndex, toIndex) {
    if (toIndex < 0 || toIndex >= queueIds.length) {
      return;
    }
    const next = [...queueIds];
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    setQueueIds(next);
  }

  async function startMerge() {
    if (!sessionId) return;
    if (!queueIds.length) {
      setStatusText("Queue is empty. Add files before merging.");
      return;
    }

    try {
      setStatusText("Starting merge job...");
      const response = await apiRequest("/api/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          queue_file_ids: queueIds,
          output_name: "merged_lectures.pdf",
        }),
      });
      const payload = await response.json();
      setMergeJob({
        job_id: payload.job_id,
        status: "pending",
        progress_current: 0,
        progress_total: queueIds.length,
      });
      setStatusText("Merge running...");
    } catch (error) {
      setStatusText(error.message);
    }
  }

  function downloadMergedFile() {
    if (!mergeJob || mergeJob.status !== "completed") return;
    const url = `${API_BASE}/api/merge/${mergeJob.job_id}/download?session_id=${sessionId}`;
    window.open(url, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="page">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />
      <header className="hero">
        <p className="kicker">PDF toolchain</p>
        <h1>Concatenate lecture PDFs with surgical control.</h1>
        <p className="lead">
          Upload. Sort. Compose a queue. Merge and download in one polished
          flow.
        </p>
      </header>

      <section
        className={`upload-zone ${dragOver ? "drag-over" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          handleUpload(Array.from(event.dataTransfer.files));
        }}
      >
        <div>
          <h2>Drop PDFs here</h2>
          <p>or choose files from your disk</p>
        </div>
        <label className="upload-button">
          Select PDFs
          <input
            type="file"
            accept="application/pdf,.pdf"
            multiple
            onChange={(event) =>
              handleUpload(Array.from(event.target.files || []))
            }
          />
        </label>
      </section>

      <section className="controls">
        <div className="sort-wrap">
          <label htmlFor="sortMode">Sort available files</label>
          <select
            id="sortMode"
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value)}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <button className="ghost" type="button" onClick={refreshFiles}>
          Reload
        </button>
        <button className="ghost" type="button" onClick={addSelectedToQueue}>
          Add Selected
        </button>
        <button className="ghost" type="button" onClick={addAllToQueue}>
          Add All
        </button>
        <button className="ghost" type="button" onClick={() => setQueueIds([])}>
          Clear Queue
        </button>
      </section>

      <section className="lists">
        <article className="panel">
          <h3>Available PDFs</h3>
          <ul className="file-list">
            {files.map((file) => {
              const checked = selectedAvailable.has(file.file_id);
              return (
                <li key={file.file_id}>
                  <label className="row">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        setSelectedAvailable((prev) => {
                          const next = new Set(prev);
                          if (next.has(file.file_id)) next.delete(file.file_id);
                          else next.add(file.file_id);
                          return next;
                        });
                      }}
                    />
                    <span className="name">{file.display_name}</span>
                    <span className="meta">{prettyBytes(file.size_bytes)}</span>
                  </label>
                </li>
              );
            })}
          </ul>
        </article>

        <article className="panel">
          <h3>Merge Queue</h3>
          <ul className="file-list queue-list">
            {queueItems.map((file, index) => (
              <li
                key={`${file.file_id}-${index}`}
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData("text/plain", String(index));
                }}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  const fromIndex = Number(
                    event.dataTransfer.getData("text/plain"),
                  );
                  moveQueueItem(fromIndex, index);
                }}
              >
                <div className="row">
                  <span className="index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="name">{file.display_name}</span>
                  <div className="inline-actions">
                    <button
                      type="button"
                      onClick={() => moveQueueItem(index, index - 1)}
                    >
                      Up
                    </button>
                    <button
                      type="button"
                      onClick={() => moveQueueItem(index, index + 1)}
                    >
                      Down
                    </button>
                    <button
                      type="button"
                      onClick={() => removeFromQueue(file.file_id)}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section className="merge-bar">
        <button className="merge" type="button" onClick={startMerge}>
          Merge Queue
        </button>
        <button
          className="download"
          type="button"
          onClick={downloadMergedFile}
          disabled={!mergeJob || mergeJob.status !== "completed"}
        >
          Download Result
        </button>
        <div className="status">
          <strong>Status:</strong> {statusText}
          {mergeJob && mergeJob.status !== "failed" ? (
            <span className="progress">
              {mergeJob.progress_total > 0
                ? ` ${mergeJob.progress_current}/${mergeJob.progress_total}`
                : ""}
            </span>
          ) : null}
        </div>
      </section>
    </div>
  );
}
