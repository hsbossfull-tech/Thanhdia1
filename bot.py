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
from urllib.parse import urlparse

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=['l ', 'L ', 'L', 'l'],
    intents=intents,
    help_command=None
)

COLOR_MAIN = 0x2e1a47
COLOR_INFO = 0x3d3d5c
COLOR_FUN = 0x5900b3
COLOR_WEATHER = 0x004d66

snipe_storage = defaultdict(lambda: deque(maxlen=20))
afk_storage = {}
spam_tracker = defaultdict(lambda: deque(maxlen=10))
spam_warn_count = defaultdict(int)

DB_FILE = "database.json"

# Các lệnh được phép quản lý GIF.
GIF_COMMANDS = [
    "dayai", "trucxuat", "camkhau", "anxa", "xatoi",
    "weather", "trogiup", "confess", "snipe", "info",
    "announce", "afk", "si", "lock", "unlock"
]

DEFAULT_DB = {
    "dayai": [],
    "trucxuat": [],
    "camkhau": [],
    "anxa": [],
    "xatoi": [],
    "weather": [],
    "trogiup": [],
    "confess": [],
    "snipe": [],
    "info": [],
    "announce": [],
    "afk": [],
    "si": [],
    "lock": [],
    "unlock": [],
    "weather_channel_id": None,
    "confess_channel_id": None
}


def load_db():
    """Đọc database và giữ nguyên dữ liệu đã lưu."""
    data = DEFAULT_DB.copy()

    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)

            if isinstance(saved_data, dict):
                data.update(saved_data)

        except (json.JSONDecodeError, OSError) as e:
            print(f"[DATABASE ERROR] {e}")

    # Đảm bảo các kho GIF luôn là danh sách.
    for command_name in GIF_COMMANDS:
        if not isinstance(data.get(command_name), list):
            data[command_name] = []

    return data


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_gif_url(item):
    """Đọc cả định dạng GIF cũ (string) lẫn định dạng mới (dict)."""
    if isinstance(item, dict):
        url = item.get("url", "")
    else:
        url = str(item) if item else ""

    if not isinstance(url, str):
        return None

    url = url.strip()

    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None

    return url


def get_random_gif(command_name):
    """Lấy ngẫu nhiên một GIF hợp lệ; không có GIF thì trả về None."""
    db = load_db()
    gifs = db.get(command_name.lower(), [])

    valid_gifs = []

    for item in gifs:
        gif_url = get_gif_url(item)
        if gif_url:
            valid_gifs.append(gif_url)

    return random.choice(valid_gifs) if valid_gifs else None


def set_embed_gif(embed, command_name):
    """Chỉ đặt ảnh khi kho có URL hợp lệ, tránh lỗi embed."""
    gif_url = get_random_gif(command_name)

    if gif_url:
        try:
            embed.set_image(url=gif_url)
        except (discord.HTTPException, ValueError):
            pass

    return embed


def is_valid_http_url(url):
    if not url:
        return False

    try:
        parsed = urlparse(url.strip())
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
        )
    except (ValueError, AttributeError):
        return False


@bot.event
async def on_ready():
    print(
        f'Logged in as {bot.user} - '
        'Gothic Sanctum Fully Restored & Operational!'
    )

    if not daily_weather_broadcast.is_running():
        daily_weather_broadcast.start()


def is_admin_or_staff():
    async def predicate(ctx):
        return (
            ctx.author.guild_permissions.manage_messages
            or ctx.author.guild_permissions.administrator
        )

    return commands.check(predicate)


def parse_time(time_str: str):
    time_str = time_str.lower()
    match = re.match(r"^(\d+)([smhd])$", time_str)

    if not match:
        return None

    val, unit = int(match.group(1)), match.group(2)

    if unit == 's':
        return datetime.timedelta(seconds=val)
    if unit == 'm':
        return datetime.timedelta(minutes=val)
    if unit == 'h':
        return datetime.timedelta(hours=val)
    if unit == 'd':
        return datetime.timedelta(days=val)

    return None


# =========================================================
# GIF MANAGER
# Cách dùng:
# l gif add dayai + đính kèm GIF
# l gif add dayai https://example.com/example.gif
# l gif list dayai
# l gif remove dayai 1
# =========================================================

@bot.command(name='gif')
@is_admin_or_staff()
async def manage_gif(
    ctx,
    action: str = None,
    cmd_name: str = None,
    *,
    url: str = None
):
    # Lấy URL attachment trước khi xóa tin nhắn.
    attachment_url = None

    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        attach
