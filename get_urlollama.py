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
TOKEN = os.getenv("DISCORD_BOT_AI")  # ← export DISCORD_BOT_AI="xxx"
MODEL = "qwen2.5:0.5b-instruct"      # ← 直書きで固定
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434

# ===== 荒らし対策設定 =====
POSTS_PER_WINDOW = 2  # 1分に1投稿のみ
WINDOW_SECONDS = 10
_user_window = {}  # user_id -> [timestamps]

# URL抽出用
URL_RE = re.compile(r"https?://\S+")

# ===== Discord Intents =====
intents = discord.Intents.none()
intents.guilds = True
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ===== Ollama 起動判定 =====
async def _http_ready_check(host, port, path="/api/version") -> bool:
    try:
        reader, writer = await asyncio.open_connection(host, port)
        req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        writer.write(req.encode())
        await writer.drain()
        data = await reader.read(4096)
        writer.close()
        await writer.wait_closed()
        return b"version" in data.lower()
    except Exception:
        return False


async def ensure_ollama_serve(timeout_sec=20):
    if await _http_ready_check(OLLAMA_HOST, OLLAMA_PORT):
        print("✅ ollama serve already running")
        return

    print("🚀 starting ollama serve…")
    import subprocess, os as _os
    subprocess.Popen(
        ["nohup", "ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=_os.setpgrp
    )

    for i in range(timeout_sec):
        await asyncio.sleep(1)
        if await _http_ready_check(OLLAMA_HOST, OLLAMA_PORT):
            print(f"✅ ollama ready ({i+1}s)")
            return

    print("⚠️ ollama not responding, continuing…")


# ===== URL本文取得 =====
async def fetch_url_text(url: str, maxlen: int = 4000) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as res:
                html = await res.text()
    except Exception as e:
        return f"（URL取得失敗: {e}）"

    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    return text[:maxlen] + " ...（省略）" if len(text) > maxlen else text


# ===== Ollama 実行 =====
async def run_ollama(prompt: str, timeout: int = 1800) -> str:  # 30分
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
            proc.communicate(prompt.encode()),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        return "⌛ Ollama 実行が30分超過しタイムアウトしました。"

    out = (stdout or b"").decode(errors="ignore").strip()
    err = (stderr or b"").decode(errors="ignore").strip()

    if proc.returncode != 0:
        return f"❌ Ollama エラー:\n```\n{err or out}\n```"

    return out or "(出力なし)"


# ===== メンション後文章抽出 =====
def extract_after_mention(message: discord.Message) -> str:
    me = message.guild.me.mention if message.guild and message.guild.me else bot.user.mention
    return message.content.replace(me, "").strip()


# ===== 荒らし対策 =====
def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    bucket = _user_window.setdefault(user_id, [])
    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.pop(0)
    if len(bucket) >= POSTS_PER_WINDOW:
        return True
    bucket.append(now)
    return False


async def try_delete(message: discord.Message):
    user = message.author
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        await message.delete()
        print(f"[{timestamp}] Deleted => {user} (ID: {user.id}) | Content: {message.content}")
    except discord.Forbidden:
        print(f"[{timestamp}] Delete failed => missing permissions | User: {user}")
    except discord.HTTPException as e:
        print(f"[{timestamp}] Delete failed => HTTPException: {e}")


# ===== Discord Hooks =====
@bot.event
async def on_ready():
    print(f"✅ Logged in as: {bot.user}")
    await ensure_ollama_serve()


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # ✅ 荒らし対策（全チャンネル）
    if is_rate_limited(message.author.id):
        await try_delete(message)
        return

    # ✅ メンションで処理開始
    if bot.user.mention in message.content:
        urls = URL_RE.findall(message.content)

        async with message.channel.typing():
            if urls:
                url = urls[0]
                page_text = await fetch_url_text(url)
                prompt = f"以下の内容を要約:\nURL:{url}\n\n{page_text}"
                reply = await run_ollama(prompt)
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
