import os
import sys

# Suppress benign warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["PYTHONWARNINGS"] = "ignore"

import shutil
import subprocess
import threading
import time
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

# Ensure FFmpeg is in PATH
FFMPEG_DIR = Path(os.environ.get("LOCALAPPDATA", "C:\\Users\\tobil\\AppData\\Local")) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-9.0.1-full_build" / "bin"
if FFMPEG_DIR.exists() and str(FFMPEG_DIR) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

# Target Desktop directory
DESKTOP_DIR = Path(os.environ.get("USERPROFILE", os.path.expanduser("~"))) / "Desktop"

# Detect Python Executable (Local Windows conda or cloud Linux sys.executable)
DEFAULT_CONDA = r"C:\Users\tobil\.conda\envs\myEnv\python.exe"
if os.path.exists(DEFAULT_CONDA):
    DEFAULT_PYTHON = DEFAULT_CONDA
else:
    DEFAULT_PYTHON = sys.executable

# Targets that map user intent to the best deep learning model & arguments
EXTRACTION_TARGETS = {
    "vocals_inst": {
        "title": "Vokal ve Altyapı / Enstrümantal (2 Kanal)",
        "description": "Şarkıyı sadece Vokal ve tertemiz Altyapı olarak ikiye ayırır.",
        "model": "htdemucs_ft",
        "two_stems": "vocals",
        "stems_info": {
            "vocals": {"label": "Vokal (Acapella)"},
            "no_vocals": {"label": "Altyapı (Enstrümantal)"}
        }
    },
    "all_4stems": {
        "title": "Tüm Temel Enstrümanlar & Vokal (4 Kanal)",
        "description": "Vokal, Davul/Bateri, Bas ve Diğer enstrümanlar (Melodi/Synth).",
        "model": "htdemucs_ft",
        "two_stems": None,
        "stems_info": {
            "vocals": {"label": "Vokal"},
            "drums": {"label": "Davul / Bateri"},
            "bass": {"label": "Bas"},
            "other": {"label": "Diğer Enstrümanlar (Melodi / Synth)"}
        }
    },
    "drums_only": {
        "title": "Sadece Davul / Bateri Çıkar (2 Kanal)",
        "description": "Davul ritimlerini ve davulsuz altyapıyı ayırır.",
        "model": "htdemucs_ft",
        "two_stems": "drums",
        "stems_info": {
            "drums": {"label": "Davul / Bateri"},
            "no_drums": {"label": "Davulsuz Altyapı"}
        }
    },
    "bass_only": {
        "title": "Sadece Bas Çıkar (2 Kanal)",
        "description": "Bas hattını (808 / Bassline) ve bassız şarkıyı ayırır.",
        "model": "htdemucs_ft",
        "two_stems": "bass",
        "stems_info": {
            "bass": {"label": "Bas Gitar / Synth Bas"},
            "no_bass": {"label": "Bassız Altyapı"}
        }
    },
    "all_6stems": {
        "title": "Gitar & Piyano Detaylı (6 Kanal)",
        "description": "Vokal, Davul, Bas, Gitar, Piyano ve Diğer enstrümanlar.",
        "model": "htdemucs_6s",
        "two_stems": None,
        "stems_info": {
            "vocals": {"label": "Vokal"},
            "drums": {"label": "Davul / Bateri"},
            "bass": {"label": "Bas"},
            "guitar": {"label": "Gitar"},
            "piano": {"label": "Piyano"},
            "other": {"label": "Diğer Enstrümanlar"}
        }
    },
    "guitar_only": {
        "title": "Sadece Gitar Çıkar (2 Kanal)",
        "description": "Gitar partilerini ve gitarsız altyapıyı ayırır.",
        "model": "htdemucs_6s",
        "two_stems": "guitar",
        "stems_info": {
            "guitar": {"label": "Gitar"},
            "no_guitar": {"label": "Gitarsız Altyapı"}
        }
    },
    "piano_only": {
        "title": "Sadece Piyano Çıkar (2 Kanal)",
        "description": "Piyano/Klavye partilerini ve piyanosuz altyapıyı ayırır.",
        "model": "htdemucs_6s",
        "two_stems": "piano",
        "stems_info": {
            "piano": {"label": "Piyano / Klavye"},
            "no_piano": {"label": "Piyanosuz Altyapı"}
        }
    }
}

class SeparationManager:
    def __init__(self, temp_dir: Path, python_exe: str):
        self.temp_dir = temp_dir
        self.python_exe = python_exe
        self.current_job: Optional[Dict[str, Any]] = None
        self.lock = threading.Lock()
        self.ensure_clean_temp()

    def ensure_clean_temp(self):
        """Clean all temporary files to save disk space."""
        if self.temp_dir.exists():
            for item in self.temp_dir.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                except Exception as e:
                    print(f"[Warning] Failed to delete {item}: {e}")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def cleanup_previous_job(self):
        """Cleans previous audio files from RAM and temp storage."""
        with self.lock:
            self.ensure_clean_temp()
            self.current_job = None

    def start_separation(self, input_file_path: Path, target_key: str, song_title: str) -> Dict[str, Any]:
        """Initiates separation with automatic model selection."""
        target_cfg = EXTRACTION_TARGETS.get(target_key, EXTRACTION_TARGETS["vocals_inst"])
        job_id = f"job_{int(time.time())}"
        
        job_info = {
            "job_id": job_id,
            "song_title": song_title,
            "target_key": target_key,
            "target_title": target_cfg["title"],
            "model_name": target_cfg["model"],
            "two_stems": target_cfg["two_stems"],
            "status": "processing",
            "progress": 5,
            "status_message": "Model hazırlanıyor (RTX 3070 CUDA)...",
            "error_message": None,
            "stems": {},
            "stems_info": target_cfg["stems_info"],
            "created_at": time.time(),
            "completed_at": None,
            "saved_desktop_folder": None
        }

        with self.lock:
            self.current_job = job_info

        # Run separation thread
        t = threading.Thread(
            target=self._run_separation_worker,
            args=(job_id, input_file_path, target_cfg, song_title),
            daemon=True
        )
        t.start()

        return job_info

    def _run_separation_worker(self, job_id: str, input_file_path: Path, target_cfg: Dict[str, Any], song_title: str):
        output_dir = self.temp_dir / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        model_name = target_cfg["model"]
        two_stems = target_cfg["two_stems"]

        # Output in high-quality 320kbps MP3 format as requested
        cmd = [
            self.python_exe,
            "-m", "demucs.separate",
            "-n", model_name,
            "-d", "cuda",
            "--shifts=2",
            "--mp3",
            "--mp3-bitrate", "320",
            "--out", str(output_dir),
        ]

        if two_stems:
            cmd.extend(["--two-stems", two_stems])

        cmd.append(str(input_file_path))

        all_logs = []

        try:
            self._update_job(job_id, progress=10, status_message="Ayrıştırma başladı (CUDA hızlandırmalı, 320kbps MP3)...")

            # Inherit environment with FFmpeg included
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

            pct_regex = re.compile(r"(\d{1,3})%")

            for line in process.stdout:
                line_str = line.strip()
                if not line_str:
                    continue

                all_logs.append(line_str)

                match = pct_regex.search(line_str)
                if match:
                    pct = int(match.group(1))
                    mapped_progress = min(96, max(12, int(10 + pct * 0.86)))
                    self._update_job(job_id, progress=mapped_progress, status_message=f"Kanallar ayrıştırılıyor: %{pct}")

                if "Downloading" in line_str:
                    self._update_job(job_id, status_message="Model ağırlıkları hazırlanıyor...")
                elif "Separating track" in line_str:
                    self._update_job(job_id, status_message="Şarkı analiz ediliyor ve MP3 kanalları üretiliyor...")

            process.wait()

            if process.returncode != 0:
                last_err = "\n".join(all_logs[-5:]) if all_logs else f"Hata kodu: {process.returncode}"
                self._update_job(
                    job_id,
                    status="failed",
                    progress=0,
                    error_message=f"Demucs hatası:\n{last_err}",
                    status_message="Ayrıştırma başarısız oldu."
                )
                return

            # Find separated tracks (*.mp3 or *.wav)
            stem_files = list(output_dir.glob("**/*.mp3"))
            if not stem_files:
                stem_files = list(output_dir.glob("**/*.wav"))

            if not stem_files:
                last_logs = "\n".join(all_logs[-8:]) if all_logs else "Log yok"
                self._update_job(
                    job_id,
                    status="failed",
                    progress=0,
                    error_message=f"Ayrıştırılan ses dosyaları bulunamadı. Detay:\n{last_logs}",
                    status_message="Çıktı dosyası bulunamadı."
                )
                return

            stems_dict = {}
            for audio_path in stem_files:
                stem_key = audio_path.stem
                stems_dict[stem_key] = {
                    "file_path": str(audio_path),
                    "file_size": audio_path.stat().st_size,
                    "extension": audio_path.suffix,
                    "stream_url": f"/api/audio/preview/{stem_key}"
                }

            self._update_job(
                job_id,
                status="completed",
                progress=100,
                status_message="Ayrıştırma tamamlandı! Dinleyebilir ve doğrudan Masaüstüne kaydedebilirsiniz.",
                stems=stems_dict,
                completed_at=time.time()
            )

        except Exception as e:
            self._update_job(
                job_id,
                status="failed",
                progress=0,
                error_message=str(e),
                status_message=f"Hata oluştu: {e}"
            )

    def _update_job(self, job_id: str, **kwargs):
        with self.lock:
            if self.current_job and self.current_job["job_id"] == job_id:
                self.current_job.update(kwargs)

    def get_current_job(self) -> Optional[Dict[str, Any]]:
        with self.lock:
            if self.current_job:
                job_data = dict(self.current_job)
                safe_stems = {}
                for k, v in job_data.get("stems", {}).items():
                    safe_stems[k] = {
                        "stream_url": v.get("stream_url"),
                        "file_size": v.get("file_size", 0),
                        "extension": v.get("extension", ".mp3")
                    }
                job_data["stems"] = safe_stems
                return job_data
            return None

    def get_stem_file_path(self, stem_name: str) -> Optional[Path]:
        with self.lock:
            if not self.current_job:
                return None
            stem_info = self.current_job.get("stems", {}).get(stem_name)
            if stem_info and "file_path" in stem_info:
                p = Path(stem_info["file_path"])
                if p.exists():
                    return p
            return None

    def save_to_desktop(self, stem_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Copies MP3 stems directly to the user's Desktop
        folder: C:\\Users\\tobil\\Desktop\\<Song_Title>_Stems\\
        """
        with self.lock:
            if not self.current_job or self.current_job["status"] != "completed":
                return {"success": False, "error": "Henüz tamamlanmış bir ayrıştırma bulunmuyor."}

            song_title = self.current_job["song_title"]
            safe_title = re.sub(r'[\\/*?:"<>|]', "", song_title).strip() or "Sarki"
            dest_folder = DESKTOP_DIR / f"{safe_title}_Stems"
            dest_folder.mkdir(parents=True, exist_ok=True)

            copied_files = []
            stems_dict = self.current_job.get("stems", {})

            if stem_name:
                # Save single stem
                if stem_name in stems_dict:
                    src_file = Path(stems_dict[stem_name]["file_path"])
                    ext = src_file.suffix or ".mp3"
                    dest_file = dest_folder / f"{safe_title}_{stem_name}{ext}"
                    shutil.copy2(src_file, dest_file)
                    copied_files.append(str(dest_file))
            else:
                # Save all stems
                for stem_key, info in stems_dict.items():
                    src_file = Path(info["file_path"])
                    ext = src_file.suffix or ".mp3"
                    dest_file = dest_folder / f"{safe_title}_{stem_key}{ext}"
                    shutil.copy2(src_file, dest_file)
                    copied_files.append(str(dest_file))

            self.current_job["saved_desktop_folder"] = str(dest_folder)

            return {
                "success": True,
                "folder_path": str(dest_folder),
                "copied_files": copied_files
            }
