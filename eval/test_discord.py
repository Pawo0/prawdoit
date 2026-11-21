"""Discord/API regressions with mocked transports; no tokens, models or messages sent."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory()
os.environ['PRAWDOWID_RUNTIME_DIR'] = TEMP.name
os.environ['PRAWDOWID_INDEX_DIR'] = str(Path(TEMP.name) / 'index')
sys.path.insert(0, str(ROOT / 'backend'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with patch.dict(os.environ, {'PRAWDOWID_DISCORD_TOKEN': 'test-token',
                             'PRAWDOWID_DISCORD_SESSION_SECRET': 'test-secret'}):
    bot = load('discord_bot', ROOT / 'bots/discord_bot.py')

from fastapi.testclient import TestClient
from prawdowid import api, store
from prawdowid.schemas import CheckResult, ClaimResult, Evidence


def result():
    evidence = [Evidence(doc_id=f's{i}', title='Tytuł dokumentu ' + 'x' * 80, publisher='Wydawca',
                         domain='example.org', url=f'https://example.org/source/{i}', source_type='official',
                         tier=1, published_at='2026-11-21', fragment='Dosłowny fragment źródła. ' * 12,
                         stance='przeczy') for i in range(3)]
    return CheckResult(id='test-analysis', created_at=store.now(), channel='discord', status='ok',
                       input_kind='text', input_excerpt='Twierdzenie', claims=[
        ClaimResult(claim=f'Twierdzenie numer {i}', verdict='falszywe', verdict_label='Fałszywe',
                    strength=.9, strength_label='mocna', explanation='Wyjaśnienie. ' * 40, evidence=evidence)
        for i in range(3)])


class ReplyTests(unittest.TestCase):
    def test_long_result_preserves_sources_quotes_and_analysis(self):
        from prawdowid.channels.formatting import chat_text
        text = chat_text(result(), bold='**', max_len=None)
        self.assertGreater(len(text), 1900)
        parts = bot.reply_parts(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(bot.units(part) <= 2000 for part in parts))
        joined = '\n'.join(part.removesuffix(bot.NOTICE) for part in parts)
        for url in ['https://example.org/source/0', 'https://example.org/source/2', '/analiza/test-analysis']:
            self.assertIn(url, joined)
        self.assertIn('Cytat:', joined)
        for i in range(3):
            self.assertIn(f'Twierdzenie numer {i}', joined)

    def test_emoji_and_single_long_line_fit_discord(self):
        original = '😀' * 4000
        parts = bot.reply_parts(original)
        self.assertTrue(all(bot.units(part) <= 2000 for part in parts))
        self.assertEqual(''.join(p.removesuffix(bot.NOTICE) for p in parts), original)

    def test_session_is_stable_secret_and_namespaced(self):
        self.assertEqual(bot.session_id(123), bot.session_id(123))
        self.assertNotEqual(bot.session_id(123), bot.session_id(456))
        with patch.object(bot, 'SESSION_SECRET', 'another-secret'):
            other = bot.session_id(123)
        self.assertNotEqual(bot.session_id(123), other)
        self.assertEqual(len(other), 32)

    def test_gate_rate_expiry_busy_and_capacity(self):
        gate = bot.UserGate()
        with patch.object(bot, 'RATE_LIMIT', 2), patch.object(bot.time, 'monotonic', return_value=1):
            self.assertIsNone(gate.enter(1))
            self.assertIn('trwa', gate.enter(1))
            self.assertIsNone(gate.enter(2))
            self.assertIn('inne zgłoszenia', gate.enter(3))
            gate.leave(1)
            gate.leave(2)
            self.assertIsNone(gate.enter(1))
            gate.leave(1)
            self.assertIn('Limit', gate.enter(1))
        with patch.object(bot.time, 'monotonic', return_value=62):
            self.assertIsNone(gate.enter(3))
            gate.leave(3)
            self.assertIsNone(gate.enter(1))


class BotTransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        bot.gate = bot.UserGate()
        self.requests = []
        self.real_client = httpx.AsyncClient

    def transport(self, status=200, payload=None, raw=None):
        def handle(request):
            self.requests.append(request)
            return httpx.Response(status, json=payload) if raw is None else httpx.Response(status, content=raw)
        return patch.object(bot.httpx, 'AsyncClient', side_effect=lambda **kw:
                            self.real_client(transport=httpx.MockTransport(handle), **kw))

    async def test_verification_and_deletion_use_same_opaque_session(self):
        with self.transport(payload={'text': 'Wynik ze źródłami'}):
            self.assertEqual(await bot.check('Czy to prawda?', 123), 'Wynik ze źródłami')
        body = json.loads(self.requests[-1].content)
        self.assertEqual(body['channel'], 'discord')
        self.assertEqual(body['session'], bot.session_id(123))
        with self.transport(payload={'deleted_checks': 2}):
            reply = await bot.delete_session(123)
        self.assertTrue(str(self.requests[-1].url).endswith('/' + body['session']))
        self.assertEqual(self.requests[-1].method, 'DELETE')
        self.assertIn('2', reply)
        self.assertIn('pozostają na Discordzie', reply)

    async def test_invalid_api_responses_do_not_become_verdicts(self):
        for status, payload, raw in [(503, {}, None), (200, {}, None), (200, {'text': 3}, None),
                                     (200, None, 'not json')]:
            bot.gate = bot.UserGate()
            with self.subTest(status=status, payload=payload), self.transport(status, payload, raw):
                self.assertEqual(await bot.check('Twierdzenie do sprawdzenia', 1), bot.TECHNICAL_ERROR)
                self.assertFalse(bot.gate.busy)
        with self.transport(429, {}):
            self.assertIn('Limit', await bot.check('Twierdzenie do sprawdzenia', 1))
        with self.transport(500, {}):
            self.assertIn('Nie udało', await bot.delete_session(1))

    async def test_empty_and_oversize_input_never_calls_api(self):
        with self.transport(payload={}):
            self.assertEqual(await bot.check('', 1), bot.HELP)
            self.assertIn('zbyt długa', await bot.check('x' * 6001, 1))
        self.assertEqual(self.requests, [])

    async def test_dm_attachment_and_mention_variants(self):
        for content in ['', '<@42>', '<@!42>']:
            message = SimpleNamespace(author=SimpleNamespace(bot=False, id=7), content=content,
                                      mentions=[SimpleNamespace(id=42)], attachments=[object()], reply=AsyncMock())
            message.channel = MagicMock(spec=bot.discord.DMChannel)
            message.channel.typing.return_value.__aenter__ = AsyncMock()
            message.channel.typing.return_value.__aexit__ = AsyncMock()
            with patch.object(bot.client, '_connection') as connection, self.transport(payload={}):
                connection.user = SimpleNamespace(id=42)
                await bot.on_message(message)
            self.assertIn(bot.ATTACHMENT_NOTICE, message.reply.call_args.args[0])
            self.assertFalse(message.reply.call_args.kwargs['allowed_mentions'].everyone)
        self.assertEqual(self.requests, [])

    async def test_followups_cannot_ping_users_or_everyone(self):
        interaction = SimpleNamespace(followup=SimpleNamespace(send=AsyncMock()))
        await bot.send_interaction(interaction, '@everyone <@123> ' + 'x' * 4500, ephemeral=True)
        self.assertGreater(interaction.followup.send.call_count, 1)
        for call in interaction.followup.send.call_args_list:
            self.assertLessEqual(bot.units(call.args[0]), 2000)
            self.assertTrue(call.kwargs['ephemeral'])
            self.assertFalse(call.kwargs['allowed_mentions'].everyone)
            self.assertFalse(call.kwargs['allowed_mentions'].users)

    async def test_alerts_only_on_success_and_new_repetition(self):
        state = Path(TEMP.name) / 'alerts'
        case = {'id': 'SPR-TEST', 'priority': 'wysoki', 'status': 'nowa', 'count': 3}
        channel = SimpleNamespace(send=AsyncMock())
        with patch.object(bot, 'STATE', state), patch.object(bot, 'ALERT_CHANNEL_ID', '42'), \
             patch.object(bot.client, 'fetch_channel', AsyncMock(return_value=channel)), \
             self.transport(payload={'cases': [case]}):
            await bot.moderator_alerts.coro()
            await bot.moderator_alerts.coro()
            self.assertEqual(channel.send.call_count, 1)
            case['count'] = 4
        with patch.object(bot, 'STATE', state), patch.object(bot, 'ALERT_CHANNEL_ID', '42'), \
             patch.object(bot.client, 'fetch_channel', AsyncMock(return_value=channel)), \
             self.transport(payload={'cases': [case]}):
            channel.send.side_effect = bot.discord.HTTPException(SimpleNamespace(status=403, reason='Forbidden'), 'no')
            await bot.moderator_alerts.coro()
            self.assertEqual(json.loads((state / 'discord-alerts.json').read_text())['42:SPR-TEST'], 3)
            channel.send.side_effect = None
            await bot.moderator_alerts.coro()
            self.assertEqual(json.loads((state / 'discord-alerts.json').read_text())['42:SPR-TEST'], 4)
        self.assertNotIn('Twierdzenie', channel.send.call_args.args[0])


class ApiTests(unittest.TestCase):
    def setUp(self):
        from prawdowid import ratelimit
        ratelimit.reset()  # the shared per-client limiter (backend/prawdowid/ratelimit.py)
        self.client = TestClient(api.app)  # no lifespan: no ML loading

    def test_chat_uses_same_service_and_does_not_truncate_answer(self):
        with patch.object(api, 'run_check', return_value=result()) as run:
            response = self.client.post('/api/chat-reply', json={'text': 'Twierdzenie', 'channel': 'discord',
                                                                'session': bot.session_id(1)})
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()['text']), 1900)
        self.assertIn('/analiza/test-analysis', response.json()['text'])
        self.assertEqual(run.call_args.args[0].channel, 'discord')
        self.assertEqual(run.call_args.args[0].session, bot.session_id(1))

    def test_bad_inputs_are_rejected_before_verification(self):
        with patch.object(api, 'run_check') as run:
            for text in ['', ' ', 'x' * 6001, None, 123, []]:
                with self.subTest(text=str(text)[:20]):
                    self.assertEqual(self.client.post('/api/chat-reply', json={'text': text}).status_code, 422)
            run.assert_not_called()

    def test_chat_and_web_share_an_api_rate_limit(self):
        with patch.object(api, 'settings', SimpleNamespace(rate_limit_per_min=2)), \
             patch.object(api, 'run_check', return_value=result()) as run:
            self.assertEqual(self.client.post('/api/chat-reply', json={'text': 'Twierdzenie'}).status_code, 200)
            self.assertEqual(self.client.post('/api/check', json={'text': 'Twierdzenie'}).status_code, 200)
            r = self.client.post('/api/chat-reply', json={'text': 'Twierdzenie'})
            self.assertEqual(r.status_code, 429)
            self.assertEqual(r.headers['Retry-After'], '60')
            self.assertEqual(run.call_count, 2)


class DeletionTests(unittest.TestCase):
    def test_removes_related_audit_and_repairs_shared_case(self):
        import numpy as np
        emb = np.array([1., 0.], dtype=np.float32)
        for i, session in enumerate(['owner-a', 'owner-b']):
            cid, _ = store.upsert_case(f'delete-{i}', 'Original title', emb, 'discord', False)
            r = result().model_dump()
            r.update(id=f'delete-{i}', case_id=cid)
            r['security_events'] = [{'kind': 'test', 'where': 'input', 'detail': 'masked'}]
            store.save_check(r, f'Masked owner {i}', session)
            store.log_error(r['id'], 'test', 'masked')
            store.add_feedback(r['id'], 'masked')
        self.assertEqual(store.delete_session('owner-a'), 1)
        self.assertIsNone(store.get_check('delete-0'))
        self.assertIsNotNone(store.get_check('delete-1'))
        case = next(c for c in store.list_cases() if c['id'] == cid)
        self.assertEqual(case['count'], 1)
        self.assertEqual(case['sample_check_ids'], ['delete-1'])
        self.assertEqual(case['title'], 'Masked owner 1')
        for table in ['security_events', 'errors', 'feedback']:
            self.assertEqual(store._db.execute(f'SELECT COUNT(*) FROM {table} WHERE check_id=?',
                                               ('delete-0',)).fetchone()[0], 0)
        self.assertEqual(store.delete_session('owner-b'), 1)
        self.assertFalse(any(c['id'] == cid for c in store.list_cases()))


if __name__ == '__main__':
    unittest.main()
