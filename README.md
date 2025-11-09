# Telegram LLM Bot (OpenAI GPT‑5 / Anthropic)

A minimal Telegram bot that lets a small, whitelisted group chat with modern LLMs. It supports:
- Text conversations (multi-message history per user)
- Vision: single photo or image document per message, auto-resized for OpenAI Vision constraints
- Provider switching (OpenAI or Anthropic) via an environment variable or message prefixes
- Simple rate limiting and access control by Telegram user IDs


## Features
- Whitelist access: only specified Telegram user IDs can use the bot
- Multi-provider:
  - OpenAI (Responses API / Chat Completions when required)
  - Anthropic (Claude Messages API)
- On-the-fly provider switch by message prefix:
  - `o:` (or Cyrillic `о:`) → OpenAI
  - `a:` / `c:` (or Cyrillic `а:` / `с:`) → Anthropic
- Vision support:
  - Accepts a single photo or image document (PNG/JPEG)
  - Resizes to meet OpenAI limits: long side ≤ 2000 px, short side ≤ 768 px
  - Encodes to a base64 data URL before sending
- Simple UI: `/start` shows an inline button; replies are short by default (system prompt is in German)


## Requirements
- Python 3.12+
- A Telegram Bot token (via BotFather: https://t.me/botfather)
- At least one AI provider configured:
  - OpenAI API key (and optional model)
  - OR Anthropic API key and model


## Environment Variables
Set the following environment variables before running. Examples are shown for bash and zsh shells.

Required for the bot:
- `TELEGRAM_LLM_BOT_TOKEN`: Telegram Bot token from BotFather
- `ALLOWED_USER_IDS`: Comma-separated Telegram user IDs who can access the bot, e.g. `123,456,789`
- `AI_PROVIDER`: Either `openai` or `anthropic` (default provider used when no prefix is present)

OpenAI:
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: Model name or Azure deployment handle (optional; defaults to `gpt-5`)
  - Notes: some models (e.g. `o1`) do not accept system messages; the bot adjusts accordingly.

Anthropic:
- `ANTHROPIC_API_KEY`: Your Anthropic API key (required when `AI_PROVIDER=anthropic`)
- `ANTHROPIC_MODEL`: Model name, e.g. `claude-3-5-sonnet` (required when `AI_PROVIDER=anthropic`)

Examples (bash):
```
# ~/.bashrc
export TELEGRAM_LLM_BOT_TOKEN="<your_bot_token>"
export ALLOWED_USER_IDS="123,456"
export AI_PROVIDER="openai"           # or "anthropic"
export OPENAI_API_KEY="<your_openai_key>"
export OPENAI_MODEL="gpt-5"           # optional
# Anthropic (if using Anthropic)
# export ANTHROPIC_API_KEY="<your_anthropic_key>"
# export ANTHROPIC_MODEL="claude-3-5-sonnet"

source ~/.bashrc
```

Examples (zsh):
```
# ~/.zshrc
export TELEGRAM_LLM_BOT_TOKEN="<your_bot_token>"
export ALLOWED_USER_IDS="123,456"
export AI_PROVIDER="openai"           # or "anthropic"
export OPENAI_API_KEY="<your_openai_key>"
export OPENAI_MODEL="gpt-5"           # optional
# Anthropic (if using Anthropic)
# export ANTHROPIC_API_KEY="<your_anthropic_key>"
# export ANTHROPIC_MODEL="claude-3-5-sonnet"

source ~/.zshrc
```


## Installation
1) Clone the repository:
```
git clone https://github.com/RomanPlusPlus/telegram-llm-bot.git
cd telegram-llm-bot
```

2) (Optional) Create and activate a virtual environment.
```
python3 -m venv venv
source venv/bin/activate
```

3) Install dependencies:
```
pip install -r requirements.txt
```


## Configuration
- `utils/images.py` implements image resizing and base64 data URL encoding.
- `config.py` defines:
  - `MAX_IMAGES_PER_MESSAGE` (default: `1`). If set to `1`, albums (media groups) are rejected.
- `main.py` contains:
  - `MAX_MESSAGES_NUM` (default: `100`) – how many messages of history to keep per user
  - `MAX_IMAGE_SIZE_MB` (default: `30`) – hard limit for image size after download

Adjust these values as needed.


## Running
Run the bot locally or on a VM. You can use tmux to keep it running in the background.

Basic run:
```
python3 main.py
```

Using tmux:
```
tmux new -s session_name
python3 main.py
# Detach: Ctrl+b, then d
# Reattach later: tmux attach -t session_name
```


## Usage
- Text: just send messages. The bot maintains a short, helpful style by default.
- Provider selection in-message:
  - Start your message with `o:` (or Cyrillic `о:`) to force OpenAI
  - Start with `a:` / `c:` (or Cyrillic `а:` / `с:`) to force Anthropic
- Images:
  - Send a single photo or image document (PNG/JPEG). Optional caption is included in the prompt.
  - If too large, the bot replies with a size error.
  - When `MAX_IMAGES_PER_MESSAGE=1`, albums (media groups) are rejected.

Access control:
- If your Telegram user ID is not in `ALLOWED_USER_IDS`, the bot replies with an unauthorized message and ignores your input.


## Troubleshooting
- "No token provided": ensure `TELEGRAM_LLM_BOT_TOKEN` is set.
- Unauthorized messages referencing your `user_id`: your ID is not included in `ALLOWED_USER_IDS`.
- "unknown AI provider": check `AI_PROVIDER` or your in-message prefix.
- Image too large errors: the original or downloaded file exceeds `MAX_IMAGE_SIZE_MB` (default 30 MB).
- OpenAI/Anthropic errors: verify API keys and model names.


## Project Structure
- `main.py`: Telegram bot setup, handlers, message routing
- `ai_providers/open_ai_provider.py`: OpenAI client and model handling
- `ai_providers/anthropic_ai_provider.py`: Anthropic client and model handling
- `ai_providers/rate_limited_ai_wrapper.py`: Provider selection and simple rate limiting
- `utils/images.py`: Vision utilities (resize, base64 data URL)
- `config.py`: Basic configuration constants


## License
See `LICENSE` for details.

