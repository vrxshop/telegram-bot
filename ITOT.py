import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ВСТАВЬ СВОЙ ТОКЕН
PROJECT_NAME = "VIP"
SUPPORT_CONTACT = "https://t.me/Nastia_sup"

DOCS = {
    "offer": "https://telegra.ph/POLZOVATELSKOE-SOGLASHENIE-07-01-29",
    "policy": "https://telegra.ph/Politika-konfidicialnosti-07-01"
}

# --- СИСТЕМА ПРОМОКОДОВ (ТОЛЬКО ЭТИ РАБОТАЮТ) ---
PROMO_CODES = {
    "10": 10,
    "25": 25,
    "40": 40,
    "50": 50,
    "VIP10": 10,   # Добавил для теста, чтобы было красиво
    "SUPER25": 25,
    "HOMAKE40": 40,
    "BANK50": 50
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

# --- ИНИЦИАЛИЗАЦИЯ ---
storage = MemoryStorage()
session = AiohttpSession()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
dp = Dispatcher(storage=storage)

# --- МАШИНА СОСТОЯНИЙ ---
class PromoStates(StatesGroup):
    waiting_for_promo = State()

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛍️ Прайс"), KeyboardButton(text="🎁 Подписки")]], resize_keyboard=True)

def get_tariff_keyboard():
    buttons = [[InlineKeyboardButton(text=f"{data['name']} • {data['price_rub']} RUB", callback_data=f"tariff_{key}")] for key, data in TARIFFS.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_method_keyboard(tariff_key, discount_percent=0):
    tariff = TARIFFS[tariff_key]
    
    if discount_percent > 0:
        rub_price = int(tariff['price_rub'] * (1 - discount_percent / 100))
        stars_price = int(tariff['price_stars'] * (1 - discount_percent / 100))
        btn_rub = f"{rub_price} RUB 🏷️(-{discount_percent}%)"
        btn_stars = f"{stars_price} STARS 🏷️(-{discount_percent}%)"
    else:
        rub_price = tariff['price_rub']
        stars_price = tariff['price_stars']
        btn_rub = f"{rub_price} RUB"
        btn_stars = f"{stars_price} STARS"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_rub, callback_data=f"pay_rub_{tariff_key}")],
        [InlineKeyboardButton(text=btn_stars, callback_data=f"pay_stars_{tariff_key}")],
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
async def cmd_start(message: Message, state: FSMContext):
    args = message.text.split()
    promo_code_from_link = None
    
    if len(args) > 1:
        promo_code_from_link = args[1].strip()
    
    # ✅ БЕЗОПАСНАЯ ПРОВЕРКА: скидка дается ТОЛЬКО если код есть в словаре
    if promo_code_from_link and promo_code_from_link in PROMO_CODES:
        discount = PROMO_CODES[promo_code_from_link]
        await state.update_data(discount=discount)
        text = (f"👋 Привет, {message.from_user.first_name}!\n\n"
                f"🎉 <b>Промокод {promo_code_from_link} активирован! Скидка {discount}%!</b>\n\n"
                f"<a href=\"{DOCS['offer']}\">Пользовательское соглашение</a>\n"
                f"<a href=\"{DOCS['policy']}\">Политика конфиденциальности</a>\n\n"
                f"Данный бот создан на платформе @TweetlyRobot")
        await message.answer(text, reply_markup=get_main_keyboard(), disable_web_page_preview=True)
    else:
        # Если код не найден или его нет — скидка НЕ дается и НЕ пишется про скидку
        text = (f"👋 Привет, {message.from_user.first_name}!\n\n"
                f"<a href=\"{DOCS['offer']}\">Пользовательское соглашение</a>\n"
                f"<a href=\"{DOCS['policy']}\">Политика конфиденциальности</a>\n\n"
                f"Данный бот создан на платформе @TweetlyRobot")
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
async def show_tariff_details(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("tariff_", "")
    tariff = TARIFFS[tariff_key]
    
    data = await state.get_data()
    discount = data.get("discount", 0)
    
    if discount > 0:
        new_price = int(tariff['price_rub'] * (1 - discount / 100))
        price_line = f"💰 Цена: <s>{tariff['price_rub']} RUB</s> -> {new_price} RUB <b>(-{discount}%)</b>"
    else:
        price_line = f"💰 Цена: {tariff['price_rub']} RUB"
        
    text = f"📋 <b>{tariff['name']}</b>\n\n{price_line}\n\n📝 <b>Описание тарифа:</b>\n{tariff['description']}\n\n🔒 <b>Будет получен доступ на срок {tariff['duration']} к:</b>\n• {PROJECT_NAME} (внешняя ссылка)"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Ввести промокод", callback_data=f"enter_promo_{tariff_key}")],
        [InlineKeyboardButton(text="💳 Способы оплаты", callback_data=f"choose_pay_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_prices")]
    ]))

# --- ЛОГИКА ПРОМОКОДОВ ---
@dp.callback_query(F.data.startswith("enter_promo_"))
async def enter_promo(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("enter_promo_", "")
    await state.update_data(current_tariff=tariff_key)
    await callback.message.edit_text(
        "🏷️ <b>Введите код промокода</b>\n\n"
        "Напишите промокод в чат.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Отмена", callback_data=f"cancel_promo_{tariff_key}")]])
    )
    await state.set_state(PromoStates.waiting_for_promo)

@dp.callback_query(F.data.startswith("cancel_promo_"))
async def cancel_promo(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("cancel_promo_", "")
    await state.clear()
    await callback.message.delete()
    tariff = TARIFFS[tariff_key]
    data = await state.get_data()
    discount = data.get("discount", 0)

    if discount > 0:
        price_line = f"💰 Цена: <s>{tariff['price_rub']} RUB</s> -> {int(tariff['price_rub'] * (1 - discount/100))} RUB <b>(-{discount}%)</b>"
    else:
        price_line = f"💰 Цена: {tariff['price_rub']} RUB"

    text = f"📋 <b>{tariff['name']}</b>\n\n{price_line}\n\n📝 <b>Описание тарифа:</b>\n{tariff['description']}\n\n🔒 <b>Будет получен доступ на срок {tariff['duration']} к:</b>\n• {PROJECT_NAME} (внешняя ссылка)"
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Ввести промокод", callback_data=f"enter_promo_{tariff_key}")],
        [InlineKeyboardButton(text="💳 Способы оплаты", callback_data=f"choose_pay_{tariff_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_prices")]
    ]))

@dp.message(PromoStates.waiting_for_promo)
async def process_promo(message: Message, state: FSMContext):
    promo_code = message.text.strip()
    data = await state.get_data()
    tariff_key = data.get("current_tariff")
    
    if not tariff_key:
        await state.clear()
        return

    if promo_code in PROMO_CODES:
        discount = PROMO_CODES[promo_code]
        await state.update_data(discount=discount)
        await state.clear()
        
        tariff = TARIFFS[tariff_key]
        new_rub = int(tariff['price_rub'] * (1 - discount / 100))
        new_stars = int(tariff['price_stars'] * (1 - discount / 100))
        
        text = (f"✅ Промокод <b>{promo_code}</b> активирован! Скидка {discount}% 🔥\n\n"
                f"📋 <b>{tariff['name']}</b>\n"
                f"💰 Цена: <s>{tariff['price_rub']} RUB</s> → {new_rub} RUB <b>(-{discount}%)</b>\n\n"
                f"Выберите валюту для оплаты.")
        
        await message.answer(text, reply_markup=get_payment_method_keyboard(tariff_key, discount))
    else:
        await message.answer("❌ Промокод не найден. Попробуйте еще раз (или нажмите ◀️ Отмена).")

# --- ЛОГИКА ОПЛАТЫ ---
@dp.callback_query(F.data.startswith("choose_pay_"))
async def choose_payment(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("choose_pay_", "")
    data = await state.get_data()
    discount = data.get("discount", 0)
    
    tariff = TARIFFS[tariff_key]
    
    if discount > 0:
        show_rub = int(tariff['price_rub'] * (1 - discount / 100))
        price_text = f"<s>{tariff['price_rub']} RUB</s> → {show_rub} RUB (-{discount}%)"
    else:
        show_rub = tariff['price_rub']
        price_text = f"{show_rub} RUB"
        
    text = f"📋 <b>{tariff['name']}</b>\nСрок доступа: {tariff['duration']}\n💰 Цена: {price_text}\n\n🔒 Будет получен доступ к:\n• {PROJECT_NAME} (внешняя ссылка)\n\nВыберите валюту для оплаты тарифа"
    await callback.message.edit_text(text, reply_markup=get_payment_method_keyboard(tariff_key, discount))

@dp.callback_query(F.data.startswith("pay_rub_"))
async def process_rub_payment(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("pay_rub_", "")
    data = await state.get_data()
    discount = data.get("discount", 0)
    tariff = TARIFFS[tariff_key]
    
    final_price = int(tariff['price_rub'] * (1 - discount / 100))
    demo_payment_url = f"https://trk.tweetly.pro/pay/demo_rub_{tariff_key}"
    
    text = f"📋 <b>{tariff['name']}</b>\nСрок доступа: {tariff['duration']}\n"
    if discount > 0:
        text += f"💰 Цена: <s>{tariff['price_rub']} RUB</s> → {final_price} RUB (-{discount}%)\n"
    else:
        text += f"💰 Цена: {final_price} RUB\n"
        
    text += f"💳 Способ оплаты: RollyPay\n\n💰 Итоговая стоимость: {final_price} RUB\n\n🔒 Будет получен доступ к:\n• {PROJECT_NAME} (внешняя ссылка)\n\n✅ Счет на оплату сформирован! Сразу же после оплаты здесь появятся ссылки с доступами"
    await callback.message.edit_text(text, reply_markup=get_payment_action_keyboard(demo_payment_url, tariff_key))

@dp.callback_query(F.data.startswith("pay_stars_"))
async def process_stars_payment(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("pay_stars_", "")
    data = await state.get_data()
    discount = data.get("discount", 0)
    tariff = TARIFFS[tariff_key]
    
    final_price = int(tariff['price_stars'] * (1 - discount / 100))
    demo_stars_url = f"https://t.me/TweetlyStarsBot?start=demo_stars_{tariff_key}"
    
    text = f"📋 <b>{tariff['name']}</b>\nСрок доступа: {tariff['duration']}\n"
    if discount > 0:
        text += f"💰 Цена: <s>{tariff['price_stars']} STARS</s> → {final_price} STARS (-{discount}%)\n"
    else:
        text += f"💰 Цена: {final_price} STARS\n"
        
    text += f"💳 Способ оплаты: ЗА ЗВЕЗДЫ ⭐\n\n💰 Итоговая стоимость: {final_price} STARS\n\nℹ️ <b>Информация по оплате</b>\nПодарить звезды или подарки на этот аккаунт - <a href=\"{SUPPORT_CONTACT}\">@Nastia_sup</a>\n\nкурс:\n1 ⭐ - 1 рубль\n\nОтправьте скриншот или файл подтверждения оплаты - он будет передан продавцу.\n\n⚠️ <b>Внимание:</b> на квитанции должны быть четко видны: дата, время и сумма платежа!\nЗа поддельные скриншоты продавец вас может заблокировать!"
    
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

# --- ФУНКЦИЯ ДЛЯ UPTIMEROBOT ---
async def handle_uptime_check(request):
    return web.Response(text="Bot is alive and kicking!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_uptime_check)
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    await site.start()
    print(f"✅ Веб-сервер для UptimeRobot запущен на порту {port}")

async def main():
    logging.basicConfig(level=logging.INFO)
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    await start_web_server()
    print("🤖 Бот запущен с безопасной системой промокодов!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
