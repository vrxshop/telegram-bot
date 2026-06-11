import asyncio
import logging
import requests
import sqlite3
import os
from decimal import Decimal
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, \
    LabeledPrice, PreCheckoutQuery, ChatJoinRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Добавь ЭТО в самое начало файла (после всех импортов)
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

# ====== ПРОКСИ (ВЫКЛЮЧЕН, РАСКОММЕНТИРУЙ ЕСЛИ НУЖЕН) ======
# import socks
# import socket
# socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 10808)
# socket.socket = socks.socksocket
# =======================================================

# ========== НАСТРОЙКИ ==========
TOKEN = os.environ.get("BOT_TOKEN")
MODERATOR_CHAT_ID = 8315293936
CRYPTOBOT_TOKEN = "582195:AAOKdczYX9Dq8QNvpJ1hY23ft33N6nvBqGk"
GROUP_URL = "https://t.me/+RN8kV8FAVAg3ZGU6"
GROUP_ID = -1003837687191

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

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


def has_join_request(user_id: int) -> bool:
    cursor.execute('SELECT user_id FROM join_requests WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None


def add_join_request(user_id: int):
    cursor.execute('INSERT OR IGNORE INTO join_requests (user_id, approved) VALUES (?, 0)', (user_id,))
    conn.commit()


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


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_tariffs_keyboard():
    buttons = []
    for i, (name, price, _) in enumerate(TARIFFS):
        style = "primary"
        if i == 0:
            style = "danger"
        elif "ᴨᴩобный" in name:
            style = "success"
        elif i == len(TARIFFS) - 2 or i == len(TARIFFS) - 1:
            style = "danger"
        buttons.append([InlineKeyboardButton(text=f"{name} ({price:.0f}₽)", callback_data=f"tariff_{i}", style=style)])
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


# ========== 15 ТАРИФОВ (сокращённо, вставь свои полные описания) ==========
TARIFFS = [
    ("💘 Всё подряд | ALL IN 🎀", 1132.80, "Описание тарифа..."),
    ("👪 Родная кровь | FAMILY INCEST 🧑‍🍼", 471.00, "Описание тарифа..."),
    ("🏘️ Запись с камер | HOME PACK 📹", 483.00, "Описание тарифа..."),
    ("🍼 Крохи | 0-4 ЛЕТ 👼", 423.00, "Описание тарифа..."),
    ("🧸 Малютики | 4-10 ЛЕТ 🙊", 411.00, "Описание тарифа..."),
    ("🩸 Алая плёнка | 10–14 ЛЕТ 👄", 435.00, "Описание тарифа..."),
    ("🌸 Молодые бутоны | 12–16 ЛЕТ 🍫", 408.00, "Описание тарифа..."),
    ("🍾 Вписка | 13-18 ЛЕТ 🥂", 380.00, "Описание тарифа..."),
    ("🍬 Пробный | 100 VIDEOS 🧃", 198.00, "Описание тарифа..."),
    ("💙 Голос отрочества | BOYS 🍆", 466.20, "Описание тарифа..."),
    ("💋 Сладкие губки | ONLY GIRL 🌹", 414.00, "Описание тарифа..."),
    ("🐕‍🦺 Хлев | ZOOPHILIA 🐈", 408.00, "Описание тарифа..."),
    ("⛓️ Мясо | AGGRESIVE 🥀", 521.40, "Описание тарифа..."),
    ("💎 Абсолют | PREMIUM PACK 🔐", 3333.00, "Описание тарифа..."),
    ("⚡ LUXE PRESTIGE 🖤", 9000.00, "Описание тарифа...")
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
            [InlineKeyboardButton(text="📢 ПОДАТЬ ЗАЯВКУ", url=GROUP_URL)],
            [InlineKeyboardButton(text="✅ Я подал(а) заявку", callback_data="check_join_request")]
        ])
        await message.answer(
            "📢 Для доступа к боту необходимо подать заявку на вступление в нашу группу.\n\n"
            "После подачи заявки нажмите кнопку «Я подал(а) заявку».",
            reply_markup=keyboard
        )


@dp.callback_query(F.data == "check_join_request")
async def check_join_request(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if has_join_request(user_id):
        await callback.message.delete()
        await show_main_menu(callback.message, state)
    else:
        await callback.answer("❌ Вы ещё не подали заявку. Пожалуйста, подайте заявку в группу.", show_alert=True)


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
    await state.update_data(selected_tariff_index=idx, selected_price=price)

    tariff_text = f"{description}\n\n💰 Цена: {price:.2f} ₽"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data="pay_start", style="success")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tariffs", style="danger")]
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


# ========== ОПЛАТА ==========
@dp.callback_query(F.data == "pay_start")
async def start_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    price = data.get("selected_price", 0)

    user_id = callback.from_user.id
    user_data = get_user_data(user_id)
    balance = user_data[0] if user_data else 0

    payment_text = (
        f"💳 Оплата проходит в автоматическом режиме. Данные карты и чеки не хранятся. "
        f"Платите один раз — пользуетесь бессрочно, без продлений\n\n"
        f'<a href="https://t.me/+pyg0bJFTrVdhZjMy">📘 Инструкция оплаты через CryptoBot</a>\n\n'
        f"✅ Выберите подходящий способ и действуйте по инструкции."
    )

    keyboard_buttons = []

    if balance > 0:
        keyboard_buttons.append([InlineKeyboardButton(text=f"💰 Оплатить с баланса ({balance:.0f} RUB)",
                                                      callback_data="pay_with_balance_check", style="success")])

    keyboard_buttons.extend([
        [InlineKeyboardButton(text="⭐️ Telegram Stars ✨", callback_data="pay_stars", style="success")],
        [InlineKeyboardButton(text="💎 CryptoBot [крипта] 💰", callback_data="pay_cryptobot", style="primary")],
        [InlineKeyboardButton(text="💶 Перевод по адресу [крипта] 📲", callback_data="pay_crypto_address",
                              style="primary")],
        [InlineKeyboardButton(text="СБП 💳", callback_data="pay_sbp", style="primary")],
        [InlineKeyboardButton(text="👈 Назад", callback_data="back_to_tariffs", style="danger")]
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(payment_text, parse_mode="HTML", reply_markup=keyboard)
    await state.update_data(current_price=price)


# ========== ОБРАБОТЧИК СБП ==========
@dp.callback_query(F.data == "pay_sbp")
async def pay_sbp_manager(callback: types.CallbackQuery):
    await callback.answer()

    text = (
        "💳 **Оплата через СБП, переводом на карту или по QR-коду**\n\n"
        "1️⃣ Напишите нашему менеджеру: **@Nastia_sup**\n"
        "2️⃣ Укажите в сообщении **название тарифа**, который хотите оплатить.\n"
        "3️⃣ Менеджер отправит вам реквизиты или QR-код.\n"
        "4️⃣ После оплаты пришлите скриншот менеджеру — он сразу выдаст доступ.\n\n"
        "📌 Доступ выдается только после подтверждения оплаты (обычно 1-2 минуты).\n\n"
        "❓ Если возникли вопросы — пишите, поможем."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👈 Назад к способам оплаты", callback_data="back_to_payment_methods")]
    ])

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)


@dp.callback_query(F.data == "back_to_payment_methods")
async def back_to_payment_methods(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_payment(callback, state)


# ========== ОСТАЛЬНЫЕ КНОПКИ ==========
@dp.message(F.text == "Тарифы 🦋")
async def show_tariffs(message: types.Message, state: FSMContext):
    await message.answer(
        "🌟 Коснись любого тарифа — и запретное откроется:",
        reply_markup=get_tariffs_keyboard()
    )
    await state.clear()


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


@dp.callback_query(F.data.startswith("refund_"))
async def refund_request(callback: types.CallbackQuery):
    await callback.answer()
    purchase_id = int(callback.data.split("_")[1])

    cursor.execute('SELECT refunded, user_id, tariff_name FROM purchases WHERE id = ?', (purchase_id,))
    result = cursor.fetchone()

    if not result:
        await callback.message.answer("❌ Покупка не найдена.")
        return

    refunded, user_id, tariff_name = result

    if refunded:
        await callback.message.answer("❌ Возврат по этому тарифу уже был сделан.")
        return

    cursor.execute('SELECT purchased_at FROM purchases WHERE id = ?', (purchase_id,))
    purchased_at = cursor.fetchone()[0]
    time_diff = datetime.now() - datetime.fromisoformat(purchased_at.replace(' ', 'T'))

    if time_diff.total_seconds() > 24 * 3600:
        await callback.message.answer("❌ Срок возврата истёк (24 часа).")
        return

    await bot.send_message(
        MODERATOR_CHAT_ID,
        f"🔔 ЗАЯВКА НА ВОЗВРАТ\n"
        f"👤 Пользователь: @{callback.from_user.username or callback.from_user.first_name} (ID: {callback.from_user.id})\n"
        f"📦 Тариф: {tariff_name}\n"
        f"🆔 ID покупки: {purchase_id}\n\n"
        f"Свяжитесь с пользователем для возврата средств."
    )

    cursor.execute('UPDATE purchases SET refunded = 1 WHERE id = ?', (purchase_id,))
    conn.commit()

    await callback.message.answer(
        "✅ Заявка на возврат отправлена администратору.\n\n"
        "👨‍💼 С вами свяжутся в ближайшее время.\n"
        "💬 По вопросам: @Nastia_sup"
    )

    await callback.message.edit_reply_markup(reply_markup=None)


# ========== ЗАПУСК ==========
async def main():
    print("🚀 Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Вебхук удалён. Бот готов к работе!")
    await dp.start_polling(bot)
    print("🏁 Бот запущен и слушает сообщения!")


if __name__ == "__main__":
    asyncio.run(main())
