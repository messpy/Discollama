import discord
from discord import app_commands
from discord.ext import commands
import os
import re
from datetime import datetime

TOKEN = "YOUR_BOT_TOKEN"
SAVE_DIR = "./downloads"

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True  # メッセージ本文取得に必須

bot = commands.Bot(command_prefix="!", intents=intents)

def sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip()

@bot.tree.command(name="getch", description="指定チャンネルのメッセージと画像URLを保存します")
@app_commands.describe(channel_id="保存したいチャンネルのID")
async def getch(interaction: discord.Interaction, channel_id: str):
    await interaction.response.defer(thinking=True)
    try:
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            await interaction.followup.send("⚠️ そのチャンネルにアクセスできません。")
            return

        os.makedirs(SAVE_DIR, exist_ok=True)
        log_path = os.path.join(SAVE_DIR, f"{sanitize(channel.name)}_log.txt")

        with open(log_path, "w", encoding="utf-8") as f:
            async for msg in channel.history(limit=None, oldest_first=True):
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {msg.author.display_name}: {msg.content}\n")

                # 添付画像をURLで残す
                for att in msg.attachments:
                    if att.content_type and att.content_type.startswith("image/"):
                        f.write(f"  📷 {att.url}\n")

                f.write("\n")

        await interaction.followup.send(f"✅ ログを保存しました。\n保存先: `{log_path}`")

    except Exception as e:
        await interaction.followup.send(f"⚠️ エラーが発生しました:\n```{e}```")

@bot.event
async def on_ready():
    print(f"✅ ログイン完了: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {len(synced)}")
    except Exception as e:
        print(f"同期エラー: {e}")


bot.run(TOKEN)

