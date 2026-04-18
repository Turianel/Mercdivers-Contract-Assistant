import subprocess
import sys
import os
import importlib.util

def install_missing_dependencies():
    """Checks for the presence of required libraries and installs them automatically."""
    required_packages = {
        'discord.py': 'discord', 
        'python-dotenv': 'dotenv', 
        'aiohttp': 'aiohttp', 
        'aiohttp-socks': 'aiohttp_socks'
    }
    
    missing = []
    for pkg_name, import_name in required_packages.items():
        if importlib.util.find_spec(import_name) is None:
            missing.append(pkg_name)

    if missing:
        if os.environ.get('RESTART_LOOP_GUARD') == '1':
            print(f"--- CRITICAL ERROR: Failed to install packages: {', '.join(missing)} ---")
            sys.exit(1)

        print(f"--- Missing components detected: {', '.join(missing)} ---")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            os.environ['RESTART_LOOP_GUARD'] = '1'
            os.execve(sys.executable, [sys.executable] + sys.argv, os.environ)
        except Exception as e:
            print(f"--- РћРЁРР‘РљРђ РџР Р РЈРЎРўРђРќРћР’РљР•: {e} ---")
            sys.exit(1)

install_missing_dependencies()

import logging
import json
import datetime
import asyncio
import aiohttp
import argparse
from typing import Optional, List, Dict, Union
from dotenv import load_dotenv
from aiohttp_socks import ProxyConnector
import discord
from discord.ext import commands, tasks

# --- Setting up logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MercBot")

load_dotenv()

# --- Constants from the environment ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")
SOCKS5_URL = os.getenv("PROXY_SOCKS5_URL")
MTPROTO_URL = os.getenv("PROXY_MTPROTO_URL")

try:
    CHANNEL_CONTRACTS_ID = int(os.getenv("CHANNEL_CONTRACTS_ID", 0))
    CHANNEL_BOUNTIES_ID = int(os.getenv("CHANNEL_BOUNTIES_ID", 0))
    CHANNEL_LOG_ID = int(os.getenv("CHANNEL_LOG_ID", 0))
except (ValueError, TypeError):
    logger.critical("Configuration error: Channel IDs in .env must be numeric.")
    sys.exit(1)

CHANNELS_CONFIG = {
    CHANNEL_CONTRACTS_ID: "CONTRACTS",
    CHANNEL_BOUNTIES_ID: "BOUNTIES"
}

# --- РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ Р±РѕС‚Р° ---
intents = discord.Intents.default()
intents.message_content = True 
intents.messages = True

class MercBot(commands.Bot):
    def __init__(self, proxy_url: Optional[str] = None):
        super().__init__(command_prefix="!", intents=intents)
        self.http_session = None
        self.proxy_url = proxy_url
        self.gist_lock = asyncio.Lock()

    async def setup_hook(self):
        connector = ProxyConnector.from_url(self.proxy_url) if self.proxy_url else None
        self.http_session = aiohttp.ClientSession(connector=connector)
        await self.tree.sync()
        logger.info(f"Slash commands are synchronized. Network mode: {'Proxy' if self.proxy_url else 'Direct'}")

    async def close(self):
        if self.http_session:
            await self.http_session.close()
        await super().close()

# --- Auxiliary functions ---
async def send_discord_log(bot_instance, message: str):
    try:
        channel = bot_instance.get_channel(CHANNEL_LOG_ID)
        if channel:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            await channel.send(f"[`{timestamp}`] {message}")
    except Exception as e:
        logger.error(f"Failed to send log to Discord: {e}")

async def get_current_gist(bot_instance) -> dict:
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        async with bot_instance.http_session.get(url, headers=headers, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                content = data.get('files', {}).get('latest_transmission.json', {}).get('content')
                if content:
                    return json.loads(content)
            return {"contract": None, "bounty": None}
    except Exception as e:
        logger.error(f"GitHub network error: {e}")
        return {"contract": None, "bounty": None}

async def update_gist(bot_instance, data_type: str, payload: Optional[dict], clear: bool = False, event_type: str = "NEW") -> bool:
    async with bot_instance.gist_lock:
        current_data = await get_current_gist(bot_instance)
        key = "contract" if data_type == "CONTRACTS" else "bounty"
        
        if not clear and current_data.get(key) == payload:
            return True

        current_data[key] = None if clear else payload
        current_data["last_update_type"] = data_type
        current_data["global_timestamp"] = datetime.datetime.now().isoformat()

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        files = {"latest_transmission.json": {"content": json.dumps(current_data, ensure_ascii=False, indent=4)}}
        
        try:
            async with bot_instance.http_session.patch(url, headers=headers, json={"files": files}, timeout=10) as r:
                if r.status == 200:
                    logger.info(f"[{event_type}] {data_type} Synched with Gist.")
                    return True
                return False
        except Exception as e:
            logger.error(f"Gist update failure: {e}")
            return False

async def sync_channel(bot_instance, channel_id: int, event_type: str = "SYNC") -> bool:
    data_type = CHANNELS_CONFIG.get(channel_id)
    if not data_type: return False
    
    channel = bot_instance.get_channel(channel_id)
    if not channel: return False

    async for message in channel.history(limit=50):
        if not message.author.bot and any(x in message.content for x in ["###", "Contract:", "Bounty:"]):
            img_url = message.attachments[0].url if message.attachments else None
            payload = {
                "content": message.content,
                "author": str(message.author),
                "timestamp": message.created_at.isoformat(),
                "message_id": str(message.id),
                "image_url": img_url
            }
            await update_gist(bot_instance, data_type, payload, event_type=event_type)
            return True
            
    await update_gist(bot_instance, data_type, None, clear=True, event_type=event_type + "_CLEAR")
    return False

# --- Setup and launch ---
def main():
    parser = argparse.ArgumentParser(description="Discord to Gist Sync Bot")
    parser.add_argument('--proxy', choices=['direct', 'socks5', 'mtproto'], default='direct',
                        help='Connection mode: (by default: direct)')
    args = parser.parse_args()

    active_proxy = None
    if args.proxy == 'socks5':
        active_proxy = SOCKS5_URL
    elif args.proxy == 'mtproto':
        active_proxy = MTPROTO_URL

    if args.proxy != 'direct' and not active_proxy:
        logger.error(f"Mode {args.proxy} chosen, but proxy's URL not found in .env")
        sys.exit(1)

    bot = MercBot(proxy_url=active_proxy)

    @bot.tree.command(name="update", description="Force update with Gist...")
    async def force_update(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        results = []
        for c_id in CHANNELS_CONFIG:
            if await sync_channel(bot, c_id, "MANUAL"):
                results.append(CHANNELS_CONFIG[c_id])
        
        msg = f"вњ… Sync completed. Updated: {', '.join(results)}" if results else "вљ пёЏ Messages not found."
        await interaction.followup.send(msg)
        await send_discord_log(bot, f"вљЎ Manual sync, initiated by {interaction.user}. Updated: {', '.join(results)}")

    @bot.event
    async def on_ready():
        logger.info(f"РЈР·РµР» Р·Р°РїСѓС‰РµРЅ: {bot.user}")
        for c_id in CHANNELS_CONFIG:
            await sync_channel(bot, c_id, "INITIAL")
        if not check_posts_existence.is_running():
            check_posts_existence.start()
        await send_discord_log(bot, f"рџџў I am alive. Looking for Contracts and Bounties. Mode: {args.proxy}")

    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot: return
        data_type = CHANNELS_CONFIG.get(message.channel.id)
        if data_type and any(x in message.content for x in ["###", "Contract:", "Bounty:"]):
            img_url = message.attachments[0].url if message.attachments else None
            payload = {
                "content": message.content, "author": str(message.author),
                "timestamp": message.created_at.isoformat(), "message_id": str(message.id),
                "image_url": img_url
            }
            if await update_gist(bot, data_type, payload, event_type="NEW"):
                await send_discord_log(bot, f"рџ“ќ {data_type} added.\nSource: {message.jump_url}")

    @bot.event
    async def on_message_edit(before: Optional[discord.Message], after: discord.Message):
        if before and before.content == after.content: return
        await on_message(after)

    @bot.event
    async def on_message_delete(message: discord.Message):
        data_type = CHANNELS_CONFIG.get(message.channel.id)
        if data_type:
            data = await get_current_gist(bot)
            key = "contract" if data_type == "CONTRACTS" else "bounty"
            if data.get(key) and data[key].get("message_id") == str(message.id):
                await send_discord_log(bot, f"рџ—‘пёЏ Message {data_type} was deleted. Searching previous one...")
                await sync_channel(bot, message.channel.id, "ROLLBACK")

    @tasks.loop(minutes=5)
    async def check_posts_existence():
        data = await get_current_gist(bot)
        for key, data_type in [("contract", "CONTRACTS"), ("bounty", "BOUNTIES")]:
            item = data.get(key)
            if item and item.get("message_id"):
                c_id = CHANNEL_CONTRACTS_ID if data_type == "CONTRACTS" else CHANNEL_BOUNTIES_ID
                channel = bot.get_channel(c_id)
                if channel:
                    try:
                        await channel.fetch_message(int(item["message_id"]))
                    except (discord.NotFound, discord.Forbidden):
                        await sync_channel(bot, c_id, "CLEANUP")

    async def run_bot():
        async with bot:
            await bot.start(DISCORD_TOKEN)

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Stopped by user.")

if __name__ == "__main__":
    main()
