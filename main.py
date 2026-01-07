import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN', '')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Welcome! Send me a YouTube video link and I will download it for you.\n'
        'Example: https://www.youtube.com/watch?v=VIDEO_ID'
    )

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    await update.message.reply_text('⏳ Processing your video...')
    
    try:
        ydl_opts = {
            'format': 'best[ext=mp4][filesize<50M]/best[ext=mp4]/best',
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = info.get('title', 'video')
        
        await update.message.reply_text(f'✅ Downloaded: {title}\n📤 Uploading...')
        
        with open(filename, 'rb') as video:
            await update.message.reply_video(video=video, caption=title)
        
        os.remove(filename)
        logger.info(f'Successfully sent video: {title}')
        
    except Exception as e:
        logger.error(f'Error: {e}')
        await update.message.reply_text(f'❌ Error: {str(e)}')

if __name__ == '__main__':
    if not BOT_TOKEN:
        print('Error: BOT_TOKEN environment variable not set')
        exit(1)
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    
    logger.info('Bot started...')
    application.run_polling()
