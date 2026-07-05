import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

# --- ДОБАВЛЯЕМ БИБЛИОТЕКУ ДЛЯ ПОРТА ---
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = "8298399133:AAFl5uIYOCCXIh6TM6Dn0AonL-Lyq39Wa3s"  # ВСТАВЬ СВОЙ ТОКЕН
PROJECT_NAME = "VIP"  # Твое название
SUPPORT_CONTACT = "https://t.me/Nastia_sup" 

DOCS = {
    "offer": "https://telegra.ph/POLZOVATELSKOE-SOGLASHENIE-07-01-29",
    "policy": "https://telegra.ph/Politika-konfidicialnosti-07-01"
}

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

# --- ИНИЦИАЛИЗАЦИЯ БОТА И ДИСПАТЧЕРА ---
session = AiohttpSession()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
dp = Dispatcher()

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛍️ Прайс"), KeyboardButton(text="🎁 Подписки")]], resize_keyboard=True)

def get_tariff_keyboard():
    buttons = [[InlineKeyboardButton(text=f"{data['name']} • {data['price_rub']} RUB", callback_data=f"tariff_{key}")] for key, data in TARIFFS.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_method_keyboard(tariff_key):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{TARIFFS[tariff_key]['price_rub']} RUB", callback_data=f"pay_rub_{tariff_key}")],
        [InlineKeyboardButton(text=f"{TARIFFS[tariff_key]['price_stars']} STARS", callback_data=f"pay_stars_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_prices")]
    ])
    return kb

def get_payment_action_keyboard(payment_url, tariff_key):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
        [InlineKeyboardButton(text="💰 Я оплатил", callback_data=f"check_payment_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_prices")]
    ])

def go_to_prices_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 К прайсу", callback_data="back_to_prices")]])

# --- ХЭНДЛЕРЫ ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    text = f"👋 Привет, {message.from_user.first_name}!\n\n<a href=\"{DOCS['offer']}\">Пользовательское соглашение</a>\n<a href=\"{DOCS['policy']}\">Политика конфиденциальности</a>\n\nДанный бот создан на платформе @TweetlyRobot"
    await message.answer(text, reply_markup=get_main_keyboard(), disable_web_page_preview=True)

@dp.message(F.text == "🛍️ Прайс")
async def show_prices(message: Message):
    await message.answer("📋 <b>Прайс</b>\n\nВыберите тариф, чтобы узнать подробности и оформить покупку.", reply_markup=get_tariff_keyboard())

@dp.message(F.text == "🎁 Подписки")
async def show_subscriptions(message: Message):
    await message.answer("📋 <b>Ваши подписки</b>\n\nУ вас пока нет активных подписок.\nВыберите тариф, чтобы оформить доступ.", reply_markup=go_to_prices_keyboard())

@dp.callback_query(F.data == "back_to_prices")
async def back_to_prices(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("📋 <b>Прайс</b>\n\nВыберите тариф, чтобы узнать подробности и оформить покупку.", reply_markup=get_tariff_keyboard())

@dp.callback_query(F.data.startswith("tariff_"))
async def show_tariff_details(callback: CallbackQuery):
    tariff_key = callback.data.replace("tariff_", "")
    tariff = TARIFFS[tariff_key]
    text = f"📋 <b>{tariff['name']}</b>\n\n💰 Цена: {tariff['price_rub']} RUB\n\n📝 <b>Описание тарифа:</b>\n{tariff['description']}\n\n🔒 <b>Будет получен доступ на срок {tariff['duration']} к:</b>\n• {PROJECT_NAME} (внешняя ссылка)"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Способы оплаты", callback_data=f"choose_pay_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_prices")]
    ]))

@dp.callback_query(F.data.startswith("choose_pay_"))
async def choose_payment(callback: CallbackQuery):
    tariff_key = callback.data.replace("choose_pay_", "")
    tariff = TARIFFS[tariff_key]
    text = f"📋 <b>{tariff['name']}</b>\nСрок доступа: {tariff['duration']}\n💰 Цена: {tariff['price_rub']} RUB\n\n🔒 Будет получен доступ к:\n• {PROJECT_NAME} (внешняя ссылка)\n\nВыберите валюту для оплаты тарифа"
    await callback.message.edit_text(text, reply_markup=get_payment_method_keyboard(tariff_key))

@dp.callback_query(F.data.startswith("pay_rub_"))
async def process_rub_payment(callback: CallbackQuery):
    tariff_key = callback.data.replace("pay_rub_", "")
    tariff = TARIFFS[tariff_key]
    demo_payment_url = f"https://trk.tweetly.pro/pay/demo_rub_{tariff_key}"
    text = f"📋 <b>{tariff['name']}</b>\nСрок доступа: {tariff['duration']}\n💰 Цена: {tariff['price_rub']} RUB\n💳 Способ оплаты: RollyPay\n\n💰 Итоговая стоимость: {tariff['price_rub']} RUB\n\n🔒 Будет получен доступ к:\n• {PROJECT_NAME} (внешняя ссылка)\n\n✅ Счет на оплату сформирован! Сразу же после оплаты здесь появятся ссылки с доступами"
    await callback.message.edit_text(text, reply_markup=get_payment_action_keyboard(demo_payment_url, tariff_key))

@dp.callback_query(F.data.startswith("pay_stars_"))
async def process_stars_payment(callback: CallbackQuery):
    tariff_key = callback.data.replace("pay_stars_", "")
    tariff = TARIFFS[tariff_key]
    demo_stars_url = f"https://t.me/TweetlyStarsBot?start=demo_stars_{tariff_key}"
    text = (f"📋 <b>{tariff['name']}</b>\nСрок доступа: {tariff['duration']}\n💰 Цена: {tariff['price_stars']} STARS\n💳 Способ оплаты: ЗА ЗВЕЗДЫ ⭐\n\n💰 Итоговая стоимость: {tariff['price_stars']} STARS\n\nℹ️ <b>Информация по оплате</b>\nПодарить звезды или подарки на этот аккаунт - <a href=\"{SUPPORT_CONTACT}\">@Nastia_sup</a>\n\nкурс:\n1 ⭐ - 1 рубль\n\nОтправьте скриншот или файл подтверждения оплаты - он будет передан продавцу.\n\n⚠️ <b>Внимание:</b> на квитанции должны быть четко видны: дата, время и сумма платежа!\nЗа поддельные скриншоты продавец вас может заблокировать!")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars со скидкой до 42%", url=demo_stars_url)],
        [InlineKeyboardButton(text="💰 Я оплатил", callback_data=f"check_payment_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"choose_pay_{tariff_key}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: CallbackQuery):
    await callback.answer("⏳ Проверка оплаты... (Демо-режим)", show_alert=True)
    await callback.message.answer("✅ Оплата успешно найдена! В реальном режиме здесь появится ссылка на доступ.\n\nПоддержка: @Nastia_sup")

# --- ФУНКЦИЯ ДЛЯ UPTIMEROBOT (ПОРТ) ---
async def handle_uptime_check(request):
    return web.Response(text="Bot is alive and kicking!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_uptime_check)
    
    # Render назначает порт через переменную окружения PORT, если нет - ставим 8080
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    await site.start()
    print(f"✅ Веб-сервер для UptimeRobot запущен на порту {port}")

# --- ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА ---
async def main():
    logging.basicConfig(level=logging.INFO)
    
    # 1. Удаляем старые вебхуки
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            await bot.delete_webhook(drop_pending_updates=True)
            print("✅ Старый Webhook удален.")
    except Exception:
        pass
        
    # 2. Запускаем веб-сервер для UptimeRobot
    await start_web_server()
    
    # 3. Запускаем бота (Polling)
    print("🤖 Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import os  # Добавил импорт os для получения порта
    asyncio.run(main())
