# Media Downloader Bot 🎬🎵

[Русский](#russian) | [English](#english)

---

<a name="russian"></a>
## 🇷🇺 Русский (Russian)

Простой и мощный Telegram бот для загрузки видео и аудио из YouTube, TikTok, Spotify, SoundCloud и VK.

### 🌟 Возможности
- **Загрузка видео**: до 1080p (через `yt-dlp`).
- **Загрузка аудио**: MP3 320kbps (поддержка Spotify через `spotDL`).
- **Инлайн-режим**: вызывайте бота через `@имя_бота` в любом чате.
- **Умная очередь**: ограничение одновременных загрузок для стабильности.
- **Локализация**: полная поддержка русского и английского языков.

### 🛠 Установка
1. **Установите FFmpeg**:
   - Windows: [Скачать](https://ffmpeg.org/download.html) и добавить в PATH или положить `ffmpeg.exe` в папку с ботом.
   - Linux: `sudo apt install ffmpeg`
2. **Клонируйте репозиторий**:
   ```bash
   git clone https://github.com/ваш-логин/MediaDownloaderBot.git
   cd MediaDownloaderBot
   ```
3. **Установите зависимости**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Настройте `config.py`**:
   Укажите свои `API_ID`, `API_HASH` и `BOT_TOKEN` (получить у [@BotFather](https://t.me/BotFather)).
5. **Запустите бота**:
   ```bash
   python bot_ru.py
   ```

### 📦 Основные зависимости
- [Kurigram](https://github.com/Kurimuzard/Kurigram) (Форк Pyrogram)
- [Pyrogram](https://docs.pyrogram.org/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [spotDL](https://github.com/spotDL/spotify-downloader)

---

<a name="english"></a>
## 🇺🇸 English

A simple and powerful Telegram bot to download video and audio from YouTube, TikTok, Spotify, SoundCloud, and VK.

### 🌟 Features
- **Video Download**: up to 1080p (via `yt-dlp`).
- **Audio Download**: MP3 320kbps (Spotify support via `spotDL`).
- **Inline Mode**: call the bot via `@botname` in any chat.
- **Smart Queue**: concurrent download limits for stability.
- **Localization**: full support for Russian and English languages.

### 🛠 Setup
1. **Install FFmpeg**:
   - Windows: [Download](https://ffmpeg.org/download.html) and add to PATH or place `ffmpeg.exe` in the bot folder.
   - Linux: `sudo apt install ffmpeg`
2. **Clone the repository**:
   ```bash
   git clone https://github.com/your-login/MediaDownloaderBot.git
   cd MediaDownloaderBot
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure `config.py`**:
   Set your `API_ID`, `API_HASH`, and `BOT_TOKEN` (get from [@BotFather](https://t.me/BotFather)).
5. **Run the bot**:
   ```bash
   python bot_en.py
   ```

### 📦 Main Dependencies
- [Kurigram](https://github.com/Kurimuzard/Kurigram) (Pyrogram Fork)
- [Pyrogram](https://docs.pyrogram.org/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [spotDL](https://github.com/spotDL/spotify-downloader)
