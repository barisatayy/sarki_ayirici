import os
import sys
import shutil
import atexit
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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

# Mount frontend
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=7860, reload=False)
