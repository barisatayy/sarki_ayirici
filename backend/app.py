import os
import sys
import json
import shutil
import atexit
import subprocess
import threading
import re
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Current directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / ".temp_cache"
FRONTEND_DIR = BASE_DIR / "frontend"

# Ensure FFmpeg is in PATH
FFMPEG_DIR = Path(os.environ.get("LOCALAPPDATA", "C:\\Users\\tobil\\AppData\\Local")) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-9.0.1-full_build" / "bin"
if FFMPEG_DIR.exists() and str(FFMPEG_DIR) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

# Python executable (Local Windows conda or cloud Linux sys.executable)
DEFAULT_CONDA = r"C:\Users\tobil\.conda\envs\myEnv\python.exe"
PYTHON_EXE = DEFAULT_CONDA if os.path.exists(DEFAULT_CONDA) else sys.executable

# Import separator module
sys.path.insert(0, str(BASE_DIR))
from backend.separator import SeparationManager, EXTRACTION_TARGETS

app = FastAPI(title="Lokal Müzik Ayrıştırma Stüdyosu", version="2.0")

# Prevent browser from caching old JS/HTML
@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = SeparationManager(temp_dir=TEMP_DIR, python_exe=PYTHON_EXE)

# Ensure cleanup on process exit
atexit.register(manager.cleanup_previous_job)

@app.get("/api/targets")
def get_targets():
    """Returns available separation modes with auto-selected model info."""
    return EXTRACTION_TARGETS

@app.post("/api/upload-and-separate")
async def upload_and_separate(
    file: UploadFile = File(...),
    target_key: str = Form(...)
):
    if target_key not in EXTRACTION_TARGETS:
        raise HTTPException(status_code=400, detail="Geçersiz ayrıştırma hedefi.")

    # 1. Clean previous job and temp files BEFORE saving the new uploaded file
    manager.cleanup_previous_job()

    # 2. Save uploaded file to clean temp cache
    safe_filename = Path(file.filename).name
    temp_upload_dir = TEMP_DIR / "upload"
    temp_upload_dir.mkdir(parents=True, exist_ok=True)
    temp_input_path = temp_upload_dir / safe_filename

    with open(temp_input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    song_title = Path(safe_filename).stem

    # 3. Start separation
    job_info = manager.start_separation(
        input_file_path=temp_input_path,
        target_key=target_key,
        song_title=song_title
    )

    return {"success": True, "job": job_info}

@app.get("/api/job")
def get_current_job():
    job = manager.get_current_job()
    return {"job": job}

@app.get("/api/audio/preview/{stem_key}")
def preview_stem_audio(stem_key: str):
    file_path = manager.get_stem_file_path(stem_key)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Ses dosyası bulunamadı.")
    
    media_type = "audio/mpeg" if file_path.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(file_path, media_type=media_type)

@app.get("/api/download-zip")
def download_zip():
    job = manager.get_current_job()
    if not job or job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Ayrıştırma tamamlanmadı.")
    
    song_title = job.get("song_title", "stems")
    zip_path = TEMP_DIR / f"{song_title}_stems.zip"
    
    # Create zip from stems
    import zipfile
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for stem_key, info in manager.current_job.get("stems", {}).items():
            src_file = Path(info["file_path"])
            if src_file.exists():
                zf.write(src_file, arcname=f"{song_title}_{src_file.name}")
                
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{song_title}_stems.zip"
    )

@app.post("/api/save-to-desktop")
def save_to_desktop(payload: dict = None):
    stem_name = payload.get("stem_name") if payload else None
    result = manager.save_to_desktop(stem_name=stem_name)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Kaydetme başarısız."))
    return result

@app.post("/api/open-desktop-folder")
def open_desktop_folder():
    job = manager.get_current_job()
    if not job or not job.get("saved_desktop_folder"):
        raise HTTPException(status_code=400, detail="Henüz masaüstüne kaydedilmiş bir klasör bulunmuyor.")
    
    folder = job["saved_desktop_folder"]
    if os.path.exists(folder):
        if hasattr(os, "startfile"):
            os.startfile(folder)
        return {"success": True, "folder": folder}
    raise HTTPException(status_code=404, detail="Klasör bulunamadı.")

@app.post("/api/cleanup")
def cleanup_temp():
    manager.cleanup_previous_job()
    return {"success": True, "message": "Geçici dosyalar ve bellek temizlendi."}

# --- YouTube Download SSE Endpoint ---

# Store latest downloaded file path for serving
_yt_download_result: dict = {}
_yt_download_lock = threading.Lock()


@app.get("/api/youtube-download")
async def youtube_download_sse(url: str):
    """SSE endpoint: downloads YouTube audio as MP3 via yt-dlp, streams progress."""
    import asyncio

    if not url or not url.strip():
        return JSONResponse({"error": "URL boş olamaz."}, status_code=400)

    # Validate URL pattern
    url = url.strip()
    yt_pattern = re.compile(
        r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/|music\.youtube\.com/watch)'
    )
    if not yt_pattern.search(url):
        return JSONResponse({"error": "Geçersiz YouTube linki."}, status_code=400)

    # Prepare temp download directory
    dl_dir = TEMP_DIR / "yt_download"
    if dl_dir.exists():
        shutil.rmtree(dl_dir, ignore_errors=True)
    dl_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(dl_dir / "%(title)s.%(ext)s")

    async def event_stream():
        # Build yt-dlp command for best audio -> MP3 conversion
        cmd = [
            PYTHON_EXE,
            "-m", "yt_dlp",
            "--no-playlist",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--newline",
            "--no-warnings",
            "-o", output_template,
            url
        ]

        env = os.environ.copy()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            env=env
        )

        pct_regex = re.compile(r'(\d+\.?\d*)%')
        title_regex = re.compile(r'\[download\]\s+Destination:\s+(.+)')
        extracted_title = None
        all_logs = []

        for line in process.stdout:
            line_str = line.strip()
            if not line_str:
                continue

            all_logs.append(line_str)

            # Extract title from destination line
            title_match = title_regex.search(line_str)
            if title_match:
                dest_path = title_match.group(1)
                extracted_title = Path(dest_path).stem

            # Extract percentage
            pct_match = pct_regex.search(line_str)
            if pct_match:
                pct = float(pct_match.group(1))
                # During download phase, map 0-100% to 0-70%
                mapped = min(70, pct * 0.7)
                msg = f"İndiriliyor: %{pct:.1f}"
                data = json.dumps({"progress": round(mapped, 1), "message": msg, "status": "downloading"})
                yield f"data: {data}\n\n"

            if "[ExtractAudio]" in line_str or "Converting" in line_str:
                data = json.dumps({"progress": 75, "message": "MP3'e dönüştürülüyor...", "status": "converting"})
                yield f"data: {data}\n\n"

            if "Deleting original" in line_str or "has already been downloaded" in line_str:
                data = json.dumps({"progress": 90, "message": "Tamamlanıyor...", "status": "finalizing"})
                yield f"data: {data}\n\n"

        process.wait()

        if process.returncode != 0:
            err_detail = "\n".join(all_logs[-5:]) if all_logs else f"Çıkış kodu: {process.returncode}"
            print(f"[YT-DLP ERROR] {err_detail}")
            data = json.dumps({"progress": 0, "message": f"İndirme başarısız: {err_detail[:200]}", "status": "error"})
            yield f"data: {data}\n\n"
            return

        # Find the downloaded MP3 file
        mp3_files = list(dl_dir.glob("*.mp3"))
        if not mp3_files:
            # Also check for other audio files
            mp3_files = list(dl_dir.glob("*.m4a")) + list(dl_dir.glob("*.webm")) + list(dl_dir.glob("*.opus"))

        if not mp3_files:
            data = json.dumps({"progress": 0, "message": "İndirilen dosya bulunamadı.", "status": "error"})
            yield f"data: {data}\n\n"
            return

        downloaded_file = mp3_files[0]
        file_size = downloaded_file.stat().st_size
        file_name = downloaded_file.name

        # Store result for serving
        with _yt_download_lock:
            _yt_download_result["path"] = str(downloaded_file)
            _yt_download_result["name"] = file_name
            _yt_download_result["size"] = file_size

        data = json.dumps({
            "progress": 100,
            "message": "İndirme tamamlandı!",
            "status": "completed",
            "file_name": file_name,
            "file_size": file_size
        })
        yield f"data: {data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/youtube-file")
def serve_youtube_file():
    """Serves the most recently downloaded YouTube MP3 file."""
    with _yt_download_lock:
        file_path = _yt_download_result.get("path")
        file_name = _yt_download_result.get("name", "download.mp3")

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="İndirilmiş dosya bulunamadı.")

    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=file_name
    )


# Mount frontend
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=7860, reload=False)
