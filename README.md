# Discollama

A Discord bot powered by Python, designed to integrate with Ollama for AI-powered conversations.

## Features

- Discord bot integration using discord.py
- Easy setup with Python virtual environment
- Environment-based configuration
- Basic command examples

## Prerequisites

- Python 3.8 or higher
- A Discord bot token (from [Discord Developer Portal](https://discord.com/developers/applications))

## Setup

### 1. Create a Virtual Environment

```bash
python -m venv venv
```

### 2. Activate the Virtual Environment

**On Windows:**
```bash
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the Bot

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Discord bot token:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   ```

### 5. Run the Bot

```bash
python bot.py
```

## Commands

- `!ping` - Check if the bot is responsive
- `!hello` - Get a greeting from the bot

## Project Structure

```
Discollama/
├── bot.py              # Main bot file
├── requirements.txt    # Python dependencies
├── .env.example       # Example environment variables
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Development

The bot uses a virtual environment to isolate dependencies. Always activate the virtual environment before working on the project:

```bash
# Activate venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install/update dependencies
pip install -r requirements.txt

# Run the bot
python bot.py

# Deactivate venv when done
deactivate
```

## License

This project is open source and available under the MIT License.