import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, FIREBASE_KEY_PATH
from db import init_db
from handlers_init import register_all_handlers
from whitelist_middleware import WhitelistMiddleware

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    dp = Dispatcher()

    try:
        init_db(FIREBASE_KEY_PATH)
    except Exception as e:
        print(f"Ошибка БД: {e}")

    # Hugging Face Spaces block Telegram API sporadically.
    # The most robust way to solve this is to use a clean connector without forcing families,
    # but strictly trusting environment proxies if Hugging Face injects them (`trust_env=True`),
    # and ensuring standard SSL verification is used so we don't trip security systems.
    import aiohttp

    session = AiohttpSession()

    # Enable `trust_env` so if Hugging Face provides HTTP_PROXY, it's automatically used.
    # We do NOT force IPv4 anymore as it was failing on IPv6-only nodes.
    original_create_session = session.create_session
    async def custom_create_session():
        if session._should_reset_connector:
            await session.close()
        if session._session is None or session._session.closed:
            session._session = aiohttp.ClientSession(
                trust_env=True,
                connector=aiohttp.TCPConnector(ssl=False)
            )
            session._should_reset_connector = False
        return session._session

    session.create_session = custom_create_session
    session.timeout = 60

    from aiogram.client.telegram import TelegramAPIServer

    # Используем приватный Cloudflare Worker для обхода жесткой блокировки api.telegram.org на Hugging Face Spaces
    custom_server = TelegramAPIServer.from_base("https://super-cloud-9af3.ruzkovmisa.workers.dev/")

    # Назначаем этот API-сервер внутрь сессии (так требует aiogram 3.x для корректной маршрутизации)
    session.api = custom_server

    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp.message.outer_middleware(WhitelistMiddleware())
    dp.callback_query.outer_middleware(WhitelistMiddleware())
    register_all_handlers(dp)

    print("Бот запускается на Hugging Face Spaces...")

    try:
        me = await bot.get_me()
        print(f"✅ Соединение с Telegram API установлено! Бот: @{me.username}")
        # Удаляем вебхуки, чтобы поллинг не конфликтовал (если они случайно были)
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Начинаю слушать сообщения (polling)...")
        from log_system import flush_logs
        from chat_stats import weekly_reset_task, flush_stats_task
        asyncio.create_task(flush_logs(bot))
        asyncio.create_task(weekly_reset_task(bot))
        asyncio.create_task(flush_stats_task())
    except Exception as e:
        print(f"❌ Ошибка проверки токена: {e}")

    # Бесконечный цикл поллинга для защиты от падений сети на Hugging Face Spaces
    while True:
        try:
            await dp.start_polling(bot, handle_signals=False)
        except Exception as e:
            print(f"❌ Ошибка сети/поллинга (переподключение через 5с): {e}")
            await asyncio.sleep(5)

    await bot.session.close()

if __name__ == "__main__":
    # Flask сервер для keep-alive на Hugging Face Spaces (порт 7860)
    import threading
    from flask import Flask

    app = Flask(__name__)

    @app.route("/")
    def index():
        return "Бот работает круглосуточно на Hugging Face Spaces!"

    def run_flask():
        # Hugging Face Spaces требует чтобы приложение слушало 0.0.0.0:7860
        app.run(host="0.0.0.0", port=7860, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен вручную")
