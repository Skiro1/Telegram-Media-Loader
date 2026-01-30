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
# CONFIGURATION AND LOGGING
# ==========================================

# Minimal logging mode (console shows only URLs and user IDs)
MINIMAL_LOGGING = True

if MINIMAL_LOGGING:
    # Disable standard library logs
    logging.basicConfig(level=logging.ERROR, force=True)
    _original_print = print
    # Redirect print to nowhere
    print = lambda *args, **kwargs: None
    def console_log(message):
        # Output to console via system stdout only
        sys.__stdout__.write(str(message) + "\n")
        sys.__stdout__.flush()
else:
    logging.basicConfig(level=logging.INFO, force=True)
    def console_log(message):
        _original_print(message) if '_original_print' in globals() else print(message)

# ==========================================
# DEPENDENCY CHECK (FFMPEG / SPOTDL)
# ==========================================

def check_ffmpeg():
    """Checks for FFmpeg in the system or local folder"""
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
    """Checks if spotDL library is installed for Spotify support"""
    try:
        import spotdl
        return True
    except ImportError:
        return False

SPOTDL_AVAILABLE = check_spotdl()

# Load settings from config.py
API_ID = config.API_ID
API_HASH = config.API_HASH
BOT_TOKEN = config.BOT_TOKEN
ALLOWED_USERS = getattr(config, 'ALLOWED_USERS', [])

# Folder paths
VIDEO_DIR = "./downloads/video/"
AUDIO_DIR = "./downloads/audio/"
DB_DIR = "./database/"
THUMB_CACHE_DIR = "./thumbs_cache/"
SPOTIFY_DIR = "./downloads/spotify/"

# File limits (2 GB for Telegram)
MAX_FILE_SIZE_BYTES = 2000 * 1024 * 1024
MAX_FILE_SIZE_MB = 1950

# Create required directories
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(THUMB_CACHE_DIR, exist_ok=True)
os.makedirs(SPOTIFY_DIR, exist_ok=True)

# Initialize Pyrogram client
app = Client(name="media_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# YouTube settings
YOUTUBE_COOKIES_FILE = './cookies.txt'
loop = asyncio.get_event_loop()
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

# Download queue management
active_downloads = {}
downloads_lock = asyncio.Lock()
MAX_CONCURRENT_DOWNLOADS = 2 # Max simultaneous downloads per user

# ==========================================
# DATABASE OPERATIONS (SQLITE)
# ==========================================

def get_db_connection():
    """Creates a database connection"""
    DB_PATH = os.path.join(DB_DIR, "bot_database.db")
    return sqlite3.connect(DB_PATH)

def init_db():
    """Creates tables if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            date_added TEXT
        )
    ''')
    # Captions table (hash -> text)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS captions (
            url_hash TEXT PRIMARY KEY,
            caption TEXT,
            date_created TEXT
        )
    ''')
    # URL mapping table (hash -> full URL)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS url_mappings (
            url_hash TEXT PRIMARY KEY,
            url TEXT,
            date_created TEXT
        )
    ''')
    # Usage limits table (for future use)
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
# DOWNLOAD FLOW CONTROL
# ==========================================

async def can_start_download(user_id):
    """Checks if a user can start a new download"""
    async with downloads_lock:
        if user_id not in active_downloads:
            active_downloads[user_id] = set()
        if len(active_downloads[user_id]) >= MAX_CONCURRENT_DOWNLOADS:
            return False
        download_id = str(uuid.uuid4())
        active_downloads[user_id].add(download_id)
        return download_id

async def finish_download(user_id, download_id):
    """Removes a download from the active list upon completion"""
    async with downloads_lock:
        if user_id in active_downloads and download_id in active_downloads[user_id]:
            active_downloads[user_id].remove(download_id)
            if not active_downloads[user_id]:
                del active_downloads[user_id]

# ==========================================
# YT-DLP OPTIONS (DOWNLOADER)
# ==========================================

def get_ydl_options(format_type='video', unique_id=None, download=False):
    """Returns a dictionary with yt-dlp settings"""
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
        # Audio settings (MP3 extraction)
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
# DATABASE HELPER FUNCTIONS
# ==========================================

async def save_user(user):
    """Saves user information to the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, date_added)
        VALUES (?, ?, ?, ?, datetime('now'))
    ''', (user.id, user.username, user.first_name, user.last_name))
    conn.commit()
    conn.close()

async def save_url_mapping(url):
    """Saves a URL and returns its hash for buttons"""
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
    """Retrieves the original URL by its hash"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM url_mappings WHERE url_hash = ?', (url_hash,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ==========================================
# COMMAND AND MESSAGE HANDLERS
# ==========================================

@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Handles the /start command"""
    await save_user(message.from_user)
    await message.reply_text(
        "👋 **Hello!** I'm a bot for downloading video and audio from various services.\n\n"
        "Just send me a link to a video from YouTube, TikTok, Spotify, SoundCloud, or VK."
    )

@app.on_message(filters.regex(r'https?://[^\s]+'))
async def link_handler(client, message):
    """Handles incoming links"""
    url = message.text.strip()
    user_id = message.from_user.id
    console_log(f"URL: {url} (User: {user_id})")
    
    url_hash = await save_url_mapping(url)
    
    # Create format selection buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Video", callback_data=f"dl_video_{url_hash}"),
            InlineKeyboardButton("🎵 Audio", callback_data=f"dl_audio_{url_hash}")
        ]
    ])
    
    await message.reply_text("Select download format:", reply_markup=keyboard)

@app.on_callback_query(filters.regex(r'^dl_(video|audio)_(.+)'))
async def download_callback(client, callback_query):
    """Handles 'Video' or 'Audio' button clicks"""
    format_type = callback_query.matches[0].group(1)
    url_hash = callback_query.matches[0].group(2)
    url = await get_url_from_hash(url_hash)
    user_id = callback_query.from_user.id
    
    if not url:
        await callback_query.answer("Error: Link not found in database.", show_alert=True)
        return

    # Check simultaneous download limits
    download_id = await can_start_download(user_id)
    if not download_id:
        await callback_query.answer("Simultaneous download limit reached (max 2).", show_alert=True)
        return

    await callback_query.answer("Starting download...")
    status_msg = await callback_query.message.edit_text("**Downloading...**")
    
    # Run download in a background task
    asyncio.create_task(download_and_send(client, callback_query.message.chat.id, url, format_type, user_id, download_id, status_msg))

async def download_and_send(client, chat_id, url, format_type, user_id, download_id, status_msg):
    """Main function to download and send the file"""
    try:
        unique_id = str(uuid.uuid4())[:8]
        ydl_opts = get_ydl_options(format_type, unique_id, download=True)
        
        # Download file via yt-dlp in a separate thread
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(executor, lambda: ydl.extract_info(url, download=True))
            file_path = ydl.prepare_filename(info)
            # Adjust extension for audio
            if format_type == 'audio':
                file_path = os.path.splitext(file_path)[0] + ".mp3"

        if os.path.exists(file_path):
            await status_msg.edit_text("**Uploading file...**")
            # Send based on type
            if format_type == 'video':
                await client.send_video(chat_id, video=file_path, caption=f"**Done!**\n{url}")
            else:
                await client.send_audio(chat_id, audio=file_path, caption=f"**Done!**\n{url}")
            
            await status_msg.delete()
            # Remove temporary file
            if os.path.exists(file_path): os.remove(file_path)
        else:
            await status_msg.edit_text("Error: File was not created.")
            
    except Exception as e:
        console_log(f"Error downloading {url}: {e}")
        await status_msg.edit_text(f"**Download error:**\n{str(e)[:100]}")
    finally:
        # Free up slot in download queue
        await finish_download(user_id, download_id)

@app.on_inline_query()
async def inline_handler(client, inline_query):
    """Handles inline queries (when calling bot via @botname)"""
    query = inline_query.query.strip()
    user = inline_query.from_user
    if not query: return
    
    console_log(f"INLINE: {query} (ID: {user.id})")
    url_hash = hashlib.md5(query.encode()).hexdigest()
    await save_url_mapping(query)
    
    # Inline search results
    results = [
        InlineQueryResultArticle(
            title="Download Video",
            input_message_content=InputTextMessageContent(f"🎬 Downloading video:\n{query}"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Download", callback_data=f"dl_video_{url_hash}")]])
        ),
        InlineQueryResultArticle(
            title="Download Audio",
            input_message_content=InputTextMessageContent(f"🎵 Downloading audio:\n{query}"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎵 Download", callback_data=f"dl_audio_{url_hash}")]])
        )
    ]
    await inline_query.answer(results, cache_time=1)

if __name__ == "__main__":
    console_log("Bot started!")
    app.run()
