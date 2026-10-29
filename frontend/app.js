// Default targets for instant zero-latency rendering
const DEFAULT_TARGETS = {
    "vocals_inst": {
        "title": "Vokal ve Altyapı / Enstrümantal (2 Kanal)",
        "description": "Şarkıyı sadece Vokal ve tertemiz Altyapı olarak ikiye ayırır.",
        "model": "htdemucs_ft"
    },
    "all_4stems": {
        "title": "Tüm Temel Enstrümanlar & Vokal (4 Kanal)",
        "description": "Vokal, Davul/Bateri, Bas ve Diğer enstrümanlar (Melodi/Synth).",
        "model": "htdemucs_ft"
    },
    "drums_only": {
        "title": "Sadece Davul / Bateri Çıkar (2 Kanal)",
        "description": "Davul ritimlerini ve davulsuz altyapıyı ayırır.",
        "model": "htdemucs_ft"
    },
    "bass_only": {
        "title": "Sadece Bas Çıkar (2 Kanal)",
        "description": "Bas hattını (808 / Bassline) ve bassız şarkıyı ayırır.",
        "model": "htdemucs_ft"
    },
    "all_6stems": {
        "title": "Gitar & Piyano Detaylı (6 Kanal)",
        "description": "Vokal, Davul, Bas, Gitar, Piyano ve Diğer enstrümanlar.",
        "model": "htdemucs_6s"
    },
    "guitar_only": {
        "title": "Sadece Gitar Çıkar (2 Kanal)",
        "description": "Gitar partilerini ve gitarsız altyapıyı ayırır.",
        "model": "htdemucs_6s"
    },
    "piano_only": {
        "title": "Sadece Piyano Çıkar (2 Kanal)",
        "description": "Piyano/Klavye partilerini ve piyanosuz altyapıyı ayırır.",
        "model": "htdemucs_6s"
    }
};

// State management
let selectedFile = null;
let selectedTargetKey = "vocals_inst";
let targetsData = { ...DEFAULT_TARGETS };
let pollInterval = null;
let ytEventSource = null;

// DOM Elements
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const selectedFileCard = document.getElementById("selectedFileCard");
const selectedFileName = document.getElementById("selectedFileName");
const selectedFileSize = document.getElementById("selectedFileSize");
const btnClearFile = document.getElementById("btnClearFile");

const targetsGrid = document.getElementById("targetsGrid");
const autoModelInfo = document.getElementById("autoModelInfo");
const autoModelName = document.getElementById("autoModelName");
const autoModelDesc = document.getElementById("autoModelDesc");
const btnStart = document.getElementById("btnStart");
const btnStartText = document.getElementById("btnStartText");

const progressSection = document.getElementById("progressSection");
const statusMessage = document.getElementById("statusMessage");
const statusPercent = document.getElementById("statusPercent");
const progressBarFill = document.getElementById("progressBarFill");

const resultsSection = document.getElementById("resultsSection");
const stemsList = document.getElementById("stemsList");
const btnSaveAllDesktop = document.getElementById("btnSaveAllDesktop");
const btnResetAll = document.getElementById("btnResetAll");
const savedBanner = document.getElementById("savedBanner");
const savedFolderPath = document.getElementById("savedFolderPath");
const btnOpenFolder = document.getElementById("btnOpenFolder");

// YouTube DOM Elements
const tabFile = document.getElementById("tabFile");
const tabYoutube = document.getElementById("tabYoutube");
const panelFile = document.getElementById("panelFile");
const panelYoutube = document.getElementById("panelYoutube");
const ytUrlInput = document.getElementById("ytUrlInput");
const btnYtDownload = document.getElementById("btnYtDownload");
const btnYtText = document.getElementById("btnYtText");
const ytProgressContainer = document.getElementById("ytProgressContainer");
const ytProgressMsg = document.getElementById("ytProgressMsg");
const ytProgressPct = document.getElementById("ytProgressPct");
const ytProgressFill = document.getElementById("ytProgressFill");

// Initialize application
document.addEventListener("DOMContentLoaded", () => {
    // 1. Render immediately so options are NEVER blank on first load
    renderTargets();
    setupEventListeners();

    // 2. Fetch from backend with retry in background
    loadTargets();
});

// Load available targets from server with auto-retry
async function loadTargets(retries = 5) {
    for (let i = 0; i < retries; i++) {
        try {
            const res = await fetch("/api/targets");
            if (res.ok) {
                targetsData = await res.json();
                renderTargets();
                return;
            }
        } catch (err) {
            // Wait 800ms and retry
            await new Promise(resolve => setTimeout(resolve, 800));
        }
    }
}

// Render separation target cards
function renderTargets() {
    targetsGrid.innerHTML = "";

    const targetKeys = Object.keys(targetsData);
    if (!targetKeys.includes(selectedTargetKey)) {
        selectedTargetKey = targetKeys[0] || "vocals_inst";
    }

    targetKeys.forEach(key => {
        const item = targetsData[key];
        const card = document.createElement("div");
        card.className = `target-card ${key === selectedTargetKey ? "selected" : ""}`;
        card.dataset.key = key;

        // Model tag name
        const modelTag = item.model === "htdemucs_6s" ? "6-Kanal AI" : "Fine-Tuned AI";

        card.innerHTML = `
            <div>
                <div class="target-title-row">
                    <span class="target-title">${item.title}</span>
                </div>
                <p class="target-desc">${item.description}</p>
            </div>
            <span class="target-tag">${modelTag} • 320kbps MP3</span>
        `;

        card.addEventListener("click", () => {
            selectTarget(key);
        });

        targetsGrid.appendChild(card);
    });

    updateAutoModelBanner();
}

function selectTarget(key) {
    selectedTargetKey = key;
    document.querySelectorAll(".target-card").forEach(c => {
        c.classList.toggle("selected", c.dataset.key === key);
    });
    updateAutoModelBanner();
}

function updateAutoModelBanner() {
    const item = targetsData[selectedTargetKey];
    if (!item) return;

    if (item.model === "htdemucs_6s") {
        autoModelName.textContent = "Otomatik Model: Demucs v4 6S (Altı Kanal Derin Öğrenme)";
        autoModelDesc.textContent = "Piyano ve gitarı diğer enstrümanlardan ayırmak için özel eğitilmiş 6 kanallı model devrede.";
    } else {
        autoModelName.textContent = "Otomatik Model: Demucs v4 FT (İnce Ayarlı Fine-Tuned)";
        autoModelDesc.textContent = "Vokal, davul, bas ve altyapı için en yüksek akustik ayrım hassasiyetine sahip model devrede.";
    }
}

// Setup Event Listeners
function setupEventListeners() {
    // Source tab switching
    tabFile.addEventListener("click", () => switchSource("file"));
    tabYoutube.addEventListener("click", () => switchSource("youtube"));

    // Drop zone click
    dropZone.addEventListener("click", () => fileInput.click());

    // File input change
    fileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files[0]) {
            handleFileSelected(e.target.files[0]);
        }
    });

    // Drag & Drop
    ["dragenter", "dragover"].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach(event => {
        dropZone.addEventListener(event, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove("dragover");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileSelected(e.dataTransfer.files[0]);
        }
    });

    // Clear file
    btnClearFile.addEventListener("click", (e) => {
        e.stopPropagation();
        clearSelectedFile();
    });

    // YouTube URL input validation
    ytUrlInput.addEventListener("input", () => {
        const url = ytUrlInput.value.trim();
        btnYtDownload.disabled = !isValidYouTubeUrl(url);
    });

    // YouTube URL paste auto-detect
    ytUrlInput.addEventListener("paste", () => {
        setTimeout(() => {
            const url = ytUrlInput.value.trim();
            btnYtDownload.disabled = !isValidYouTubeUrl(url);
        }, 50);
    });

    // YouTube Enter key to download
    ytUrlInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !btnYtDownload.disabled) {
            startYouTubeDownload();
        }
    });

    // YouTube download button
    btnYtDownload.addEventListener("click", startYouTubeDownload);

    // Start Separation
    btnStart.addEventListener("click", startSeparation);

    // Save All to Desktop
    btnSaveAllDesktop.addEventListener("click", async () => {
        await saveStemsToDesktop(null);
    });

    // Open Saved Folder
    btnOpenFolder.addEventListener("click", async () => {
        try {
            await fetch("/api/open-desktop-folder", { method: "POST" });
        } catch (e) {
            console.error(e);
        }
    });

    // Reset & New Song
    btnResetAll.addEventListener("click", resetAll);
}

// Source tab switching
function switchSource(source) {
    // Don't switch if file is already selected
    if (selectedFile) return;

    tabFile.classList.toggle("active", source === "file");
    tabYoutube.classList.toggle("active", source === "youtube");
    panelFile.classList.toggle("active", source === "file");
    panelYoutube.classList.toggle("active", source === "youtube");
}

// YouTube URL validation
function isValidYouTubeUrl(url) {
    if (!url) return false;
    const pattern = /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|shorts\/)|youtu\.be\/|music\.youtube\.com\/watch)/;
    return pattern.test(url);
}

// Start YouTube download with SSE progress
function startYouTubeDownload() {
    const url = ytUrlInput.value.trim();
    if (!isValidYouTubeUrl(url)) return;

    // Disable input and button during download
    ytUrlInput.disabled = true;
    btnYtDownload.disabled = true;
    btnYtText.textContent = "İndiriliyor...";

    // Show progress bar
    ytProgressContainer.style.display = "block";
    updateYtProgress(0, "İndirme başlatılıyor...");

    // Close any previous event source
    if (ytEventSource) {
        ytEventSource.close();
        ytEventSource = null;
    }

    // Start SSE connection
    const encodedUrl = encodeURIComponent(url);
    ytEventSource = new EventSource(`/api/youtube-download?url=${encodedUrl}`);

    ytEventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            updateYtProgress(data.progress || 0, data.message || "");

            if (data.status === "completed") {
                ytEventSource.close();
                ytEventSource = null;
                onYouTubeDownloadComplete(data);
            } else if (data.status === "error") {
                ytEventSource.close();
                ytEventSource = null;
                onYouTubeDownloadError(data.message);
            }
        } catch (err) {
            console.error("SSE parse error:", err);
        }
    };

    ytEventSource.onerror = () => {
        ytEventSource.close();
        ytEventSource = null;
        onYouTubeDownloadError("Bağlantı hatası oluştu.");
    };
}

function updateYtProgress(pct, msg) {
    ytProgressPct.textContent = `%${Math.round(pct)}`;
    ytProgressMsg.textContent = msg;
    ytProgressFill.style.width = `${pct}%`;
}

async function onYouTubeDownloadComplete(data) {
    updateYtProgress(100, "İndirme tamamlandı! Dosya yükleniyor...");

    try {
        // Fetch the downloaded file from server and create a File object
        const response = await fetch("/api/youtube-file");
        if (!response.ok) throw new Error("Dosya alınamadı");

        const blob = await response.blob();
        const fileName = data.file_name || "youtube_download.mp3";
        const file = new File([blob], fileName, { type: "audio/mpeg" });

        // Auto-load as if user manually selected it
        handleFileSelected(file);

        // Hide YouTube panel and progress
        ytProgressContainer.style.display = "none";

    } catch (err) {
        console.error("YouTube file fetch error:", err);
        onYouTubeDownloadError("İndirilen dosya yüklenemedi: " + err.message);
    }
}

function onYouTubeDownloadError(message) {
    updateYtProgress(0, "Hata: " + message);

    // Re-enable inputs
    ytUrlInput.disabled = false;
    btnYtDownload.disabled = false;
    btnYtText.textContent = "İndir";

    // Keep progress visible so user sees the error
    setTimeout(() => {
        ytProgressContainer.style.display = "none";
    }, 5000);
}

function handleFileSelected(file) {
    selectedFile = file;
    selectedFileName.textContent = file.name;
    selectedFileSize.textContent = formatBytes(file.size);

    // Hide both panels and show the file card
    panelFile.classList.remove("active");
    panelYoutube.classList.remove("active");
    dropZone.style.display = "none";
    selectedFileCard.style.display = "flex";
    btnStart.disabled = false;
}

function clearSelectedFile() {
    selectedFile = null;
    fileInput.value = "";
    dropZone.style.display = "block";
    selectedFileCard.style.display = "none";
    btnStart.disabled = true;

    // Reset YouTube state
    ytUrlInput.value = "";
    ytUrlInput.disabled = false;
    btnYtDownload.disabled = true;
    btnYtText.textContent = "İndir";
    ytProgressContainer.style.display = "none";

    // Restore active tab panel
    if (tabYoutube.classList.contains("active")) {
        panelYoutube.classList.add("active");
        panelFile.classList.remove("active");
    } else {
        // Default to file tab
        tabFile.classList.add("active");
        tabYoutube.classList.remove("active");
        panelFile.classList.add("active");
        panelYoutube.classList.remove("active");
    }
}

// Start Separation API call
async function startSeparation() {
    if (!selectedFile) return;

    btnStart.disabled = true;
    btnStartText.textContent = "İşleniyor...";
    resultsSection.style.display = "none";
    savedBanner.style.display = "none";
    progressSection.style.display = "block";

    updateProgress(5, "Dosya yükleniyor ve CUDA modeli hazırlanıyor...");

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("target_key", selectedTargetKey);

    try {
        const res = await fetch("/api/upload-and-separate", {
            method: "POST",
            body: formData
        });

        const data = await res.json();
        if (!data.success) {
            alert("Ayrıştırma başlatılamadı: " + (data.detail || "Bilinmeyen hata"));
            btnStart.disabled = false;
            btnStartText.textContent = "Ayrıştırmayı Başlat";
            return;
        }

        // Start polling status
        startPolling();

    } catch (err) {
        console.error("Yükleme hatası:", err);
        alert("Bağlantı hatası: " + err.message);
        btnStart.disabled = false;
        btnStartText.textContent = "Ayrıştırmayı Başlat";
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        try {
            const res = await fetch("/api/job");
            const data = await res.json();
            const job = data.job;

            if (!job) return;

            updateProgress(job.progress || 10, job.status_message || "İşleniyor...");

            if (job.status === "completed") {
                clearInterval(pollInterval);
                onSeparationCompleted(job);
            } else if (job.status === "failed") {
                clearInterval(pollInterval);
                onSeparationFailed(job.error_message || "Ayrıştırma işlemi başarısız oldu.");
            }
        } catch (err) {
            console.error("Polling hatası:", err);
        }
    }, 1200);
}

function updateProgress(pct, msg) {
    statusPercent.textContent = `%${pct}`;
    statusMessage.textContent = msg;
    progressBarFill.style.width = `${pct}%`;
}

function onSeparationCompleted(job) {
    btnStart.disabled = false;
    btnStartText.textContent = "Ayrıştırmayı Başlat";
    progressSection.style.display = "none";
    resultsSection.style.display = "block";

    renderStems(job);

    // Scroll smoothly to results
    resultsSection.scrollIntoView({ behavior: "smooth" });
}

function onSeparationFailed(errorMsg) {
    btnStart.disabled = false;
    btnStartText.textContent = "Ayrıştırmayı Başlat";
    alert("Hata: " + errorMsg);
}

// Render stems list with audio players
function renderStems(job) {
    stemsList.innerHTML = "";

    const stems = job.stems || {};
    const stemsInfo = job.stems_info || {};

    Object.keys(stems).forEach(stemKey => {
        const stemData = stems[stemKey];
        const info = stemsInfo[stemKey] || { label: stemKey.toUpperCase() };

        const card = document.createElement("div");
        card.className = "stem-card";

        card.innerHTML = `
            <div class="stem-info">
                <div class="stem-names">
                    <span class="stem-label">${info.label}</span>
                    <span class="stem-sub">${(stemData.extension || '.mp3').toUpperCase()} (320kbps) • ${formatBytes(stemData.file_size)}</span>
                </div>
            </div>

            <div class="stem-player">
                <audio controls preload="metadata" src="${stemData.stream_url}"></audio>
            </div>

            <div class="stem-actions">
                <button class="btn-save-stem" data-stem="${stemKey}" title="Bu kanalı masaüstüne kaydet">
                    Masaüstüne Kaydet
                </button>
            </div>
        `;

        // Save single stem listener
        const btnSaveStem = card.querySelector(".btn-save-stem");
        btnSaveStem.addEventListener("click", () => {
            saveStemsToDesktop(stemKey);
        });

        stemsList.appendChild(card);
    });
}

// Save stems to Desktop
async function saveStemsToDesktop(stemName = null) {
    try {
        const res = await fetch("/api/save-to-desktop", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ stem_name: stemName })
        });

        const data = await res.json();
        if (data.success) {
            savedFolderPath.textContent = data.folder_path;
            savedBanner.style.display = "flex";

            // Automatically trigger Windows explorer to open the folder
            await fetch("/api/open-desktop-folder", { method: "POST" });
        } else {
            alert("Kaydetme hatası: " + (data.error || "Bilinmeyen hata"));
        }
    } catch (err) {
        console.error("Kaydetme hatası:", err);
        alert("Kaydedilemedi: " + err.message);
    }
}

// Reset all and cleanup memory/temp
async function resetAll() {
    if (pollInterval) clearInterval(pollInterval);
    if (ytEventSource) {
        ytEventSource.close();
        ytEventSource = null;
    }
    
    try {
        await fetch("/api/cleanup", { method: "POST" });
    } catch (e) {
        console.error(e);
    }

    clearSelectedFile();
    progressSection.style.display = "none";
    resultsSection.style.display = "none";
    savedBanner.style.display = "none";
    stemsList.innerHTML = "";
    btnStart.disabled = true;
    btnStartText.textContent = "Ayrıştırmayı Başlat";

    // Reset to default file tab
    switchSource("file");
    tabFile.classList.add("active");
    tabYoutube.classList.remove("active");
}

function formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes === 0) return "0 Bytes";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}
