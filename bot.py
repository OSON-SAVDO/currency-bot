import asyncio
import datetime
import logging
import os
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

# 2. Гирифтани курс аз API
async def get_exchange_rates():
    url = "https://open.er-api.com/v6/latest/RUB"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get("rates", {})
                    
                    usd_rate = rates.get("USD")
                    tjs_rate = rates.get("TJS", 0)
                    
                    if usd_rate and usd_rate > 0:
                        usd_in_rub = round(1 / usd_rate, 2)
                        rub_in_tjs = round(tjs_rate, 4)
                        return usd_in_rub, rub_in_tjs
    except Exception as e:
        logging.error(f"Хатогӣ дар гирифтани курс: {e}")
    return None, None

# 3. Вазифаи асосии пайгирӣ ва ҳимоя аз хоб рафтан
async def track_currency_loop():
    global last_notified_rate, welcomed_today
    render_ping_timer = 0
    
    while True:
        now = datetime.datetime.now()
        weekday = now.weekday()  # 0-4 Душанбе то Ҷумъа, 5-6 Шанбе ва Якшанбе
        is_weekend = (weekday >= 5)
        
        usd_rub, rub_tjs = await get_exchange_rates()
        
        if usd_rub and rub_tjs:
            if last_notified_rate is None:
                last_notified_rate = usd_rub

            # Санҷиши оғози рӯзи корӣ (Пас аз истироҳат - Душанбе)
            if not is_weekend:
                if not welcomed_today:
                    morning_msg = (
                        "🌅 **Субҳи бахайр! Рӯзи корӣ оғоз ёфт.** 💼\n"
                        f"📊 Курси ҳозираи асъор:\n"
                        f"🇺🇸 **1 USD:** {usd_rub} RUB\n"
                        f"🇹🇯 **1000 RUB:** {round(rub_tjs * 1000, 2)} TJS"
                    )
                    try:
                        await bot.send_message(chat_id=MY_CHAT_ID, text=morning_msg, parse_mode="Markdown")
                    except Exception as e:
                        logging.error(f"Хатогӣ дар паёми субҳона: {e}")
                    welcomed_today = True
            else:
                welcomed_today = False

            # Санҷиши фарқияти 1 рубл
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

        # Тадбир барои нигоҳ доштани фаъолияти Render (~8 дақиқа)
        render_ping_timer += 10
        if render_ping_timer >= 480:
            print("🔄 [Render Keep-Alive] Бот барои бедор мондан фаъолият кард.")
            render_ping_timer = 0

        await asyncio.sleep(10)

# 4. Фармонҳои фаврии /start ва /kurs бо назардошти рӯзҳои истироҳат
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

    await message.answer("⏳ Санҷида истодааст...")
    
    usd_rub, rub_tjs = await get_exchange_rates()
    
    if usd_rub and rub_tjs:
        tjs_1000 = round(rub_tjs * 1000, 2)
        full_msg = (
            f"{weekend_reply}"
            f"🇺🇸 **1 USD:** {usd_rub} RUB\n"
            f"🇹🇯 **1 RUB:** {rub_tjs} TJS\n"
            f"🇹🇯 **1000 RUB:** {tjs_1000} TJS"
        )
        await message.answer(full_msg, parse_mode="Markdown")
    else:
        await message.answer("❌ Хатогӣ дар пайвастшавӣ ба интернет.")

# 5. Қисми асосӣ
async def main():
    logging.basicConfig(level=logging.INFO)
    print("-----------------------------------")
    print("🚀 БОТИ КОМИЛ БА КОР ДАРОМАД!")
    print("-----------------------------------")
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Веб-серверро барои Render кор медарорем
    asyncio.create_task(start_web_server())
    # Пайгирии курсро сар медиҳем
    asyncio.create_task(track_currency_loop())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main:)
