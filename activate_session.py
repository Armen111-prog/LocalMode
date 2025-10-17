#!/usr/bin/env python3
# activate_session.py
# Запускает Telethon-клиент с указанным session-файлом и держит его онлайн.
# Используется ТОЛЬКО локально на машине пользователя.

import argparse
import asyncio
import logging
from pathlib import Path
from telethon import TelegramClient, events

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

async def run_client(session_path: str, api_id: int, api_hash: str):
    session_path = str(Path(session_path))
    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()
    me = await client.get_me()
    logging.info(f"Client started as {me.username or me.first_name} (id={me.id}) — session: {session_path}")

    @client.on(events.NewMessage(incoming=True))
    async def on_new_message(event):
        logging.info(f"Incoming from {event.sender_id}: {getattr(event.message, 'text', '')[:100]}")

    try:
        await client.run_until_disconnected()
    except Exception as e:
        logging.exception("Client stopped with error: %s", e)

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("session", help="Path to .session file (Telethon format)")
    p.add_argument("--api-id", required=True, type=int, help="API ID from my.telegram.org")
    p.add_argument("--api-hash", required=True, help="API Hash from my.telegram.org")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_client(args.session, args.api_id, args.api_hash))
