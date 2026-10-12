import asyncio
import datetime
import logging
import os
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import aiohttp
from aiohttp import web

# 1. Танзимот (Токен ва ID-и худро гузоред)
BOT_TOKEN = "8182346917:AAGgZpSXqf-XOTl1HJjgsw1vC_fLRK3U46U"
MY_CHAT_ID = 6900346716  # Telegram ID-и худро гузоред

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

last_notified_rate = None
welcomed_today = False

# Веб-сервер барои қонеъ кардани талаботи Render (кушодани порт)
async def handle(request):
    return web.Response(text="Bot is running and alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Веб-сервер дар порги {port} ба кор даромад.")

# 2. Гирифтани курси воқеӣ аз Бонки Марказии Русия ва биржа
async def get_exchange_rates():
    timestamp = int(time.time())
    url_cbr = "https://www.cbr-xml-daily.ru/daily_json.js"
    
    headers = {
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": "Mozilla/5.0"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Гирифтани курси USD ба RUB аз Бонки Марказии Русия
            async with session.get(url_cbr, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    valutes = data.get("Valute", {})
                    usd_data = valutes.get("USD", {})
                    usd_in_rub = usd_data.get("Value")
                    
                    if usd_in_rub:
                        usd_in_rub = round(usd_in_rub, 2)
                        
                        # Гирифтани курси USD ба TJS барои ҳисоби Рубл ба Сомонӣ
                        url_tjs = f"https://open.er-api.com/v6/latest/USD?t={timestamp}"
                        async with session.get(url_tjs, headers=headers, timeout=10) as resp_tjs:
                            if resp_tjs.status == 200:
                                data_tjs = await resp_tjs.json()
                                rates = data_tjs.get("rates", {})
                                tjs_rate = rates.get("TJS")
                                
                                if tjs_rate and usd_in_rub > 0:
                                    rub_in_tjs = round(tjs_rate / usd_in_rub, 4)
                                    return usd_in_rub, rub_in_tjs
    except Exception as e:
        logging.error(f"Хатогӣ дар гирифтани курси воқеӣ аз CBR: {e}")
        
    # Захираи дуюм (Fallback API) дар сурати хатогии манбаи якум
    try:
        url_backup = f"https://api.exchangerate-api.com/v4/latest/USD?t={timestamp}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url_backup, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get("rates", {})
                    rub_rate = rates.get("RUB")
                    tjs_rate = rates.get("TJS")
                    if rub_rate and tjs_rate and rub_rate > 0:
                        usd_in_rub = round(rub_rate, 2)
                        rub_in_tjs = round(tjs_rate / rub_rate, 4)
                        return usd_in_rub, rub_in_tjs
    except Exception as e:
        logging.error(f"Хатогӣ дар backup API: {e}")

    return None, None

# 3. Вазифаи асосии пайгирӣ ва ҳимоя аз хоб рафтан
async def track_currency_loop():
    global last_notified_rate, welcomed_today
    render_ping_timer = 0
    
    while True:
        now = datetime.datetime.now()
        weekday = now.weekday()
        is_weekend = (weekday >= 5)
        
        usd_rub, rub_tjs = await get_exchange_rates()
        
        if usd_rub and rub_tjs:
            if last_notified_rate is None:
                last_notified_rate = usd_rub

            if not is_weekend:
                if not welcomed_today:
                    morning_msg = (
                        "🌅 **Субҳи бахайр! Рӯзи корӣ оғоз ёфт.** 💼\n"
                        f"📊 Курси ҳозираи асъор:\n"
                        f"🇺🇸 **1 USD:** {usd_rub} RUB\n"
                        f"🇹🇯 **1 RUB:** {rub_tjs} TJS\n"
                        f"🇹🇯 **1000 RUB:** {round(rub_tjs * 1000, 2)} TJS"
                    )
                    try:
                        await bot.send_message(chat_id=MY_CHAT_ID, text=morning_msg, parse_mode="Markdown")
                    except Exception as e:
                        logging.error(f"Хатогӣ дар паёми субҳона: {e}")
                    welcomed_today = True
            else:
                welcomed_today = False

            diff = round(usd_rub - last_notified_rate, 2)
            if abs(diff) >= 1.0:
                tjs_1000 = round(rub_tjs * 1000, 2)
                
                if diff < 0:
                    trend_text = "📉 **ДИҚҚАТ! Доллар поён фаромад / Рубл қавитар шуд!**\n⚡️ *Тайёр шав, фурсати харид аст!*"
                else:
                    trend_text = "📈 **ДИҚҚАТ! Доллар боло рафт / Рубл арзон шуд!**"

                alert_msg = (
                    f"🚨 **ТАҒЙИРИ НАЗАРРАСИ КУРС!**\n\n"
                    f"{trend_text}\n\n"
                    f"🇺🇸 **1 USD:** {usd_rub} RUB (Фарқият: {diff:+.2f})\n"
                    f"🇹🇯 **1 RUB:** {rub_tjs} TJS\n"
                    f"🇹🇯 **1000 RUB:** {tjs_1000} TJS"
                )
                
                try:
                    await bot.send_message(chat_id=MY_CHAT_ID, text=alert_msg, parse_mode="Markdown")
                    last_notified_rate = usd_rub
                except Exception as e:
                    logging.error(f"Хатогӣ дар фиристодани ҳушдор: {e}")

        render_ping_timer += 30
        if render_ping_timer >= 480:
            print("🔄 [Render Keep-Alive] Бот барои бедор мондан фаъолият кард.")
            render_ping_timer = 0

        await asyncio.sleep(30)

# 4. Фармонҳои фаврии /start ва /kurs
@dp.message(Command("start", "kurs"))
async def handle_commands(message: types.Message):
    now = datetime.datetime.now()
    is_weekend = (now.weekday() >= 5)
    
    if is_weekend:
        weekend_reply = (
            "🏖 **Имрӯз рӯзи истироҳат аст!**\n"
            "Бозорҳо ва бонкҳо маҳкаманд, аммо курси кунунии биржа чунин аст:\n\n"
        )
    else:
        weekend_reply = "💼 **Рӯзи корӣ. Курси ҳозираи асъор:**\n\n"

    sent_msg = await message.answer("⏳ Санҷида истодааст...")
    
    usd_rub, rub_tjs = await get_exchange_rates()
    
    if usd_rub and rub_tjs:
        tjs_1000 = round(rub_tjs * 1000, 2)
        full_msg = (
            f"{weekend_reply}"
            f"🇺🇸 **1 USD:** {usd_rub} RUB\n"
            f"🇹🇯 **1 RUB:** {rub_tjs} TJS\n"
            f"🇹🇯 **1000 RUB:** {tjs_1000} TJS"
        )
        await bot.edit_message_text(
            text=full_msg, 
            chat_id=message.chat.id, 
            message_id=sent_msg.message_id, 
            parse_mode="Markdown"
        )
    else:
        await bot.edit_message_text(
            text="❌ Хатогӣ дар пайвастшавӣ ба интернет ё API.", 
            chat_id=message.chat.id, 
            message_id=sent_msg.message_id
        )

# 5. Қисми асосӣ
async def main():
    logging.basicConfig(level=logging.INFO)
    print("-----------------------------------")
    print("🚀 БОТИ КОМИЛ БА КОР ДАРОМАД!")
    print("-----------------------------------")
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    asyncio.create_task(start_web_server())
    asyncio.create_task(track_currency_loop())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
