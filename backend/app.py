"""Local web API and dashboard host."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .traffic import monitor


@asynccontextmanager
async def lifespan(_app: FastAPI):
    monitor.start()
    yield
    monitor.stop()


app = FastAPI(title="AI Based Smart Traffic Control System", lifespan=lifespan)


@app.get("/api/status")
def status():
    return monitor.snapshot()


@app.post("/api/upload-video")
async def upload_video(file: UploadFile = File(...)):
    allowed_suffixes = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    filename = Path(file.filename or "")
    suffix = filename.suffix.lower()
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="Upload an MP4, MOV, AVI, MKV, or WEBM video.")

    media_directory = Path(__file__).resolve().parents[1] / "media"
    media_directory.mkdir(parents=True, exist_ok=True)
    stored_path = media_directory / f"{uuid.uuid4().hex}{suffix}"

    try:
        with stored_path.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)
        monitor.switch_source(stored_path)
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Could not start the uploaded video: {exc}") from exc
    finally:
        file.file.close()

    return {"ok": True, "filename": filename.name, "path": str(stored_path)}


@app.websocket("/ws")
async def websocket_state(socket: WebSocket):
    await socket.accept()
    try:
        while True:
            await socket.send_json(monitor.snapshot())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


@app.get("/video.mjpg")
def video_stream():
    async def frames():
        while True:
            jpeg = monitor.latest_jpeg()
            if jpeg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            await asyncio.sleep(0.08)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


dashboard = Path(__file__).resolve().parents[1] / "dashboard"
app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")
