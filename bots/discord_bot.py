"""Discord channel adapter. Setup and Docker instructions: docs/DISCORD.md.

DM, @mention, /sprawdz or message context menu all use the same HTTP verification API.
No models or verification rules run in this process.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import time
from collections import OrderedDict, deque
from pathlib import Path

import discord
import httpx
from discord import app_commands
from discord.ext import tasks

API = os.environ.get("PRAWDOWID_API", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("PRAWDOWID_DISCORD_TOKEN", "").strip()
SESSION_SECRET = os.environ.get("PRAWDOWID_DISCORD_SESSION_SECRET", "").strip() or TOKEN
RATE_LIMIT = max(1, int(os.environ.get("PRAWDOWID_DISCORD_RATE_LIMIT", "5")))
ALERT_CHANNEL_ID = os.environ.get("PRAWDOWID_DISCORD_ALERT_CHANNEL_ID", "").strip()
MODERATOR_TOKEN = os.environ.get("PRAWDOWID_MODERATOR_TOKEN", "")
PUBLIC_URL = os.environ.get("PRAWDOWID_PUBLIC_URL", "http://localhost:8000").rstrip("/")
STATE = Path(os.environ.get("PRAWDOWID_RUNTIME_DIR", str(Path(__file__).resolve().parents[1] / "data/runtime")))
NOTICE = "\n-# 🤖 Automatyczny system (SI) · ocena wynika z jawnych reguł i źródeł · nie jest „sędzią prawdy”."
HELP = ("Napisz jedno konkretne pytanie lub wklej sam link, np. „Czy to prawda, że Ukraina nie płaci "
        "Orlenowi za paliwo?”. Użyj /sprawdz albo oznacz mnie na kanale. "
        "Każde pytanie sprawdzam niezależnie, bez pamięci rozmowy. "
        "Komenda /usun_sesje usuwa Twoje sprawdzenia z Prawdowida; nie usuwa wiadomości z Discorda.")
ATTACHMENT_NOTICE = ("Nie analizuję załączników: obrazów, zrzutów ekranu, plików, nagrań ani wideo. "
                     "Wklej treść jako tekst lub podaj publiczny link do artykułu.")
TECHNICAL_ERROR = "Błąd techniczny — to nie jest ocena treści. Spróbuj za chwilę."
log = logging.getLogger("prawdowid.discord")


def session_id(user_id: int) -> str:
    # Keyed pseudonym: a public Discord ID is not enough to guess a deletion session.
    return hmac.new(SESSION_SECRET.encode(), f"discord:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def reply_parts(text: str) -> list[str]:
    """Preserve the whole answer, source links and final analysis link within Discord's limit."""
    budget = 2000 - units(NOTICE)
    parts, current = [], ""
    for line in text.splitlines(keepends=True):
        while units(line) > budget:
            if current:
                parts.append(current.rstrip() + NOTICE)
                current = ""
            end, size = 0, 0
            for char in line:
                size += units(char)
                if size > budget:
                    break
                end += 1
            parts.append(line[:end].rstrip() + NOTICE)
            line = line[end:]
        if units(current + line) > budget:
            parts.append(current.rstrip() + NOTICE)
            current = ""
        current += line
    if current.strip():
        parts.append(current.rstrip() + NOTICE)
    return parts or [HELP + NOTICE]


class UserGate:
    """Bounded rolling rate limit and one in-flight operation per user (check or deletion)."""
    def __init__(self):
        self.hits: OrderedDict[int, deque] = OrderedDict()
        self.busy: set[int] = set()

    def enter(self, user_id: int) -> str | None:
        now = time.monotonic()
        while self.hits and now - next(iter(self.hits.values()))[-1] >= 60:
            self.hits.popitem(last=False)
        if user_id in self.busy:
            return "Poprzednie sprawdzenie lub usuwanie sesji jeszcze trwa. Poczekaj na odpowiedź."
        if len(self.busy) >= 2:
            return "System obsługuje teraz inne zgłoszenia. Spróbuj za chwilę. To nie jest ocena treści."
        q = self.hits.setdefault(user_id, deque())
        while q and now - q[0] >= 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return "Limit zapytań — spróbuj za minutę. To nie jest ocena treści."
        q.append(now)
        self.hits.move_to_end(user_id)
        while len(self.hits) > 10000:
            self.hits.popitem(last=False)
        self.busy.add(user_id)
        return None

    def leave(self, user_id: int) -> None:
        self.busy.discard(user_id)


gate = UserGate()


class PrawdowidClient(discord.Client):
    async def setup_hook(self):
        await tree.sync()  # once per login, rather than on every Gateway reconnect
        if ALERT_CHANNEL_ID and MODERATOR_TOKEN:
            moderator_alerts.start()
        elif ALERT_CHANNEL_ID:
            log.error("Moderator alerts disabled: PRAWDOWID_MODERATOR_TOKEN is missing.")


intents = discord.Intents.default()
intents.message_content = True
client = PrawdowidClient(intents=intents, allowed_mentions=discord.AllowedMentions.none())
tree = app_commands.CommandTree(client)


async def check(text: str, user_id: int) -> str:
    text = text.strip()
    if not text:
        return HELP
    if len(text) > 6000:
        return "Wiadomość jest zbyt długa. Wklej do 6000 znaków lub sam link do artykułu."
    rejected = gate.enter(user_id)
    if rejected:
        return rejected
    try:
        async with httpx.AsyncClient(timeout=45) as h:
            r = await h.post(f"{API}/api/chat-reply", json={"text": text, "channel": "discord",
                                                         "session": session_id(user_id)})
            if r.status_code == 429:
                return "Limit zapytań serwera — spróbuj za minutę. To nie jest ocena treści."
            r.raise_for_status()
            result = r.json()["text"]
            if not isinstance(result, str) or not result.strip():
                raise ValueError("Invalid response")
            return result
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        log.warning("Verification API failed (%s).", type(e).__name__)
        return TECHNICAL_ERROR
    finally:
        gate.leave(user_id)


async def delete_session(user_id: int) -> str:
    rejected = gate.enter(user_id)
    if rejected:
        return rejected
    try:
        async with httpx.AsyncClient(timeout=45) as h:
            r = await h.delete(f"{API}/api/session/{session_id(user_id)}")
            r.raise_for_status()
            count = int(r.json()["deleted_checks"])
        return (f"Usunięto Twoje sprawdzenia z Prawdowida: {count}. "
                "Wiadomości i odpowiedzi pozostają na Discordzie — możesz usunąć swoje wiadomości w aplikacji.")
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        log.warning("Session deletion failed (%s).", type(e).__name__)
        return "Nie udało się potwierdzić usunięcia sesji. Spróbuj ponownie."
    finally:
        gate.leave(user_id)


async def send_interaction(interaction: discord.Interaction, text: str, *, ephemeral=False):
    for part in reply_parts(text):
        await interaction.followup.send(part, ephemeral=ephemeral, suppress_embeds=True,
                                        allowed_mentions=discord.AllowedMentions.none())


@tree.command(name="sprawdz", description="Sprawdź informację w wiarygodnych źródłach")
@app_commands.describe(tekst="Treść wiadomości lub sam link do sprawdzenia")
async def sprawdz(interaction: discord.Interaction, tekst: str):
    await interaction.response.defer(thinking=True)
    await send_interaction(interaction, await check(tekst, interaction.user.id))


@tree.command(name="usun_sesje", description="Usuń swoje sprawdzenia zapisane w Prawdowidzie")
async def usun_sesje(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await send_interaction(interaction, await delete_session(interaction.user.id), ephemeral=True)


@tree.context_menu(name="Sprawdź w Prawdowidzie")
async def sprawdz_msg(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True, ephemeral=True)
    result = await check(message.content, interaction.user.id) if message.content.strip() else HELP
    if message.attachments:
        result = ATTACHMENT_NOTICE + "\n\n" + result
    await send_interaction(interaction, result, ephemeral=True)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot or client.user is None:
        return
    is_dm = isinstance(message.channel, discord.DMChannel)
    if not (is_dm or client.user in message.mentions):
        return
    text = re.sub(rf"<@!?{client.user.id}>", "", message.content).strip()
    async with message.channel.typing():
        if text.lower() in ("/usun_sesje", "usuń sesję", "usun sesje"):
            result = await delete_session(message.author.id)
        else:
            result = await check(text, message.author.id)
            if message.attachments:
                result = ATTACHMENT_NOTICE + "\n\n" + result
        try:
            for part in reply_parts(result):
                await message.reply(part, mention_author=False, suppress_embeds=True,
                                    allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as e:
            log.warning("Discord reply failed (%s).", type(e).__name__)


@tasks.loop(seconds=60)
async def moderator_alerts():
    """Opt-in, all-channel priority-case alerts; persist successful delivery checkpoints."""
    state_path = STATE / "discord-alerts.json"
    try:
        sent = json.loads(state_path.read_text()) if state_path.exists() else {}
        if not isinstance(sent, dict):
            raise ValueError("Invalid alert state")
        async with httpx.AsyncClient(timeout=15) as h:
            r = await h.get(f"{API}/api/cases", headers={"X-Moderator-Token": MODERATOR_TOKEN})
            r.raise_for_status()
            cases = r.json()["cases"]
        channel = None
        for case in cases:
            if case["priority"] != "wysoki" or case["status"] == "zamknięta":
                continue
            key = f"{ALERT_CHANNEL_ID}:{case['id']}"
            if sent.get(key, 0) >= case["count"]:
                continue
            if channel is None:
                channel = await client.fetch_channel(int(ALERT_CHANNEL_ID))
                if not hasattr(channel, "send"):
                    raise ValueError("Moderator channel does not support messages")
            await channel.send(
                f"📨 Sprawa **{case['id']}** wymaga uwagi analityka. "
                f"Priorytet: wysoki. Liczba zgłoszeń: {case['count']}.\n"
                f"Szczegóły w panelu moderatora: {PUBLIC_URL}/moderator\n"
                "To powiadomienie o sprawie, nie werdykt ani potwierdzenie jej rozpatrzenia.",
                suppress_embeds=True, allowed_mentions=discord.AllowedMentions.none())
            sent[key] = case["count"]
            STATE.mkdir(parents=True, exist_ok=True)
            temp = state_path.with_suffix(".tmp")
            temp.write_text(json.dumps(sent))
            temp.replace(state_path)
    except (httpx.HTTPError, discord.DiscordException, OSError, ValueError, KeyError, TypeError) as e:
        log.warning("Moderator notification not confirmed (%s); will retry.", type(e).__name__)


@moderator_alerts.before_loop
async def before_alerts():
    await client.wait_until_ready()


@client.event
async def on_ready():
    log.info("Prawdowid bot online as %s → API %s", client.user, API)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Ustaw PRAWDOWID_DISCORD_TOKEN (docs/DISCORD.md).")
    logging.basicConfig(level=logging.INFO)
    client.run(TOKEN)
