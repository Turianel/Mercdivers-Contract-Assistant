import discord
from discord.ext import commands
import json
import requests
import datetime
import asyncio
import aiohttp
import os
from dotenv import load_dotenv
from aiohttp_socks import ProxyConnector

# Загружаем переменные из файла .env
load_dotenv()

# Достаем настройки
TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")
PROXY_URL = os.getenv("PROXY_URL")

# Проверка, что всё загрузилось
if not all([TOKEN, GITHUB_TOKEN, GIST_ID, PROXY_URL]):
    print("❌ Ошибка: Не все переменные найдены в .env файле!")
    exit()

CHANNELS_CONFIG = {
    1485359518153183417: "CONTRACTS",
    1485368542093381754: "BOUNTIES"
}

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# Настройка прокси для синхронных запросов requests
REQUESTS_PROXIES = {
    "http": PROXY_URL,
    "https": PROXY_URL
}

# --- ЛОГИКА GIST ---
def get_current_gist():
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        r = requests.get(url, headers=headers, proxies=REQUESTS_PROXIES, timeout=10)
        if r.status_code == 200:
            content = r.json()['files'].get('latest_transmission.json', {}).get('content')
            if content:
                return json.loads(content)
        else:
            print(f"⚠️ Ошибка получения Gist: {r.status_code} - {r.text}")
        return {"contract": None, "bounty": None}
    except Exception as e:
        print(f"⚠️ Ошибка сети при получении Gist: {e}")
        return {"contract": None, "bounty": None}

def update_gist(data_type, payload):
    current_data = get_current_gist()
    if data_type == "CONTRACTS":
        current_data["contract"] = payload
    else:
        current_data["bounty"] = payload
    
    current_data["last_update_type"] = data_type
    # Используем метку времени для уведомления оверлея об обновлении
    current_data["global_timestamp"] = datetime.datetime.now().isoformat()

    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    files = {
        "latest_transmission.json": {
            "content": json.dumps(current_data, ensure_ascii=False, indent=4)
        }
    }
    try:
        r = requests.patch(url, headers=headers, json={"files": files}, proxies=REQUESTS_PROXIES, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ Ошибка обновления Gist: {r.status_code} - {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"⚠️ Ошибка сети GitHub при патче: {e}")
        return False

# --- СОБЫТИЯ БОТА ---
@bot.event
async def on_ready():
    print(f"✅ Бот запущен под именем: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot: return

    data_type = CHANNELS_CONFIG.get(message.channel.id)
    if data_type and ("###" in message.content or "Contract:" in message.content or "Bounty:" in message.content):
        payload = {
            "content": message.content,
            "author": str(message.author),
            "timestamp": message.created_at.isoformat(),
            "message_id": str(message.id)
        }
        
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, update_gist, data_type, payload)
        
        if success:
            print(f"[{datetime.datetime.now().strftime('%H:%M')}] {data_type} (Новое сообщение) обновлен в Gist.")
        else:
            print(f"[{datetime.datetime.now().strftime('%H:%M')}] ❌ Ошибка при создании {data_type}.")

    await bot.process_commands(message)

@bot.event
async def on_message_edit(before, after):
    """Событие редактирования сообщения"""
    if after.author.bot: return
    
    # Игнорируем правку, если текст не изменился (например, обновились только ссылки)
    if before.content == after.content: return

    data_type = CHANNELS_CONFIG.get(after.channel.id)
    if data_type and ("###" in after.content or "Contract:" in after.content or "Bounty:" in after.content):
        payload = {
            "content": after.content,
            "author": str(after.author),
            "timestamp": after.edited_at.isoformat() if after.edited_at else after.created_at.isoformat(),
            "message_id": str(after.id),
            "is_edited": True
        }
        
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, update_gist, data_type, payload)
        
        if success:
            print(f"[{datetime.datetime.now().strftime('%H:%M')}] {data_type} (Правка сообщения) обновлен в Gist.")
        else:
            print(f"[{datetime.datetime.now().strftime('%H:%M')}] ❌ Ошибка при обновлении правки {data_type}.")

# --- ЗАПУСК ---
async def start_bot():
    connector = ProxyConnector.from_url(PROXY_URL)
    async with aiohttp.ClientSession(connector=connector) as session:
        bot.http.connector = connector
        async with bot:
            await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("Завершение работы...")