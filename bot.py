import os
import asyncio
import logging
import tempfile
from aiogram import Bot, Dispatcher, types
import vk_api
import requests

# Загружаем .env
load_dotenv() 

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Получаем токены из переменных окружения
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID"))
YOUR_TELEGRAM_ID = int(os.getenv("YOUR_TELEGRAM_ID", 0)) or None

# Инициализация
bot = Bot(token=TG_BOT_TOKEN)
dp = Dispatcher(bot)
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()

# --- Функции загрузки ---
async def upload_photo_to_vk(photo_bytes):
    upload_url = vk.photos.getWallUploadServer(group_id=VK_GROUP_ID)['upload_url']
    response = requests.post(upload_url, files={'photo': photo_bytes})
    result = response.json()
    saved = vk.photos.saveWallPhoto(group_id=VK_GROUP_ID, **result)[0]
    return f"photo{saved['owner_id']}_{saved['id']}"

async def upload_doc_to_vk(file_path, title="Файл"):
    upload_url = vk.docs.getWallUploadServer(group_id=VK_GROUP_ID)['upload_url']
    with open(file_path, 'rb') as f:
        response = requests.post(upload_url, files={'file': f})
    result = response.json()
    doc = vk.docs.save(file=result['file'], title=title, group_id=VK_GROUP_ID)[0]
    return f"doc{doc['owner_id']}_{doc['id']}"

# --- Основной обработчик ---
@dp.message_handler(content_types=types.ContentTypes.ANY)
async def handle_message(message: types.Message):
    # Опционально: принимать только от вас
    if YOUR_TELEGRAM_ID and message.from_user.id != YOUR_TELEGRAM_ID:
        return

    text = message.caption or message.text or ""
    attachments = []

    with tempfile.TemporaryDirectory() as temp_dir:
        # === Фото ===
        if message.photo:
            photo = message.photo[-1]
            file = await bot.download(photo)
            att = await upload_photo_to_vk(file.read())
            attachments.append(att)

        # === Видео / GIF ===
        elif message.video or message.animation:
            media = message.video or message.animation
            ext = ".mp4"
            file_path = os.path.join(temp_dir, f"{media.file_unique_id}{ext}")
            await bot.download(media, destination=file_path)
            att = await upload_doc_to_vk(file_path, title="Видео" if message.video else "GIF")
            attachments.append(att)

        # === Документы ===
        elif message.document:
            doc = message.document
            file_name = doc.file_name or f"{doc.file_unique_id}"
            file_path = os.path.join(temp_dir, file_name)
            await bot.download(doc, destination=file_path)
            att = await upload_doc_to_vk(file_path, title=file_name)
            attachments.append(att)

        # === Публикация во ВКонтакте ===
        try:
            vk.wall.post(
                owner_id=-VK_GROUP_ID,
                message=text,
                attachments=','.join(attachments) if attachments else None
            )
            logging.info("✅ Пост опубликован во ВК!")
            await message.answer("✅ Отправлено в ВК!")
        except Exception as e:
            logging.error(f"❌ Ошибка ВК: {e}")
            await message.answer("❌ Ошибка при публикации.")

# --- Запуск ---
if __name__ == '__main__':
    print("🚀 Бот запущен. Отправляйте контент!")
    asyncio.run(dp.start_polling())
