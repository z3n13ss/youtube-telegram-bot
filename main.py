import os
import re
import logging
import requests
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.abspath("downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SECRET_CODE = os.getenv("SECRET_CODE", "Dload2212")
authenticated_users = set()

YOUTUBE_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[\w-]+'
)

# Fetch proxy from ProxyScrape
def get_proxy():
    """Fetch a working proxy from ProxyScrape API"""
    try:
        # ProxyScrape free API - returns HTTP/HTTPS proxies
        url = 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&timeout=20000'
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            proxies = response.text.strip().split('\n')
            if proxies:
                # Pick a random proxy from the list
                proxy = random.choice(proxies)
                logger.info(f"Using proxy: {proxy}")
                return proxy
    except Exception as e:
        logger.error(f"Failed to fetch proxy: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in authenticated_users:
        await update.message.reply_text(
            "You're already authenticated!\n\n"
            "Just send me a YouTube link and I'll download the video for you.\n\n"
            "Commands:\n"
            "/start - Show this message\n"
            "/help - Get help"
        )
        return
    
    await update.message.reply_text("🔐 Please enter the secret code to use this bot:")
    context.user_data['awaiting_code'] = True

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authenticated_users:
        await update.message.reply_text("Please use /start and enter the secret code first.")
        return
    
    await update.message.reply_text(
        "How to use this bot:\n\n"
        "1. Send me a YouTube video link\n"
        "2. Wait for the video to download\n"
        "3. Receive the video file\n\n"
        "Supported formats:\n"
        "- Regular YouTube videos\n"
        "- YouTube Shorts\n"
        "- youtu.be short links"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('awaiting_code'):
        if text == SECRET_CODE:
            authenticated_users.add(user_id)
            context.user_data['awaiting_code'] = False
            await update.message.reply_text(
                "✅ Authenticated successfully!\n\n"
                "Now send me any YouTube link and I'll download the video for you."
            )
        else:
            await update.message.reply_text("❌ Wrong code! Please try again.")
        return
    
    if user_id not in authenticated_users:
        await update.message.reply_text("Please use /start to authenticate first.")
        return
    
    await download_video(update, context)

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    
    match = YOUTUBE_REGEX.search(message_text)
    if not match:
        await update.message.reply_text("Please send a valid YouTube link.")
        return
    
    url = match.group()
    if not url.startswith('http'):
        url = 'https://' + url
    
    status_message = await update.message.reply_text("⏳ Downloading video...")
    
    try:
        # Get a proxy from ProxyScrape
        proxy = get_proxy()
        
        # Enhanced yt-dlp options with proxy support
        ydl_opts = {
            'format': 'best',
            'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': False,
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
            'verbose': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            },
        }
        
        # Add proxy if available
        if proxy:
            ydl_opts['proxy'] = proxy
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Downloading: {url}")
            info = ydl.extract_info(url, download=True)
            
            if info is None:
                await status_message.edit_text("❌ Failed to download video.")
                return
            
            filename = ydl.prepare_filename(info)
            title = info.get('title', 'Video')
            
            if not os.path.exists(filename):
                await status_message.edit_text("❌ Download failed. File was not created.")
                return
            
            file_size = os.path.getsize(filename)
            
            if file_size == 0 or file_size < 1024:
                await status_message.edit_text("❌ Download failed - empty file.")
                try:
                    os.remove(filename)
                except:
                    pass
                return
            
            if file_size > 2000 * 1024 * 1024:
                await status_message.edit_text("❌ Video file is too large (>2GB).")
                try:
                    os.remove(filename)
                except:
                    pass
                return
            
            await status_message.edit_text("📤 Uploading video...")
            
            with open(filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"🎬 {title}",
                    supports_streaming=True,
                    read_timeout=60,
                    write_timeout=60
                )
            
            await status_message.delete()
            
            try:
                os.remove(filename)
            except Exception as e:
                logger.error(f"Failed to delete file: {e}")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        await status_message.edit_text(f"❌ Download failed: {str(e)[:200]}")

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return
    
    logger.info("Starting bot...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot is running!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
