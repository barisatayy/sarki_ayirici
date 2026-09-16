@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Lokal Muzik Ayristirma Studyosu (RTX 3070 CUDA)

echo ========================================================
echo    LOKAL MUZIK AYRISTIRMA STUDYOSU (DEMUCS v4 CUDA)
echo ========================================================
echo.
echo [1/3] Donanim ve Ekran Karti Kontrol Ediliyor...
set PYTHON_EXE=C:\Users\tobil\.conda\envs\myEnv\python.exe
set FFMPEG_PATH=C:\Users\tobil\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin

if exist "%FFMPEG_PATH%" (
    set "PATH=%FFMPEG_PATH%;%PATH%"
)

if not exist "%PYTHON_EXE%" (
    echo [HATA] Python ortami bulunamadi: %PYTHON_EXE%
    pause
    exit /b
)

echo [2/3] Tarayici Aciliyor (http://localhost:7860)...
start http://localhost:7860

echo [3/3] Sunucu Baslatiliyor...
echo.
echo Ayristirma yapmaya baslayabilirsiniz.
echo Programi kapatmak icin bu pencereyi kapatmaniz yeterlidir.
echo.

"%PYTHON_EXE%" backend\app.py
pause