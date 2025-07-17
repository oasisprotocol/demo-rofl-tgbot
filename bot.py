from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import InvalidToken

from ollama import Client, ChatResponse

import os
import logging
import sys
import re

logger = logging.getLogger(__name__)

class TokenRedactingFormatter(logging.Formatter):
    def format(self, record):
        original = super().format(record)
        if os.getenv("TELEGRAM_API_TOKEN"):
            pattern = rf'bot{re.escape(os.getenv("TELEGRAM_API_TOKEN"))}'
            original = re.sub(pattern, 'bot[REDACTED]', original)
        return original

formatter = TokenRedactingFormatter('%(levelname)s:%(name)s:%(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)

logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)

OLLAMA_ADDRESS="http://ollama:11434"
history = {}

async def hello(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def clear(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    history[update.effective_user.id] = []

async def ask_ollama(prompts: list[str]) -> str:
    try:
        messages = []
        if os.getenv("OLLAMA_SYSTEM_PROMPT"):
            messages.append({
                'role': 'system',
                'content': os.getenv("OLLAMA_SYSTEM_PROMPT")
            })
        for prompt in prompts:
            messages.append({
                'role': 'user',
                'content': prompt
            })
        client = Client(
            host=OLLAMA_ADDRESS,
        )
        response: ChatResponse = client.chat(model=os.getenv("OLLAMA_MODEL"), messages=messages)
        return response['message']['content']
    except Exception as e:
        logger.error(f"Error calling Ollama API: {e}")
        return f"Error generating response {e}"

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in history:
        await clear(update, context)

    history[update.effective_user.id].append(update.message.text)
    response = await ask_ollama(history[update.effective_user.id])

    if "</think>" in response:
        response = response[response.find("</think>") + 9:]

    # Split messages longer than 4096 characters (Telegram's message length limit)
    chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
    for chunk in chunks:
        await update.message.reply_text(chunk)

original_invalid_token_init = InvalidToken.__init__

def patched_invalid_token_init(self, message):
    if os.getenv("TELEGRAM_API_TOKEN") and os.getenv("TELEGRAM_API_TOKEN") in message:
        message = message.replace(os.getenv("TELEGRAM_API_TOKEN"), "[REDACTED]")
    original_invalid_token_init(self, message)

InvalidToken.__init__ = patched_invalid_token_init

try:
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_API_TOKEN")).build()
    
    app.add_handler(CommandHandler("hello", hello))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    app.run_polling()
except InvalidToken as e:
    logger.error("Invalid Telegram bot token provided.")
    sys.exit(1)
except Exception as e:
    error_msg = str(e)
    if "token" in error_msg.lower() and os.getenv("TELEGRAM_API_TOKEN"):
        error_msg = error_msg.replace(os.getenv("TELEGRAM_API_TOKEN"), "[REDACTED]")
    logger.error(f"{error_msg}")
    sys.exit(1)
