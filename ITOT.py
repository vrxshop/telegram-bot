import asyncio
import logging
import sqlite3
import secrets
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== НАСТРОЙКИ ==========
# ТОКЕН БЕРЕТСЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ НА RENDER!
TOKEN = os.getenv("BOT_TOKEN")  # НЕ ХРАНИТСЯ В КОДЕ!

# СПИСОК АДМИНОВ (ID можно оставить, это не секрет)
ADMIN_IDS = [
    8315293936,   # Твой основной ID (ПК)
    # 123456789,  # Добавь сюда второй ID когда узнаешь
]

MANAGER_USERNAME = "Nastia_sup"
GROUP_URL = "https://t.me/+RN8kV8FAVAg3ZGU6"

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ========== БАЗА ДАННЫХ ==========
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
        payment_method TEXT,
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
    CREATE TABLE IF NOT EXISTS join_requests
    (
        user_id INTEGER PRIMARY KEY,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS manual_payments
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT,
        tariff_name TEXT,
        tariff_price REAL,
        payment_method TEXT,
        status TEXT DEFAULT 'pending',
        request_code TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.commit()

# ========== ФУНКЦИИ ==========
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
                cursor.execute('UPDATE users SET balance = balance + 185, first_bonus_given = 1, referral_count = referral_count + 1 WHERE user_id = ?', (referrer_id,))
            else:
                cursor.execute('UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?', (referrer_id,))
            conn.commit()
        return True, "success"
    return False, "already_registered"

def get_user_data(user_id: int):
    cursor.execute('SELECT balance, referral_count FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def add_purchase(user_id: int, tariff_name: str, tariff_price: float, payment_method: str):
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
    cursor.execute('SELECT id, tariff_name, tariff_price, purchased_at, status, payment_method, refunded FROM purchases WHERE user_id = ? ORDER BY purchased_at DESC', (user_id,))
    return cursor.fetchall()

async def get_referral_link(user_id: int) -> str:
    bot_info = await bot.get_me()
    return f"https://t.me/{bot_info.username}?start=ref_{user_id}"

def add_withdraw_request(user_id: int, amount: float):
    cursor.execute('INSERT INTO withdraw_requests (user_id, amount) VALUES (?, ?)', (user_id, amount))
    conn.commit()

def add_manual_payment_request(user_id: int, user_name: str, tariff_name: str, tariff_price: float, payment_method: str):
    request_code = secrets.token_hex(3).upper()
    cursor.execute('''INSERT INTO manual_payments (user_id, user_name, tariff_name, tariff_price, payment_method, request_code, status) 
                      VALUES (?, ?, ?, ?, ?, ?, 'pending')''',
                   (user_id, user_name, tariff_name, tariff_price, payment_method, request_code))
    conn.commit()
    return cursor.lastrowid, request_code

def update_manual_payment_status(request_id: int, status: str):
    cursor.execute('UPDATE manual_payments SET status = ? WHERE id = ?', (status, request_id))
    conn.commit()

def has_join_request(user_id: int) -> bool:
    cursor.execute('SELECT user_id FROM join_requests WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None

def add_join_request(user_id: int):
    cursor.execute('INSERT OR IGNORE INTO join_requests (user_id, approved) VALUES (?, 0)', (user_id,))
    conn.commit()

# ========== ТАРИФЫ ==========
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

# ========== FSM ==========
class PaymentState(StatesGroup):
    selected_tariff_index = State()
    selected_price = State()
    selected_tariff_name = State()

# ========== КЛАВИАТУРЫ ==========
def get_tariffs_keyboard():
    buttons = []
    for i, (name, price, _) in enumerate(TARIFFS):
        buttons.append([InlineKeyboardButton(text=f"{name} ({price:.0f}₽)", callback_data=f"tariff_{i}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Тарифы 🦋"), KeyboardButton(text="Мои покупки 📦")],
        [KeyboardButton(text="📲 Поддержка 👩🏻‍💻"), KeyboardButton(text="🦄 Пример 🙇‍♀️")],
        [KeyboardButton(text="Реф. работа 💸")],
    ],
    resize_keyboard=True
)

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
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
async def handle_join_request(request: types.ChatJoinRequest):
    add_join_request(request.from_user.id)

async def show_main_menu(message: types.Message, state: FSMContext):
    welcome_text = (
        "<b><u>Добро пожаловать в Райский уголок</u></b>\n\n"
        "📶 Максимальная конфиденциальность\n"
        "-- анонимная оплата без лишних данных и привязок.\n"
        "📘 Никаких логов и истории -- ваши переписки остаются только с вами."
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=reply_keyboard)
    await message.answer("🌟 Коснись любого тарифа — и запретное откроется:", reply_markup=get_tariffs_keyboard())
    await state.clear()

# ========== ТАРИФЫ ==========
@dp.callback_query(F.data.startswith("tariff_"))
async def process_tariff(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    idx = int(callback.data.split("_")[1])
    name, price, description = TARIFFS[idx]
    await state.update_data(selected_tariff_index=idx, selected_price=price, selected_tariff_name=name)

    tariff_text = f"{description}\n\n💰 Цена: {price:.2f} ₽"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data="pay_start")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tariffs")]
    ])

    await callback.message.edit_text(tariff_text, parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("🌟 Коснись любого тарифа — и запретное откроется:", reply_markup=get_tariffs_keyboard())
    await state.clear()

# ========== МЕНЮ ОПЛАТЫ ==========
@dp.callback_query(F.data == "pay_start")
async def start_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    price = data.get("selected_price", 0)
    tariff_name = data.get("selected_tariff_name", "")
    
    you_get_official = price * 0.7

    text = (
        f"💳 <b>Выберите способ оплаты</b>\n\n"
        f"📦 {tariff_name}\n"
        f"💰 {price:.0f} ₽\n\n"
        f"<b>⭐️ Telegram Stars (официально)</b>\n"
        f"   • Комиссия Telegram: 30%\n"
        f"   • Ты получишь: {you_get_official:.0f} ₽\n"
        f"   • ✅ Моментально, автоматически\n\n"
        f"<b>🤝 Альтернативная оплата Stars</b>\n"
        f"   • Комиссия: 0%\n"
        f"   • Ты получишь: {price:.0f} ₽\n"
        f"   • ⏱ Проверка вручную (1-2 мин)\n\n"
        f"<b>💳 СБП (через менеджера)</b>\n"
        f"   • Комиссия: 0%\n"
        f"   • ⏱ Проверка вручную"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐️ Stars (официально, авто)", callback_data="pay_stars_official")],
        [InlineKeyboardButton(text="🤝 Stars (без комиссии)", callback_data="pay_stars_alternative")],
        [InlineKeyboardButton(text="💳 СБП", callback_data="pay_sbp")],
        [InlineKeyboardButton(text="👈 Назад", callback_data="back_to_tariffs")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

# ========== ОПЛАТА СБП ==========
@dp.callback_query(F.data == "pay_sbp")
async def pay_sbp(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    tariff_name = data.get("selected_tariff_name")
    tariff_price = data.get("selected_price")
    
    user_name = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name
    request_id, request_code = add_manual_payment_request(
        user_id=callback.from_user.id,
        user_name=user_name,
        tariff_name=tariff_name,
        tariff_price=tariff_price,
        payment_method="sbp"
    )
    
    text = (
        f"💳 <b>ОПЛАТА СБП</b>\n\n"
        f"📦 <b>Тариф:</b> {tariff_name}\n"
        f"💰 <b>Сумма:</b> {tariff_price:.0f} RUB\n"
        f"🆔 <b>Код заявки:</b> <code>{request_code}</code>\n\n"
        f"⬇️ <b>ИНСТРУКЦИЯ:</b>\n\n"
        f"1️⃣ <b>Напиши менеджеру:</b> @{MANAGER_USERNAME}\n"
        f"2️⃣ <b>Отправь код:</b> <code>{request_code}</code>\n"
        f"3️⃣ <b>Менеджер отправит QR-код</b> для оплаты\n"
        f"4️⃣ <b>Оплати</b> и напиши менеджеру <b>«ГОТОВО»</b>\n\n"
        f"✅ Доступ откроется после подтверждения оплаты"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Написать менеджеру", url=f"https://t.me/{MANAGER_USERNAME}")],
        [InlineKeyboardButton(text="📋 Скопировать код", callback_data=f"copy_code_{request_code}")],
        [InlineKeyboardButton(text="👈 Назад", callback_data="back_to_payment_methods")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    
    for admin_id in ADMIN_IDS:
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_manual_{request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_manual_{request_id}")
            ],
            [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={callback.from_user.id}")]
        ])
        
        await bot.send_message(
            admin_id,
            f"🔔 <b>НОВАЯ ЗАЯВКА НА ОПЛАТУ СБП</b>\n\n"
            f"📦 <b>Тариф:</b> {tariff_name}\n"
            f"💰 <b>Сумма:</b> {tariff_price:.0f} RUB\n"
            f"👤 <b>Пользователь:</b> {user_name} (ID: {callback.from_user.id})\n"
            f"🆔 <b>Код:</b> <code>{request_code}</code>\n\n"
            f"📌 <b>Действия:</b>\n"
            f"1. Напиши пользователю\n"
            f"2. Отправь QR-код на сумму {tariff_price:.0f} RUB\n"
            f"3. Дождись «ГОТОВО»\n"
            f"4. Нажми «Подтвердить»",
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )

# ========== ОПЛАТА STARS (ОФИЦИАЛЬНО, АВТО) ==========
@dp.callback_query(F.data == "pay_stars_official")
async def pay_stars_official(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    tariff_name = data.get("selected_tariff_name")
    tariff_price = data.get("selected_price")
    
    text = (
        f"⭐️ <b>TELEGRAM STARS (ОФИЦИАЛЬНАЯ ОПЛАТА)</b>\n\n"
        f"📦 <b>Тариф:</b> {tariff_name}\n"
        f"💰 <b>Сумма:</b> {tariff_price:.0f} RUB\n"
        f"⭐️ <b>Нужно Stars:</b> {int(tariff_price)} ⭐️ (1 Star = 1 RUB)\n\n"
        f"⬇️ <b>ИНСТРУКЦИЯ:</b>\n\n"
        f"1️⃣ Нажми на кнопку <b>«Оплатить Stars»</b>\n"
        f"2️⃣ Откроется окно оплаты в Telegram\n"
        f"3️⃣ Подтверди оплату\n"
        f"4️⃣ Доступ откроется <b>АВТОМАТИЧЕСКИ</b>!\n\n"
        f"✨ Быстро и удобно!\n\n"
        f"⚠️ Комиссия Telegram: 30%"
    )
    
    prices = [LabeledPrice(label=tariff_name[:30], amount=int(tariff_price * 100))]
    
    await callback.message.delete()
    
    await callback.message.answer_invoice(
        title=f"⭐️ {tariff_name[:30]}",
        description=f"Доступ к тарифу {tariff_name}",
        payload=f"stars_official_{int(datetime.now().timestamp())}",
        provider_token="",
        currency="XTR",
        prices=prices,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐️ Оплатить Stars", pay=True)]
        ])
    )

# ========== ОПЛАТА STARS (АЛЬТЕРНАТИВНАЯ, БЕЗ КОМИССИИ) ==========
@dp.callback_query(F.data == "pay_stars_alternative")
async def pay_stars_alternative(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    tariff_name = data.get("selected_tariff_name")
    tariff_price = data.get("selected_price")
    stars_amount = int(tariff_price)
    
    user_name = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name
    request_id, request_code = add_manual_payment_request(
        user_id=callback.from_user.id,
        user_name=user_name,
        tariff_name=tariff_name,
        tariff_price=tariff_price,
        payment_method="stars_alternative"
    )
    
    text = (
        f"🤝 <b>ОПЛАТА STARS БЕЗ КОМИССИИ</b>\n\n"
        f"📦 <b>Тариф:</b> {tariff_name}\n"
        f"💰 <b>Сумма:</b> {tariff_price:.0f} RUB\n"
        f"⭐️ <b>Нужно Stars:</b> {stars_amount} шт.\n"
        f"🆔 <b>Код заявки:</b> <code>{request_code}</code>\n\n"
        f"⬇️ <b>ИНСТРУКЦИЯ (2 способа):</b>\n\n"
        f"<b>Способ 1 - Через бота-партнера:</b>\n"
        f"1️⃣ Запусти бота: @StarsovBot\n"
        f"2️⃣ Нажми «Купить звёзды»\n"
        f"3️⃣ Укажи ник получателя: <code>@{MANAGER_USERNAME}</code>\n"
        f"4️⃣ Оплати {tariff_price:.0f} RUB через СБП/карту\n"
        f"5️⃣ Сохрани скриншот\n\n"
        f"<b>Способ 2 - Подарком:</b>\n"
        f"1️⃣ Купи Stars в Telegram\n"
        f"2️⃣ Отправь подарок: @{MANAGER_USERNAME}\n"
        f"3️⃣ Сделай скриншот\n\n"
        f"📌 <b>После оплаты:</b>\n"
        f"• Отправь скриншот сюда\n"
        f"• Или напиши менеджеру с кодом <code>{request_code}</code>\n\n"
        f"✅ Доступ откроется после проверки"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Перейти в StarsovBot", url="https://t.me/StarsovBot")],
        [InlineKeyboardButton(text="📨 Написать менеджеру", url=f"https://t.me/{MANAGER_USERNAME}")],
        [InlineKeyboardButton(text="📋 Скопировать код", callback_data=f"copy_code_{request_code}")],
        [InlineKeyboardButton(text="👈 Назад", callback_data="back_to_payment_methods")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    
    for admin_id in ADMIN_IDS:
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_manual_{request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_manual_{request_id}")
            ],
            [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={callback.from_user.id}")]
        ])
        
        await bot.send_message(
            admin_id,
            f"🔔 <b>НОВАЯ ЗАЯВКА (STARS БЕЗ КОМИССИИ)</b>\n\n"
            f"📦 Тариф: {tariff_name}\n"
            f"💰 Сумма: {tariff_price:.0f} RUB\n"
            f"⭐️ Stars: {stars_amount} шт.\n"
            f"👤 Пользователь: {user_name} (ID: {callback.from_user.id})\n"
            f"🆔 Код: <code>{request_code}</code>\n\n"
            f"📌 Дождись скриншота или сообщения «ГОТОВО»",
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )

@dp.callback_query(F.data.startswith("copy_code_"))
async def copy_code(callback: types.CallbackQuery):
    code = callback.data.split("copy_code_")[1]
    await callback.answer(f"✅ Код {code} скопирован!", show_alert=True)

@dp.callback_query(F.data == "back_to_payment_methods")
async def back_to_payment_methods(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_payment(callback, state)

# ========== АДМИН-ОБРАБОТЧИКИ ==========
@dp.callback_query(F.data.startswith("approve_manual_"))
async def approve_manual_payment(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    request_id = int(callback.data.split("approve_manual_")[1])
    
    cursor.execute('SELECT user_id, tariff_name, tariff_price, payment_method FROM manual_payments WHERE id = ?', (request_id,))
    result = cursor.fetchone()
    
    if not result:
        await callback.answer("❌ Заявка не найдена!", show_alert=True)
        return
    
    user_id, tariff_name, tariff_price, payment_method = result
    
    update_manual_payment_status(request_id, "approved")
    add_purchase(user_id, tariff_name, tariff_price, payment_method)
    
    method_text = "СБП" if payment_method == "sbp" else "Stars без комиссии"
    
    await bot.send_message(
        user_id,
        f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
        f"🎉 Доступ к тарифу <b>«{tariff_name}»</b> активирован!\n\n"
        f"💳 Способ: {method_text}\n"
        f"📌 Доступ сохраняется навсегда!\n\n"
        f"Приятного просмотра 🌟",
        parse_mode="HTML"
    )
    
    await callback.message.edit_text(
        f"✅ <b>ЗАЯВКА #{request_id} ПОДТВЕРЖДЕНА</b>\n\n"
        f"Пользователь получил доступ к тарифу {tariff_name}",
        parse_mode="HTML"
    )
    
    await callback.answer("✅ Доступ выдан!", show_alert=True)

@dp.callback_query(F.data.startswith("reject_manual_"))
async def reject_manual_payment(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    request_id = int(callback.data.split("reject_manual_")[1])
    
    cursor.execute('SELECT user_id, tariff_name FROM manual_payments WHERE id = ?', (request_id,))
    result = cursor.fetchone()
    
    if result:
        user_id, tariff_name = result
        update_manual_payment_status(request_id, "rejected")
        
        await bot.send_message(
            user_id,
            f"❌ <b>ЗАЯВКА ОТКЛОНЕНА</b>\n\n"
            f"К сожалению, ваша заявка на оплату тарифа <b>«{tariff_name}»</b> была отклонена.\n\n"
            f"💬 Свяжитесь с поддержкой: @{MANAGER_USERNAME}",
            parse_mode="HTML"
        )
        
        await callback.message.edit_text(f"❌ <b>ЗАЯВКА #{request_id} ОТКЛОНЕНА</b>", parse_mode="HTML")
    
    await callback.answer("❌ Заявка отклонена", show_alert=True)

# ========== ПРЕЧЕКАУТ ДЛЯ STARS (АВТО) ==========
@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payment = message.successful_payment
    
    await message.answer(
        f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
        f"🎉 Доступ к тарифу активирован!\n\n"
        f"⭐️ Оплачено: {payment.total_amount} Stars\n\n"
        f"Приятного просмотра 🌟",
        parse_mode="HTML"
    )
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"⭐️ <b>АВТО-ОПЛАТА STARS</b>\n\n"
            f"👤 Пользователь: @{message.from_user.username or message.from_user.first_name} (ID: {message.from_user.id})\n"
            f"💰 Сумма: {payment.total_amount} Stars\n"
            f"✅ Доступ выдан автоматически",
            parse_mode="HTML"
        )

# ========== ОСТАЛЬНЫЕ КНОПКИ ==========
@dp.message(F.text == "Тарифы 🦋")
async def show_tariffs(message: types.Message, state: FSMContext):
    await message.answer("🌟 Коснись любого тарифа — и запретное откроется:", reply_markup=get_tariffs_keyboard())
    await state.clear()

@dp.message(F.text == "Мои покупки 📦")
async def my_purchases(message: types.Message):
    user_id = message.from_user.id
    purchases = get_user_purchases(user_id)
    
    if not purchases:
        await message.answer("📦 У вас пока нет покупок.")
        return
    
    for purchase_id, tariff_name, tariff_price, purchased_at, status, payment_method, refunded in purchases:
        time_diff = datetime.now() - datetime.fromisoformat(purchased_at.replace(' ', 'T'))
        can_refund = time_diff.total_seconds() < 24 * 3600 and status == "active" and refunded == 0
        
        status_icon = "✅ активен" if status == "active" else "❌ истёк"
        date_str = purchased_at.split()[0] if purchased_at else "дата неизвестна"
        
        text = (
            f"📦 {tariff_name}\n"
            f"💰 {tariff_price:.0f} ₽\n"
            f"📅 {date_str}\n"
            f"📌 {status_icon}\n"
            f"💳 {payment_method}\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        if can_refund:
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="❌ Вернуть тариф", callback_data=f"refund_{purchase_id}")])
        await message.answer(text, reply_markup=keyboard if keyboard.inline_keyboard else None)

@dp.message(F.text == "📲 Поддержка 👩🏻‍💻")
async def support(message: types.Message):
    await message.answer(f"❓ Вопросы и поддержка: @{MANAGER_USERNAME}\n\nПишите суть максимально кратко — и ответ не заставит себя ждать!", parse_mode="HTML")

@dp.message(F.text == "🦄 Пример 🙇‍♀️")
async def preview(message: types.Message):
    text = (
        "🔗 <b>«Что внутри канала ты сможешь узнать в нашем канале»</b> - https://t.me/+cHjJzv1hvZdjNGIx\n\n"
        "🔗 <b>«Так же загляни в наш чат где ты сможешь обменяться контентом»</b> - https://t.me/+YgpfPVh34980ZDkx"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "Реф. работа 💸")
async def referral_menu(message: types.Message):
    user_id = message.from_user.id
    data = get_user_data(user_id)
    balance = data[0] if data else 0
    referral_count = data[1] if data else 0
    referral_link = await get_referral_link(user_id)
    
    text = (
        f"💰 <b>Ваш баланс:</b> {balance:.0f} RUB\n"
        f"👥 <b>Рефералов:</b> {referral_count}\n\n"
        f"🔥 <b>Вы получаете 40% от каждой покупки вашего реферала!</b>\n\n"
        f"🔗 <b>Ваша реферальная ссылка:</b>\n{referral_link}\n\n"
        f"📌 <b>Условия вывода:</b>\n"
        f"• Минимальная сумма: 500 RUB\n"
        f"• Минимальное количество рефералов: 1"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывод средств", callback_data="withdraw_request")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query(F.data == "withdraw_request")
async def withdraw_request(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    
    if not data:
        await callback.answer("❌ Данные не найдены!", show_alert=True)
        return
    
    balance, referral_count = data
    
    if balance < 500:
        await callback.answer(f"❌ Минимальная сумма для вывода: 500 RUB. Ваш баланс: {balance:.0f} RUB", show_alert=True)
        return
    
    if referral_count < 1:
        await callback.answer(f"❌ Минимальное количество рефералов для вывода: 1. Ваше количество: {referral_count}", show_alert=True)
        return
    
    add_withdraw_request(user_id, balance)
    
    await callback.message.answer(
        f"✅ <b>Заявка на вывод принята!</b>\n\n"
        f"💰 Сумма: {balance:.0f} RUB\n\n"
        f"👨‍💼 Менеджер свяжется с вами в ближайшее время.\n\n"
        f"💬 По вопросам: @{MANAGER_USERNAME}",
        parse_mode="HTML"
    )
    
    for admin_id in ADMIN_IDS:
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выплачено", callback_data=f"approve_withdraw_{user_id}_{int(balance)}"),
                InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject_withdraw_{user_id}")
            ],
            [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={user_id}")]
        ])
        
        await bot.send_message(
            admin_id,
            f"💰 <b>НОВАЯ ЗАЯВКА НА ВЫВОД</b>\n\n"
            f"👤 Пользователь: @{callback.from_user.username or callback.from_user.first_name} (ID: {user_id})\n"
            f"💰 Сумма: {balance:.0f} RUB\n"
            f"👥 Рефералов: {referral_count}",
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("approve_withdraw_"))
async def approve_withdraw(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[2])
    amount = int(parts[3])
    
    cursor.execute('UPDATE withdraw_requests SET status = "approved" WHERE user_id = ? AND amount = ? AND status = "pending"', (user_id, amount))
    conn.commit()
    
    await bot.send_message(
        user_id,
        f"✅ <b>Ваша заявка на вывод {amount:.0f} RUB одобрена!</b>\n\n"
        f"💰 Средства будут отправлены в ближайшее время.\n\n"
        f"💬 По вопросам: @{MANAGER_USERNAME}",
        parse_mode="HTML"
    )
    
    await callback.message.edit_text(f"✅ Выплачено {amount:.0f} RUB пользователю {user_id}")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_withdraw_"))
async def reject_withdraw(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    cursor.execute('UPDATE withdraw_requests SET status = "rejected" WHERE user_id = ? AND status = "pending"', (user_id,))
    conn.commit()
    
    await bot.send_message(
        user_id,
        f"❌ <b>Ваша заявка на вывод отклонена.</b>\n\n"
        f"Причина: не соблюдены условия вывода.\n\n"
        f"💬 По вопросам: @{MANAGER_USERNAME}",
        parse_mode="HTML"
    )
    
    await callback.message.edit_text(f"❌ Заявка пользователя {user_id} отклонена")
    await callback.answer()

@dp.callback_query(F.data.startswith("refund_"))
async def refund_request(callback: types.CallbackQuery):
    await callback.answer()
    purchase_id = int(callback.data.split("_")[1])
    
    cursor.execute('SELECT refunded, user_id, tariff_name, purchased_at FROM purchases WHERE id = ?', (purchase_id,))
    result = cursor.fetchone()
    
    if not result:
        await callback.message.answer("❌ Покупка не найдена.")
        return
    
    refunded, user_id, tariff_name, purchased_at = result
    
    if refunded:
        await callback.message.answer("❌ Возврат по этому тарифу уже был сделан.")
        return
    
    time_diff = datetime.now() - datetime.fromisoformat(purchased_at.replace(' ', 'T'))
    if time_diff.total_seconds() > 24 * 3600:
        await callback.message.answer("❌ Срок возврата истёк (24 часа).")
        return
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"🔔 <b>ЗАЯВКА НА ВОЗВРАТ</b>\n\n"
            f"👤 Пользователь: @{callback.from_user.username or callback.from_user.first_name} (ID: {callback.from_user.id})\n"
            f"📦 Тариф: {tariff_name}\n"
            f"🆔 ID покупки: {purchase_id}\n\n"
            f"Свяжитесь с пользователем для возврата средств.",
            parse_mode="HTML"
        )
    
    cursor.execute('UPDATE purchases SET refunded = 1 WHERE id = ?', (purchase_id,))
    conn.commit()
    
    await callback.message.answer(
        f"✅ <b>Заявка на возврат отправлена администратору.</b>\n\n"
        f"👨‍💼 С вами свяжутся в ближайшее время.\n"
        f"💬 По вопросам: @{MANAGER_USERNAME}",
        parse_mode="HTML"
    )
    
    await callback.message.edit_reply_markup(reply_markup=None)

# ========== АДМИН КОМАНДА ==========
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Активные заявки на оплату", callback_data="admin_active_requests")],
        [InlineKeyboardButton(text="💰 Заявки на вывод", callback_data="admin_withdraw_requests")]
    ])
    
    await message.answer("👨‍💼 <b>Админ панель</b>\n\nВыберите раздел:", parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query(F.data == "admin_active_requests")
async def admin_active_requests(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    cursor.execute('''
        SELECT id, request_code, user_name, tariff_name, tariff_price, payment_method, created_at 
        FROM manual_payments WHERE status = 'pending' ORDER BY created_at ASC
    ''')
    
    results = cursor.fetchall()
    
    if not results:
        await callback.message.answer("📭 Нет активных заявок на оплату")
        await callback.answer()
        return
    
    for req_id, code, user_name, tariff_name, price, method, created_at in results:
        method_emoji = "💳" if method == "sbp" else "⭐️"
        method_text = "СБП" if method == "sbp" else "Stars без комиссии"
        
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_manual_{req_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_manual_{req_id}")
            ],
            [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={callback.from_user.id}")]
        ])
        
        await callback.message.answer(
            f"{method_emoji} <b>ЗАЯВКА #{code}</b>\n\n"
            f"📦 {tariff_name}\n"
            f"💰 {price:.0f} RUB\n"
            f"👤 {user_name}\n"
            f"💳 {method_text}\n"
            f"🕐 {created_at}",
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )
    
    await callback.answer()

@dp.callback_query(F.data == "admin_withdraw_requests")
async def admin_withdraw_requests(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    cursor.execute('SELECT id, user_id, amount, created_at FROM withdraw_requests WHERE status = "pending" ORDER BY created_at ASC')
    results = cursor.fetchall()
    
    if not results:
        await callback.message.answer("📭 Нет заявок на вывод")
        await callback.answer()
        return
    
    for req_id, user_id, amount, created_at in results:
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выплачено", callback_data=f"approve_withdraw_{user_id}_{int(amount)}"),
                InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject_withdraw_{user_id}")
            ],
            [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={user_id}")]
        ])
        
        await callback.message.answer(
            f"💰 <b>ЗАЯВКА НА ВЫВОД</b>\n\n"
            f"👤 ID: {user_id}\n"
            f"💰 Сумма: {amount:.0f} RUB\n"
            f"🕐 {created_at}",
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )
    
    await callback.answer()

# ========== FLASK ДЛЯ RENDER (ЧТОБЫ СЕРВЕР НЕ ЗАСЫПАЛ) ==========
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

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Запускаем бота
    print("🚀 Бот запускается...")
    asyncio.run(main())
