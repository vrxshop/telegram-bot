import asyncio
import logging
import os
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

API_TOKEN = os.getenv("API_TOKEN")  # Токен от @BotFather (на Render)

# ========== ЖЁСТКО ЗАШИТЫЕ ДАННЫЕ ==========
CRYPTOBOT_TOKEN = "583069:AA7qHMROf39Thi7lXuzFem9F3thVsOiocDC"  # Токен от @CryptoBot
ADMIN_ID = 8559381302  # Твой Telegram ID

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КНОПКИ ГЛАВНОГО МЕНЮ ==========
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛒 Товары")],
        [KeyboardButton(text="✉️ Обратная связь"), KeyboardButton(text="🌐 Язык")]
    ],
    resize_keyboard=True
)

# ========== ТОВАРЫ ==========
PRODUCTS = {
    "🍑1000-видео🍑": {"price": 150, "desc": "1000 отборных видео💎\n\nпересыл сообщений открыт\nБессрочная гарантия 🔥"},
    "☀️2000-видео☀️": {"price": 180, "desc": "2000 отборных видео💎\n\nпересыл сообщений открыт\nБессрочная гарантия 🔥"},
    "🧸4000-видео🧸": {"price": 330, "desc": "4000 отборных видео💎\n\nпересыл сообщений открыт\nБессрочная гарантия 🔥"},
    "👄6000-видео👄": {"price": 400, "desc": "6000 отборных видео💎\n\nпересыл сообщений открыт\nБессрочная гарантия 🔥"},
    "🎀10 000-видео🎀": {"price": 500, "desc": "10 000 отборных видео💎\n\nпересыл сообщений открыт\nБессрочная гарантия 🔥"},
    "⚡️20 000-видео⚡️": {"price": 600, "desc": "20 000 отборных видео💎\n\nпересыл сообщений открыт\nБессрочная гарантия 🔥"},
    "🏫clиvы в шķołe🏫": {"price": 300, "desc": "31фото/225 видео + приватка пополняется ✅✨"},
    "🪩pábыни+slivы+kryжki🪩": {"price": 250, "desc": "129фото/400 отборных видео💎"},
    "🍑cóló wķolницы🍑": {"price": 250, "desc": "1000 отборных видео💎"},
    "🍑не colo wķolniцы🍑": {"price": 250, "desc": "1000 отборных видео💎"},
    "🎉NEW VPISKA🎉": {"price": 250, "desc": "129фото/400видео отборных 💎"},
    "⚡️👑ВСЕ СРАЗУ👑⚡️": {"price": 1500, "desc": "Все категории одним пакетом 😋✅"}
}

# Клавиатура товаров
product_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🍑1000-видео🍑", callback_data="product_🍑1000-видео🍑"),
     InlineKeyboardButton(text="☀️2000-видео☀️", callback_data="product_☀️2000-видео☀️"),
     InlineKeyboardButton(text="🧸4000-видео🧸", callback_data="product_🧸4000-видео🧸")],
    [InlineKeyboardButton(text="👄6000-видео👄", callback_data="product_👄6000-видео👄"),
     InlineKeyboardButton(text="🎀10 000-видео🎀", callback_data="product_🎀10 000-видео🎀"),
     InlineKeyboardButton(text="⚡️20 000-видео⚡️", callback_data="product_⚡️20 000-видео⚡️")],
    [InlineKeyboardButton(text="🏫clиvы в шķołe🏫", callback_data="product_🏫clиvы в шķołe🏫"),
     InlineKeyboardButton(text="🪩pábыни+slivы+kryжki🪩", callback_data="product_🪩pábыни+slivы+kryжki🪩"),
     InlineKeyboardButton(text="🍑cóló wķolницы🍑", callback_data="product_🍑cóló wķolницы🍑")],
    [InlineKeyboardButton(text="🍑не colo wķolniцы🍑", callback_data="product_🍑не colo wķolniцы🍑"),
     InlineKeyboardButton(text="🎉NEW VPISKA🎉", callback_data="product_🎉NEW VPISKA🎉"),
     InlineKeyboardButton(text="⚡️👑ВСЕ СРАЗУ👑⚡️", callback_data="product_⚡️👑ВСЕ СРАЗУ👑⚡️")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
])

# Клавиатура оплаты
payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💳 СБП (Система быстрых платежей)", callback_data="pay_sbp")],
    [InlineKeyboardButton(text="🤖 CryptoBot (USDT)", callback_data="pay_cryptobot")],
    [InlineKeyboardButton(text="⭐️ Telegram stars", callback_data="pay_stars")],
    [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_products")]
])

# Клавиатура подтверждения оплаты
confirm_payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я оплатил.", callback_data="payment_done")],
    [InlineKeyboardButton(text="✖️ Отменить", callback_data="back_to_products")]
])

lang_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Русский"), KeyboardButton(text="English")]],
    resize_keyboard=True
)

class PromoState(StatesGroup):
    waiting_for_promo = State()

# ========== ФУНКЦИИ ==========
async def send_to_admin(message: str):
    try:
        await bot.send_message(ADMIN_ID, message)
    except Exception as e:
        logging.error(f"Не удалось отправить админу: {e}")

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🔞LUNAxab🔞\nДобро пожаловать в бот!\n\nВыберите товар:", reply_markup=main_keyboard)

@dp.message(F.text == "🛒 Товары")
async def show_products(message: types.Message):
    await message.answer("Выберите товар:", reply_markup=product_keyboard)

@dp.message(F.text == "✉️ Обратная связь")
async def feedback(message: types.Message):
    await message.answer("Отправьте ваше сообщение боту, поддержка ответит вам в ближайшее время.", reply_markup=main_keyboard)

@dp.message(F.text == "🌐 Язык")
@dp.message(Command("lang"))
async def change_lang(message: types.Message):
    await message.answer("🌐 Выбор языка / Language Selection\n\nВыберите предпочитаемый язык.", reply_markup=lang_keyboard)

@dp.message(F.text == "Русский")
async def set_russian(message: types.Message):
    await message.answer("Язык установлен: Русский", reply_markup=main_keyboard)

@dp.message(F.text == "English")
async def set_english(message: types.Message):
    await message.answer("Language set: English", reply_markup=main_keyboard)

# ========== ОБРАБОТКА ТОВАРОВ ==========
@dp.callback_query(F.data.startswith("product_"))
async def product_detail(callback: types.CallbackQuery, state: FSMContext):
    product_name = callback.data.replace("product_", "")
    product = PRODUCTS.get(product_name)
    
    if product:
        await state.update_data(selected_product=product_name)
        await state.update_data(current_price=product['price'])
        
        text = f"""Товар: {product_name}
Цена: {product['price']} RUB

{product['desc']}"""
        await callback.message.edit_text(text, reply_markup=payment_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "back_to_products")
async def back_to_products(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите товар:", reply_markup=product_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=main_keyboard)
    await callback.answer()

# ========== CRYPTOBOT АВТООПЛАТА ==========
@dp.callback_query(F.data == "pay_cryptobot")
async def pay_cryptobot(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("🔄 Создаём счёт...")
    
    data = await state.get_data()
    price_rub = data.get("current_price", 0)
    product_name = data.get("selected_product", "тариф")
    
    if price_rub == 0:
        await callback.message.answer("❌ Ошибка: выберите товар сначала")
        return
    
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "amount": str(price_rub),
        "currency_type": "fiat",
        "fiat": "RUB",
        "accepted_assets": "USDT,BTC,ETH,TON",
        "description": f"LUNAxab — {product_name}",
        "expires_in": 3600,
        "allow_comments": True,
        "allow_anonymous": True
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        result = response.json()
        
        if result.get("ok"):
            invoice = result["result"]
            invoice_id = invoice["invoice_id"]
            bot_invoice_url = invoice["bot_invoice_url"]
            
            await state.update_data(cryptobot_invoice_id=invoice_id)
            
            text = f"✅ Счёт на оплату через CryptoBot создан!\n\n"
            text += f"🎯 Товар: {product_name}\n"
            text += f"💰 Сумма: {price_rub} ₽\n\n"
            text += f"⬇️ Нажмите кнопку ниже для оплаты ⬇️"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Перейти к оплате 💸", url=bot_invoice_url)],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_cryptobot_payment")],
                [InlineKeyboardButton(text="👈 Назад к способам оплаты", callback_data="back_to_products")]
            ])
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            error = result.get('error', 'Неизвестная ошибка')
            await callback.message.answer(f"❌ Ошибка создания счёта: {error}")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    await callback.answer()

@dp.callback_query(F.data == "check_cryptobot_payment")
async def check_cryptobot_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Проверяем оплату...")
    
    data = await state.get_data()
    invoice_id = data.get("cryptobot_invoice_id")
    price = data.get("current_price", 0)
    product_name = data.get("selected_product", "товар")
    
    if not invoice_id:
        await callback.answer("❌ Счёт не найден. Создайте новый.", show_alert=True)
        return
    
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    params = {"invoice_ids": invoice_id}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        result = response.json()
        
        if result.get("ok") and result.get("result"):
            items = result["result"].get("items", [])
            if items and len(items) > 0:
                invoice = items[0]
                status = invoice.get("status")
                
                if status == "paid":
                    # АВТОВЫДАЧА ТОВАРА
                    await callback.message.answer(
                        f"✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n\n"
                        f"📦 Товар: {product_name}\n"
                        f"💰 Сумма: {price} ₽\n\n"
                        f"🎉 Ссылка на канал: https://t.me/+cHjJzv1hvZdjNGIx\n\n"
                        f"📌 Пересылка сообщений открыта\n"
                        f"🔄 Бессрочная гарантия\n\n"
                        f"💬 Вопросы: @Lunaxab_support"
                    )
                    
                    # Уведомление админу
                    await send_to_admin(
                        f"🔔 НОВАЯ ОПЛАТА (CryptoBot)\n"
                        f"👤 Пользователь: @{callback.from_user.username or callback.from_user.first_name} (ID: {callback.from_user.id})\n"
                        f"📦 Товар: {product_name}\n"
                        f"💰 Сумма: {price} ₽\n"
                        f"✅ Оплачено через CryptoBot"
                    )
                    
                    await state.update_data(cryptobot_invoice_id=None)
                elif status == "expired":
                    await callback.answer("❌ Счёт истёк. Создайте новый через «Назад»", show_alert=True)
                else:
                    await callback.answer("⏳ Платёж ещё не поступил. Попробуйте через 30 секунд.", show_alert=True)
            else:
                await callback.answer("❌ Счёт не найден.", show_alert=True)
        else:
            await callback.answer("❌ Ошибка проверки. Попробуйте позже.", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

# ========== ОСТАЛЬНЫЕ ОПЛАТЫ ==========
@dp.callback_query(F.data == "pay_sbp")
async def pay_sbp(callback: types.CallbackQuery):
    text = """💳 Способ оплаты: СБП

📋 Реквизиты:
Номер: +7 961 855 33 19

❗️ ИНСТРУКЦИЯ:
1. Откройте приложение банка
2. Выберите «Перевод по номеру телефона»
3. Введите номер +7 961 855 33 19
4. Укажите сумму товара
5. Отправьте скриншот чека в этот чат

✅ После проверки выдадут товар"""
    await callback.message.edit_text(text, reply_markup=confirm_payment_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "pay_stars")
async def pay_stars(callback: types.CallbackQuery):
    text = """⭐️ Способ оплаты: Telegram stars

📋 Инструкция:
1️⃣ Запустите @StarsovBot
2️⃣ Укажите ник: @Nastia_sup
3️⃣ Оплатите нужную сумму
4️⃣ Отправьте скриншот в этот чат

✅ После проверки выдадут товар"""
    await callback.message.edit_text(text, reply_markup=confirm_payment_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "enter_promo")
async def enter_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправьте боту ваш промокод:\n🔙 Назад", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_products")]]))
    await state.set_state(PromoState.waiting_for_promo)
    await callback.answer()

@dp.message(PromoState.waiting_for_promo)
async def get_promo(message: types.Message, state: FSMContext):
    promocodes = {"test": 10, "luna2026": 20}
    if message.text.lower() in promocodes:
        await message.answer(f"✅ Промокод принят! Скидка {promocodes[message.text.lower()]}%", reply_markup=main_keyboard)
    else:
        await message.answer("❌ Неверный промокод", reply_markup=main_keyboard)
    await state.clear()

@dp.callback_query(F.data == "payment_done")
async def payment_done(callback: types.CallbackQuery):
    await callback.message.edit_text("✅ Отправьте скриншот/чек в этот чат.\n\nПосле проверки (1-5 мин) вы получите товар.")
    await callback.answer()

@dp.message(F.photo | F.document)
async def handle_screenshot(message: types.Message):
    await message.answer("📸 Скриншот получен! Администратор проверит оплату в ближайшее время.")
    await send_to_admin(f"📸 Чек от @{message.from_user.username}\nID: {message.from_user.id}")

# ========== ЗАПУСК ==========
async def main():
    print("🤖 Бот запущен!")
    print("✅ CryptoBot автооплата подключена")
    print(f"👑 Админ ID: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
