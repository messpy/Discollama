import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    """Called when the bot is ready."""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')

@bot.event
async def on_message(message):
    """Called when a message is received."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Process commands
    await bot.process_commands(message)

@bot.command(name='ping')
async def ping(ctx):
    """Check if the bot is responsive."""
    await ctx.send('Pong! 🏓')

@bot.command(name='hello')
async def hello(ctx):
    """Say hello to the user."""
    await ctx.send(f'Hello {ctx.author.mention}! 👋')

def main():
    """Main function to run the bot."""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print('Error: DISCORD_TOKEN not found in environment variables')
        print('Please create a .env file with your bot token')
        return
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        print('Error: Invalid token. Please check your DISCORD_TOKEN in .env file')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    main()
