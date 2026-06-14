import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

API_TOKEN = "YOUR_BOT_TOKEN_HERE"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КНОПКИ ГЛАВНОГО МЕНЮ (REPLY) ==========
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛒 Товары")],
        [KeyboardButton(text="✉️ Обратная связь"), KeyboardButton(text="🌐 Язык")]
    ],
    resize_keyboard=True
)

# ========== ВСЕ ТОВАРЫ С ПОЛНЫМИ ОПИСАНИЯМИ ==========
PRODUCTS = {
    "🍑1000-видео🍑": {
        "price": 150,
        "desc": """1000 отборных видео💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+652yHxJVqN5lYjll

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "☀️2000-видео☀️": {
        "price": 180,
        "desc": """2000 отборных видео💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+652yHxJVqN5lYjll

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "🧸4000-видео🧸": {
        "price": 330,
        "desc": """4000 отборных видео💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+652yHxJVqN5lYjll

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "👄6000-видео👄": {
        "price": 400,
        "desc": """6000 отборных видео💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+652yHxJVqN5lYjll

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "🎀10 000-видео🎀": {
        "price": 500,
        "desc": """10 000 отборных видео💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+652yHxJVqN5lYjll

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "⚡️20 000-видео⚡️": {
        "price": 600,
        "desc": """20 000 отборных видео💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+652yHxJVqN5lYjll

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "🏫clиvы в шķołe🏫": {
        "price": 300,
        "desc": """Что входит в приват?

Эти видео и фото собраны в школе и все что описано снизу происходит в шķоле💦

-подгядывания✅
-seks✅
-жопы однаклаssниц✅
-sisьки однаклаssниц✅
-Droчка за парной ✅
-подглядывания за раздвинутыми ножками под парной за одноклаssницей ✅
-разDевания перед физкультурой ✅
-разDевания в туалете✅
-миnet одноклаssнику прямо в школе ✅
-поDглядывания за юбк0й ✅
-и многое другое ✅

и это все за копейки ✨❤️

успей ведь это эксклюзив такого нету не у кого ✨❗️

31фото/225 видео + приватка пополняется ✅✨"""
    },
    "🪩pábыни+slivы+kryжki🪩": {
        "price": 250,
        "desc": """129фото/400 отборных видео💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+652yHxJVqN5lYjll

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "🍑cóló wķolницы🍑": {
        "price": 250,
        "desc": """1000 отборных видео💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+652yHxJVqN5lYjll

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "🍑не colo wķolniцы🍑": {
        "price": 250,
        "desc": """1000 отборных видео💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+652yHxJVqN5lYjll

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "🎉NEW VPISKA🎉": {
        "price": 250,
        "desc": """129фото/400видео отборных 💎

пересыл сообщений открыт
(Можно сохранить себе либо поделиться с другом )📍

Бессрочная гарантия на наши каналы 🔥
(Даже если канал заблокируют мы вас добавим бесплатно )🆓

Безопасная покупка🍓

Что внутри канала ты можешь узнать в нашем канале- https://t.me/+Gr6GyhhyVB5hMDkx

Так же загляни в наш чат где сможешь обменяться кonтентом- https://t.me/+yVZE8Lqcyew2OWQ1"""
    },
    "⚡️👑ВСЕ СРАЗУ👑⚡️": {
        "price": 1500,
        "desc": """Вы получите все категории в боте а выйдет намного дешевле чем брать поштучно 😋✅"""
    }
}

# Клавиатура товаров (2 ряда по 3 кнопки)
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
    [InlineKeyboardButton(text="🤖 Cryptobot (USDT)", callback_data="pay_crypto")],
    [InlineKeyboardButton(text="⭐️ Telegram stars", callback_data="pay_stars")],
    [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_products")]
])

# Клавиатура подтверждения оплаты
confirm_payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я оплатил.", callback_data="payment_done")],
    [InlineKeyboardButton(text="✖️ Отменить", callback_data="back_to_products")]
])

# Клавиатура языка
lang_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Русский"), KeyboardButton(text="English")]],
    resize_keyboard=True
)

class PromoState(StatesGroup):
    waiting_for_promo = State()

class PaymentState(StatesGroup):
    waiting_for_screenshot = State()

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🔞LUNAxab🔞\nДобро пожаловать в бот!\n\nВыберите товар:",
        reply_markup=main_keyboard
    )

@dp.message(F.text == "🛒 Товары")
async def show_products(message: types.Message):
    await message.answer("Выберите товар:", reply_markup=product_keyboard)

@dp.message(F.text == "✉️ Обратная связь")
async def feedback(message: types.Message):
    await message.answer("Отправьте ваше сообщение боту, поддержка ответит вам в ближайшее время.", reply_markup=main_keyboard)

@dp.message(F.text == "🌐 Язык")
async def change_lang_button(message: types.Message):
    await message.answer("🌐 Выбор языка / Language Selection\n\nВыберите предпочитаемый язык интерфейса бота.\nChoose your preferred bot interface language.", reply_markup=lang_keyboard)

@dp.message(Command("lang"))
async def change_lang_command(message: types.Message):
    await message.answer("🌐 Выбор языка / Language Selection\n\nВыберите предпочитаемый язык интерфейса бота.\nChoose your preferred bot interface language.", reply_markup=lang_keyboard)

@dp.message(F.text == "Русский")
async def set_russian(message: types.Message):
    await message.answer("Язык установлен: Русский", reply_markup=main_keyboard)

@dp.message(F.text == "English")
async def set_english(message: types.Message):
    await message.answer("Language set: English", reply_markup=main_keyboard)

# ========== ОБРАБОТКА ТОВАРОВ ==========
@dp.callback_query(F.data.startswith("product_"))
async def product_detail(callback: types.CallbackQuery):
    product_name = callback.data.replace("product_", "")
    product = PRODUCTS.get(product_name)
    
    if product:
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

# ========== ОПЛАТА ==========
@dp.callback_query(F.data == "pay_sbp")
async def pay_sbp(callback: types.CallbackQuery):
    text = """💳 Способ оплаты: СБП (Система быстрых платежей)

Сумма к оплате: зависит от выбранного товара

📋 Реквизиты:
Номер телефона: +7 961 855 33 19
Банк: любой банк РФ с поддержкой СБП

❗️ ИНСТРУКЦИЯ:
1. Откройте приложение своего банка
2. Выберите «Оплата по СБП» или «Перевод по номеру телефона»
3. Введите номер +7 961 855 33 19
4. Укажите сумму согласно выбранному товару
5. Подтвердите перевод

✅ После оплаты сделайте скриншот чека и отправьте в этот чат
✅ Бот проверит платеж и выдаст вам продукт 👑

❗️ ВАЖНО: переводы по СБП проходят мгновенно"""
    await callback.message.edit_text(text, reply_markup=confirm_payment_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "pay_crypto")
async def pay_crypto(callback: types.CallbackQuery):
    text = """🤖 Способ оплаты: Cryptobot (USDT)

Сумма к оплате: зависит от выбранного товара (конвертация по курсу)

📋 ИНСТРУКЦИЯ:
1️⃣ Запустите бота: @CryptoBot
2️⃣ Выберите «Купить USDT» или пополните баланс
3️⃣ Переведите USDT (TRC20 или BEP20) на кошелек бота
4️⃣ Укажите ник получателя: @Nastia_sup
5️⃣ Отправьте перевод

✅ После оплаты нажмите «Я оплатил» и отправьте скриншот/чек
✅ Бот проверит платеж и выдаст вам продукт

ℹ️ Курс USDT актуален на момент оплаты
❗️ Минимальная сумма перевода: 5 USDT"""
    await callback.message.edit_text(text, reply_markup=confirm_payment_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "pay_stars")
async def pay_stars(callback: types.CallbackQuery):
    text = """⭐️ Способ оплаты: Telegram stars

Сумма к оплате: зависит от выбранного товара

📋 Инструкция:
1️⃣ Запустите бота: @StarsovBot
2️⃣ Нажмите «Купить звёзды» и укажите ник: @Nastia_sup
3️⃣ Оплатите нужную сумму через СБП или карту РФ.
4️⃣ Сохраните скриншот или квитанцию об оплате.
5️⃣ Нажмите кнопку «Я оплатил» и отправьте чек администратору.

✅ После оплаты вам выдадут ваш канал ✅

ℹ️ Так же можно оплатить подарками — перейдите по юзернейму @Nastia_sup и киньте подарки на сумму указанную выше ☝️, загрузите скриншот в бота и получите товар 🤝"""
    await callback.message.edit_text(text, reply_markup=confirm_payment_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "enter_promo")
async def enter_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправьте боту ваш промокод для скидки.\n🔙 Назад", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_products")]]))
    await state.set_state(PromoState.waiting_for_promo)
    await callback.answer()

@dp.message(PromoState.waiting_for_promo)
async def get_promo(message: types.Message, state: FSMContext):
    promocodes = {
        "test": 10,
        "luna2026": 20,
        "vip2026": 30
    }
    if message.text.lower() in promocodes:
        await message.answer(f"✅ Промокод принят! Скидка {promocodes[message.text.lower()]}%", reply_markup=main_keyboard)
    else:
        await message.answer("❌ Неверный промокод. Попробуйте снова или нажмите «Назад»", reply_markup=main_keyboard)
    await state.clear()

@dp.callback_query(F.data == "payment_done")
async def payment_done(callback: types.CallbackQuery):
    await callback.message.edit_text("✅ Спасибо за оплату! Отправьте скриншот/чек в этот чат.\n\n📎 Прикрепите файл одним сообщением.\n\nПосле проверки (обычно 1-5 минут) вы получите ссылку на канал/товар.")
    await callback.answer()

# ========== ОБРАБОТКА СКРИНШОТОВ ==========
@dp.message(F.photo)
async def handle_screenshot(message: types.Message):
    await message.answer("📸 Скриншот получен! Администратор проверит оплату в ближайшее время.\n\nВаш заказ обрабатывается...")
    # Пересылка админу (укажи свой ID)
    # ADMIN_ID = 123456789
    # await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"Чек от @{message.from_user.username}\nID: {message.from_user.id}")

@dp.message(F.document)
async def handle_document(message: types.Message):
    await message.answer("📎 Файл получен! Администратор проверит оплату в ближайшее время.\n\nВаш заказ обрабатывается...")

# ========== ЗАПУСК ==========
async def main():
    print("🤖 Бот запущен!")
    print("✅ Доступные команды: /start, /lang")
    print("💳 Способы оплаты: СБП, Cryptobot, Telegram Stars")
    print(f"📦 Всего товаров: {len(PRODUCTS)}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
