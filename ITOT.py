import logging
import asyncio
import os
import json
import uuid
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

# --- КОНФИГУРАЦИЯ RollyPay ---
ROLLYPAY_API_KEY = "z39_r_COJdiB7PWeddOYvzT2rx4cjIbS1m4JJcgBTi0"
ROLLYPAY_CALLBACK_URL = "https://t-bot-18jz.onrender.com/webhook"

# --- КОНФИГУРАЦИЯ БОТА ---
BOT_TOKEN = "8298399133:AAFl5uIYOCCXIh6TM6Dn0AonL-Lyq39Wa3s"
PROJECT_NAME = "VIP"
SUPPORT_CONTACT_RU = "https://t.me/Nastia_sup"
SUPPORT_CONTACT_EN = "https://t.me/Nastia_sup"

DOCS_RU = {
    "offer": "https://telegra.ph/POLZOVATELSKOE-SOGLASHENIE-07-01-29",
    "policy": "https://telegra.ph/Politika-konfidicialnosti-07-01"
}
DOCS_EN = {
    "offer": "https://telegra.ph/POLZOVATELSKOE-SOGLASHENIE-07-01-29",
    "policy": "https://telegra.ph/Politika-konfidicialnosti-07-01"
}

# --- ТЕКСТЫ И ТАРИФЫ ---
LANG = {
    "ru": {
        "start_promo": "🎉 <b>Промокод {code} активирован! Скидка {discount}%!</b>",
        "start_welcome": "👋 Привет, {name}!\n\n<a href=\"{offer}\">Пользовательское соглашение</a>\n<a href=\"{policy}\">Политика конфиденциальности</a>",
        "prices_menu": "📋 <b>Прайс</b>\n\nВыберите тариф, чтобы узнать подробности и оформить покупку.",
        "subs_menu": "📋 <b>Ваши подписки</b>\n\nУ вас пока нет активных подписок.\nВыберите тариф, чтобы оформить доступ.",
        "tariff_desc": "📋 <b>{name}</b>\n\n{price_line}\n\n📝 <b>Описание тарифа:</b>\n{desc}\n\n🔒 <b>Будет получен доступ на срок {duration} к:</b>\n• {project} (внешняя ссылка)",
        "enter_promo": "🏷️ <b>Введите код промокода</b>\n\nНапишите промокод в чат.",
        "promo_success": "✅ Промокод <b>{code}</b> активирован! Скидка {discount}% 🔥\n\n📋 <b>{name}</b>\n💰 Цена: <s>{old_rub} RUB</s> → {new_rub} RUB <b>(-{discount}%)</b>\n\nВыберите валюту для оплаты.",
        "promo_fail": "❌ Промокод не найден. Попробуйте еще раз (или нажмите ◀️ Отмена).",
        "choose_pay": "📋 <b>{name}</b>\nСрок доступа: {duration}\n💰 Цена: {price_text}\n\n🔒 Будет получен доступ к:\n• {project} (внешняя ссылка)\n\nВыберите валюту для оплаты тарифа",
        "pay_rub": "📋 <b>{name}</b>\nСрок доступа: {duration}\n{price_line}💳 Способ оплаты: RollyPay\n\n💰 Итоговая стоимость: {final} RUB\n\n🔒 Будет получен доступ к:\n• {project} (внешняя ссылка)\n\n✅ Счет на оплату сформирован! Сразу же после оплаты здесь появятся ссылки с доступами",
        "pay_stars": "📋 <b>{name}</b>\nСрок доступа: {duration}\n{price_line}💳 Способ оплаты: ЗА ЗВЕЗДЫ ⭐\n\n💰 Итоговая стоимость: {final} STARS\n\nℹ️ <b>Информация по оплате</b>\nПодарить звезды или подарки на этот аккаунт - <a href=\"{support}\">@Nastia_sup</a>\n\nкурс:\n1 ⭐ - 1 рубль\n\nОтправьте скриншот или файл подтверждения оплаты - он будет передан продавцу.\n\n⚠️ <b>Внимание:</b> на квитанции должны быть четко видны: дата, время и сумма платежа!\nЗа поддельные скриншоты продавец вас может заблокировать!",
        "refresh_link": "♻️ <i>Ссылка обновлена!</i>",
        "btn_prices": "🛍️ Прайс",
        "btn_subs": "🎁 Подписки",
        "btn_promo": "🏷️ Ввести промокод",
        "btn_pay": "💳 Способы оплаты",
        "btn_back": "◀️ Назад",
        "btn_pay_rub": "{price} RUB",
        "btn_pay_rub_disc": "{price} RUB 🏷️(-{disc}%)",
        "btn_pay_stars": "{price} STARS",
        "btn_pay_stars_disc": "{price} STARS 🏷️(-{disc}%)",
        "btn_goto_pay": "💳 Перейти к оплате",
        "btn_new_link": "🔗 Получить новую ссылку",
        "btn_to_prices": "📋 К прайсу",
        "btn_cancel": "◀️ Отмена",
        "btn_stars_go": "⭐ Stars со скидкой до 42%",
        "btn_lang": "🇷🇺 Язык"
    },
    "en": {
        "start_promo": "🎉 <b>Promo code {code} activated! {discount}% discount!</b>",
        "start_welcome": "👋 Hello, {name}!\n\n<a href=\"{offer}\">Terms of Service</a>\n<a href=\"{policy}\">Privacy Policy</a>",
        "prices_menu": "📋 <b>Prices</b>\n\nSelect a tariff to view details and make a purchase.",
        "subs_menu": "📋 <b>Your subscriptions</b>\n\nYou don't have any active subscriptions yet.\nSelect a tariff to get access.",
        "tariff_desc": "📋 <b>{name}</b>\n\n{price_line}\n\n📝 <b>Tariff description:</b>\n{desc}\n\n🔒 <b>You will get access for {duration} to:</b>\n• {project} (external link)",
        "enter_promo": "🏷️ <b>Enter promo code</b>\n\nType the promo code in the chat.",
        "promo_success": "✅ Promo code <b>{code}</b> activated! {discount}% discount 🔥\n\n📋 <b>{name}</b>\n💰 Price: <s>{old_rub} RUB</s> → {new_rub} RUB <b>(-{discount}%)</b>\n\nChoose a currency for payment.",
        "promo_fail": "❌ Promo code not found. Try again (or press ◀️ Cancel).",
        "choose_pay": "📋 <b>{name}</b>\nAccess duration: {duration}\n💰 Price: {price_text}\n\n🔒 You will get access to:\n• {project} (external link)\n\nChoose a currency for payment",
        "pay_rub": "📋 <b>{name}</b>\nAccess duration: {duration}\n{price_line}💳 Payment method: RollyPay\n\n💰 Total cost: {final} RUB\n\n🔒 You will get access to:\n• {project} (external link)\n\n✅ Invoice created! Right after payment, access links will appear here",
        "pay_stars": "📋 <b>{name}</b>\nAccess duration: {duration}\n{price_line}💳 Payment method: FOR STARS ⭐\n\n💰 Total cost: {final} STARS\n\nℹ️ <b>Payment info</b>\nSend stars or gifts to this account - <a href=\"{support}\">@Nastia_sup</a>\n\nRate:\n1 ⭐ - 1 ruble\n\nSend a screenshot or file confirming payment - it will be forwarded to the seller.\n\n⚠️ <b>Attention:</b> the receipt must clearly show: date, time, and payment amount!\nFor fake screenshots, the seller may block you!",
        "refresh_link": "♻️ <i>Link refreshed!</i>",
        "btn_prices": "🛍️ Prices",
        "btn_subs": "🎁 Subscriptions",
        "btn_promo": "🏷️ Enter promo code",
        "btn_pay": "💳 Payment methods",
        "btn_back": "◀️ Back",
        "btn_pay_rub": "{price} RUB",
        "btn_pay_rub_disc": "{price} RUB 🏷️(-{disc}%)",
        "btn_pay_stars": "{price} STARS",
        "btn_pay_stars_disc": "{price} STARS 🏷️(-{disc}%)",
        "btn_goto_pay": "💳 Go to payment",
        "btn_new_link": "🔗 Get new link",
        "btn_to_prices": "📋 Go to prices",
        "btn_cancel": "◀️ Cancel",
        "btn_stars_go": "⭐ Stars up to 42% off",
        "btn_lang": "🇬🇧 Language"
    }
}

# ТАРИФЫ (цены только в кнопках, в названиях цены убраны)
TARIFFS = {
    "celebrity": {
        "name_ru": "Слив знаменитостей",
        "name_en": "Celebrity Leaks",
        "price_rub": 349,
        "price_stars": 300,
        "duration_ru": "1 месяц",
        "duration_en": "1 month",
        "desc_ru": "Слив знаменитостей\n\nИнст Рина\nДаша Дошик\nЛиза Анохина\nXdhka\nВаля Карнавал\nДаша Дошик\nИнстасамка\nСвета Соллар\nИ множество других блогерш\n\nДипфейков нет, только реальные сливы и засветы от блогерш ❤️"
    },
    "shkur": {
        "name_ru": "Сливы шкур",
        "name_en": "Skin Leaks",
        "price_rub": 349,
        "price_stars": 300,
        "duration_ru": "1 месяц",
        "duration_en": "1 month",
        "desc_ru": "После покупки вы попадете в приватный канал со сливом девушек\n\nЧто в канале? Порно девок 13-19, а так-же слив и их разводом на фото, видео и \"беседы\" в скайпе, иногда ссылками на соц сети и Некоторых особых шкур есть номера и страницы вк\n\nУровень? В основном 14-20, но встречаются и до 14 Возраст\n\nПомимо канала прилагается еще немного архивов с шкурками"
    },
    "mini_det": {
        "name_ru": "Mini Детск. До 12",
        "name_en": "Mini Child. Up to 12",
        "price_rub": 499,
        "price_stars": 450,
        "duration_ru": "1 месяц",
        "duration_en": "1 month",
        "desc_ru": "Это мини пак с огромным количеством небольших видео\n\nПосле покупки вы попадете в приватный канал с детским порно довольно таки жестким\n\nУровень? 11-12 возраст, секс, изнасилование, инцест, ласкает себя и т.д.\n\nПомимо видео прилагается еще архивы с множеством гб"
    },
    "shkodnitsy": {
        "name_ru": "ШкоДнищь (13-17 Лет)",
        "name_en": "Schoolgirls (13-17 Years)",
        "price_rub": 799,
        "price_stars": 700,
        "duration_ru": "1 месяц",
        "duration_en": "1 month",
        "desc_ru": "После покупки вы попадете в приватный канал с цельным процессом порно\n\nБольшой сборник из мега подборки порно ваших любимых школьниц возрастом от 12 до 17, есть износа, инцест, много сливов с вписок и просто слив шкур, скрытые камеры школьниц/студенток и сексом, ласкает себя и т.д.\n\nПомимо видео прилагается еще архивы с множеством гб этой категории.\n\nКонтента очень много"
    },
    "premium_det": {
        "name_ru": "Premium Детск. До 12",
        "name_en": "Premium Child. Up to 12",
        "price_rub": 899,
        "price_stars": 800,
        "duration_ru": "1 месяц",
        "duration_en": "1 month",
        "desc_ru": "После покупки вы попадете в приватный канал с детским порно довольно таки жестким\n\nУровень? 11-12 возраст, секс, износа, инцест, ласкает себя и т.д.\n\nПомимо видео прилагается еще архивы с множеством гб\n\nКонтента очень много"
    },
    "zoo": {
        "name_ru": "Канал Зоо",
        "name_en": "Zoo Channel",
        "price_rub": 239,
        "price_stars": 200,
        "duration_ru": "2 месяца",
        "duration_en": "2 months",
        "desc_ru": "Канал с зоо контентом"
    },
    "gay": {
        "name_ru": "Геи",
        "name_en": "Gay",
        "price_rub": 299,
        "price_stars": 250,
        "duration_ru": "1 месяц",
        "duration_en": "1 month",
        "desc_ru": "Вы получите доступ к следующим ресурсам:\n- Gg (канал)\n\nУровень? Есть до 12, но в основном видео 12-17, есть немного износа, инцест, скрытые камеры школьников/студентов и конечно основное же секс и минет\n\nПомимо видео прилагается еще дополнительный архив."
    },
    "zakladchitsy": {
        "name_ru": "Закладчицы",
        "name_en": "Stashers",
        "price_rub": 499,
        "price_stars": 450,
        "duration_ru": "1 месяц",
        "duration_en": "1 month",
        "desc_ru": "Что тебя ждет в наших приватах\nЖесткие изнасилования Закладчиц\nОтсосы, ебля закладчиц в посадках\nПолные видео с закладчицами"
    },
    "pak_obnovlenie": {
        "name_ru": "Пак - Обновление ссылок",
        "name_en": "Pack - Link Update",
        "price_rub": 699,
        "price_stars": 600,
        "duration_ru": "21 дней",
        "duration_en": "21 days",
        "desc_ru": "Сливаем ссылки других каналов, рекомендуем покупать после просмотра других тарифов\n\nЕдинственный пак который не входит во всё включено"
    },
    "vse_vklyucheno": {
        "name_ru": "Всё включено 2026",
        "name_en": "All inclusive 2026",
        "price_rub": 3999,
        "price_stars": 3500,
        "duration_ru": "Бессрочно",
        "duration_en": "Forever",
        "desc_ru": "Вы получите доступ сразу в 10 наших каналов при этом их подписка останется у вас НАВСЕГДА! А выйдет гораздо дешевле чем покупать по отдельности\n\nКонтента у вас выйдет очень МНОГО\n\n+ Бонусные каналы к тарифу"
    },
    "vpn": {
        "name_ru": "Vpn 7 дней",
        "name_en": "Vpn 7 days",
        "price_rub": 10000,
        "price_stars": 9000,
        "duration_ru": "1 день",
        "duration_en": "1 day",
        "desc_ru": "Не покупать, читайте описание.\n\nХороший VPN для обхода белых списков.\n\nПереходим по ссылке:\nhttps://t.me/velvet_vpn_bot?start=AW3BJ7Iz\n\nВам дают 2 дня бесплатного доступа, а также вводим ещё 2 секретных промокода на 7 дней:\n\nWELCOME_BACK\nJUSTTRY"
    }
}

PROMO_CODES = {
    "VIP10": 10, "SUPER25": 25, "HOMAKE40": 40, "BANK50": 50
}

# --- ИНИЦИАЛИЗАЦИЯ ---
storage = MemoryStorage()
session = AiohttpSession()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
dp = Dispatcher(storage=storage)

class PromoStates(StatesGroup):
    waiting_for_promo = State()

# --- ФУНКЦИЯ ДЛЯ RollyPay ---
async def create_rollypay_payment(amount: int, user_id: int, tariff_key: str, tariff_name: str) -> str:
    url = "https://rollypay.io/api/v1/payments"
    headers = {
        "X-API-Key": ROLLYPAY_API_KEY,
        "Content-Type": "application/json",
        "X-Nonce": str(uuid.uuid4())
    }
    payload = {
        "amount": str(amount),
        "payment_currency": "RUB",
        "order_id": f"order_{user_id}_{tariff_key}_{int(asyncio.get_event_loop().time())}",
        "description": "Оплата доступа к контенту",
        "callback_url": ROLLYPAY_CALLBACK_URL,
        "success_url": "https://t.me/blogprivatbot",
        "fail_url": "https://t.me/blogprivatbot",
        "merchant_fee": "true"
    }
    
    async with aiohttp.ClientSession() as client:
        async with client.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("pay_url")
            else:
                error_text = await response.text()
                logging.error(f"Ошибка RollyPay: {response.status} - {error_text}")
                print(f"Ошибка RollyPay: {response.status} - {error_text}")
                return None

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def get_lang(state: FSMContext):
    data = await state.get_data()
    return data.get("lang", "ru")

# --- КЛАВИАТУРЫ ---
def get_main_keyboard(lang):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=LANG[lang]["btn_prices"]), KeyboardButton(text=LANG[lang]["btn_subs"])]
    ], resize_keyboard=True)

def get_tariff_keyboard(lang):
    buttons = []
    for key, data in TARIFFS.items():
        name = data['name_ru'] if lang == 'ru' else data['name_en']
        buttons.append([InlineKeyboardButton(text=f"{name} • {data['price_rub']} RUB", callback_data=f"tariff_{key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_method_keyboard(tariff_key, discount_percent=0, lang="ru"):
    tariff = TARIFFS[tariff_key]
    
    if discount_percent > 0:
        rub_price = int(tariff['price_rub'] * (1 - discount_percent / 100))
        stars_price = int(tariff['price_stars'] * (1 - discount_percent / 100))
        btn_rub = LANG[lang]["btn_pay_rub_disc"].format(price=rub_price, disc=discount_percent)
        btn_stars = LANG[lang]["btn_pay_stars_disc"].format(price=stars_price, disc=discount_percent)
    else:
        rub_price = tariff['price_rub']
        stars_price = tariff['price_stars']
        btn_rub = LANG[lang]["btn_pay_rub"].format(price=rub_price)
        btn_stars = LANG[lang]["btn_pay_stars"].format(price=stars_price)

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_rub, callback_data=f"pay_rub_{tariff_key}")],
        [InlineKeyboardButton(text=btn_stars, callback_data=f"pay_stars_{tariff_key}")],
        [InlineKeyboardButton(text=LANG[lang]["btn_back"], callback_data="back_to_prices")]
    ])

def get_payment_action_keyboard(payment_url, tariff_key, lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANG[lang]["btn_goto_pay"], url=payment_url)],
        [InlineKeyboardButton(text=LANG[lang]["btn_new_link"], callback_data=f"refresh_link_{tariff_key}")],
        [InlineKeyboardButton(text=LANG[lang]["btn_back"], callback_data="back_to_prices")]
    ])

def get_back_to_prices_keyboard(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=LANG[lang]["btn_to_prices"], callback_data="back_to_prices")]])

# --- НАСТРОЙКА МЕНЮ КОМАНД ---
async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="Запустить бота / Start bot"),
        BotCommand(command="language", description="Сменить язык / Change language")
    ]
    await bot.set_my_commands(commands)
    print("✅ Команды /start и /language установлены в меню!")

# --- ХЭНДЛЕРЫ ---

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    args = message.text.split()
    promo_code_from_link = None
    if len(args) > 1:
        promo_code_from_link = args[1].strip()

    lang = await get_lang(state)
    user_name = message.from_user.first_name
    
    if promo_code_from_link and promo_code_from_link in PROMO_CODES:
        discount = PROMO_CODES[promo_code_from_link]
        await state.update_data(discount=discount)
        text = f"👋 Привет, {user_name}!\n\n{LANG[lang]['start_promo'].format(code=promo_code_from_link, discount=discount)}\n\n<a href=\"{DOCS_RU['offer']}\">Пользовательское соглашение</a>\n<a href=\"{DOCS_RU['policy']}\">Политика конфиденциальности</a>"
        await message.answer(text, disable_web_page_preview=True)
    else:
        docs = DOCS_RU if lang == "ru" else DOCS_EN
        text = LANG[lang]["start_welcome"].format(name=user_name, offer=docs['offer'], policy=docs['policy'])
        await message.answer(text, disable_web_page_preview=True)

    await message.answer(
        LANG[lang]["prices_menu"],
        reply_markup=get_tariff_keyboard(lang)
    )

@dp.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext):
    current_lang = await get_lang(state)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")]
    ])
    if current_lang == "ru":
        await message.answer("🌍 Выберите язык:", reply_markup=kb)
    else:
        await message.answer("🌍 Choose language:", reply_markup=kb)

@dp.callback_query(F.data.startswith("set_lang_"))
async def process_lang_change(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.replace("set_lang_", "")
    await state.update_data(lang=lang)
    await callback.answer()
    await callback.message.delete()
    
    if lang == "ru":
        await callback.message.answer("✅ Язык установлен на Русский! Нажмите /start")
    else:
        await callback.message.answer("✅ Language set to English! Press /start")

@dp.message(F.text.in_([LANG["ru"]["btn_prices"], LANG["en"]["btn_prices"]]))
async def show_prices(message: Message, state: FSMContext):
    lang = await get_lang(state)
    await message.answer(LANG[lang]["prices_menu"], reply_markup=get_tariff_keyboard(lang))

@dp.message(F.text.in_([LANG["ru"]["btn_subs"], LANG["en"]["btn_subs"]]))
async def show_subscriptions(message: Message, state: FSMContext):
    lang = await get_lang(state)
    await message.answer(LANG[lang]["subs_menu"], reply_markup=get_back_to_prices_keyboard(lang))

@dp.callback_query(F.data == "back_to_prices")
async def back_to_prices(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await callback.answer()
    await callback.message.edit_text(LANG[lang]["prices_menu"], reply_markup=get_tariff_keyboard(lang))

@dp.callback_query(F.data.startswith("tariff_"))
async def show_tariff_details(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("tariff_", "")
    tariff = TARIFFS[tariff_key]
    lang = await get_lang(state)
    data = await state.get_data()
    discount = data.get("discount", 0)
    
    name = tariff['name_ru'] if lang == "ru" else tariff['name_en']
    duration = tariff['duration_ru'] if lang == "ru" else tariff['duration_en']
    desc = tariff['desc_ru'] if lang == "ru" else tariff['desc_en']
    
    if discount > 0:
        new_price = int(tariff['price_rub'] * (1 - discount / 100))
        price_line = f"💰 Цена: <s>{tariff['price_rub']} RUB</s> -> {new_price} RUB <b>(-{discount}%)</b>"
    else:
        price_line = f"💰 Цена: {tariff['price_rub']} RUB"
        
    text = LANG[lang]["tariff_desc"].format(name=name, price_line=price_line, desc=desc, duration=duration, project=PROJECT_NAME)
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANG[lang]["btn_promo"], callback_data=f"enter_promo_{tariff_key}")],
        [InlineKeyboardButton(text=LANG[lang]["btn_pay"], callback_data=f"choose_pay_{tariff_key}")],
        [InlineKeyboardButton(text=LANG[lang]["btn_back"], callback_data="back_to_prices")]
    ]))

@dp.callback_query(F.data.startswith("enter_promo_"))
async def enter_promo(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("enter_promo_", "")
    lang = await get_lang(state)
    await state.update_data(current_tariff=tariff_key)
    await callback.message.edit_text(
        LANG[lang]["enter_promo"],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=LANG[lang]["btn_cancel"], callback_data=f"cancel_promo_{tariff_key}")]])
    )
    await state.set_state(PromoStates.waiting_for_promo)

@dp.callback_query(F.data.startswith("cancel_promo_"))
async def cancel_promo(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("cancel_promo_", "")
    lang = await get_lang(state)
    await state.clear()
    await callback.message.delete()
    tariff = TARIFFS[tariff_key]
    data = await state.get_data()
    discount = data.get("discount", 0)
    
    name = tariff['name_ru'] if lang == "ru" else tariff['name_en']
    duration = tariff['duration_ru'] if lang == "ru" else tariff['duration_en']
    desc = tariff['desc_ru'] if lang == "ru" else tariff['desc_en']

    if discount > 0:
        price_line = f"💰 Цена: <s>{tariff['price_rub']} RUB</s> -> {int(tariff['price_rub'] * (1 - discount/100))} RUB <b>(-{discount}%)</b>"
    else:
        price_line = f"💰 Цена: {tariff['price_rub']} RUB"

    text = LANG[lang]["tariff_desc"].format(name=name, price_line=price_line, desc=desc, duration=duration, project=PROJECT_NAME)
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANG[lang]["btn_promo"], callback_data=f"enter_promo_{tariff_key}")],
        [InlineKeyboardButton(text=LANG[lang]["btn_pay"], callback_data=f"choose_pay_{tariff_key}")],
        [InlineKeyboardButton(text=LANG[lang]["btn_back"], callback_data="back_to_prices")]
    ]))

@dp.message(PromoStates.waiting_for_promo)
async def process_promo(message: Message, state: FSMContext):
    promo_code = message.text.strip()
    data = await state.get_data()
    tariff_key = data.get("current_tariff")
    lang = await get_lang(state)
    
    if not tariff_key:
        await state.clear()
        return

    if promo_code in PROMO_CODES:
        discount = PROMO_CODES[promo_code]
        await state.update_data(discount=discount)
        await state.clear()
        
        tariff = TARIFFS[tariff_key]
        name = tariff['name_ru'] if lang == "ru" else tariff['name_en']
        new_rub = int(tariff['price_rub'] * (1 - discount / 100))
        
        text = LANG[lang]["promo_success"].format(code=promo_code, discount=discount, name=name, old_rub=tariff['price_rub'], new_rub=new_rub)
        await message.answer(text, reply_markup=get_payment_method_keyboard(tariff_key, discount, lang))
    else:
        await message.answer(LANG[lang]["promo_fail"])

@dp.callback_query(F.data.startswith("choose_pay_"))
async def choose_payment(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("choose_pay_", "")
    lang = await get_lang(state)
    data = await state.get_data()
    discount = data.get("discount", 0)
    
    tariff = TARIFFS[tariff_key]
    name = tariff['name_ru'] if lang == "ru" else tariff['name_en']
    duration = tariff['duration_ru'] if lang == "ru" else tariff['duration_en']
    
    if discount > 0:
        show_rub = int(tariff['price_rub'] * (1 - discount / 100))
        price_text = f"<s>{tariff['price_rub']} RUB</s> → {show_rub} RUB (-{discount}%)"
    else:
        show_rub = tariff['price_rub']
        price_text = f"{show_rub} RUB"
        
    text = LANG[lang]["choose_pay"].format(name=name, duration=duration, price_text=price_text, project=PROJECT_NAME)
    await callback.message.edit_text(text, reply_markup=get_payment_method_keyboard(tariff_key, discount, lang))

@dp.callback_query(F.data.startswith("pay_rub_"))
async def process_rub_payment(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("pay_rub_", "")
    lang = await get_lang(state)
    data = await state.get_data()
    discount = data.get("discount", 0)
    tariff = TARIFFS[tariff_key]
    
    final_price = int(tariff['price_rub'] * (1 - discount / 100))
    user_id = callback.from_user.id
    
    payment_url = await create_rollypay_payment(final_price, user_id, tariff_key, tariff['name_ru'])
    
    if payment_url:
        name = tariff['name_ru'] if lang == "ru" else tariff['name_en']
        duration = tariff['duration_ru'] if lang == "ru" else tariff['duration_en']
        
        if discount > 0:
            price_line = f"💰 Цена: <s>{tariff['price_rub']} RUB</s> → {final_price} RUB (-{discount}%)\n"
        else:
            price_line = f"💰 Цена: {final_price} RUB\n"
            
        text = LANG[lang]["pay_rub"].format(name=name, duration=duration, price_line=price_line, final=final_price, project=PROJECT_NAME)
        await callback.message.edit_text(text, reply_markup=get_payment_action_keyboard(payment_url, tariff_key, lang))
    else:
        await callback.answer("❌ Ошибка создания платежа. Попробуйте позже или выберите другой способ оплаты.", show_alert=True)

@dp.callback_query(F.data.startswith("pay_stars_"))
async def process_stars_payment(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("pay_stars_", "")
    lang = await get_lang(state)
    data = await state.get_data()
    discount = data.get("discount", 0)
    tariff = TARIFFS[tariff_key]
    name = tariff['name_ru'] if lang == "ru" else tariff['name_en']
    duration = tariff['duration_ru'] if lang == "ru" else tariff['duration_en']
    
    final_price = int(tariff['price_stars'] * (1 - discount / 100))
    demo_stars_url = f"https://t.me/TweetlyStarsBot?start=demo_stars_{tariff_key}"
    
    if discount > 0:
        price_line = f"💰 Цена: <s>{tariff['price_stars']} STARS</s> → {final_price} STARS (-{discount}%)\n"
    else:
        price_line = f"💰 Цена: {final_price} STARS\n"
        
    support = SUPPORT_CONTACT_RU if lang == "ru" else SUPPORT_CONTACT_EN
    text = LANG[lang]["pay_stars"].format(name=name, duration=duration, price_line=price_line, final=final_price, project=PROJECT_NAME, support=support)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANG[lang]["btn_stars_go"], url=demo_stars_url)],
        [InlineKeyboardButton(text=LANG[lang]["btn_back"], callback_data=f"choose_pay_{tariff_key}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("refresh_link_"))
async def refresh_link(callback: CallbackQuery, state: FSMContext):
    tariff_key = callback.data.replace("refresh_link_", "")
    tariff = TARIFFS[tariff_key]
    user_id = callback.from_user.id
    final_price = tariff['price_rub']

    payment_url = await create_rollypay_payment(final_price, user_id, tariff_key, tariff['name_ru'])

    if payment_url:
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
                [InlineKeyboardButton(text="🔗 Получить новую ссылку", callback_data=f"refresh_link_{tariff_key}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_prices")]
            ])
        )
        await callback.answer("✅ Новая ссылка сгенерирована!", show_alert=True)
    else:
        await callback.answer("❌ Ошибка создания новой ссылки. Попробуйте позже.", show_alert=True)

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
    
    await set_bot_commands()
    await start_web_server()
    print("🤖 Бот полностью готов (2 языка + меню команд)!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
