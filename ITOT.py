import asyncio
import logging
import requests
import sqlite3
from decimal import Decimal
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, \
    LabeledPrice, PreCheckoutQuery, ChatJoinRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== Flask-ЗАГЛУШКА ДЛЯ RENDER (ДОЛЖНА БЫТЬ В САМОМ НАЧАЛЕ) ==========
from flask import Flask
import threading
import os

flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health():
    return "Bot is running", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# Запускаем Flask в отдельном потоке
threading.Thread(target=run_flask, daemon=True).start()
print("✅ Flask-сервер запущен на порту 10000")
# ==================================================================

# ========== НАСТРОЙКИ ==========
TOKEN = "8659138133:AAGHE6O02blJvGSKoGQAUwgZCMEKcftOZBU"
MODERATOR_CHAT_ID = 8315293936
CRYPTOBOT_TOKEN = "582195:AAOKdczYX9Dq8QNvpJ1hY23ft33N6nvBqGk"
GROUP_URL = "https://t.me/+RN8kV8FAVAg3ZGU6"
GROUP_ID = -1003837687191

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# ========== БАЗА ДАННЫХ (SQLite) ==========
# ... (весь остальной твой код без изменений) ...

# ========== ЗАПУСК ==========
async def main():
    print("🚀 Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Вебхук удалён. Бот готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
