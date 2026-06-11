import os
import asyncio
import logging
import requests
import sqlite3
import time
from decimal import Decimal
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, \
    LabeledPrice, PreCheckoutQuery, ChatJoinRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== Flask-ЗАГЛУШКА ==========
from flask import Flask
import threading

flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health():
    return "Bot is running", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()
print("✅ Flask-сервер запущен")
# ===================================

# ========== НАСТРОЙКИ ==========
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден!")
    exit(1)

MODERATOR_CHAT_ID = 8315293936
CRYPTOBOT_TOKEN = "582195:AAOKdczYX9Dq8QNvpJ1hY23ft33N6nvBqGk"
GROUP_URL = "https://t.me/+qYXlqkHfN2sxMTZi"
GROUP_ID = -1003837687191

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# Для защиты от спама
last_payment_request = {}  # {user_id: timestamp}

# ========== БАЗА ДАННЫХ (SQLite) ==========
conn = sqlite3.connect('referrals.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users
    (
        user_id INTEGER PRIMARY KEY,
        referrer_id INTEGER DEFAULT NULL,
        balance REAL DEFAULT 0,
        referral_count INTEGER DEFAULT 0,
        first_bonus_given INTEGER DEFAULT 0,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchases
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tariff_name TEXT,
        tariff_price REAL,
        purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'active',
        payment_method TEXT DEFAULT 'cryptobot',
        refunded INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdraw_requests
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS payment_requests
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tariff_name TEXT,
        amount REAL,
        screenshot_file_id TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS join_requests
    (
        user_id INTEGER PRIMARY KEY,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved INTEGER DEFAULT 0
    )
''')
conn.commit()


# ========== ФУНКЦИИ БАЗЫ ДАННЫХ ==========
def register_user(user_id: int, referrer_id: int = None):
    if referrer_id == user_id:
        return False, "self_referral"

    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO users (user_id, referrer_id) VALUES (?, ?)', (user_id, referrer_id))
        conn.commit()

        if referrer_id:
            cursor.execute('SELECT first_bonus_given FROM users WHERE user_id = ?', (referrer_id,))
            data = cursor.fetchone()
            first_given = data[0] if data else 0

            if first_given == 0:
                cursor.execute(
                    'UPDATE users SET balance = balance + 185, first_bonus_given = 1, referral_count = referral_count + 1 WHERE user_id = ?',
                    (referrer_id,))
                conn.commit()
            else:
                cursor.execute('UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?', (referrer_id,))
                conn.commit()
        return True, "success"
    return False, "already_registered"


def get_user_data(user_id: int):
    cursor.execute('SELECT balance, referral_count FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()


def add_purchase(user_id: int, tariff_name: str, tariff_price: float, payment_method: str = "cryptobot"):
    cursor.execute('INSERT INTO purchases (user_id, tariff_name, tariff_price, payment_method) VALUES (?, ?, ?, ?)',
                   (user_id, tariff_name, tariff_price, payment_method))
    conn.commit()

    cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        referrer_id = result[0]
        bonus = tariff_price * 0.4
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bonus, referrer_id))
        conn.commit()


def get_user_purchases(user_id: int):
    cursor.execute(
        'SELECT id, tariff_name, tariff_price, purchased_at, status, payment_method, refunded FROM purchases WHERE user_id = ? ORDER BY purchased_at DESC',
        (user_id,))
    return cursor.fetchall()


async def get_referral_link(user_id: int) -> str:
    bot_info = await bot.get_me()
    return f"https://t.me/{bot_info.username}?start=ref_{user_id}"


def add_withdraw_request(user_id: int, amount: float):
    cursor.execute('INSERT INTO withdraw_requests (user_id, amount) VALUES (?, ?)', (user_id, amount))
    conn.commit()


def get_pending_withdraw_requests():
    cursor.execute(
        'SELECT id, user_id, amount, created_at FROM withdraw_requests WHERE status = "pending" ORDER BY created_at ASC')
    return cursor.fetchall()


def add_payment_request(user_id: int, tariff_name: str, amount: float, screenshot_file_id: str):
    cursor.execute(
        'INSERT INTO payment_requests (user_id, tariff_name, amount, screenshot_file_id) VALUES (?, ?, ?, ?)',
        (user_id, tariff_name, amount, screenshot_file_id))
    conn.commit()


def get_pending_payment_requests():
    cursor.execute(
        'SELECT id, user_id, tariff_name, amount, created_at FROM payment_requests WHERE status = "pending" ORDER BY created_at ASC')
    return cursor.fetchall()


def approve_withdraw(request_id: int, user_id: int):
    cursor.execute('UPDATE withdraw_requests SET status = "approved" WHERE id = ?', (request_id,))
    cursor.execute('UPDATE users SET balance = 0 WHERE user_id = ?', (user_id,))
    conn.commit()


def reject_withdraw(request_id: int):
    cursor.execute('UPDATE withdraw_requests SET status = "rejected" WHERE id = ?', (request_id,))
    conn.commit()


def approve_payment(request_id: int, user_id: int, tariff_name: str, amount: float):
    cursor.execute('UPDATE payment_requests SET status = "approved" WHERE id = ?', (request_id,))
    add_purchase(user_id, tariff_name, amount)
    conn.commit()


def reject_payment(request_id: int):
    cursor.execute('UPDATE payment_requests SET status = "rejected" WHERE id = ?', (request_id,))
    conn.commit()


def has_join_request(user_id: int) -> bool:
    cursor.execute('SELECT user_id FROM join_requests WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None


def add_join_request(user_id: int):
    cursor.execute('INSERT OR IGNORE INTO join_requests (user_id, approved) VALUES (?, 0)', (user_id,))
    conn.commit()


def approve_join_request(user_id: int):
    cursor.execute('UPDATE join_requests SET approved = 1 WHERE user_id = ?', (user_id,))
    conn.commit()


def get_pending_join_requests():
    cursor.execute('SELECT user_id, requested_at FROM join_requests WHERE approved = 0 ORDER BY requested_at ASC')
    return cursor.fetchall()


def get_rub_to_stars(rub: float) -> int:
    return int(rub / 1.33)


def get_stars_to_rub(stars: int) -> float:
    return round(stars * 1.33, 2)


# ========== КУРСЫ ==========
CRYPTO_RATES = {
    "USDT": Decimal("73.10"),
    "TON": Decimal("140.6"),
    "BTC": Decimal("5731417"),
    "ETH": Decimal("160232.59"),
    "SOL": Decimal("6351.12"),
    "TRX": Decimal("25.70"),
    "USDC": Decimal("73.10"),
}
STARS_RATE = 0.75


# ========== FSM ==========
class PaymentState(StatesGroup):
    selected_tariff_index = State()
    selected_price = State()
    current_price = State()
    cryptobot_invoice_id = State()
    cryptobot_price = State()
    cryptobot_tariff_idx = State()
    awaiting_screenshot = State()
    verifying = State()
    admin_panel = State()
    awaiting_payment_id = State()


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_tariffs_keyboard():
    buttons = []
    for i, (name, price, _) in enumerate(TARIFFS):
        buttons.append([InlineKeyboardButton(text=f"{name} ({price:.0f}₽)", callback_data=f"tariff_{i}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tariffs_keyboard_with_balance():
    buttons = []
    for i, (name, price, _) in enumerate(TARIFFS):
        buttons.append([InlineKeyboardButton(text=f"{name} ({price:.0f}₽)", callback_data=f"balance_tariff_{i}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_crypto_amount(rub_price: float, crypto: str) -> str:
    if crypto not in CRYPTO_RATES:
        return "0"
    amount = Decimal(str(rub_price)) / CRYPTO_RATES[crypto]
    if crypto in ["BTC", "ETH"]:
        return f"{amount:.8f}"
    elif crypto in ["SOL", "TON"]:
        return f"{amount:.4f}"
    else:
        return f"{amount:.2f}"


def get_stars_amount(rub_price: float) -> int:
    return int(rub_price * STARS_RATE)


# ========== 15 ТАРИФОВ (ПОЛНЫЕ ОПИСАНИЯ) ==========
TARIFFS = [
    ("💘 Всё подряд | ALL IN 🎀", 1132.80, """<b>Тариф: 💘 Всё подряд | ALL IN 🎀</b>
💵 Стоимость: 1132.80 ₽

<b>Описание тарифа:</b>
Один платёж — и ты получаешь абсолютно всё, что мы продаём. Кроме «💎 Абсолют | PREMIUM PACK» и «Мастурбаторский рай». Никаких доплат. Только полный доступ ко всем закрытым категориям 👑

➕ <b>Дополнительно:</b>
· Все onion-ссылки из всех тарифов — 50+ рабочих адресов
· Все облачные папки (MEGA, Яндекс.Диск, Mail.ru) с пожизненной подпиской
· Обновления 3 раза в сутки — новый контент падает автоматически
· Приоритетная поддержка — отвечаем за 2 минуты

♾️ Заплатил раз — пользуешься вечно. Никаких подписок, лимитов, удалений, блокировок.

⚡ Экономия: если покупать все тарифы по отдельности — выйдет больше 5000 ₽. Тариф «ВСЁ ПОДРЯД» — одна цена за всё.

🤖 Бот выдаст полный доступ ко всем категориям моментально после оплаты.

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("👪 Родная кровь | FAMILY INCEST 🧑‍🍼", 471.00, """<b>Тариф: 👪 Родная кровь | FAMILY INCEST 🧑‍🍼</b>
💵 Стоимость: 471.00 ₽

<b>Описание тарифа:</b>
👪 Один платёж — безлимит на самое запретное в семье. Только реальные инцест-пары. Отец/дочь, мать/сын, брат/сестра. 💀

📦 500+ паков: домашние сливы, скрытая камера в спальнях, семейные архивы.
🎥 50+ часов видео: ночные записи, подслушанные разговоры, постановки под видом реальных семей.
🧅 10 onion-форумов по инцесту в подарок.
💾 MEGA + Яндекс.Диск с автопополнением каждые 2 дня.

♾️ Заплатил раз — навсегда.
⚡️ Обновления 2 раза в неделю.
🤖 Доступ выдаётся сразу же после оплаты.

Семья — это самое близкое. Получи их всех. 👪🩸🍿

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("🏘️ Запись с камер | HOME PACK 📹", 483.00, """<b>Тариф: 🏘️ Запись с камер | HOME PACK 📹</b>
💵 Стоимость: 483.00 ₽

<b>Описание тарифа:</b>
🏠 Один платёж — безлимит на чужую жизнь. Скрытая камера в квартирах соседей. Спальни, ванные, детские комнаты. 💀

📦 600+ паков: реальные люди дома. Раздевание, секс, сон, душ. Никто не знает, что их снимают.
🎥 70+ часов видео: скрытые камеры в розетках, шкафах, зеркалах, ванных комнатах.
🧅 8 onion-форумов с домашней скрытой камерой в подарок.
💾 MEGA + Яндекс.Диск с автопополнением каждые 12 часов.

♾️ Заплатил раз — навсегда.
⚡️ Обновления каждый день.
🤖 Доступ выдаётся сразу же после оплаты.

Они живут своей жизнью. Ты смотришь. 📹

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("🍼 Крохи | 0-4 ЛЕТ 👼", 423.00, """<b>Тариф: 🍼 Крохи | 0-4 ЛЕТ 👼</b>
💵 Стоимость: 423.00 ₽

<b>Описание тарифа:</b>
🧸 Самый нежный и самый запретный край. Только самые маленькие. Только реальные дети от новорождённых до 4 лет. Без постановок, без актёров, без цензуры💀

📦 800+ уникальных паков — домашние сливы: купание, пеленание, сон, игры, раздевание, скрытая камера в детских комнатах и ванных. Только реальные семьи.

🎥 60+ часов эксклюзивного видео — скрытая камера в кроватках, на пеленальных столиках, в душевых. Крик, плач, беспомощность. Никакой цензуры.

🧅 8 onion-форумов для самых маленьких — вход по приглашению внутри тарифа. То, что не публикуют даже на закрытых ресурсах.

💾 Приватные MEGA и Яндекс.Диски с ежедневным автопополнением — новые малыши падают к тебе каждые 12 часов.

⚡️ Обновления каждый день — самые свежие сливы с малышами со всего СНГ, Европы и Азии.

🤖 Доступ выдаётся сразу же после оплаты.

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("🧸 Малютики | 4-10 ЛЕТ 🙊", 411.00, """<b>Тариф: 🧸 Малютики | 4-10 ЛЕТ 🙊</b>
💵 Стоимость: 411.00 ₽

<b>Описание тарифа:</b>
🧸 Один платёж — безлимит на самых маленьких. Только реальные дети 4–10 лет. Без постановок. 💀

📦 600+ паков: ванные, спальни, раздевалки, игры, сон.
🎥 40+ часов скрытой камеры в детских комнатах и бассейнах.
🧅 8 onion-форумов для малышек в подарок.
💾 MEGA + Яндекс.Диск с ежедневным автопополнением.

♾️ Заплатил раз — навсегда.
⚡ Обновления каждый день.
🤖 Доступ выдается сразу после оплаты.

Самые маленькие — самые сладкие. Получи их всех. 🧸🍼🍿

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("🩸 Алая плёнка | 10–14 ЛЕТ 👄", 435.00, """<b>Тариф: 🩸 Алая плёнка | 10–14 ЛЕТ 👄</b>
💵 Стоимость: 435.00 ₽

<b>Описание тарифа:</b>
🩸 Один платёж — безлимит на первые разы. Только реальные девочки 10–14 лет. Кровь, крики, уговоры. Без монтажа. 💀

📦 400+ паков: первый секс с мальчиками, с девочками, с родственниками.
🎥 45+ часов видео: скрытая камера + телефон, два ракурса.
🧅 8 onion-форумов со свежими «первыми разами» в подарок.
💾 MEGA + Яндекс.Диск с автопополнением каждые 12 часов.

♾️ Заплатил раз — навсегда.
⚡ Обновления каждый день.
🤖 Доступ выдаётся сразу же после оплаты.

Первый раз бывает только раз. Ты посмотришь сотни. 🩸🍿

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("🌸 Молодые бутоны | 12–16 ЛЕТ 🍫", 408.00, """<b>Тариф: 🌸 Молодые бутоны | 12–16 ЛЕТ 🍫</b>
💵 Стоимость: 408.00 ₽

<b>Описание тарифа:</b>
🌸 Один платёж — безлимит на самых свежих. Девочки и мальчики 12–16 лет. Школы, раздевалки, первые разы. 💀

📦 700+ паков: школьные туалеты, душевые, спортзалы, домашние сливы.
🎥 50+ часов скрытой камеры в школах и раздевалках.
🧅 10 onion-форумов с молодыми сливами в подарок.
💾 MEGA + Яндекс.Диск с ежедневным автопополнением.

♾️ Заплатил раз — навсегда.
⚡ Обновления 2 раза в день.
🤖 Доступ выдаётся сразу же после оплаты.

Молодость — самая сочная. Получи их всех. 🌸🍿

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("🍾 Вписка | 13-18 ЛЕТ 🥂", 380.00, """<b>Тариф: 🍾 Вписка | 13-18 ЛЕТ 🥂</b>
💵 Стоимость: 380.00 ₽

<b>Описание тарифа:</b>
🍾 Самый свежий и дерзкий возраст. Только реальные подростки 13–18 лет. Первые вечеринки, алкоголь, откровенные игры, скрытая камера на тусовках и домашних вечеринках. Без цензуры, без постановок 💀

📦 500+ уникальных паков — школьные вечеринки, ночные гулянки, пьяные поцелуи, раздевание под бутылочку, скрытая камера в гостях и на выездах.

🎥 50+ часов эксклюзивного видео — скрытая камера в спальнях, душевых после вечеринок, раздевалки на выпускных. Только реальные сливы с тусовок.

🧅 10 onion-ссылок на закрытые форумы с молодёжным контентом — вход по приглашению внутри тарифа.

💾 Приватные MEGA и Яндекс.Диски с ежедневным автопополнением — новые сливы падают каждые 12 часов.

⚡️ Обновления каждый день — самые свежие вечеринки со всего СНГ, Европы и Азии.

🤖 Доступ выдаётся сразу же после оплаты.

Молодость — самая дерзкая. Алкоголь раскрепощает. Смотри на чужую жизнь. 🍾🔥

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("🍬 Пробный | 100 VIDEOS 🧃", 198.00, """<b>Тариф: 🍬 Пробный | 100 VIDEOS 🧃</b>
💵 Стоимость: 198.00 ₽

<b>Описание тарифа:</b>
Один маленький платёж — и ты увидишь, что мы не продаём воздух. Проверь качество перед большой покупкой. 👀

Что внутри: 📦
• 🎒 15 лучших паков со школьницами 7–16 лет — фото и видео, сливы из школ
• 👧 По 5 паков на возраст: младшие, средние, старшие
• 🎥 1 видео скрытой камеры — из раздевалки или душевой

🤖 Бот выдаст доступ сразу же после оплаты.

Сначала попробуй. Потом реши. 👆

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("💙 Голос отрочества | BOYS 🍆", 466.20, """<b>Тариф: 💙 Голос отрочества | BOYS 🍆</b>
💵 Стоимость: 466.20 ₽

<b>Описание тарифа:</b>
🧢 Голос Отрочества | Boys — только мальчики. Только реальные. 6–15 лет. Никаких девочек, никакой воды. Самая закрытая коллекция в нашем сервере. 💀

📦 800+ уникальных паков — раздевалки спортшкол, душевые бассейнов, школьные туалеты, домашние сливы, лагеря, врачебные кабинеты.

🎥 70+ часов эксклюзивного видео — скрытая камера в раздевалках, душевых, туалетах, спальнях. Только проверенные источники из 10 стран.

👦 Сортировка по возрастам: 6–8 лет / 9–11 лет / 12–15 лет. Отдельная папка — «первые разы» (мальчик с мальчиком, мальчик с девочкой).

🧅 8 onion-ссылок на закрытые форумы — специализируются только на мальчиках. Вход по приглашению внутри тарифа.

💾 Приватные MEGA + Яндекс.Диск с ежедневным автопополнением — новые мальчики падают каждые 12 часов.

♾️ Заплатил раз — навсегда. Никаких доплат и удалений.

⚡ Обновления каждый день — самые свежие сливы со всего СНГ, Европы и Азии.

🤖 Доступ выдаётся сразу же после оплаты.

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("💋 Сладкие губки | ONLY GIRL 🌹", 414.00, """<b>Тариф: 💋 Сладкие губки | ONLY GIRL 🌹</b>
💵 Стоимость: 414.00 ₽

<b>Описание тарифа:</b>
👩‍❤️‍👩 Один платёж — девушки с девушками. Без мужчин. Чистая женская страсть.

📦 750+ паков: школьницы 13–17, студентки 18–22. Домашние сливы, скрытая камера
🏳️‍🌈 Сортировка: «в душе», «в кровати», «пьяные на вписке», «училка/ученица», «мать/дочь», «первые раз»
🎥 55+ часов видео: раздевалки, душевые, спальни. Только реальные лесби-пары
🧅 8 onion-ссылок на закрытые лесби-форумы
💾 Облачные папки с пополнением каждые 12 часов

♾️ Платёж раз — навсегда
⚡ Обновления 2 раза в день (весь мир)
🤖 Доступ за 10 секунд

Две девушки лучше, чем одна. 👭🔞🍿

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("🐕‍🦺 Хлев | ZOOPHILIA 🐈", 408.00, """<b>Тариф: 🐕‍🦺 Хлев | ZOOPHILIA 🐈</b>
💵 Стоимость: 408.00 ₽

<b>Описание тарифа:</b>
🐕 Один платёж — самый животный, самый запретный контент. Сцены с животными. Без цензуры.

📦 500+ паков: собаки, лошади, свиньи, коровы, петухи. Женщины, мужчины, малолетние
🐎 Сортировка по животным: собаки, лошади, копытные, птицы, экзотика
👧 Отдельная категория — дети с животными (12–17 лет). Самое редкое
🎥 60+ часов видео: фермы, подвалы, частные дома. 15 стран
🧅 10 onion-ссылок на закрытые зоо-форумы
💾 MEGA-облака с пополнением каждые 6 часов

♾️ Платёж раз — навсегда
⚡ Обновления каждый день
🤖 Доступ за 10 секунд

Животные не скажут. Ты получишь всё. 🐕💦🔞🍿

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("⛓️ Мясо | AGGRESIVE 🥀", 521.40, """<b>Тариф: ⛓️ Мясо | AGGRESIVE 🥀</b>
💵 Стоимость: 521.40 ₽

<b>Описание тарифа:</b>
⛓️ Один платёж — безлимит на самое жестокое. Только реальное насилие. Изнасилования, пытки, удушение, групповые. 💀

📦 400+ паков: уличные нападения, домашнее насилие, похищения, постмортем.
🎥 55+ часов видео: скрытые камеры, трофейные записи насильников.
🧅 10 onion-ссылок на закрытые хардкор-форумы в подарок.
💾 MEGA + Яндекс.Диск с автопополнением каждые 6 часов.

♾️ Заплатил раз — навсегда.
⚡ Обновления каждый день.
🤖 Доступ выдаётся сразу же после оплаты.

Не для слабонервных. Только для настоящих ценителей боли. ⛓️☠️🍿

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("💎 Абсолют | PREMIUM PACK 🔐", 3333.00, """<b>Тариф: 💎 Абсолют | PREMIUM PACK 🔐</b>
💵 Стоимость: 3333.00 ₽

<b>Описание тарифа:</b>
👑 Абсолют | Premium Pack — это максимальная степень погружения в запретное. Ты покупаешь не просто набор файлов. Ты покупаешь пожизненный билет в закрытый мир, куда обычные люди не заходят даже под угрозой смерти. 💀

📦 Гигантский архив — более 15 000 уникальных файлов.
🎥 Более 800 часов эксклюзивного видео.
🧅 Доступ к 30+ закрытым onion-ресурсам.
💾 Личные облачные хранилища с ежедневной синхронизацией.
🔒 Абсолютная анонимность.
⚡ Обновления 3 раза в сутки.
♾️ Один платёж — доступ навсегда.
🤖 Мгновенная выдача доступа.

💎 Полный архив всех тарифов, ранний доступ к сливам, приоритетная поддержка 24/7, персональный бот-помощник.

🍿 Добро пожаловать в Абсолют 🔞

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки»."""),

    ("⚡ LUXE PRESTIGE 🖤", 9000.00, """<b>Тариф: ⚡ LUXE PRESTIGE 🖤</b>
💵 Стоимость: 9000.00 ₽

<b>Описание тарифа:</b>
💎 LUXE PRESTIGE — это не тариф. Это статус. Вход в закрытый клуб для тех, кто привык получать лучшее.

📦 5 000+ уникальных паков (эксклюзив, удаляются через 24 часа)
🎥 200+ часов 4K видео
🧅 Доступ к 20 закрытым onion-ресурсам
💾 VIP-облака MEGA Pro / Яндекс.Диск Premium
⚡️ Персональный источник под заказ
🔒 Абсолютная приватизация
🤵 Личный менеджер 24/7
♾️ Платёж раз — доступ навсегда + страховка

💎 LUXE PRESTIGE — для тех, кто не считает деньги.

💡 Гарантия: возврат средств в течение 24 часов. По вопросам возврата — в раздел «Мои покупки».""")
]

# ========== REPLY-КЛАВИАТУРА ==========
reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Тарифы 🦋"), KeyboardButton(text="Мои покупки 📦")],
        [KeyboardButton(text="📲 Поддержка 👩🏻‍💻"), KeyboardButton(text="🦄 Превью (FREE) 🙇‍♀️")],
        [KeyboardButton(text="Реф. работа 💸"), KeyboardButton(text="CryptoBot инструкция оплаты✔️")]
    ],
    resize_keyboard=True
)


# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    print(f"✅ Получена команда /start от {message.from_user.id}")
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].split("_")[1])
        except:
            pass

    if referrer_id == message.from_user.id:
        await message.answer("❌ Вы не можете стать рефералом для себя самого!")
        referrer_id = None

    await state.update_data(referrer_id=referrer_id)

    user_id = message.from_user.id
    
    if has_join_request(user_id):
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user_exists = cursor.fetchone() is not None
        if not user_exists:
            register_user(user_id, referrer_id)
        await show_main_menu(message, state)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 ВСТУПИТЬ В КАНАЛ 📢", url=GROUP_URL)],
            [InlineKeyboardButton(text="✅ Я вступил(а)", callback_data="check_join_request")]
        ])
        await message.answer(
            "📢 Для доступа к боту необходимо вступить в наш канал.\n\n"
            "После вступления нажмите кнопку «✅ Я вступил(а)».",
            reply_markup=keyboard
        )


@dp.callback_query(F.data == "check_join_request")
async def check_join_request(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if has_join_request(user_id):
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user_exists = cursor.fetchone() is not None
        if not user_exists:
            data = await state.get_data()
            referrer_id = data.get("referrer_id")
            register_user(user_id, referrer_id)
        await callback.message.delete()
        await show_main_menu(callback.message, state)
    else:
        await callback.answer("❌ Вы ещё не вступили в канал. Пожалуйста, вступите и нажмите кнопку снова.", show_alert=True)


@dp.chat_join_request()
async def handle_join_request(request: ChatJoinRequest):
    user_id = request.from_user.id
    add_join_request(user_id)
    print(f"📝 Заявка от {user_id} зафиксирована")


async def show_main_menu(message: types.Message, state: FSMContext):
    welcome_text = (
        "<b><u>Добро пожаловать в Райский уголок</u></b>\n\n"
        "📶 Максимальная конфиденциальность\n"
        "-- анонимная оплата без лишних данных и привязок.\n"
        "📘 Никаких логов и истории -- ваши переписки остаются только с вами.\n\n"
        "🎯 <b>Не потеряй вход (а то не найдёшь):</b> https://vrxshop.github.io/vrx/"
    )

    try:
        photo = FSInputFile("start.jpg")
        await message.answer_photo(photo=photo, caption=welcome_text, parse_mode="HTML", reply_markup=reply_keyboard)
    except:
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=reply_keyboard)

    await message.answer(
        "🌟 Коснись любого тарифа — и запретное откроется:",
        reply_markup=get_tariffs_keyboard()
    )
    await state.clear()


@dp.callback_query(F.data.startswith("tariff_"))
async def process_tariff(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    idx = int(callback.data.split("_")[1])
    name, price, description = TARIFFS[idx]
    await state.update_data(selected_tariff_index=idx, selected_price=price, tariff_name=name)
    
    stars = get_rub_to_stars(price)
    discount_stars = get_rub_to_stars(price * 0.8)
    
    tariff_text = f"{description}\n\n"
    tariff_text += f"⭐️ Цена: {stars} ⭐ ({price:.0f} ₽)\n\n"
    tariff_text += "👇 Как хотите оплатить?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐️ Оплатить", callback_data="pay_stars_full")],
        [InlineKeyboardButton(text="🎁 Оплатить со скидкой", callback_data="pay_stars_discount")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tariffs")]
    ])

    await callback.message.edit_text(tariff_text, parse_mode="HTML", reply_markup=keyboard)


@dp.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "🌟 Коснись любого тарифа — и запретное откроется:",
        reply_markup=get_tariffs_keyboard()
    )
    await state.clear()


# ========== ОПЛАТА (ПОЛНАЯ ЦЕНА) ==========
@dp.callback_query(F.data == "pay_stars_full")
async def pay_stars_full(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    price = data.get("selected_price", 0)
    tariff_name = data.get("tariff_name", "тариф")
    stars = get_rub_to_stars(price)

    text = (
        f"⭐️ Оплата Telegram Stars\n\n"
        f"📦 Тариф: {tariff_name}\n"
        f"💰 К оплате: {price:.0f} ₽\n"
        f"⭐️ Звёзд: {stars}\n"
        f"⏳ Счёт активен: 30 мин\n\n"
        f"👇 Нажмите кнопку ниже — откроется окно подтверждения Telegram"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐️ Оплатить {stars} ⭐", callback_data="stars_pay_invoice")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await state.update_data(stars_price=price, stars_tariff_name=tariff_name, stars_tariff_idx=data.get("selected_tariff_index", 0))


@dp.callback_query(F.data == "stars_pay_invoice")
async def stars_invoice(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get("stars_price", 0)
    tariff_name = data.get("stars_tariff_name", "тариф")
    stars = get_rub_to_stars(price)

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Оплата тарифа",
        description=f"Тариф: {tariff_name}\nСумма: {price:.0f} ₽",
        payload=f"stars_payment_{int(price * 100)}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Telegram Stars", amount=stars)],
        start_parameter="stars_payment"
    )
    await callback.answer("Счёт создан! После оплаты нажмите «Проверить оплату»")


@dp.callback_query(F.data == "check_stars_payment")
async def check_stars_payment(callback: types.CallbackQuery):
    await callback.answer("⏳ Платёж ещё не поступил. Откройте кнопку оплаты и подтвердите в Telegram.", show_alert=True)


@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    price = data.get("stars_price", 0)
    idx = data.get("stars_tariff_idx", 0)
    tariff_name = TARIFFS[idx][0] if idx < len(TARIFFS) else "тариф"

    add_purchase(message.from_user.id, tariff_name, price, "stars")

    await message.answer(
        f"✅ Оплата подтверждена!\n\n"
        f"📦 Тариф: {tariff_name}\n"
        f"💰 Сумма: {price:.0f} ₽\n\n"
        f"🕐 Доступ будет выдан в течение 30 минут — готовлю для вас отдельный канал.\n\n"
        f"👨‍💼 С вами свяжется администратор.\n\n"
        f"Спасибо за доверие!\n\n"
        f"💡 У вас есть 24 часа, чтобы попробовать тариф. Если не подойдёт — вернём деньги. Запросить возврат можно в разделе «Мои покупки»."
    )

    await bot.send_message(
        MODERATOR_CHAT_ID,
        f"🔔 НОВАЯ ОПЛАТА (Telegram Stars)\n"
        f"👤 Пользователь: @{message.from_user.username or message.from_user.first_name} (ID: {message.from_user.id})\n"
        f"📦 Тариф: {tariff_name}\n"
        f"💰 Сумма: {price:.0f} ₽\n"
        f"Нужно выдать доступ в канал."
    )


# ========== ОПЛАТА СО СКИДКОЙ ==========
@dp.callback_query(F.data == "pay_stars_discount")
async def pay_stars_discount(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    price = data.get("selected_price", 0)
    tariff_name = data.get("tariff_name", "тариф")
    
    discount_price = price * 0.8
    stars_discount = get_rub_to_stars(discount_price)
    savings = price - discount_price
    
    text = (
        f"⭐️ ОПЛАТА СО СКИДКОЙ 20%\n\n"
        f"📦 Тариф: {tariff_name}\n"
        f"💰 Обычная цена: {price:.0f} ₽\n"
        f"🎁 Цена со скидкой: {discount_price:.0f} ₽\n"
        f"💸 Твоя экономия: {savings:.0f} ₽\n\n"
        f"⭐️ Нужно звёзд: {stars_discount}\n\n"
        f"📋 ИНСТРУКЦИЯ:\n\n"
        f"1️⃣ Запусти @StarsovBot\n"
        f"2️⃣ Нажми «Купить звёзды»\n"
        f"3️⃣ Укажи мой юзернейм: @Nastia_sup\n"
        f"4️⃣ Оплати {stars_discount} звёзд через СБП или карту\n"
        f"5️⃣ Скопируй ID платежа из StarsovBot\n"
        f"6️⃣ Нажми кнопку «✅ Проверить оплату»\n\n"
        f"✅ После проверки я выдам доступ к тарифу\n\n"
        f"⏰ Время проверки заявок: 10:00 – 23:00 по МСК"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_discount_payment")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await state.update_data(discount_price=discount_price, discount_stars=stars_discount, tariff_name_discount=tariff_name)


@dp.callback_query(F.data == "check_discount_payment")
async def check_discount_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    
    current_time = time.time()
    last_time = last_payment_request.get(user_id, 0)
    
    if current_time - last_time < 300:
        remaining = int(300 - (current_time - last_time))
        minutes = remaining // 60
        seconds = remaining % 60
        await callback.message.answer(
            f"❌ Вы уже отправляли заявку на проверку.\n\n"
            f"Пожалуйста, подождите {minutes} мин {seconds} сек перед повторной отправкой."
        )
        return
    
    await callback.message.answer(
        "🔍 Отправьте ID платежа из StarsovBot\n\n"
        "Пример: PAY-1234567890"
    )
    await state.set_state(PaymentState.awaiting_payment_id)


@dp.message(PaymentState.awaiting_payment_id)
async def process_payment_id(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    payment_id = message.text.strip()
    
    if len(payment_id) < 5:
        await message.answer("❌ ID платежа слишком короткий. Пожалуйста, отправьте правильный ID.")
        return
    
    last_payment_request[user_id] = time.time()
    
    data = await state.get_data()
    tariff_name = data.get("tariff_name_discount", "тариф")
    discount_price = data.get("discount_price", 0)
    
    username = message.from_user.username or message.from_user.first_name
    user_link = f"tg://user?id={user_id}"
    
    admin_text = (
        f"🔔 НОВАЯ ЗАЯВКА НА ОПЛАТУ СО СКИДКОЙ\n\n"
        f"👤 Пользователь: @{username} (ID: {user_id})\n"
        f"📦 Тариф: {tariff_name}\n"
        f"💰 Сумма: {discount_price:.0f} ₽\n"
        f"🔢 ID платежа: {payment_id}\n\n"
        f"📌 Проверьте ID в StarsovBot и выдайте доступ вручную."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать пользователю", url=user_link)]
    ])
    
    await bot.send_message(MODERATOR_CHAT_ID, admin_text, reply_markup=keyboard)
    
    await message.answer(
        "✅ Заявка отправлена модератору!\n\n"
        f"📦 Тариф: {tariff_name}\n"
        f"💰 Сумма: {discount_price:.0f} ₽\n\n"
        f"🕐 Модератор проверит оплату и выдаст доступ в ближайшее время.\n\n"
        f"⏰ График работы: 10:00 – 23:00 по МСК"
    )
    
    await state.clear()


# ========== CRYPTOBOT ==========
@dp.callback_query(F.data == "pay_cryptobot")
async def pay_cryptobot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("🔄 Создаём счёт...")
    data = await state.get_data()
    price_rub = data.get("current_price", 0)
    idx = data.get("selected_tariff_index", 0)
    tariff_name = TARIFFS[idx][0] if idx < len(TARIFFS) else "тариф"

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "amount": str(price_rub),
        "currency_type": "fiat",
        "fiat": "RUB",
        "accepted_assets": "USDT,BTC,ETH,TON,BNB,TRX,USDC,LTC,DOGE",
        "description": f"Райский уголок — {tariff_name}",
        "expires_in": 3600,
        "allow_comments": True,
        "allow_anonymous": True
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()

        if result.get("ok"):
            invoice = result["result"]
            invoice_id = invoice["invoice_id"]
            bot_invoice_url = invoice["bot_invoice_url"]

            await state.update_data(cryptobot_invoice_id=invoice_id)
            await state.update_data(cryptobot_price=price_rub)
            await state.update_data(cryptobot_tariff_idx=idx)

            text = (
                f"✅ Счёт на оплату через CryptoBot успешно создан.\n\n"
                f"🧾 Нажмите кнопку «Перейти к оплате», далее выберите монету и нажмите «Оплатить»\n\n"
                f"🎯 К оплате: {price_rub:.2f} ₽"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Перейти к оплате 💸", url=bot_invoice_url)],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_cryptobot_payment")],
                [InlineKeyboardButton(text="👈 Назад к способам оплаты", callback_data="back_to_payment_methods")]
            ])
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            error = result.get('error', 'Неизвестная ошибка')
            await callback.message.answer(f"❌ Ошибка создания счёта: {error}")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")


@dp.callback_query(F.data == "check_cryptobot_payment")
async def check_cryptobot_payment(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    invoice_id = data.get("cryptobot_invoice_id")
    price = data.get("cryptobot_price", 0)
    idx = data.get("cryptobot_tariff_idx", 0)

    if not invoice_id:
        await callback.answer("❌ Счёт не найден. Создайте новый.", show_alert=True)
        return

    tariff_name = TARIFFS[idx][0] if idx < len(TARIFFS) else "тариф"

    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    params = {"invoice_ids": invoice_id}

    try:
        response = requests.get(url, headers=headers, params=params)
        result = response.json()

        if result.get("ok") and result.get("result"):
            items = result["result"].get("items", [])
            if items and len(items) > 0:
                invoice = items[0]
                status = invoice.get("status")

                if status == "paid":
                    add_purchase(callback.from_user.id, tariff_name, price, "cryptobot")

                    await callback.message.answer(
                        f"✅ Оплата подтверждена!\n\n"
                        f"📦 Тариф: {tariff_name}\n"
                        f"💰 Сумма: {price:.2f} ₽\n\n"
                        f"🕐 Доступ будет выдан в течение 30 минут.\n\n"
                        f"👨‍💼 С вами свяжется администратор.\n\n"
                        f"Спасибо за доверие!\n\n"
                        f"💡 У вас есть 24 часа, чтобы попробовать тариф. Если не подойдёт — вернём деньги. Запросить возврат можно в разделе «Мои покупки»."
                    )
                    await bot.send_message(
                        MODERATOR_CHAT_ID,
                        f"🔔 НОВАЯ ОПЛАТА (CryptoBot)\n"
                        f"👤 Пользователь: @{callback.from_user.username or callback.from_user.first_name} (ID: {callback.from_user.id})\n"
                        f"📦 Тариф: {tariff_name}\n"
                        f"💰 Сумма: {price:.2f} ₽\n"
                        f"Нужно выдать доступ в канал."
                    )
                    await state.update_data(cryptobot_invoice_id=None)
                elif status == "expired":
                    await callback.answer("❌ Счёт истёк. Создайте новый.", show_alert=True)
                else:
                    await callback.answer("⏳ Платёж ещё не поступил. Попробуйте через минуту.", show_alert=True)
            else:
                await callback.answer("❌ Счёт не найден.", show_alert=True)
        else:
            await callback.answer("❌ Ошибка проверки. Попробуйте позже.", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ========== ПЕРЕВОД ПО АДРЕСУ ==========
@dp.callback_query(F.data == "pay_crypto_address")
async def pay_crypto_address(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    price = data.get("current_price", 0)

    usdt_amount = get_crypto_amount(price, "USDT")
    ton_amount = get_crypto_amount(price, "TON")
    btc_amount = get_crypto_amount(price, "BTC")
    eth_amount = get_crypto_amount(price, "ETH")
    sol_amount = get_crypto_amount(price, "SOL")
    trx_amount = get_crypto_amount(price, "TRX")

    text = f"""К оплате: {price:.0f} RUB
Адреса для переводов:
🪙 Tether (USDT): ~{usdt_amount} USDT
🪙 TRC20—TM2UCR8vh6a8fTLphBTHjfztzdTNF8g9j7
🪙 TON — UQCNVsPIrzyqKVJaAjnG964wW_MTMJLhQP7h2vagOTqN53M5
🪙 ERC20—0x7e3aB5eDB43c3aD3C1aA8D50e34Ce7044632d371
🪙 SPL—8KHZyMkJCswJzRbMJqtK5smmrSX7c4SXFvdpDy3uTUhh
🪙 Toncoin (TON): ~{ton_amount} TON
UQCNVsPIrzyqKVJaAjnG964wW_MTMJLhQP7h2vagOTqN53M5
🪙 Solana (SOL): ~{sol_amount} SOL
8KHZyMkJCswJzRbMJqtK5smmrSX7c4SXFvdpDy3uTUhh
🪙 Ethereum ETH (ERC20): ~{eth_amount} ETH
0x7e3aB5eDB43c3aD3C1aA8D50e34Ce7044632d371
🪙 Bitcoin (BTC): ~{btc_amount} BTC
bc1q553edzt4dxnkmmg9ny3tgs8rwh5ucv80d6gccd
🪙 Tron TRX (TRC20): ~{trx_amount} TRX
TM2UCR8vh6a8fTLphBTHjfztzdTNF8g9j7
🪙 USD Coin (USDC): ~{usdt_amount} USDC
🪙 TRC20—0x7e3aB5eDB43c3aD3C1aA8D50e34Ce7044632d371
🪙 SPL—8KHZyMkJCswJzRbMJqtK5smmrSX7c4SXFvdpDy3uTUhh
ℹ️ Переводите сумму, равную цене тарифа!"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="manual_paid_crypto_address")],
        [InlineKeyboardButton(text="👈 Назад к способам оплаты", callback_data="back_to_payment_methods")]
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@dp.callback_query(F.data == "manual_paid_crypto_address")
async def manual_paid_crypto_address(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "💰 Оплатили?\n\nОтправьте боту квитанцию об оплате: скриншот или фото.\nНа квитанции должны быть четко видны: дата, время и сумма платежа.")
    await state.set_state(PaymentState.awaiting_screenshot)


@dp.callback_query(F.data == "back_to_payment_methods")
async def back_to_payment_methods(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_payment(callback, state)


# ========== МОИ ПОКУПКИ ==========
@dp.message(F.text == "Мои покупки 📦")
async def my_purchases(message: types.Message):
    user_id = message.from_user.id
    purchases = get_user_purchases(user_id)

    if not purchases:
        text = (
            "📦 *Ваши покупки:*\n\n"
            "У вас пока нет активных подписок.\n\n"
            "💡 *Как получить доступ после оплаты:*\n"
            "• После успешной оплаты администратор свяжется с вами\n"
            "• Вы получите ссылку на приватный канал с контентом\n"
            "• Доступ сохраняется навсегда"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Приобрести доступ", callback_data="tariffs_from_purchases")]
        ])
        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
        return

    for purchase_id, tariff_name, tariff_price, purchased_at, status, payment_method, refunded in purchases:
        time_diff = datetime.now() - datetime.fromisoformat(purchased_at.replace(' ', 'T'))
        hours_passed = time_diff.total_seconds() / 3600
        can_refund = hours_passed < 24 and status == "active" and refunded == 0

        status_icon = "✅ активен" if status == "active" else "❌ истёк"
        date_str = purchased_at.split()[0] if purchased_at else "дата неизвестна"

        text = (
            f"📦 *{tariff_name}*\n"
            f"💰 {tariff_price:.0f} ₽\n"
            f"📅 {date_str}\n"
            f"📌 {status_icon}\n"
            f"💳 {payment_method}\n"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        if can_refund:
            keyboard.inline_keyboard.append(
                [InlineKeyboardButton(text="❌ Вернуть тариф", callback_data=f"refund_{purchase_id}")]
            )
        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard if keyboard.inline_keyboard else None)


@dp.callback_query(F.data == "tariffs_from_purchases")
async def tariffs_from_purchases(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🌟 Коснись любого тарифа — и запретное откроется:",
        reply_markup=get_tariffs_keyboard()
    )


# ========== ПОДДЕРЖКА, ПРЕВЬЮ, ИНСТРУКЦИЯ ==========
@dp.message(F.text == "📲 Поддержка 👩🏻‍💻")
async def support(message: types.Message):
    await message.answer(
        "❓ Есть вопросы или трудности?\n"
        "🛠 Поддержка: @Nastia_sup\n\n"
        "Пишите суть максимально кратко — и ответ не заставит себя ждать!",
        parse_mode="HTML"
    )


@dp.message(F.text == "🦄 Превью (FREE) 🙇‍♀️")
async def proofs_button(message: types.Message):
    await message.answer(
        "Хотите бесплатный канал? ✅\n\n"
        "Подпишитесь на наш резерв - https://t.me/+_8cUpjfS4581OTYy\n\n"
        "( в нём есть бесплатный канал с контентом ) ⭐️\n\n"
        "Наши отзывы - https://t.me/+_8cUpjfS4581OTYy\n\n"
        "Это резерв на нашего бота ( отправляем там новые ссылки на наших ботов ) 🔥"
    )


@dp.message(F.text == "CryptoBot инструкция оплаты✔️")
async def cryptobot_instruction(message: types.Message):
    text = (
        "<b>Мы для вас подготовили короткую инструкцию, как оплатить любой тариф криптой через CryptoBot буквально в пару кликов! 🚀</b>\n\n"
        "✦ Открываем <a href=\"https://t.me/send?start=r-fpc8p\">CryptoBot</a> → переходим в раздел <a href=\"https://t.me/send?start=r-fpc8p-market\">P2P</a> 🤖\n"
        "✦ В разделе P2P жмем <b>«Купить»</b> 🛒\n"
        "✦ Выбираем монету, которую принимает бот к оплате (лучше всего USDT TRC20)💰\n"
        "✦ Указываем удобный способ оплаты → ищем объявление с подходящим объемом 🔍\n"
        "✦ Нашли? Жмем на него и выбираем «Купить» ✅\n"
        "✦ Вписываем сумму в рублях, которую хотим купить 📝\n"
        "✦ После подтверждения от продавца получаем реквизиты для перевода 💳\n"
        "✦ Переводим деньги и прикрепляем чек 🧾\n"
        "✦ Крипта у вас на счету! 🎉\n\n"
        '<a href="https://t.me/+pyg0bJFTrVdhZjMy">📘 Более подробная инструкция по ссылке</a>\n\n'
        "Возвращаемся к нашем боту и оплачиваем тариф 🔥"
    )
    await message.answer(text, parse_mode="HTML")


# ========== РЕФЕРАЛЬНАЯ СИСТЕМА ==========
@dp.message(F.text == "Реф. работа 💸")
async def referral_menu(message: types.Message):
    user_id = message.from_user.id
    data = get_user_data(user_id)

    if data:
        balance, referral_count = data
    else:
        balance, referral_count = 0, 0

    referral_link = await get_referral_link(user_id)

    text = (
        f"<b>Ваш баланс:</b> {balance:.0f} RUB\n\n"
        f"<b>Вы пригласили:</b> {referral_count} человек\n\n"
        f"🔥 <b>Вы получаете 40% от каждой покупки вашего реферала!</b>\n\n"
        f"С каждой оплаченной покупки человека, которого вы пригласили в нашего бота, вы получите - 40 %\n\n"
        f"( Наша реферальная система работает исправно, рассылайте ссылку которая будет внизу и получайте прибыль с нашего бота )\n\n"
        f"<b>Инструкция</b> - https://telegra.ph/Kak-rabotat-u-nas-01-21\n\n"
        f"<b>Ваша реферальная ссылка:</b> {referral_link}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывод средств", callback_data="withdraw_request")],
        [InlineKeyboardButton(text="👥 Мои рефералы", callback_data="my_referrals")],
        [InlineKeyboardButton(text="💎 Оплатить тариф с баланса", callback_data="pay_with_balance_from_referral")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@dp.callback_query(F.data == "pay_with_balance_from_referral")
async def pay_with_balance_from_referral(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    balance = data[0] if data else 0

    if balance <= 0:
        await callback.message.answer(
            "❌ У вас нет средств на балансе.\n\n💡 Приглашайте друзей — получайте 40% от их покупок!")
        return

    await callback.message.answer(
        f"💎 *Выберите тариф для оплаты с баланса:*\n\n"
        f"💰 *Ваш баланс:* {balance:.0f} RUB",
        parse_mode="Markdown",
        reply_markup=get_tariffs_keyboard_with_balance()
    )
    await state.update_data(payment_method="balance_from_referral")


@dp.callback_query(F.data.startswith("balance_tariff_"))
async def process_balance_tariff(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.split("_")[2])
    tariff_name, tariff_price, description = TARIFFS[idx]
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    balance = data[0] if data else 0

    if balance >= tariff_price:
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (tariff_price, user_id))
        conn.commit()
        add_purchase(user_id, tariff_name, tariff_price, "balance")

        await callback.message.answer(
            f"✅ Тариф *{tariff_name}* успешно оплачен с баланса!\n\n"
            f"💰 Остаток на балансе: {balance - tariff_price:.0f} RUB\n\n"
            f"🕐 Доступ будет выдан в течение 30 минут.\n\n"
            f"👨‍💼 С вами свяжется администратор.",
            parse_mode="Markdown"
        )
        await bot.send_message(
            MODERATOR_CHAT_ID,
            f"🔔 ОПЛАТА С БАЛАНСА\n"
            f"👤 Пользователь: @{callback.from_user.username or callback.from_user.first_name} (ID: {user_id})\n"
            f"📦 Тариф: {tariff_name}\n"
            f"💰 Сумма: {tariff_price:.2f} ₽\n"
            f"Остаток: {balance - tariff_price:.0f} ₽"
        )
    else:
        need = tariff_price - balance
        await callback.message.answer(
            f"❌ Недостаточно средств на балансе.\n\n"
            f"📦 Тариф: {tariff_name}\n"
            f"💰 Цена: {tariff_price:.0f} ₽\n"
            f"💳 Ваш баланс: {balance:.0f} ₽\n"
            f"💸 Не хватает: {need:.0f} ₽\n\n"
            f"💡 Приглашайте друзей или долейте криптой через обычную оплату."
        )


@dp.callback_query(F.data == "withdraw_request")
async def withdraw_request(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = get_user_data(user_id)

    if data:
        balance, referral_count = data
    else:
        balance, referral_count = 0, 0

    if balance < 500:
        await callback.answer(f"❌ Минимальная сумма для вывода: 500 RUB. Ваш баланс: {balance:.0f} RUB",
                              show_alert=True)
        return

    if referral_count < 1:
        await callback.answer(f"❌ Минимальное количество рефералов для вывода: 1. Ваше количество: {referral_count}",
                              show_alert=True)
        return

    add_withdraw_request(user_id, balance)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_withdraw_{user_id}_{balance}"),
            InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject_withdraw_{user_id}")
        ],
        [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={user_id}")]
    ])

    await bot.send_message(
        MODERATOR_CHAT_ID,
        f"🔔 НОВАЯ ЗАЯВКА НА ВЫВОД\n"
        f"👤 Пользователь: @{callback.from_user.username or callback.from_user.first_name} (ID: {user_id})\n"
        f"💰 Сумма: {balance:.0f} RUB\n"
        f"👥 Рефералов: {referral_count}",
        reply_markup=keyboard
    )

    await callback.message.answer(
        f"✅ Заявка на вывод принята!\n\n"
        f"💰 Сумма: {balance:.0f} RUB\n\n"
        f"👨‍💼 Администратор свяжется с вами в ближайшее время для отправки средств.\n\n"
        f"💬 По вопросам: @Nastia_sup"
    )


@dp.callback_query(F.data == "my_referrals")
async def my_referrals(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    referral_count = data[1] if data else 0
    await callback.answer(f"👥 Ваши рефералы: {referral_count}", show_alert=True)


@dp.callback_query(F.data.startswith("approve_withdraw_"))
async def approve_withdraw(callback: types.CallbackQuery):
    if callback.from_user.id != MODERATOR_CHAT_ID:
        await callback.answer("⛔ У вас нет прав.", show_alert=True)
        return

    parts = callback.data.split("_")
    user_id = int(parts[2])
    amount = float(parts[3])

    cursor.execute('UPDATE users SET balance = 0 WHERE user_id = ?', (user_id,))
    conn.commit()

    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ ЗАЯВКА ПРИНЯТА\n💰 Сумма: {amount:.0f} RUB отправлена пользователю."
    )

    await callback.answer("✅ Заявка принята! Баланс обнулён.", show_alert=True)

    try:
        await bot.send_message(
            user_id,
            f"✅ Ваша заявка на вывод {amount:.0f} RUB принята!\n\n"
            f"💰 Средства будут отправлены в ближайшее время.\n\n"
            f"💬 По вопросам: @Nastia_sup"
        )
    except:
        pass


@dp.callback_query(F.data.startswith("reject_withdraw_"))
async def reject_withdraw(callback: types.CallbackQuery):
    if callback.from_user.id != MODERATOR_CHAT_ID:
        await callback.answer("⛔ У вас нет прав.", show_alert=True)
        return

    user_id = int(callback.data.split("_")[2])

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ ЗАЯВКА ОТКЛОНЕНА"
    )

    await callback.answer("❌ Заявка отклонена!", show_alert=True)

    try:
        await bot.send_message(
            user_id,
            f"❌ Ваша заявка на вывод отклонена.\n\n"
            f"Пожалуйста, проверьте условия вывода и попробуйте снова.\n\n"
            f"💬 По вопросам: @Nastia_sup"
        )
    except:
        pass


# ========== АДМИН-ПАНЕЛЬ ==========
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != MODERATOR_CHAT_ID:
        await message.answer("⛔ У вас нет прав.")
        return

    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]

    pending_withdraws = get_pending_withdraw_requests()
    pending_payments = get_pending_payment_requests()

    text = (
        f"📋 *АДМИН-ПАНЕЛЬ*\n\n"
        f"👥 Всего пользователей: {users_count}\n\n"
        f"🆕 *Новые заявки:*\n"
        f"💰 Вывод средств: {len(pending_withdraws)}\n"
        f"📸 Проверка оплат: {len(pending_payments)}\n\n"
        f"📌 Выберите раздел:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Вывод средств", callback_data="admin_withdraws")],
        [InlineKeyboardButton(text="📸 Проверка оплат", callback_data="admin_payments")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")]
    ])

    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@dp.callback_query(F.data == "admin_withdraws")
async def admin_withdraws(callback: types.CallbackQuery):
    if callback.from_user.id != MODERATOR_CHAT_ID:
        await callback.answer("⛔ У вас нет прав.", show_alert=True)
        return

    withdraws = get_pending_withdraw_requests()

    if not withdraws:
        await callback.message.edit_text("📭 Нет активных заявок на вывод.")
        return

    for req_id, user_id, amount, created_at in withdraws:
        try:
            chat = await bot.get_chat(user_id)
            username = chat.username or chat.first_name
        except:
            username = str(user_id)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_withdraw_{user_id}_{amount}"),
                InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject_withdraw_{user_id}")
            ],
            [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={user_id}")]
        ])

        await callback.message.answer(
            f"💰 ЗАЯВКА #{req_id}\n"
            f"👤 Пользователь: @{username} (ID: {user_id})\n"
            f"📅 Дата: {created_at}\n"
            f"💰 Сумма: {amount:.0f} RUB",
            reply_markup=keyboard
        )

    await callback.message.delete()


@dp.callback_query(F.data == "admin_payments")
async def admin_payments(callback: types.CallbackQuery):
    if callback.from_user.id != MODERATOR_CHAT_ID:
        await callback.answer("⛔ У вас нет прав.", show_alert=True)
        return

    payments = get_pending_payment_requests()

    if not payments:
        await callback.message.edit_text("📭 Нет заявок на проверку оплат.")
        return

    for req_id, user_id, tariff_name, amount, created_at in payments:
        try:
            chat = await bot.get_chat(user_id)
            username = chat.username or chat.first_name
        except:
            username = str(user_id)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить",
                                     callback_data=f"approve_payment_{user_id}_{amount}_{tariff_name}"),
                InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject_payment_{user_id}")
            ],
            [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={user_id}")]
        ])

        await callback.message.answer(
            f"📸 ЗАЯВКА #{req_id}\n"
            f"👤 Пользователь: @{username} (ID: {user_id})\n"
            f"📦 Тариф: {tariff_name}\n"
            f"💰 Сумма: {amount:.0f} RUB\n"
            f"📅 Дата: {created_at}",
            reply_markup=keyboard
        )

    await callback.message.delete()


@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    if callback.from_user.id != MODERATOR_CHAT_ID:
        await callback.answer("⛔ У вас нет прав.", show_alert=True)
        return

    cursor.execute('SELECT COUNT(*) FROM users')
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM purchases')
    purchases_total = cursor.fetchone()[0]

    cursor.execute('SELECT SUM(tariff_price) FROM purchases')
    total_revenue = cursor.fetchone()[0] or 0

    text = (
        f"👥 *СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ*\n\n"
        f"📊 Всего пользователей: {total}\n"
        f"🛍 Всего покупок: {purchases_total}\n"
        f"💰 Общий доход: {total_revenue:.0f} RUB"
    )

    await callback.message.edit_text(text, parse_mode="Markdown")


# ========== РАССЫЛКА ==========
@dp.message(Command("broadcast"))
async def broadcast_message(message: types.Message):
    if message.from_user.id != MODERATOR_CHAT_ID:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    text = message.text.replace("/broadcast", "").strip()

    if not text:
        await message.answer("❌ Напишите текст рассылки после команды.\nПример: /broadcast Всем скидка 40%")
        return

    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()

    if not users:
        await message.answer("❌ Нет пользователей для рассылки.")
        return

    success = 0
    fail = 0

    status_msg = await message.answer(f"📢 Начинаю рассылку для {len(users)} пользователей...")

    for user in users:
        user_id = user[0]
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1

    await status_msg.edit_text(f"✅ Рассылка завершена!\n📨 Доставлено: {success}\n❌ Не доставлено: {fail}")


# ========== ЗАПУСК ==========
async def main():
    print("🚀 Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Вебхук удалён")
    
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_join_request"])
    print("🏁 Бот запущен и слушает сообщения!")


if __name__ == "__main__":
    asyncio.run(main())
