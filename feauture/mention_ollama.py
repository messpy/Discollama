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

# ===== 環境・固定設定 =====
TOKEN = os.getenv("DISCORD_BOT_AI")                 # Botトークン環境変数名
TARGET_CHANNEL_ID = 1005826751391342663             # 固定チャンネルID
MODEL = "qwen2.5:0.5b-instruct"                     # Ollamaモデル直書き
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434

# ===== 荒らし対策（ per-user rate limit ）=====
POSTS_PER_WINDOW = 1        # ← 1分あたり許可する投稿数（要求通り「変数」で）
WINDOW_SECONDS = 60         # ← 窓の長さ（秒）
_user_window = {}           # user_id -> [timestamps]

# URL抽出用
URL_RE = re.compile(r"https?://\S+")

# ===== Discord Intents（最小限）=====
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
        writer.close(); 
        try: await writer.wait_closed()
        except Exception: pass
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
    if len(text) > maxlen:
        text = text[:maxlen] + " ...（省略）"
    return text

# ===== Ollama 実行（タイムアウト=30分）=====
async def run_ollama(prompt: str, timeout: int = 1800) -> str:
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
        return "⌛ Ollama 実行がタイムアウトしました（30分超過）。"
    out = (stdout or b"").decode(errors="ignore").strip()
    err = (stderr or b"").decode(errors="ignore").strip()
    if proc.returncode != 0:
        return f"❌ Ollama エラー:\n```\n{err or out}\n```"
    return out or "(出力なし)"

# ===== メンション後テキスト抽出 =====
def extract_after_mention(message: discord.Message) -> str:
    me = message.guild.me.mention if message.guild and message.guild.me else bot.user.mention
    return message.content.replace(me, "").strip()

# ===== 荒らし対策ロジック =====
def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    bucket = _user_window.setdefault(user_id, [])
    # 窓外を掃除
    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.pop(0)
    if len(bucket) >= POSTS_PER_WINDOW:
        return True
    # 許可されるときだけ記録（拒否時は記録しない）
    bucket.append(now)
    return False

async def try_delete(message: discord.Message):
    try:
        await message.delete()
    except discord.Forbidden:
        # 権限なし
        pass
    except discord.HTTPException:
        pass

# ===== Discord Hooks =====
@bot.event
async def on_ready():
    print(f"Logged in as: {bot.user}")
    await ensure_ollama_serve()

@bot.event
async def on_message(message: discord.Message):
    # Bot自身は無視
    if message.author.bot:
        return

    # 対象チャンネル以外は何もしない
    if message.channel.id != TARGET_CHANNEL_ID:
        return

    # ---- 荒らし対策：メンション関係なく適用（1分に1投稿まで）----
    # ※ 超過メッセージは到着のたびに即削除
    # 先に判定するが、最初の1通だけは通す必要があるため
    # is_rate_limited() は許可時に記録、超過なら削除してリターン
    if is_rate_limited(message.author.id):
        await try_delete(message)
        return

    # ---- ここから通常処理 ----
    if bot.user.mention in message.content:
        urls = URL_RE.findall(message.content)
        async with message.channel.typing():
            if urls:
                url = urls[0]
                page_text = await fetch_url_text(url)
                prompt = f"以下を要約:\nURL:{url}\n\n{page_text}"
                reply = await run_ollama(prompt)
            else:
                prompt = extract_after_mention(message)
                reply = await run_ollama(prompt)

        # 2000字制限対策
        MAX = 1900
        if len(reply) <= MAX:
            await message.channel.send(reply)
        else:
            for i in range(0, len(reply), MAX):
                await message.channel.send(reply[i:i+MAX])

    await bot.process_commands(message)

# ===== 実行 =====
if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("環境変数 DISCORD_BOT_AI が未設定です。")
    bot.run(TOKEN)
