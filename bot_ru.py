import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
import logging
import asyncio
import concurrent.futures
import os
import config
import hashlib
import subprocess
import sqlite3
import uuid
import sys

# ==========================================
# КОНФИГУРАЦИЯ И ЛОГИРОВАНИЕ
# ==========================================

# Режим минимального логирования (в консоли только ссылки и ID пользователей)
MINIMAL_LOGGING = True

if MINIMAL_LOGGING:
    # Отключаем стандартные логи библиотек
    logging.basicConfig(level=logging.ERROR, force=True)
    _original_print = print
    # Перенаправляем print в никуда
    print = lambda *args, **kwargs: None
    def console_log(message):
        # Вывод в консоль только через системный поток
        sys.__stdout__.write(str(message) + "\n")
        sys.__stdout__.flush()
else:
    logging.basicConfig(level=logging.INFO, force=True)
    def console_log(message):
        _original_print(message) if '_original_print' in globals() else print(message)

# ==========================================
# ПРОВЕРКА ЗАВИСИМОСТЕЙ (FFMPEG / SPOTDL)
# ==========================================

def check_ffmpeg():
    """Проверяет наличие FFmpeg в системе или в текущей папке"""
    if os.path.exists("./ffmpeg"):
        os.chmod("./ffmpeg", 0o755)
        try:
            subprocess.run(["./ffmpeg", "-version"], capture_output=True, check=True)
            return "./ffmpeg"
        except:
            pass
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return "ffmpeg"
    except:
        return None

FFMPEG_PATH = check_ffmpeg()
FFMPEG_AVAILABLE = FFMPEG_PATH is not None

def check_spotdl():
    """Проверяет установлена ли библиотека spotDL для Spotify"""
    try:
        import spotdl
        return True
    except ImportError:
        return False

SPOTDL_AVAILABLE = check_spotdl()

# Загрузка настроек из config.py
API_ID = config.API_ID
API_HASH = config.API_HASH
BOT_TOKEN = config.BOT_TOKEN
ALLOWED_USERS = getattr(config, 'ALLOWED_USERS', [])

# Пути к папкам
VIDEO_DIR = "./downloads/video/"
AUDIO_DIR = "./downloads/audio/"
DB_DIR = "./database/"
THUMB_CACHE_DIR = "./thumbs_cache/"
SPOTIFY_DIR = "./downloads/spotify/"

# Лимиты файлов (2 ГБ для Telegram)
MAX_FILE_SIZE_BYTES = 2000 * 1024 * 1024
MAX_FILE_SIZE_MB = 1950

# Создание необходимых папок
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(THUMB_CACHE_DIR, exist_ok=True)
os.makedirs(SPOTIFY_DIR, exist_ok=True)

# Инициализация клиента Pyrogram
app = Client(name="media_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Настройки для работы с YouTube
YOUTUBE_COOKIES_FILE = './cookies.txt'
loop = asyncio.get_event_loop()
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

# Управление очередью загрузок
active_downloads = {}
downloads_lock = asyncio.Lock()
MAX_CONCURRENT_DOWNLOADS = 2 # Максимум одновременных загрузок на одного пользователя

# ==========================================
# РАБОТА С БАЗОЙ ДАННЫХ (SQLITE)
# ==========================================

def get_db_connection():
    """Создает подключение к БД"""
    DB_PATH = os.path.join(DB_DIR, "bot_database.db")
    return sqlite3.connect(DB_PATH)

def init_db():
    """Создает таблицы, если они не существуют"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            date_added TEXT
        )
    ''')
    # Таблица для хранения описаний (хэш -> текст)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS captions (
            url_hash TEXT PRIMARY KEY,
            caption TEXT,
            date_created TEXT
        )
    ''')
    # Таблица соответствия хэша и полной ссылки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS url_mappings (
            url_hash TEXT PRIMARY KEY,
            url TEXT,
            date_created TEXT
        )
    ''')
    # Таблица лимитов использования (на будущее)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS command_limits (
            user_id INTEGER,
            usage_date TEXT,
            usage_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, usage_date)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# УПРАВЛЕНИЕ ПОТОКАМИ ЗАГРУЗКИ
# ==========================================

async def can_start_download(user_id):
    """Проверяет, может ли пользователь начать новую загрузку"""
    async with downloads_lock:
        if user_id not in active_downloads:
            active_downloads[user_id] = set()
        if len(active_downloads[user_id]) >= MAX_CONCURRENT_DOWNLOADS:
            return False
        download_id = str(uuid.uuid4())
        active_downloads[user_id].add(download_id)
        return download_id

async def finish_download(user_id, download_id):
    """Удаляет загрузку из списка активных по завершении"""
    async with downloads_lock:
        if user_id in active_downloads and download_id in active_downloads[user_id]:
            active_downloads[user_id].remove(download_id)
            if not active_downloads[user_id]:
                del active_downloads[user_id]

# ==========================================
# НАСТРОЙКИ YT-DLP (ЗАГРУЗЧИК)
# ==========================================

def get_ydl_options(format_type='video', unique_id=None, download=False):
    """Возвращает словарь с настройками для yt-dlp"""
    options = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'check_hostname': False,
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'format_sort': ['vcodec:h264', 'res:1080', 'ext:mp4:m4a'],
        'socket_timeout': 30,
        'cookiefile': YOUTUBE_COOKIES_FILE if os.path.exists(YOUTUBE_COOKIES_FILE) else None,
        'ignoreerrors': True,
    }
    if not download:
        return options
    options.update({
        'extract_flat': False,
        'merge_output_format': 'mp4',
    })
    if format_type == 'video':
        options.update({
            'ignoreerrors': False,
            'max_filesize': MAX_FILE_SIZE_BYTES,
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'outtmpl': os.path.join(VIDEO_DIR, f'%(title)s_{unique_id}.%(ext)s') if unique_id else os.path.join(VIDEO_DIR, '%(title)s.%(ext)s')
        })
    else:
        # Настройки для аудио (извлечение MP3)
        options.update({
            'ignoreerrors': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320'
            }],
            'outtmpl': os.path.join(AUDIO_DIR, f'%(title)s_{unique_id}.%(ext)s') if unique_id else os.path.join(AUDIO_DIR, '%(title)s.%(ext)s')
        })
    return options

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ БАЗЫ
# ==========================================

async def save_user(user):
    """Сохраняет информацию о пользователе в БД"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, date_added)
        VALUES (?, ?, ?, ?, datetime('now'))
    ''', (user.id, user.username, user.first_name, user.last_name))
    conn.commit()
    conn.close()

async def save_url_mapping(url):
    """Сохраняет ссылку и возвращает её хэш для кнопок"""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO url_mappings (url_hash, url, date_created)
        VALUES (?, ?, datetime('now'))
    ''', (url_hash, url))
    conn.commit()
    conn.close()
    return url_hash

async def get_url_from_hash(url_hash):
    """Получает оригинальную ссылку по её хэшу"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM url_mappings WHERE url_hash = ?', (url_hash,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ==========================================
# ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ
# ==========================================

@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Обработка команды /start"""
    await save_user(message.from_user)
    await message.reply_text(
        "👋 **Привет!** Я бот для загрузки видео и аудио из различных сервисов.\n\n"
        "Просто отправь мне ссылку на видео из YouTube, TikTok, Spotify, SoundCloud или VK."
    )

@app.on_message(filters.regex(r'https?://[^\s]+'))
async def link_handler(client, message):
    """Обработка входящих ссылок"""
    url = message.text.strip()
    user_id = message.from_user.id
    console_log(f"URL: {url} (User: {user_id})")
    
    url_hash = await save_url_mapping(url)
    
    # Создание кнопок выбора формата
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Видео", callback_data=f"dl_video_{url_hash}"),
            InlineKeyboardButton("🎵 Аудио", callback_data=f"dl_audio_{url_hash}")
        ]
    ])
    
    await message.reply_text("Выберите формат загрузки:", reply_markup=keyboard)

@app.on_callback_query(filters.regex(r'^dl_(video|audio)_(.+)'))
async def download_callback(client, callback_query):
    """Обработка нажатия на кнопки 'Видео' или 'Аудио'"""
    format_type = callback_query.matches[0].group(1)
    url_hash = callback_query.matches[0].group(2)
    url = await get_url_from_hash(url_hash)
    user_id = callback_query.from_user.id
    
    if not url:
        await callback_query.answer("Ошибка: Ссылка не найдена в базе.", show_alert=True)
        return

    # Проверка лимитов на одновременные загрузки
    download_id = await can_start_download(user_id)
    if not download_id:
        await callback_query.answer("Достигнут лимит одновременных загрузок (макс. 2).", show_alert=True)
        return

    await callback_query.answer("Начинаю загрузку...")
    status_msg = await callback_query.message.edit_text("**Загрузка началась...**")
    
    # Запуск загрузки в фоновой задаче
    asyncio.create_task(download_and_send(client, callback_query.message.chat.id, url, format_type, user_id, download_id, status_msg))

async def download_and_send(client, chat_id, url, format_type, user_id, download_id, status_msg):
    """Основная функция загрузки и отправки файла"""
    try:
        unique_id = str(uuid.uuid4())[:8]
        ydl_opts = get_ydl_options(format_type, unique_id, download=True)
        
        # Скачивание файла через yt-dlp в отдельном потоке
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(executor, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info)
            # Корректировка расширения для аудио
            if format_type == 'audio':
                file_path = os.path.splitext(file_path)[0] + ".mp3"

        if os.path.exists(file_path):
            await status_msg.edit_text("**Отправка файла...**")
            # Отправка в зависимости от типа
            if format_type == 'video':
                await client.send_video(chat_id, video=file_path, caption=f"**Готово!**\n{url}")
            else:
                await client.send_audio(chat_id, audio=file_path, caption=f"**Готово!**\n{url}")
            
            await status_msg.delete()
            # Удаление временного файла
            if os.path.exists(file_path): os.remove(file_path)
        else:
            await status_msg.edit_text("Ошибка: Файл не был создан.")
            
    except Exception as e:
        console_log(f"Error downloading {url}: {e}")
        await status_msg.edit_text(f"**Ошибка при загрузке:**\n{str(e)[:100]}")
    finally:
        # Освобождаем место в очереди загрузок
        await finish_download(user_id, download_id)

@app.on_inline_query()
async def inline_handler(client, inline_query):
    """Обработка инлайн-запросов (когда бота вызывают через @botname)"""
    query = inline_query.query.strip()
    user = inline_query.from_user
    if not query: return
    
    console_log(f"INLINE: {query} (ID: {user.id})")
    url_hash = hashlib.md5(query.encode()).hexdigest()
    await save_url_mapping(query)
    
    # Результаты инлайн-поиска
    results = [
        InlineQueryResultArticle(
            title="Скачать Видео",
            input_message_content=InputTextMessageContent(f"🎬 Загрузка видео:\n{query}"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Скачать", callback_data=f"dl_video_{url_hash}")]])
        ),
        InlineQueryResultArticle(
            title="Скачать Аудио",
            input_message_content=InputTextMessageContent(f"🎵 Загрузка аудио:\n{query}"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎵 Скачать", callback_data=f"dl_audio_{url_hash}")]])
        )
    ]
    await inline_query.answer(results, cache_time=1)

if __name__ == "__main__":
    console_log("Бот запущен!")
    app.run()
