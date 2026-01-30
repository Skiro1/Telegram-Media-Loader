# Media Downloader Bot

Простой Telegram бот для загрузки видео и аудио из YouTube, TikTok, Spotify, SoundCloud и VK.

## Возможности

- Загрузка видео (до 1080p)
- Загрузка аудио (MP3 320kbps)
- Поддержка YouTube, TikTok, Spotify, SoundCloud, VK
- Поддержка инлайн-режима
- Минимальное логирование в консоль
- Ограничение количества одновременных загрузок

## Установка

1. Установите [FFmpeg](https://ffmpeg.org/) и [Deno](https://deno.land/) (опционально, для решения сигнатур YouTube).
2. Склонируйте репозиторий.
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Настройте `config.py`, указав ваши `API_ID`, `API_HASH` и `BOT_TOKEN`.
5. Запустите бота:
   ```bash
   python bot_ru.py
   ```

## Настройка

Отредактируйте `config.py`:
- `API_ID`: Ваш Telegram API ID с сайта [my.telegram.org](https://my.telegram.org).
- `API_HASH`: Ваш Telegram API Hash с сайта [my.telegram.org](https://my.telegram.org).
- `BOT_TOKEN`: Токен вашего бота от [@BotFather](https://t.me/BotFather).
- `ALLOWED_USERS`: (Опционально) Список ID пользователей, которым разрешено использовать бота.

## Зависимости

- [Pyrogram](https://docs.pyrogram.org/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [spotDL](https://github.com/spotDL/spotify-downloader)
