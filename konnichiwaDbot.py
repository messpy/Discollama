#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
import datetime

# ===== Bot環境設定 =====
TOKEN = os.getenv("DISCORD_BOT_AI")          # export DISCORD_BOT_AI="xxx"
MODEL = "qwen2.5:0.5b-instruct"              # 軽量モデルを直書き
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434

# ===== 連投制限（全チャンネル対象）=====
POSTS_PER_WINDOW = 4      # 1分に許可する投稿数
WINDOW_SECONDS = 10
_user_window: dict[int, list[float]] = {}  # user_id -> [timestamps]

# ===== 違反のエスカレーション（Kick / Ban）=====
VIOLATION_WINDOW  = 10 * 60   # 10分間の違反数で判定
KICK_AFTER_DELETES = 3        # 10分で3回削除 → Kick
BAN_AFTER_DELETES  = 6        # 10分で5回削除 → Ban
_user_violations: dict[int, list[float]] = {}  # user_id -> [deleted_timestamps]

# ===== ログ送信先（ギルドごとに“bot”系チャンネルを自動検出）=====
_guild_log_channel: dict[int, int] = {}   # guild_id -> channel_id

# URL抽出用
URL_RE = re.compile(r"https?://\S+")

# ===== Discord Intents（最小）=====
intents = discord.Intents.none()
intents.guilds = True
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== Ollama 起動確認 =====
async def _http_ready_check(host, port, path="/api/version") -> bool:
    try:
        reader, writer = await asyncio.open_connection(host, port)
        req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        writer.write(req.encode()); await writer.drain()
        data = await reader.read(4096)
        writer.close(); await writer.wait_closed()
        return b"version" in data.lower()
    except Exception:
        return False

async def ensure_ollama_serve(timeout_sec=20):
    if await _http_ready_check(OLLAMA_HOST, OLLAMA_PORT):
        print("✅ ollama serve already running"); return
    print("🚀 starting ollama serve…")
    import subprocess, os as _os
    subprocess.Popen(
        ["nohup", "ollama", "serve"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=_os.setpgrp
    )
    for i in range(timeout_sec):
        await asyncio.sleep(1)
        if await _http_ready_check(OLLAMA_HOST, OLLAMA_PORT):
            print(f"✅ ollama ready ({i+1}s)"); return
    print("⚠️ ollama not responding, continuing…")

# ===== URL本文取得（サイズ/リダイレクト制限付き）=====
MAX_BYTES = 2_000_000  # 2MB
MAX_REDIRECTS = 3

async def fetch_url_text(url: str, maxlen: int = 4000) -> str:
    try:
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url, timeout=15, max_redirects=MAX_REDIRECTS) as res:
                total = 0; chunks = []
                async for chunk, _ in res.content.iter_chunks():
                    if not chunk: continue
                    total += len(chunk)
                    if total > MAX_BYTES:
                        chunks.append("cut big size...".encode("utf-8")); break
                    chunks.append(chunk)
                html = b"".join(chunks).decode(errors="ignore")
    except Exception as e:
        return f"（URL取得失敗: {e}）"
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    return text[:maxlen] + " ...（省略）" if len(text) > maxlen else text

# ===== Ollama 実行（30分タイムアウト・同時1本）=====
OLLAMA_SEMAPHORE = asyncio.Semaphore(1)

async def run_ollama(prompt: str, timeout: int = 1800) -> str:
    async with OLLAMA_SEMAPHORE:
        cmd = ["ollama", "run", MODEL]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return "❌ `ollama` が見つかりません。"
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(prompt.encode()), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return "⌛ Ollama 実行が30分超過しタイムアウトしました。"
        out = (stdout or b"").decode(errors="ignore").strip()
        err = (stderr or b"").decode(errors="ignore").strip()
        if proc.returncode != 0:
            return f"❌ Ollama エラー:\n```\n{err or out}\n```"
        return out or "(出力なし)"

# ===== ユーティリティ =====
def extract_after_mention(message: discord.Message) -> str:
    me = message.guild.me.mention if message.guild and message.guild.me else bot.user.mention
    return message.content.replace(me, "").strip()

def _now() -> float:
    return time.time()

def _prune(bucket: list[float], window: int):
    now = _now()
    while bucket and now - bucket[0] > window:
        bucket.pop(0)

def _short(s: str, n: int = 100) -> str:
    return s if len(s) <= n else s[:n] + "..."

async def send_log(guild: discord.Guild, text: str):
    """ギルド内の“bot”系テキストチャンネルへログ送信（見つからなければ標準出力のみ）"""
    if not guild:
        print(text); return
    chan_id = _guild_log_channel.get(guild.id)
    channel: discord.TextChannel | None = None
    if chan_id:
        channel = guild.get_channel(chan_id)
    if channel is None:
        # “bot”を含む名前のテキストチャンネルを探す（bot, bot-logs, bot_log 等）
        candidates = []
        for ch in guild.text_channels:
            name = (ch.name or "").lower()
            if "bot" in name:
                candidates.append(ch)
        # 名前が短い方が優先（"bot" > "bot-logs"）
        candidates.sort(key=lambda c: len(c.name))
        if candidates:
            channel = candidates[0]
            _guild_log_channel[guild.id] = channel.id
    if channel:
        try:
            await channel.send(text)
        except Exception as e:
            print(f"(log send failed in {guild.name}): {e}\n{text}")
    else:
        print(f"(no bot-channel in {guild.name if guild else 'DM'})\n{text}")

# ===== 連投制限（全チャンネル）=====
def is_rate_limited(user_id: int) -> bool:
    bucket = _user_window.setdefault(user_id, [])
    _prune(bucket, WINDOW_SECONDS)
    if len(bucket) >= POSTS_PER_WINDOW:
        return True
    bucket.append(_now())
    return False

# ===== 違反記録＆エスカレーション（残り回数も計算して通知）=====
async def record_violation_and_escalate(message: discord.Message):
    user = message.author
    guild = message.guild
    if not guild:
        return
    vbucket = _user_violations.setdefault(user.id, [])
    _prune(vbucket, VIOLATION_WINDOW)
    vbucket.append(_now())
    count = len(vbucket)

    remain_to_kick = max(0, KICK_AFTER_DELETES - count)
    remain_to_ban  = max(0, BAN_AFTER_DELETES  - count)

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base = (f"🔧 Anti-Spam Log\n"
            f"Guild: {guild.name}\n"
            f"User: {user} (ID:{user.id})\n"
            f"Action: Message deleted (violation count: {count})\n"
            f"Remaining: Kickまで{remain_to_kick} / Banまで{remain_to_ban}\n"
            f"Time: {ts}")
    await send_log(guild, base)

    # 閾値到達で制裁
    try:
        member = user if isinstance(user, discord.Member) else guild.get_member(user.id)
        if count >= BAN_AFTER_DELETES:
            if member:
                await guild.ban(member, reason="Spam/連投（自動Ban）", delete_message_seconds=0)
            else:
                await guild.ban(user, reason="Spam/連投（自動Ban）", delete_message_seconds=0)
            await send_log(guild, f"🚫 BANNED: {user} (ID:{user.id})  Reason: Spam/連投（自動Ban）")
        elif count >= KICK_AFTER_DELETES:
            if member:
                await member.kick(reason="Spam/連投（自動Kick）")
                await send_log(guild, f"👢 KICKED: {user} (ID:{user.id})  Reason: Spam/連投（自動Kick）")
            else:
                await send_log(guild, f"⚠️ Kick skipped (member not found): {user} (ID:{user.id})")
    except discord.Forbidden:
        await send_log(guild, f"❗制裁失敗（権限不足）: {user} (ID:{user.id})")
    except discord.HTTPException as e:
        await send_log(guild, f"❗制裁失敗（HTTP）: {e}")

# ===== メッセージ削除（標準出力＋Discordへも通知）=====
async def try_delete(message: discord.Message):
    user = message.author
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        await message.delete()
        line = f"[{ts}] Deleted => {user} (ID:{user.id}) | Content: {_short(message.content)}"
        print(line)
        if message.guild:
            await send_log(message.guild, f"🧹 Deleted message from {user} (ID:{user.id})\nContent: `{_short(message.content, 120)}`\nTime: {ts}")
    except discord.Forbidden:
        print(f"[{ts}] Delete failed (perm) => {user} (ID:{user.id})")
        if message.guild:
            await send_log(message.guild, f"❗Delete failed (permission) for {user} (ID:{user.id})")
    except discord.HTTPException as e:
        print(f"[{ts}] Delete failed (HTTP) => {e}")
        if message.guild:
            await send_log(message.guild, f"❗Delete failed (HTTP) => {e}")

# ===== Discord Hooks =====
@bot.event
async def on_ready():
    print(f"✅ Logged in as: {bot.user}")
    # 各ギルドの“bot”系チャンネルを先に探索してキャッシュ
    for g in bot.guilds:
        await send_log(g, f"🔔 Bot is online (model={MODEL})")
    await ensure_ollama_serve()

@bot.event
async def on_guild_join(guild: discord.Guild):
    # 参加時にも案内
    await send_log(guild, f"👋 Joined guild: {guild.name}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # 1) 連投制限：超過なら削除→ログ→違反カウント→残り回数通知→必要なら制裁
    if is_rate_limited(message.author.id):
        await try_delete(message)
        await record_violation_and_escalate(message)
        return

    # 2) メンションで LLM / URL要約
    if bot.user.mention in message.content:
        urls = URL_RE.findall(message.content)
        async with message.channel.typing():
            if urls:
                url = urls[0]
                page_text = await fetch_url_text(url)
                prompt = f"以下の内容を要約:\nURL:{url}\n\n{page_text}"
            else:
                prompt = extract_after_mention(message)
            reply = await run_ollama(prompt)

        MAX = 1900
        if len(reply) <= MAX:
            await message.channel.send(reply)
        else:
            for i in range(0, len(reply), MAX):
                await message.channel.send(reply[i:i + MAX])

    await bot.process_commands(message)

# ===== 実行 =====
if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("環境変数 DISCORD_BOT_AI が未設定です。")
    bot.run(TOKEN)
