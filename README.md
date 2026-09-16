# Lokal Şarkı ve Enstrüman Ayrıştırma Stüdyosu

Tamamen yerel, açık kaynaklı ve donanım hızlandırmalı (NVIDIA CUDA) müzik ayrıştırma (stem separation) aracı. Şarkıları herhangi bir ücretli API veya kota kısıtı olmadan kendi ekran kartınızda sınırsızca kanallarına ayırır.

---

## Özellikler

- **100% Yerel & Çevrimdışı**: Hiçbir harici API veya bulut servisine bağlanmaz, internet kotası harcamaz.
- **CUDA Hızlandırma**: NVIDIA GPU (Tensor çekirdekleri) ile 3-4 dakikalık bir şarkıyı ortalama **20-30 saniyede** ayırır.
- **Yüksek Kalite Çıktı**: Stüdyo ve FL Studio için hazır **320kbps MP3** formatında çıktı üretir.
- **Otomatik Model Seçimi**: Seçtiğiniz ayrıştırma hedefine göre en uygun Meta AI Demucs v4 modelini (`htdemucs_ft` veya `htdemucs_6s`) otomatik olarak belirler:
  -  **Vokal & Altyapı (2 Kanal)**: Şarkıyı Vokal (Acapella) ve temiz Altyapı olarak ayırır.
  -  **Sadece Davul / Bateri Çıkar (2 Kanal)**: Davul ritimleri ve davulsuz altyapı.
  -  **Sadece Bas Çıkar (2 Kanal)**: Bas hattı ve bassız şarkı.
  -  **Sadece Piyano Çıkar (2 Kanal)**: Piyano/klavye ve piyanosuz altyapı.
  -  **Sadece Gitar Çıkar (2 Kanal)**: Gitar partileri ve gitarsız altyapı.
  -  **Tüm Temel Enstrümanlar & Vokal (4 Kanal)**: Vokal, Davul, Bas, Diğer.
  -  **Gitar & Piyano Detaylı (6 Kanal)**: Vokal, Davul, Bas, Gitar, Piyano, Diğer.
- **Akıllı Bellek Yönetimi**: Ayrıştırılan dosyalar geçici bellekte tutulur, diskte yer kaplamaz. Yeni şarkı yüklendiğinde öncekiler otomatik temizlenir.
- **Masaüstüne Tek Tıkla Kayıt**: Ayrıştırılan kanalları doğrudan Masaüstünde klasör oluşturup kaydeder ve klasörü otomatik açar.

---

##  Başlangıç & Çalıştırma

### Gereksinimler
- Python 3.10+
- NVIDIA Ekran Kartı (CUDA destekli)
- FFmpeg

### Kurulum
```bash
pip install -r requirements.txt
```

### Çalıştırma
Windows'ta doğrudan **`baslat.bat`** dosyasına çift tıklayarak tarayıcınızda stüdyo arayüzünü (`http://localhost:7860`) başlatabilirsiniz.
