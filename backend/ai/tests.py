import io
import json
import socket
import urllib.error
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from farms.models import Farm, SoilRecord

from . import services


def _gemini_response(text="Plant maize at the start of the rains.", grounded=True):
    candidate = {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}
    if grounded:
        candidate["groundingMetadata"] = {
            "webSearchQueries": ["maize planting season Uganda"],
            "searchEntryPoint": {"renderedContent": "<div class='chips'>maize planting</div>"},
            "groundingChunks": [
                {"web": {"uri": "https://vertexaisearch.cloud.google.com/a", "title": "naro.go.ug"}},
                {"web": {"uri": "https://vertexaisearch.cloud.google.com/a", "title": "naro.go.ug"}},
                {"web": {"uri": "javascript:alert(1)", "title": "bad"}},
            ],
        }
    return {"candidates": [candidate]}


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _ok(payload):
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


def _http_error(code=400):
    return urllib.error.HTTPError(
        services.API_URL, code, "Bad Request", {}, io.BytesIO(b'{"error": {"message": "Search grounding is not available"}}')
    )


class ParseResponseTests(SimpleTestCase):
    def test_grounded_answer_keeps_https_sources_once(self):
        reply = services.parse_response(_gemini_response())
        self.assertEqual(reply["text"], "Plant maize at the start of the rains.")
        self.assertEqual(reply["sources"], [{"title": "naro.go.ug", "uri": "https://vertexaisearch.cloud.google.com/a"}])
        self.assertIn("chips", reply["search_html"])
        self.assertTrue(reply["web"])

    def test_answer_without_search(self):
        reply = services.parse_response(_gemini_response(grounded=False))
        self.assertEqual(reply["sources"], [])
        self.assertEqual(reply["search_html"], "")
        self.assertFalse(reply["web"])

    def test_thought_parts_are_left_out(self):
        data = _gemini_response(grounded=False)
        data["candidates"][0]["content"]["parts"].insert(0, {"text": "internal reasoning", "thought": True})
        self.assertEqual(services.parse_response(data)["text"], "Plant maize at the start of the rains.")

    def test_blocked_or_empty_answers_return_none(self):
        self.assertIsNone(services.parse_response({"promptFeedback": {"blockReason": "SAFETY"}}))
        self.assertIsNone(services.parse_response({"candidates": [{"finishReason": "SAFETY"}]}))


@override_settings(GEMINI_API_KEY="test-key", GEMINI_MODEL="test-model", GEMINI_WEB_SEARCH=True)
class AskGeminiTests(SimpleTestCase):
    @override_settings(GEMINI_API_KEY="")
    def test_no_key_means_no_request(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            self.assertIsNone(services.ask_gemini("hello"))
        urlopen.assert_not_called()

    def test_request_uses_search_header_key_and_history(self):
        history = [{"sender": "user", "text": "Hi"}, {"sender": "bot", "text": "Hello!"}]
        with mock.patch("urllib.request.urlopen", return_value=_ok(_gemini_response())) as urlopen:
            reply = services.ask_gemini("When do I plant maize?", history=history, farm_context="Farm in Gulu.")
        self.assertTrue(reply["web"])

        request = urlopen.call_args.args[0]
        self.assertIn("models/test-model:generateContent", request.full_url)
        self.assertNotIn("test-key", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")

        body = json.loads(request.data)
        self.assertEqual(body["tools"], [{"google_search": {}}])
        self.assertEqual([c["role"] for c in body["contents"]], ["user", "model", "user"])
        self.assertEqual(body["contents"][-1]["parts"][0]["text"], "When do I plant maize?")
        self.assertIn("Farm in Gulu.", body["system_instruction"]["parts"][0]["text"])

    def test_history_is_trimmed(self):
        history = [{"sender": "user", "text": f"q{i}"} for i in range(20)]
        with mock.patch("urllib.request.urlopen", return_value=_ok(_gemini_response())) as urlopen:
            services.ask_gemini("latest", history=history)
        body = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(len(body["contents"]), services.HISTORY_MESSAGES + 1)

    def test_refused_search_retries_without_search(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=[_http_error(), _ok(_gemini_response(grounded=False))]) as urlopen:
            with self.assertLogs("ai.services", "WARNING"):
                reply = services.ask_gemini("hello")
        self.assertFalse(reply["web"])
        self.assertEqual(urlopen.call_count, 2)
        self.assertNotIn("tools", json.loads(urlopen.call_args_list[1].args[0].data))

    def test_timeout_does_not_retry(self):
        with mock.patch("urllib.request.urlopen", side_effect=socket.timeout()) as urlopen:
            with self.assertLogs("ai.services", "WARNING"):
                self.assertIsNone(services.ask_gemini("hello"))
        self.assertEqual(urlopen.call_count, 1)

    @override_settings(GEMINI_WEB_SEARCH=False)
    def test_search_can_be_switched_off(self):
        with mock.patch("urllib.request.urlopen", return_value=_ok(_gemini_response(grounded=False))) as urlopen:
            services.ask_gemini("hello")
        self.assertNotIn("tools", json.loads(urlopen.call_args.args[0].data))


@override_settings(GEMINI_API_KEY="test-key", GEMINI_DAILY_LIMIT=2)
class ChatViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("farmer1", password="Sm0ke!pass123")
        self.farm = Farm.objects.create(user=self.user, farm_name="Hill Farm", district="Gulu",
                                        subcounty="Bardege", size_acres=2, soil_type="Loam")
        SoilRecord.objects.create(farm=self.farm, nitrogen=20, phosphorus=40, potassium=40, ph=6.5,
                                  temperature=24, humidity=70, rainfall=1200)
        self.client.force_login(self.user)

    def _ask(self, message="When do I plant maize?", farm_id=None):
        return self.client.post(reverse("ai:chat"), {"message": message, "farm_id": farm_id or ""})

    def test_web_answer_is_shown_with_sources_and_suggestions(self):
        reply = services.parse_response(_gemini_response())
        with mock.patch("ai.views.ask_gemini", return_value=reply) as ask:
            self.assertRedirects(self._ask(farm_id=self.farm.id), reverse("ai:chat"))
        self.assertIn("Gulu District", ask.call_args.kwargs["farm_context"])

        page = self.client.get(reverse("ai:chat"))
        self.assertContains(page, "AI answer using a web search")
        self.assertContains(page, 'href="https://vertexaisearch.cloud.google.com/a"')
        self.assertContains(page, "srcdoc=")
        self.assertContains(page, f'value="{self.farm.id}" selected')

    def test_failed_ai_falls_back_to_crop_guide(self):
        with mock.patch("ai.views.ask_gemini", return_value=None):
            self._ask("How do I deal with caterpillars?")
        page = self.client.get(reverse("ai:chat"))
        self.assertContains(page, "From the CropAI crop guide")

    def test_daily_limit_stops_ai_calls(self):
        reply = services.parse_response(_gemini_response(grounded=False))
        with mock.patch("ai.views.ask_gemini", return_value=reply) as ask:
            for _ in range(3):
                self._ask()
        self.assertEqual(ask.call_count, 2)
        self.assertContains(self.client.get(reverse("ai:chat")), "used today's AI answers")

    def test_other_users_farm_and_bad_ids_are_ignored(self):
        other = User.objects.create_user("farmer2", password="Sm0ke!pass123")
        other_farm = Farm.objects.create(user=other, farm_name="Not Yours", district="Mbale",
                                         subcounty="X", size_acres=1, soil_type="Clay")
        with mock.patch("ai.views.ask_gemini", return_value=None) as ask:
            self._ask(farm_id=other_farm.id)
            self._ask(farm_id="abc")
        for call in ask.call_args_list:
            self.assertEqual(call.kwargs["farm_context"], "")

    def test_history_is_capped(self):
        with mock.patch("ai.views.ask_gemini", return_value=None):
            for i in range(15):
                self._ask(f"question {i}")
        self.assertEqual(len(self.client.session["chat_history"]), 20)
