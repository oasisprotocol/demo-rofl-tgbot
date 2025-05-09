from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from ollama import Client, ChatResponse

import os

OLLAMA_ADDRESS="http://ollama:11434"
history = {}

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    history[update.effective_user.id] = []

async def ask_ollama(prompts: list[str]) -> str:
    try:
        messages = []
        for prompt in prompts:
            messages.append({
                'role': 'user',
                'content': prompt
            })
        client = Client(
            host=OLLAMA_ADDRESS,
        )
        response: ChatResponse = client.chat(model='deepseek-r1:1.5b', messages=messages)
        return response['message']['content']
    except Exception as e:
        print(f"Error calling Ollama API: {e}")
        return f"Error generating response {e}"

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in history:
        await clear(update, context)

    history[update.effective_user.id].append(update.message.text)
    response = await ask_ollama(history[update.effective_user.id])
    await update.message.reply_text(response)

app = ApplicationBuilder().token(os.getenv("TOKEN")).build()

app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("clear", clear))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

app.run_polling()
