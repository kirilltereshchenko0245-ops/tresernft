"""
Скрипт для создания файла сессии Telegram
Запустите этот файл локально, чтобы создать tracker_session.session
"""
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv
import os
import socks

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
SESSION_NAME = os.getenv("SESSION_NAME", "tracker_session")

# Прокси (опционально, если Telegram заблокирован)
PROXY_HOST = os.getenv("PROXY_HOST", "")
PROXY_PORT = int(os.getenv("PROXY_PORT", "0")) if os.getenv("PROXY_PORT") else 0
PROXY_USER = os.getenv("PROXY_USER", "")
PROXY_PASS = os.getenv("PROXY_PASS", "")

async def create_session():
    print("=== Создание Telegram сессии ===")
    print(f"API_ID: {API_ID}")
    print(f"PHONE_NUMBER: {PHONE_NUMBER}")
    print(f"SESSION_NAME: {SESSION_NAME}")
    
    if not API_ID or not API_HASH:
        print("\n❌ ОШИБКА: Заполните API_ID и API_HASH в .env файле")
        return
    
    if not PHONE_NUMBER:
        print("\n❌ ОШИБКА: Заполните PHONE_NUMBER в .env файле")
        return
    
    # Настройка прокси если указан
    proxy = None
    if PROXY_HOST and PROXY_PORT:
        print(f"\n🔒 Используется прокси: {PROXY_HOST}:{PROXY_PORT}")
        proxy = (socks.SOCKS5, PROXY_HOST, PROXY_PORT, True, PROXY_USER or None, PROXY_PASS or None)
    else:
        print("\n⚠️  Прокси не настроен. Если Telegram заблокирован, добавьте прокси в .env")
    
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH, proxy=proxy)
    
    try:
        print("\nПодключение к Telegram...")
        await client.start(phone=PHONE_NUMBER)
        
        me = await client.get_me()
        print(f"\n✅ Успешная авторизация!")
        print(f"Имя пользователя: {me.username or me.first_name}")
        print(f"ID: {me.id}")
        print(f"\n✅ Файл сессии создан: {SESSION_NAME}.session")
        print("\n📤 СЛЕДУЮЩИЙ ШАГ: Загрузите этот файл на ваш сервер Fadehost")
        
        await client.disconnect()
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        print("\n💡 РЕШЕНИЯ:")
        print("1. Проверьте интернет-соединение")
        print("2. Добавьте SOCKS5 прокси в .env файл (если Telegram заблокирован)")
        print("3. Отключите антивирус/firewall временно")
        print("4. Попробуйте запустить с VPN")

if __name__ == "__main__":
    asyncio.run(create_session())
