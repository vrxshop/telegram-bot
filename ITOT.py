import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties  # <--- ВАЖНАЯ СТРОКА (ДОБАВИЛ)
import asyncio

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = "8298399133:AAFl5uIYOCCXIh6TM6Dn0AonL-Lyq39Wa3s"  # Вставь токен

# НАЗВАНИЕ ТВОЕГО ПРОЕКТА (ЗАМЕНИ НА СВОЕ!)
PROJECT_NAME = "VIP КАНАЛ"

# ССЫЛКИ НА ДОКУМЕНТЫ (Твои)
DOCS = {
    "offer": "https://telegra.ph/POLZOVATELSKOE-SOGLASHENIE-07-01-29",
    "policy": "https://telegra.ph/Politika-konfidicialnosti-07-01"
}

# Твой контакт для кнопки поддержки
SUPPORT_CONTACT = "https://t.me/Nastia_sup" 

# Настройка тарифов
TARIFFS = {
    "month": {
        "name": "VIP на месяц 🚀",
        "price_rub": 349,
        "price_stars": 300,
        "duration": "1 мес.",
        "description": "Доступ к приватке на месяц! 🦄\n\nИнст Рина\nДаша Дошик\nЛиза Анохина\nXdhka\nВаля Карнавал\nДаша Дошик\nИнстасамка\nСвета Соллар\nИ множество других блогерш\n\nДипфейков нет, только реальные сливы и засветы от блогерш ❤️"
    },
    "forever": {
        "name": "VIP навсегда 👑",
        "price_rub": 499,
        "price_stars": 450,
        "duration": "Навсегда",
        "description": "Доступ к приватке навсегда! 🦄\n\nИнст Рина\nДаша Дошик\nЛиза Анохина\nXdhka\nВаля Карнавал\nДаша Дошик\nИнстасамка\nСвета Соллар\nИ множество других блогерш\n\nДипфейков нет, только реальные сливы и засветы от блогерш ❤️"
    },
    "leaks": {
        "name": "СЛИВЫ АЛЬТУШЕК 🦄",
        "price_rub": 299,
        "price_stars": 270,
        "duration": "Навсегда",
        "description": "Сливы альтушек 🦄\n\nБольше тысячи видосов, домашки альтушек, онлики и так далее 🔥\n\nДОСТУП ДАЕТСЯ НАВСЕГДА!!!"
    },
    "all_at_once": {
        "name": "ВСЕ СРАЗУ 🔥",
        "price_rub": 699,
        "price_stars": 550,
        "duration": "Навсегда",
        "description": "Даю доступ навсегда во все приватки и во все следующие, которые будут добавляться\n\nСамый выгодный тариф!"
    }
}

# Инициализация бота (ИСПРАВЛЕННАЯ СТРОКА!)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- КЛАВИАТУРЫ ---

def get_main_keyboard():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍️ Прайс"), KeyboardButton(text="🎁 Подписки")]
        ],
        resize_keyboard=True
    )
    return kb

def get_tariff_keyboard():
    buttons = []
    for key, data in TARIFFS.items():
        buttons.append([InlineKeyboardButton(text=f"{data['name']} • {data['price_rub']} RUB", callback_data=f"tariff_{key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_method_keyboard(tariff_key):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{TARIFFS[tariff_key]['price_rub']} RUB", callback_data=f"pay_rub_{tariff_key}")],
        [InlineKeyboardButton(text=f"{TARIFFS[tariff_key]['price_stars']} STARS", callback_data=f"pay_stars_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_prices")]
    ])
    return kb

def get_payment_action_keyboard(payment_url, tariff_key):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
        [InlineKeyboardButton(text="💰 Я оплатил", callback_data=f"check_payment_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_prices")]
    ])
    return kb

def go_to_prices_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 К прайсу", callback_data="back_to_prices")]
    ])

# --- ЛОГИКА ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"<a href=\"{DOCS['offer']}\">Пользовательское соглашение</a>\n"
        f"<a href=\"{DOCS['policy']}\">Политика конфиденциальности</a>\n\n"
        f"Данный бот создан на платформе @TweetlyRobot"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), disable_web_page_preview=True)

@dp.message(F.text == "🛍️ Прайс")
async def show_prices(message: Message):
    text = "📋 <b>Прайс</b>\n\nВыберите тариф, чтобы узнать подробности и оформить покупку."
    await message.answer(text, reply_markup=get_tariff_keyboard())

@dp.message(F.text == "🎁 Подписки")
async def show_subscriptions(message: Message):
    text = (
        "📋 <b>Ваши подписки</b>\n\n"
        "У вас пока нет активных подписок.\n"
        "Выберите тариф, чтобы оформить доступ."
    )
    await message.answer(text, reply_markup=go_to_prices_keyboard())

@dp.callback_query(F.data == "back_to_prices")
async def back_to_prices(callback: CallbackQuery):
    await callback.answer()
    text = "📋 <b>Прайс</b>\n\nВыберите тариф, чтобы узнать подробности и оформить покупку."
    await callback.message.edit_text(text, reply_markup=get_tariff_keyboard())

@dp.callback_query(F.data.startswith("tariff_"))
async def show_tariff_details(callback: CallbackQuery):
    tariff_key = callback.data.replace("tariff_", "")
    tariff = TARIFFS[tariff_key]
    
    text = (
        f"📋 <b>{tariff['name']}</b>\n\n"
        f"💰 Цена: {tariff['price_rub']} RUB\n\n"
        f"📝 <b>Описание тарифа:</b>\n{tariff['description']}\n\n"
        f"🔒 <b>Будет получен доступ на срок {tariff['duration']} к:</b>\n"
        f"• {PROJECT_NAME} (внешняя ссылка)"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Способы оплаты", callback_data=f"choose_pay_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_prices")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("choose_pay_"))
async def choose_payment(callback: CallbackQuery):
    tariff_key = callback.data.replace("choose_pay_", "")
    tariff = TARIFFS[tariff_key]
    
    text = (
        f"📋 <b>{tariff['name']}</b>\n"
        f"Срок доступа: {tariff['duration']}\n"
        f"💰 Цена: {tariff['price_rub']} RUB\n\n"
        f"🔒 Будет получен доступ к:\n"
        f"• {PROJECT_NAME} (внешняя ссылка)\n\n"
        f"Выберите валюту для оплаты тарифа"
    )
    await callback.message.edit_text(text, reply_markup=get_payment_method_keyboard(tariff_key))

@dp.callback_query(F.data.startswith("pay_rub_"))
async def process_rub_payment(callback: CallbackQuery):
    tariff_key = callback.data.replace("pay_rub_", "")
    tariff = TARIFFS[tariff_key]
    
    demo_payment_url = f"https://trk.tweetly.pro/pay/demo_rub_{tariff_key}"
    
    text = (
        f"📋 <b>{tariff['name']}</b>\n"
        f"Срок доступа: {tariff['duration']}\n"
        f"💰 Цена: {tariff['price_rub']} RUB\n"
        f"💳 Способ оплаты: RollyPay\n\n"
        f"💰 Итоговая стоимость: {tariff['price_rub']} RUB\n\n"
        f"🔒 Будет получен доступ к:\n"
        f"• {PROJECT_NAME} (внешняя ссылка)\n\n"
        f"✅ Счет на оплату сформирован! Сразу же после оплаты здесь появятся ссылки с доступами"
    )
    await callback.message.edit_text(text, reply_markup=get_payment_action_keyboard(demo_payment_url, tariff_key))

@dp.callback_query(F.data.startswith("pay_stars_"))
async def process_stars_payment(callback: CallbackQuery):
    tariff_key = callback.data.replace("pay_stars_", "")
    tariff = TARIFFS[tariff_key]
    
    demo_stars_url = f"https://t.me/TweetlyStarsBot?start=demo_stars_{tariff_key}"
    
    text = (
        f"📋 <b>{tariff['name']}</b>\n"
        f"Срок доступа: {tariff['duration']}\n"
        f"💰 Цена: {tariff['price_stars']} STARS\n"
        f"💳 Способ оплаты: ЗА ЗВЕЗДЫ ⭐\n\n"
        f"💰 Итоговая стоимость: {tariff['price_stars']} STARS\n\n"
        f"ℹ️ <b>Информация по оплате</b>\n"
        f"Подарить звезды или подарки на этот аккаунт - <a href=\"{SUPPORT_CONTACT}\">@eshkereqe</a>\n\n"
        f"курс:\n"
        f"1 ⭐ - 1 рубль\n\n"
        f"Отправьте скриншот или файл подтверждения оплаты - он будет передан продавцу.\n\n"
        f"⚠️ <b>Внимание:</b> на квитанции должны быть четко видны: дата, время и сумма платежа!\n"
        f"За поддельные скриншоты продавец вас может заблокировать!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars со скидкой до 42%", url=demo_stars_url)],
        [InlineKeyboardButton(text="💰 Я оплатил", callback_data=f"check_payment_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"choose_pay_{tariff_key}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: CallbackQuery):
    await callback.answer("⏳ Проверка оплаты... (Демо-режим)", show_alert=True)
    await callback.message.answer("✅ Оплата успешно найдена! В реальном режиме здесь появится ссылка на доступ.\n\nПоддержка: @eshkereqe")

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
