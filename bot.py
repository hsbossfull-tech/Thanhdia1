
import discord
from discord.ext import commands, tasks
import datetime
from datetime import time
import re
import requests
import json
import os
import random
from collections import defaultdict, deque

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=['l ', 'L ', 'L', 'l'], intents=intents, help_command=None)

COLOR_MAIN = 0x2e1a47
COLOR_INFO = 0x3d3d5c
COLOR_FUN = 0x5900b3
COLOR_WEATHER = 0x004d66

snipe_storage = defaultdict(lambda: deque(maxlen=20))
afk_storage = {}          
spam_tracker = defaultdict(lambda: deque(maxlen=10))
spam_warn_count = defaultdict(int)

DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "dayai": [], "trucxuat": [], "camkhau": [], "anxa": [],
        "xatoi": [], "weather": [], "trogiup": [], "confess": [],
        "snipe": [], "info": [], "announce": [], "afk": [], "si": [],
        "lock": [], "unlock": [], "weather_channel_id": None, "confess_channel_id": None, "gif_channel_id": None
    }

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_random_gif(command_name):
    db = load_db()
    gifs = db.get(command_name, [])
    if gifs:
        item = random.choice(gifs)
        if isinstance(item, dict):
            return item.get("url", "https://media.giphy.com/media/13feGo1n7yG30c/giphy.gif")
        return str(item)
    return "https://media.giphy.com/media/13feGo1n7yG30c/giphy.gif"

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} - Gothic Sanctum Fully Restored & Operational!')
    if not daily_weather_broadcast.is_running():
        daily_weather_broadcast.start()

def is_admin_or_staff():
    async def predicate(ctx):
        return ctx.author.guild_permissions.manage_messages or ctx.author.guild_permissions.administrator
    return commands.check(predicate)

def parse_time(time_str: str):
    time_str = time_str.lower()
    match = re.match(r"^(\d+)([smhd])$", time_str)
    if not match:
        return None
    val, unit = int(match.group(1)), match.group(2)
    if unit == 's': return datetime.timedelta(seconds=val)
    if unit == 'm': return datetime.timedelta(minutes=val)
    if unit == 'h': return datetime.timedelta(hours=val)
    if unit == 'd': return datetime.timedelta(days=val)
    return None

@bot.command(name='gif')
@is_admin_or_staff()
async def manage_gif(ctx, action: str = None, cmd_name: str = None, *, url: str = None):
    try: await ctx.message.delete()
    except: pass
    db = load_db()
    
    attachment_url = ctx.message.attachments[0].url if ctx.message.attachments else None
    target_url = url if url and url.startswith("http") else attachment_url

    if not action or action.lower() not in ["add", "list", "remove"]:
        embed = discord.Embed(
            title="<:caccc:1547883345944387594> **Kho lưu trữ GIF Hắc Ám · Hướng dẫn**",
            description=(
                "† Thêm GIF: `l gif add <lệnh> <link_hoặc_đính_kèm>`\n"
                "† Xem kho GIF: `l gif list <lệnh>`\n"
                "† Xóa GIF: `l gif remove <lệnh> <số_thứ_tự>`\n"
                "† Tạo kênh lưu trữ: `l setgifchannel`"
            ),
            color=COLOR_MAIN
        )
        embed.set_footer(text="Gothic Sanctum · GIF Manager")
        await ctx.send(embed=embed)
        return

    cmd_name = cmd_name.lower() if cmd_name else ""
    if cmd_name not in db:
        db[cmd_name] = []

    if action.lower() == "add":
        if not target_url:
            await ctx.send("❌ *Hãy cung cấp đường dẫn GIF hoặc đính kèm tệp ảnh/GIF!*")
            return
            
        gif_channel_id = db.get("gif_channel_id")
        final_url = target_url
        
        if gif_channel_id:
            gif_channel = bot.get_channel(gif_channel_id)
            if gif_channel:
                try:
                    sent_msg = await gif_channel.send(f"† **Kho lưu trữ linh lực cho lệnh:** `l {cmd_name}`\n{target_url}")
                    if sent_msg.attachments:
                        final_url = sent_msg.attachments[0].url
                except Exception as e:
                    print(f"[STORAGE ERROR]: {e}")

        db[cmd_name].append(final_url)
        save_db(db)
        
        embed = discord.Embed(
            title="<:emoji_16:1547886424760520744> **Đã nạp linh lực vào kho · GIF Added**",
            description=f"Đã thêm thành công 1 GIF mới vào lệnh `l {cmd_name}`.\n*Tổng số GIF hiện tại:* **{len(db[cmd_name])}**",
            color=COLOR_MAIN
        )
        embed.set_image(url=final_url)
        embed.set_footer(text="Gothic Sanctum · Storage Sanctuary")
        await ctx.send(embed=embed)

    elif action.lower() == "list":
        gifs = db[cmd_name]
        if not gifs:
            await ctx.
