from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from ollama import Client, ChatResponse

import os
import logging
import sys

class SuppressOutput:
    def write(self, _):
        pass
    def flush(self):
        pass

if os.getenv("TOKEN"):
    sys.stderr = SuppressOutput()

logging.getLogger("telegram").setLevel(logging.CRITICAL)
logging.getLogger("telegram.ext").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)

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
        print(f"Error calling Ollama API: {e}")
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

token = os.getenv("TELEGRAM_API_TOKEN") or os.getenv("TOKEN")
app = ApplicationBuilder().token(token).build()

app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("clear", clear))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

app.run_polling()
