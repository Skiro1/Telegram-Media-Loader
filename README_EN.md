# Media Downloader Bot

A simple Telegram bot to download video and audio from YouTube, TikTok, Spotify, SoundCloud, and VK.

## Features

- Download video (up to 1080p)
- Download audio (MP3 320kbps)
- Supports YouTube, TikTok, Spotify, SoundCloud, VK
- Inline mode support
- Minimal logging
- Concurrent download limits

## Setup

1. Install [FFmpeg](https://ffmpeg.org/) and [Deno](https://deno.land/) (optional, for signature solving).
2. Clone the repository.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure `config.py` with your `API_ID`, `API_HASH`, and `BOT_TOKEN`.
5. Run the bot:
   ```bash
   python bot_en.py
   ```

## Configuration

Edit `config.py`:
- `API_ID`: Your Telegram API ID from [my.telegram.org](https://my.telegram.org).
- `API_HASH`: Your Telegram API Hash from [my.telegram.org](https://my.telegram.org).
- `BOT_TOKEN`: Your Telegram Bot Token from [@BotFather](https://t.me/BotFather).
- `ALLOWED_USERS`: (Optional) List of user IDs allowed to use the bot.

## Dependencies

- [Kurigram](https://github.com/KurimuzonAkuma/kurigram) (Pyrogram Fork)
- [Pyrogram](https://docs.pyrogram.org/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [spotDL](https://github.com/spotDL/spotify-downloader)

