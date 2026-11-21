"""Prawdowid Discord bot — a thin channel adapter over the Prawdowid HTTP API (same verification logic as the web).

Features: DM the bot, @mention it, use /sprawdz <tekst>, or right-click any message → Apps → "Sprawdź w Prawdowidzie".
Setup (5 min, no business verification): https://discord.com/developers/applications → New Application → Bot →
Reset Token; enable "Message Content Intent"; OAuth2 URL Generator: scopes bot + applications.commands,
permissions Send Messages + Read Message History; open the URL to invite the bot.
Run:  PRAWDOWID_DISCORD_TOKEN=... PRAWDOWID_API=http://localhost:8000 python bots/discord_bot.py
"""
from __future__ import annotations

import hashlib
import os

import discord
import httpx
from discord import app_commands

API = os.environ.get("PRAWDOWID_API", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("PRAWDOWID_DISCORD_TOKEN", "")
NOTICE = "\n-# 🤖 Automatyczny system (SI) · ocena wynika z jawnych reguł i źródeł · nie jest „sędzią prawdy”."

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


async def check(text: str, user_id: int) -> str:
    session = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]  # pseudonymised, never the raw Discord ID
    try:
        async with httpx.AsyncClient(timeout=45) as h:
            r = await h.post(f"{API}/api/chat-reply", json={"text": text, "channel": "discord", "session": session})
            r.raise_for_status()
            return r.json()["text"][:1900] + NOTICE
    except httpx.HTTPError as e:
        return f"**Prawdowid** — błąd techniczny ({type(e).__name__}). To nie jest ocena treści — spróbuj za chwilę."


@tree.command(name="sprawdz", description="Sprawdź informację w wiarygodnych źródłach")
@app_commands.describe(tekst="Treść wiadomości lub link do sprawdzenia")
async def sprawdz(interaction: discord.Interaction, tekst: str):
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(await check(tekst, interaction.user.id), suppress_embeds=True)


@tree.context_menu(name="Sprawdź w Prawdowidzie")
async def sprawdz_msg(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await interaction.followup.send(await check(message.content, interaction.user.id), ephemeral=True, suppress_embeds=True)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    is_dm = isinstance(message.channel, discord.DMChannel)
    if not (is_dm or client.user in message.mentions):
        return
    text = message.content.replace(f"<@{client.user.id}>", "").strip()
    if not text:
        return
    async with message.channel.typing():
        await message.reply(await check(text, message.author.id), mention_author=False, suppress_embeds=True)


@client.event
async def on_ready():
    await tree.sync()
    print(f"Prawdowid bot online as {client.user} → API {API}")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Ustaw PRAWDOWID_DISCORD_TOKEN (patrz docstring).")
    client.run(TOKEN)
