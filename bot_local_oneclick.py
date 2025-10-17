#!/usr/bin/env python3
# bot_local_oneclick.py
import os
import sys
import json
import shlex
import subprocess
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# --------------- CONFIG ---------------
BOT_TOKEN = os.getenv("8286146152:AAGz1iARSOYSaT7hxHy6TlaydG97xB26xoo") or "PUT_YOUR_BOT_TOKEN_HERE"
APP_NAME = "oneclick_local_bot"
BASE = Path.cwd()
SESSIONS = BASE / "sessions"
SESSIONS.mkdir(exist_ok=True)
DELETE_AFTER_SEND = True        # удалять копию после отправки
MAX_FILE_BYTES = 500 * 1024 * 1024
API_STORE = BASE / "api_credentials.json"
ACTIVATE_SCRIPT = BASE / "activate_session.py"
LOCAL_MODE = os.getenv("LOCAL_MODE", "1") == "1"  # нужно установить LOCAL_MODE=1 для автозапуска
# ---------------------------------------

app = Client(APP_NAME, bot_token=BOT_TOKEN)
user_consents = {}  # user_id -> bool

DISCLAIMER = (
    "⚠️ ВАЖНО\n\n"
    "Файл сессии содержит полный доступ к вашему Telegram‑аккаунту. "
    "Никогда не передавайте его посторонним.\n\n"
    "Нажимая «Я согласен», вы подтверждаете, что файл принадлежит вам и что вы понимаете риски."
)

def menu(consented: bool):
    if not consented:
        return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Я прочитал(а) и согласен(а)", callback_data="consent")]])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Экспорт (получить мою сессию)", callback_data="export")],
        [InlineKeyboardButton("📥 Импорт (отправить файл)", callback_data="import")],
        [InlineKeyboardButton("⚙️ Настроить API (опционально)", callback_data="set_api")],
        [InlineKeyboardButton("❓Помощь", callback_data="help")]
    ])

def load_api():
    if not API_STORE.exists():
        return {}
    try:
        return json.loads(API_STORE.read_text(encoding="utf-8"))
    except:
        return {}

def save_api(data: dict):
    API_STORE.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(API_STORE, 0o600)
    except Exception:
        pass

def list_user_files(uid: int):
    pref = f"{uid}_"
    return [p.name for p in SESSIONS.iterdir() if p.is_file() and p.name.startswith(pref)]

@app.on_message(filters.command("start") & filters.private)
async def start(c: Client, m: Message):
    user_consents[m.from_user.id] = False
    await m.reply(DISCLAIMER, reply_markup=menu(False))

@app.on_callback_query()
async def cb(c: Client, q):
    uid = q.from_user.id
    data = q.data

    if data == "consent":
        user_consents[uid] = True
        await q.answer("Согласие принято.")
        await q.message.edit_text(DISCLAIMER, reply_markup=menu(True))
        return

    if not user_consents.get(uid, False):
        await q.answer("Сначала подтвердите дисклеймер.", show_alert=True)
        return

    if data == "help":
        await q.message.reply("Инструкция:\n• Нажмите Импорт и отправьте .session\n• Или положите файл в папку sessions/ с именем <your_userid>_name.session\n• Нажмите Экспорт, чтобы получить файл.\n• Для автологина: используйте /set_api и затем импорт — при LOCAL_MODE=1 бот запустит Telethon локально.")
        await q.answer()
        return

    if data == "set_api":
        await q.message.reply("Отправьте команду в формате:\n`/set_api <api_id> <api_hash>`\nЭти данные сохранятся локально и будут использоваться только на этой машине.", parse_mode="markdown")
        await q.answer()
        return

    if data == "import":
        await q.message.reply("Пожалуйста, отправьте .session как файл (Attach -> File).")
        await q.answer()
        return

    if data == "export":
        files = list_user_files(uid)
        if not files:
            await q.answer("Файл не найден. Загрузите его в бот или поместите в sessions/ с префиксом <user_id>_.", show_alert=True)
            return
        # если несколько — отправляем список, если 1 — сразу
        if len(files) == 1:
            f = SESSIONS / files[0]
            if f.stat().st_size > MAX_FILE_BYTES:
                await q.answer("Файл слишком большой.", show_alert=True); return
            try:
                await q.message.reply_document(str(f), caption="Ваш файл сессии")
                await q.answer("Файл отправлен.")
                if DELETE_AFTER_SEND:
                    f.unlink(missing_ok=True)
                return
            except Exception as e:
                await q.answer("Ошибка отправки: " + str(e), show_alert=True); return
        else:
            buttons = [[InlineKeyboardButton(n, callback_data=f"export_file:{n}")] for n in files]
            await q.message.reply("Найдено несколько файлов — выберите:", reply_markup=InlineKeyboardMarkup(buttons))
            await q.answer()
            return

    if data.startswith("export_file:"):
        fname = data.split("export_file:",1)[1]
        f = SESSIONS / fname
        if not f.exists():
            await q.answer("Файл не найден.", show_alert=True); return
        try:
            await q.message.reply_document(str(f), caption=f"Ваш файл: {fname}")
            await q.answer("Файл отправлен.")
            if DELETE_AFTER_SEND:
                f.unlink(missing_ok=True)
        except Exception as e:
            await q.answer("Ошибка отправки: "+str(e), show_alert=True)

@app.on_message(filters.command("set_api") & filters.private)
async def set_api(c: Client, m: Message):
    parts = m.text.strip().split()
    if len(parts) != 3:
        await m.reply("Неверный формат. Используйте: /set_api <api_id> <api_hash>")
        return
    uid = m.from_user.id
    store = load_api()
    store[str(uid)] = {"api_id": int(parts[1]), "api_hash": parts[2]}
    save_api(store)
    await m.reply("API данные сохранены локально (файл api_credentials.json, права 600).")

@app.on_message(filters.document & filters.private)
async def on_doc(c: Client, m: Message):
    uid = m.from_user.id
    if not user_consents.get(uid, False):
        await m.reply("Сначала подтвердите дисклеймер.")
        return
    doc = m.document
    if doc.file_size and doc.file_size > MAX_FILE_BYTES:
        await m.reply("Файл слишком большой."); return
    safe = f"{uid}_{doc.file_name}"
    path = SESSIONS / safe
    i = 1
    while path.exists():
        path = SESSIONS / f"{uid}_{i}_{doc.file_name}"; i += 1
    await m.download(file_name=str(path))
    # сразу вернуть файл пользователю
    await m.reply_document(str(path), caption="Файл сохранён и возвращён.")
    # попытка автозапуска локального Telethon клиента
    store = load_api()
    creds = store.get(str(uid))
    if LOCAL_MODE and creds and ACTIVATE_SCRIPT.exists():
        # запускаем подпроцесс: python activate_session.py <path> --api-id <id> --api-hash <hash>
        cmd = [sys.executable, str(ACTIVATE_SCRIPT), str(path), "--api-id", str(creds["api_id"]), "--api-hash", str(creds["api_hash"])]
        try:
            subprocess.Popen(cmd)
            await m.reply("➡️ Локальная активация запущена в фоне (Telethon). Проверьте логи в терминале, где запущен activate_session.py.")
        except Exception as e:
            await m.reply(f"⚠️ Не удалось запустить локальный активатор: {e}")
    else:
        if not LOCAL_MODE:
            await m.reply("ℹ️ LOCAL_MODE не включён — автозапуск отключён. Установите LOCAL_MODE=1 для локального автозапуска.")
        elif not creds:
            await m.reply("ℹ️ API creds не настроены. Используйте /set_api <api_id> <api_hash> чтобы настроить локально.")
        elif not ACTIVATE_SCRIPT.exists():
            await m.reply("ℹ️ Скрипт activate_session.py не найден рядом с ботом.")
    # удаляем копию если нужно
    if DELETE_AFTER_SEND:
        try: path.unlink(missing_ok=True)
        except: pass
    return

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(c: Client, m: Message):
    await m.reply("Инструкция:\n1) /start -> согласиться с дисклеймером\n2) /set_api <id> <hash> (опционально, нужен для автологина)\n3) Отправьте .session как файл -> бот вернёт файл и, при LOCAL_MODE=1 и настроенных creds, запустит локальный Telethon клиент.")

if __name__ == "__main__":
    print("Starting bot. Sessions dir:", SESSIONS)
    print("LOCAL_MODE:", LOCAL_MODE)
    app.run()
