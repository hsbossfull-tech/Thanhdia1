
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
        attachment_url = attachment.url

    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.HTTPException):
        pass

    db = load_db()

    if not action or action.lower() not in ("add", "list", "remove"):
        embed = discord.Embed(
            title="<:caccc:1547883345944387594> "
                  "**Kho lưu trữ GIF Hắc Ám · Hướng dẫn**",
            description=(
                "† Thêm GIF bằng link:\n"
                "`l gif add <lệnh> <link>`\n\n"
                "† Thêm GIF bằng tệp đính kèm:\n"
                "`l gif add <lệnh>` rồi đính kèm GIF\n\n"
                "† Xem kho GIF:\n"
                "`l gif list <lệnh>`\n\n"
                "† Xóa GIF theo số thứ tự:\n"
                "`l gif remove <lệnh> <số_thứ_tự>`"
            ),
            color=COLOR_MAIN
        )
        embed.set_footer(text="Gothic Sanctum · GIF Manager")
        await ctx.send(embed=embed)
        return

    cmd_name = cmd_name.lower().strip() if cmd_name else ""
    action = action.lower()

    if cmd_name not in GIF_COMMANDS:
        await ctx.send(
            "❌ Lệnh này chưa được hỗ trợ trong kho GIF.\n"
            "Dùng `l gif` để xem hướng dẫn."
        )
        return

    gifs = db[cmd_name]

    if action == "add":
        gif_url = attachment_url or (url.strip() if url else None)

        if not gif_url:
            await ctx.send(
                "❌ Hãy gửi link GIF hoặc đính kèm tệp "
                "trong cùng tin nhắn với lệnh."
            )
            return

        if not is_valid_http_url(gif_url):
            await ctx.send(
                "❌ Link không hợp lệ. Hãy dùng đường dẫn bắt đầu "
                "bằng `https://` hoặc `http://`."
            )
            return

        # Lưu theo dạng dict để hỗ trợ mở rộng sau này.
        gifs.append({"url": gif_url})
        save_db(db)

        embed = discord.Embed(
            title="<:emoji_16:1547886424760520744> "
                  "**Đã nạp linh lực vào kho · GIF Added**",
            description=(
                f"Đã thêm thành công 1 GIF vào lệnh `l {cmd_name}`.\n"
                f"Tổng số GIF hiện tại: **{len(gifs)}**"
            ),
            color=COLOR_MAIN
        )

        embed.set_image(url=gif_url)
        embed.set_footer(text="Gothic Sanctum · Storage")
        await ctx.send(embed=embed)

    elif action == "list":
        if not gifs:
            await ctx.send(
                f"📭 Lệnh `l {cmd_name}` chưa có GIF nào trong kho."
            )
            return

        lines = []

        for index, item in enumerate(gifs, 1):
            gif_url = get_gif_url(item)

            if gif_url:
                lines.append(f"**{index}.** [Link GIF]({gif_url})")
            else:
                lines.append(f"**{index}.** Link không hợp lệ")

        embed = discord.Embed(
            title=(
                f"<a:emoji_24:1547899636222533682> "
                f"**Kho GIF của lệnh: `l {cmd_name}`**"
            ),
            description="\n".join(lines),
            color=COLOR_MAIN
        )
        embed.set_footer(text=f"Tổng số: {len(gifs)} GIF")
        await ctx.send(embed=embed)

    elif action == "remove":
        try:
            index = int(url) - 1

            if index < 0 or index >= len(gifs):
                raise IndexError

            gifs.pop(index)
            save_db(db)

            await ctx.send(
                f"🔥 Đã xóa GIF số {index + 1} "
                f"khỏi lệnh `l {cmd_name}`."
            )

        except (ValueError, TypeError, IndexError):
            await ctx.send(
                "❌ Số thứ tự không hợp lệ. "
                "Hãy kiểm tra bằng `l gif list <lệnh>`."
            )


# =========================================================
# TRỢ GIÚP
# =========================================================

@bot.command(name='trogiup', aliases=['help', 'h'])
@is_admin_or_staff()
async def trogiup(ctx):
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.HTTPException):
        pass

    embed = discord.Embed(
        title="<:goth_cross:1557438198378930246> "
              "𝔊𝔬𝔱𝔥𝔦𝔠 𝔖𝔞𝔫𝔠𝔱𝔲𝔪 · "
              "𝖲𝔞𝼼𝗋𝔢ᴅ 𝖢𝔬𝔪𝔪𝔞𝗇ْد𝘴 "
              "<a:black_butterflies:1556339019418443988>",
        description=(
            "*(Ấn hiệu quyền năng dành riêng cho thánh địa)*\n\n"
            "† `l đày ải` / `l dayai` @user [lý do] : "
            "Tuyên án đày ải (Admin)\n"
            "† `l xá tội` / `l xatoi` [UserID] : "
            "Ân xá lưu vong (Admin)\n"
            "† `l trục xuất` / `l trucxuat` @user [lý do] : "
            "Trục xuất khỏi cõi thiêng (Admin)\n"
            "† `l cấm khẩu` / `l camkhau` @user [thời_gian] : "
            "Giam cầm khẩu ải (Admin)\n"
            "† `l ân xá` / `l anxa` @user : "
            "Giải nguyền thanh âm (Admin)\n"
            "† `l gif add <lệnh> <link>` : "
            "Nạp kho GIF ngẫu nhiên (Admin)\n"
            "† `l gif add <lệnh>` + tệp GIF : "
            "Thêm GIF đính kèm (Admin)\n"
            "† `l gif list <lệnh>` : Xem kho GIF (Admin)\n"
            "† `l gif remove <lệnh> <số>` : Xóa GIF (Admin)\n"
            "† `l lock` / `l unlock` : "
            "Khóa / Mở cửa thánh điện (Admin)\n"
            "† `l snipe` : Soi rọi 20 bóng ma ngôn từ (Admin)\n"
            "† `l info` [@user] : Soi thấu linh hồn (Admin)\n"
            "† `l si` : Soi thấu toàn cảnh thánh địa & vai trò (Admin)\n"
            "† `l xoa [num]` : Thiêu rụi tàn dư tin nhắn (Admin)\n"
            "† `l announce` [nội dung] : Ban hành sắc lệnh (Admin)\n"
            "† `l afk [lý do]` : Linh hồn nhập định (Member & Admin)\n"
            "† `l roll` : Đổ xí ngầu định mệnh 1-100 (Member & Admin)\n"
            "† `l say [nội dung]` : Tiếng vọng hư vô (Member & Admin)\n"
            "† `l weather [thành phố]` : Tiên tri khí tượng (Member & Admin)\n"
            "† `l av` / `l avt` [@user] : Soi thấu dung mạo (Member & Admin)"
        ),
        color=COLOR_MAIN
    )

    set_embed_gif(embed, "trogiup")
    embed.set_footer(text="Gothic Sanctum · System Commands (Admin Only)")
    await ctx.send(embed=embed)


# =========================================================
# MESSAGE HANDLER
# =========================================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    db = load_db()

    if not message.guild:
        confess_channel_id = db.get("confess_channel_id")

        if confess_channel_id:
            channel = bot.get_channel(confess_channel_id)

            if channel:
                embed = discord.Embed(
                    title="<a:005:1556756974438326362> "
                          "**Bức thư nùng cõi âm · Lời thú tội ẩn giấu**",
                    description=(
                        f"> *\"{message.content}\"*\n\n"
                        "*Một linh hồn vừa rũ bỏ gánh nặng phàm trần, "
                        "lén lút thả vào hư vô dòng tâm sự...*"
                    ),
                    color=COLOR_MAIN
                )

                set_embed_gif(embed, "confess")
                embed.set_footer(text="Gothic Sanctum · Confession Ẩn Danh")

                try:
                    msg_sent = await channel.send(embed=embed)

                    for emoji in ["🖤", "🕯️", "🥀"]:
                        await msg_sent.add_reaction(emoji)

                    await message.author.send(
                        "🦇 *Bức thư của ngươi đã được gió lạnh "
                        "cuốn trôi vào hòm thư ẩn danh của thánh địa.*"
                    )

                except discord.HTTPException as e:
                    print(f"[CONFESS ERROR] {e}")

            else:
                await message.author.send(
                    "❌ Kênh thú tội không còn tồn tại hoặc bot "
                    "không truy cập được."
                )
        else:
            await message.author.send(
                "❌ *Hòm thư của thánh địa chưa được định vị "
                "(Staff chưa thiết lập `l setconfess`).*"
            )

        return

    content = message.content
    author = message.author
    channel = message.channel

    is_staff = (
        author.guild_permissions.manage_messages
        or author.guild_permissions.administrator
    )

    if not is_staff:
        now = datetime.datetime.now().timestamp()
        user_messages = spam_tracker[author.id]
        user_messages.append(now)

        if (
            len(user_messages) >= 10
            and user_messages[-1] - user_messages[0] <= 5
        ):
            spam_warn_count[author.id] += 1
            warns = spam_warn_count[author.id]
            user_messages.clear()

            try:
                await message.delete()
            except discord.HTTPException:
                pass

            if warns == 1 or warns == 2:
                msg = await channel.send(
                    f"<:A_heartbroken002:1554569090717450281> "
                    f"**Cảnh cáo Spam ({warns}/2):** `{author.name}` - "
                    "Đừng làm hoen ố sự tĩnh lặng nơi đây bằng bão chữ!"
                )
                await msg.delete(delay=6)

            elif warns == 3:
                try:
                    await author.timeout(
                        datetime.timedelta(minutes=2),
                        reason="Spam liên tục · Vi phạm lần 3"
                    )
                    msg = await channel.send(
                        f"<:tpt12:1556339039173476407> "
                        f"**Giam cầm khẩu ải (2 phút):** `{author.name}` "
                        "đã bị phong ấn thanh âm vì cố chấp spam!"
                    )
                    await msg.delete(delay=8)
                except discord.HTTPException:
                    pass

            else:
                try:
                    await author.timeout(
                        datetime.timedelta(hours=1),
                        reason="Spam liên tục · Vi phạm từ lần 4"
                    )
                    msg = await channel.send(
                        f"<a:xxx043:1558850313258147925> "
                        f"**Trục xuất vắng lặng (1 giờ):** `{author.name}` "
                        "đã bị đày ải vào ngục tối 1 tiếng "
                        "vì tái phạm spam nhiều lần!"
                    )
                    await msg.delete(delay=8)
                except discord.HTTPException:
                    pass

            return

    if (
        author.id in afk_storage
        and not content.lower().startswith(('l afk', 'lafk'))
    ):
        afk_data = afk_storage.pop(author.id)

        passed = int(
            (datetime.datetime.now() - afk_data["time"]).total_seconds()
            // 60
        )

        tags_list = afk_data["tags"]

        tags_text = (
            "".join([
                f"* † **{tag['author']}**: *\"{tag['content']}\"* — "
                f"[Tới tin nhắn]({tag['jump_url']})\n"
                for tag in tags_list
            ])
            if tags_list
            else "*Không một bóng ma nào dám quấy rền giấc ngủ của ngươi.*"
        )

        embed = discord.Embed(
            title="<a:006:1556339034425524314> "
                  "**Thức giấc từ bóng tối · Báo cáo bóng ma**",
            description=(
                f"Màn đêm tan biến. Linh hồn của `{author.name}` "
                f"đã tỉnh giấc sau **{passed} phút** "
                "đắm chìm trong hư vô.\n\n"
                "🦇 **Danh sách những kẻ đã réo gọi tên ngươi:**\n"
                f"{tags_text}"
            ),
            color=COLOR_MAIN
        )

        set_embed_gif(embed, "afk")
        embed.set_footer(text="Gothic Sanctum · AFK Logger")
        await channel.send(embed=embed)

    for mention in message.mentions:
        if mention.id in afk_storage and mention.id != author.id:
            a_data = afk_storage[mention.id]

            passed = int(
                (datetime.datetime.now() - a_data["time"]).total_seconds()
                // 60
            )

            afk_storage[mention.id]["tags"].append({
                "author": author.name,
                "content": content[:100],
                "jump_url": message.jump_url
            })

            embed = discord.Embed(
                description=(
                    f"🕯️ **Chớ quấy rền:** `{mention.name}` hiện đang "
                    f"chìm trong hư vô từ `{passed} phút trước` "
                    f"(Lý do: *{a_data['reason']}*)."
                ),
                color=COLOR_MAIN
            )

            warn_tag = await channel.send(embed=embed)
            await warn_tag.delete(delay=6)

    if not is_staff:
        if re.search(
            r'(discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)',
            content,
            re.IGNORECASE
        ):
            try:
                await message.delete()
                msg = await channel.send(
                    f"<:caccc:1547883345944387594> "
                    f"**Vi phạm giáo điều:** `{author.name}` - "
                    "Không được phát tán liên kết dịch chuyển!"
                )
                await msg.delete(delay=5)
                return
            except discord.HTTPException:
                pass

        if any(
            domain in content.lower()
            for domain in ['bit.ly', 'tinyurl.com', 'rb.gy', 'cutt.ly']
        ):
            try:
                await message.delete()
                msg = await channel.send(
                    f"<:emoji_16:1547886424760520744> "
                    f"**Vi phạm giáo điều:** `{author.name}` - "
                    "Link rút gọn bị cấm tiệt tại cõi này!"
                )
                await msg.delete(delay=5)
                return
            except discord.HTTPException:
                pass

    await bot.process_commands(message)


# =========================================================
# MODERATION COMMANDS
# =========================================================

@bot.command(name='dayai', aliases=['đàyải', 'ban'])
@is_admin_or_staff()
async def mod_dayai(
    ctx,
    member: discord.Member = None,
    *,
    reason="Kẻ ngoại đạo làm hoen ố thánh điện"
):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    if not member:
        msg = await ctx.send(
            "❌ *Hãy chỉ định rõ linh hồn phàm trần cần đày ải.*"
        )
        await msg.delete(delay=8)
        return

    await member.ban(reason=reason)

    desc = (
        "_Nguyện cầu cho linh hồn bạn lạc lối ở một thế giới khác_"
        "<:8ctombstone:1557437899820109985> "
        f"({ctx.author.mention} đã đày ải {member.mention})"
    )

    embed = discord.Embed(description=desc, color=COLOR_MAIN)
    set_embed_gif(embed, "dayai")

    msg = await ctx.send(embed=embed)
    await msg.delete(delay=8)


@bot.command(name='trucxuat', aliases=['trụcxuất', 'kick'])
@is_admin_or_staff()
async def mod_trucxuat(
    ctx,
    member: discord.Member = None,
    *,
    reason="Khước từ sự hiện diện"
):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    if not member:
        msg = await ctx.send("❌ *Hãy chỉ định rõ linh hồn cần trục xuất.*")
        await msg.delete(delay=8)
        return

    await member.kick(reason=reason)

    desc = (
        "_Cánh cổng thánh đường mở ra để tiễn bạn rời khỏi cõi này_"
        "<a:emoji_63:1548185249492508722> "
        f"({ctx.author.mention} đã trục xuất {member.mention})"
    )

    embed = discord.Embed(description=desc, color=COLOR_MAIN)
    set_embed_gif(embed, "trucxuat")

    msg = await ctx.send(embed=embed)
    await msg.delete(delay=8)


@bot.command(name='camkhau', aliases=['cấmkhẩu', 'mute'])
@is_admin_or_staff()
async def mod_camkhau(
    ctx,
    member: discord.Member = None,
    duration_str: str = "24h"
):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    if not member:
        msg = await ctx.send("❌ *Hãy chỉ định rõ linh hồn cần cấm khẩu.*")
        await msg.delete(delay=8)
        return

    delta = parse_time(duration_str)

    if not delta:
        delta = datetime.timedelta(days=1)

    try:
        await member.timeout(delta, reason="Phong ấn khẩu ải")

        desc = (
            "_Hơi thở của ngươi làm vấy bẩn sự tôn nghiêm nơi này "
            "thật hôi hám câm ngay_"
            "<:7crs:1556756950144786543> "
            f"({ctx.author.mention} đã cấm khẩu "
            f"{member.mention} trong {duration_str})"
        )

        embed = discord.Embed(description=desc, color=COLOR_MAIN)
        set_embed_gif(embed, "camkhau")

        msg = await ctx.send(embed=embed)
        await msg.delete(delay=8)

    except Exception as e:
        msg = await ctx.send(f"❌ Lỗi phong ấn: {e}")
        await msg.delete(delay=8)


@bot.command(name='anxa', aliases=['ânxá', 'unmute'])
@is_admin_or_staff()
async def mod_anxa(ctx, member: discord.Member = None):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    if not member:
        msg = await ctx.send("❌ *Hãy chỉ định rõ linh hồn cần giải nguyền.*")
        await msg.delete(delay=8)
        return

    try:
        await member.timeout(None, reason="Giải nguyền thanh âm")

        desc = (
            "_Ánh sáng vấy máu từ ngọn tháp đen đã rọi rứa. "
            "Lời nguyền câm lặng bị xé toạc_"
            "<:emoji_180:1555786447653568622> "
            f"({ctx.author.mention} đã ân xá {member.mention})"
        )

        embed = discord.Embed(description=desc, color=COLOR_MAIN)
        set_embed_gif(embed, "anxa")

        msg = await ctx.send(embed=embed)
        await msg.delete(delay=8)

    except Exception as e:
        msg = await ctx.send(f"❌ Lỗi giải ấn: {e}")
        await msg.delete(delay=8)


@bot.command(name='xatoi', aliases=['xátội', 'unban'])
@is_admin_or_staff()
async def mod_xatoi(ctx, user_id: int = None):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    if not user_id:
        msg = await ctx.send("❌ *Hãy cung cấp UserID cần xá tội.*")
        await msg.delete(delay=8)
        return

    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason="Ân xá biên giới")

        desc = (
            "_Ánh sáng khoan dung đã chạm tới vùng biên viễn_"
            "<:emoji_28:1556761089331429432> "
            f"({ctx.author.mention} đã xá tội cho ID `{user_id}`)"
        )

        embed = discord.Embed(description=desc, color=COLOR_MAIN)
        set_embed_gif(embed, "xatoi")

        msg = await ctx.send(embed=embed)
        await msg.delete(delay=8)

    except Exception as e:
        msg = await ctx.send(f"❌ Lỗi xá tội: {e}")
        await msg.delete(delay=8)


@bot.command(name='lock')
@is_admin_or_staff()
async def mod_lock(ctx):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    try:
        await ctx.channel.set_permissions(
            ctx.guild.default_role,
            send_messages=False,
            reason="Khóa kênh"
        )

        embed = discord.Embed(
            description=(
                f"<a:xxx043:1558850313258147925> "
                f"`{ctx.author.name}` đã yểm ấn phong tỏa kênh này. "
                "Mọi lời phàm trần phải im bặt..."
            ),
            color=COLOR_MAIN
        )

        set_embed_gif(embed, "lock")
        msg = await ctx.send(embed=embed)
        await msg.delete(delay=8)

    except Exception as e:
        msg = await ctx.send(f"❌ Lỗi khóa kênh: {e}")
        await msg.delete(delay=8)


@bot.command(name='unlock')
@is_admin_or_staff()
async def mod_unlock(ctx):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    try:
        await ctx.channel.set_permissions(
            ctx.guild.default_role,
            send_messages=True,
            reason="Mở cửa thánh điện"
        )

        embed = discord.Embed(
            description=(
                f"<a:black_butterflies:1556339019418443988> "
                f"`{ctx.author.name}` đã mở cửa thánh điện. "
                "Hơi thở sự sống tuôn trào trở lại..."
            ),
            color=COLOR_MAIN
        )

        set_embed_gif(embed, "unlock")
        msg = await ctx.send(embed=embed)
        await msg.delete(delay=8)

    except Exception as e:
        msg = await ctx.send(f"❌ Lỗi mở kênh: {e}")
        await msg.delete(delay=8)


@bot.command(name='announce', aliases=['thongbao'])
@is_admin_or_staff()
async def mod_announce(ctx, *, text: str):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    embed = discord.Embed(
        title="<a:xxx043:1558850313258147925> "
              "𝖲ắ𝖈 𝖑ệ𝖓𝖍 𝖙ừ 𝖙𝖍á𝖓𝖥 đị𝖆",
        description=text,
        color=COLOR_MAIN
    )

    set_embed_gif(embed, "announce")
    embed.set_footer(
        text=f"Gothic Sanctum · Thông cáo chính thức bởi {ctx.author.name}"
    )

    await ctx.send(embed=embed)


# =========================================================
# SNIPE
# =========================================================

class SnipeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="Bỏ qua tin nhắn",
        style=discord.ButtonStyle.secondary,
        emoji="💀"
    )
    async def dismiss_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not (
            interaction.user.guild_permissions.manage_messages
            or interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "❌ *Ngươi không có quyền khép lại gương soi này!*",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass


@bot.command(name='snipe')
@is_admin_or_staff()
async def mod_snipe(ctx):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    channel_id = ctx.channel.id

    if channel_id not in snipe_storage or not snipe_storage[channel_id]:
        await ctx.send(
            "📭 *Hư vô bao trùm, không một bóng ma ngôn từ nào sót lại.*"
        )
        return

    items = list(snipe_storage[channel_id])
    desc_lines = []

    for idx, data in enumerate(reversed(items), 1):
        content_preview = (
            data["content"]
            if data["content"]
            else "[Chỉ chứa hình ảnh/tệp vô hình]"
        )

        desc_lines.append(
            f"**{idx}. [{data['time']}] {data['author']}:** "
            f"{content_preview}"
        )

    embed = discord.Embed(
        title="<:A_heartbroken002:1554569090717450281> "
              "𝔅ó𝔫𝔤 𝔪𝔞 𝔫𝔤ô𝔫 𝔱ừ "
              "𝓿ừ𝔞 ᴛʜứᴄ ɢɪấᴄ (20 ᴛàɴ dư)",
        description="\n".join(desc_lines),
        color=COLOR_INFO
    )

    set_embed_gif(embed, "snipe")
    await ctx.send(embed=embed, view=SnipeView())


# =========================================================
# USER INFO / SERVER INFO
# =========================================================

@bot.command(name='info', aliases=['userinfo'])
@is_admin_or_staff()
async def mod_userinfo(ctx, member: discord.Member = None):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    member = member or ctx.author
    roles = [
        role.mention for role in member.roles
        if role != ctx.guild.default_role
    ]

    roles_str = ", ".join(roles) if roles else "Không có tước hiệu"

    embed = discord.Embed(
        title=(
            f"<:goth_cross:1557438198378930246> "
            f"𝖲𝔬𝔦 𝗍𝍍ấ𝗎 𝖑𝖎𝖓𝍠 𝍕ồ𝖓 · {member.name}"
        ),
        color=COLOR_INFO
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    set_embed_gif(embed, "info")

    embed.add_field(
        name="† Định danh (ID)",
        value=f"`{member.id}`",
        inline=True
    )

    embed.add_field(
        name="† Bước chân vào thánh địa",
        value=(
            f"<t:{int(member.joined_at.timestamp())}:R>"
            if member.joined_at else "Not found"
        ),
        inline=True
    )

    embed.add_field(
        name="† Ngày hình thành linh hồn",
        value=f"<t:{int(member.created_at.timestamp())}:R>",
        inline=True
    )

    embed.add_field(
        name="† Tước hiệu trong thánh điện",
        value=roles_str,
        inline=False
    )

    await ctx.send(embed=embed)


@bot.command(name='si', aliases=['serverinfo', 'thanhdia'])
@is_admin_or_staff()
async def mod_si(ctx):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    guild = ctx.guild

    roles = [
        role.mention for role in reversed(guild.roles)
        if role != guild.default_role
    ]

    role_pairs = [
        f"{roles[i]}  |  {roles[i + 1]}"
        if i + 1 < len(roles)
        else roles[i]
        for i in range(0, len(roles), 2)
    ]

    roles_formatted = ""

    for pair in role_pairs:
        if len(roles_formatted) + len(pair) + 1 > 950:
            roles_formatted += "\n*...và nhiều vai trò khác*"
            break

        roles_formatted += pair + "\n"

    if not roles_formatted:
        roles_formatted = "Không có vai trò riêng"

    embed = discord.Embed(
        title=(
            f"<:caccc:1547883345944387594> "
            f"**𝔖𝔬𝔦 𝔱𝖍ấ𝔲 𝔱𝖍á𝔫𝔥 đị𝔞 · {guild.name}**"
        ),
        color=COLOR_INFO
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    set_embed_gif(embed, "si")

    embed.add_field(
        name="👑 Chủ sở hữu",
        value=f"{guild.owner.mention}" if guild.owner else "Không rõ",
        inline=True
    )

    embed.add_field(
        name="🆔 Server ID",
        value=f"{guild.id}",
        inline=True
    )

    embed.add_field(
        name="👥 Linh hồn trú ngụ",
        value=f"**{guild.member_count}** thành viên",
        inline=True
    )

    embed.add_field(
        name="📜 Ngày khởi tạo",
        value=f"<t:{int(guild.created_at.timestamp())}:D>",
        inline=True
    )

    embed.add_field(
        name="🔮 Cấp độ Boost",
        value=(
            f"Level {guild.premium_tier} "
            f"({guild.premium_subscription_count} Boosts)"
        ),
        inline=True
    )

    embed.add_field(
        name="💬 Số lượng kênh",
        value=f"{len(guild.channels)} kênh",
        inline=True
    )

    embed.add_field(
        name="🎭 Bảng Vai Trò (Roles)",
        value=roles_formatted,
        inline=False
    )

    embed.set_footer(text="Gothic Sanctum · Server Inspection")

    await ctx.send(embed=embed, view=SnipeView())


# =========================================================
# CLEAR MESSAGES
# =========================================================

@bot.command(name='xoa', aliases=['clear', 'purge'])
@is_admin_or_staff()
async def mod_xoa(ctx, amount: int = 5):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    amount = max(1, min(amount, 100))
    deleted = await ctx.channel.purge(limit=amount)

    msg = await ctx.send(
        f"🔥 *Đã dùng lửa thánh thiêu rụi "
        f"{len(deleted)} vệt bụi ngôn từ.*"
    )

    await msg.delete(delay=3)


# =========================================================
# AFK
# =========================================================

@bot.command(name='afk')
async def mod_afk(ctx, *, reason: str = "Linh hồn chìm vào hư vô"):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    afk_storage[ctx.author.id] = {
        "reason": reason,
        "time": datetime.datetime.now(),
        "tags": []
    }

    embed = discord.Embed(
        description=(
            f"🕯️ **Nhập định:** `{ctx.author.name}` "
            "đã chìm vào hư vô...\n"
            f"*Lý do:* {reason}"
        ),
        color=COLOR_MAIN
    )

    set_embed_gif(embed, "afk")
    await ctx.send(embed=embed)


# =========================================================
# ROLL / SAY
# =========================================================

@bot.command(name='roll')
async def mod_roll(ctx):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    luck = random.randint(1, 100)

    embed = discord.Embed(
        title="<:emoji_16:1547886424760520744> "
              "**Xúc sắc định mệnh · Roll**",
        description=(
            f"Linh hồn `{ctx.author.name}` gieo quẻ xí ngầu vực thẳm "
            "và nhận được điểm số linh lực:\n\n"
            f"# 🔮 **{luck} / 100**"
        ),
        color=COLOR_FUN
    )

    embed.set_footer(text="Gothic Sanctum · Destiny Roll")
    await ctx.send(embed=embed)


@bot.command(name='say')
async def mod_say(ctx, *, text: str = None):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    if not text:
        return

    embed = discord.Embed(
        description=f"<a:emoji_24:1547899636222533682> *\"{text}\"*",
        color=COLOR_FUN
    )

    embed.set_footer(text=f"Tiếng vọng hư vô từ {ctx.author.name}")
    await ctx.send(embed=embed)


# =========================================================
# WEATHER
# =========================================================

@bot.command(name='weather', aliases=['thoitiet'])
async def mod_weather(ctx, *, city: str = "Ho Chi Minh"):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    api_key = "bd5e378503939ddaee76f12ad7a97608"

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&units=metric&lang=vi"
    )

    try:
        response = requests.get(url, timeout=10).json()

        if response.get("cod") != 200:
            await ctx.send(
                "❌ *Khí tượng đài ở vùng đất này "
                "không tồn tại trong cõi thực.*"
            )
            return

        temp = response["main"]["temp"]
        desc = response["weather"][0]["description"]
        humidity = response["main"]["humidity"]
        wind = response["wind"]["speed"]
        loc = response["name"]

        embed = discord.Embed(
            title=(
                f"<:goth_cross:1557438198378930246> "
                f"**Sấm truyền khí tượng · {loc}**"
            ),
            description=(
                "Quan sát bầu trời từ ngọn tháp hắc ám, "
                "tầng mây tại đây đang mang theo điềm báo:\n\n"
                f"† **Nhiệt độ hiện tại:** `{temp}°C`\n"
                f"† **Trạng thái:** *{desc.capitalize()}*\n"
                f"† **Độ ẩm cõi âm:** `{humidity}%`\n"
                f"† **Sức gió vực thẳm:** `{wind} m/s`"
            ),
            color=COLOR_WEATHER
        )

        set_embed_gif(embed, "weather")
        embed.set_footer(
            text=f"Khí tượng thực tế: {temp}°C, {desc.capitalize()}"
        )

        await ctx.send(embed=embed)

    except Exception as e:
        print(f"[WEATHER API ERROR]: {e}")
        await ctx.send(f"❌ Lỗi thiên văn đài: {e}")


@tasks.loop(time=time(hour=6, minute=0, second=0))
async def daily_weather_broadcast():
    db = load_db()
    weather_channel_id = db.get("weather_channel_id")

    if weather_channel_id is None:
        return

    channel = bot.get_channel(weather_channel_id)

    if not channel:
        return

    city = "Ho Chi Minh"
    api_key = "bd5e378503939ddaee76f12ad7a97608"

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&units=metric&lang=vi"
    )

    try:
        res = requests.get(url, timeout=10).json()

        if res.get("cod") == 200:
            temp = res["main"]["temp"]
            desc = res["weather"][0]["description"]

            embed = discord.Embed(
                title=(
                    "<:goth_cross:1557438198378930246> "
                    "**Sắc lệnh khí tượng đầu ngày · "
                    "Tháp quan sát hắc ám**"
                ),
                description=(
                    "Đúng thời khắc chuyển giao (6:00 AM), "
                    "ngọn tháp cổ xin gửi điềm báo thời tiết hôm nay:\n\n"
                    f"† **Nhiệt độ:** `{temp}°C`\n"
                    f"† **Trạng thái:** *{desc.capitalize()}*\n"
                    "*Hãy cẩn trọng bước chân khi hành khất ngoài phàm thế!*"
                ),
                color=COLOR_WEATHER
            )

            set_embed_gif(embed, "weather")
            embed.set_footer(
                text=f"Khí tượng thực tế: {temp}°C, {desc.capitalize()}"
            )

            await channel.send(embed=embed)

    except Exception as e:
        print(f"[WEATHER BROADCAST EXCEPTION]: {e}")


# =========================================================
# WEATHER / CONFESSION CHANNEL SETUP
# =========================================================

@bot.command(name='setweather')
@is_admin_or_staff()
async def set_weather_channel(
    ctx,
    channel: discord.TextChannel = None
):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    db = load_db()
    channel = channel or ctx.channel
    db["weather_channel_id"] = channel.id
    save_db(db)

    embed = discord.Embed(
        description=(
            f"<:caccc:1547883345944387594> "
            f"**Đã định vị tháp quan sát:** Kênh `{channel.name}` "
            "được chọn làm nơi phát sấm truyền khí tượng tự động "
            "vào lúc **6:00 sáng** hàng ngày."
        ),
        color=COLOR_MAIN
    )

    await ctx.send(embed=embed)


@bot.command(name='setconfess')
@is_admin_or_staff()
async def set_confess_channel(
    ctx,
    channel: discord.TextChannel = None
):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    db = load_db()
    channel = channel or ctx.channel
    db["confess_channel_id"] = channel.id
    save_db(db)

    embed = discord.Embed(
        description=(
            f"<a:black_butterflies:1556339019418443988> "
            f"**Đã yểm ấn hòm thư:** Kênh `{channel.name}` "
            "được chọn làm nơi thu gom mọi lời thú tội ẩn danh."
        ),
        color=COLOR_MAIN
    )

    await ctx.send(embed=embed)


# =========================================================
# AVATAR
# =========================================================

@bot.command(name='av', aliases=['avt', 'avatar'])
async def mod_avatar(ctx, member: discord.Member = None):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

    member = member or ctx.author

    embed = discord.Embed(
        title=(
            f"<a:006:1556339034425524314> "
            f"𝖁ẻ 𝖉𝖚𝖓𝍠àm 𝖙𝖈𝖍rà𝖓 · {member.name}"
        ),
        description=(
            "_Dung mạo phàm trần phản chiếu "
            "qua gương soi hắc ám..._"
        ),
        color=COLOR_INFO
    )

    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)


# =========================================================
# SNIPE STORAGE
# =========================================================

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return

    snipe_storage[message.channel.id].append({
        "content": message.content,
        "author": message.author.name,
        "avatar": message.author.display_avatar.url,
        "time": datetime.datetime.now().strftime("%H:%M")
    })


# =========================================================
# BOT START
# =========================================================

TOKEN = os.environ.get('DISCORD_TOKEN')

if not TOKEN:
    raise RuntimeError(
        TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
