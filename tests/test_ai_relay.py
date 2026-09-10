"""Tests for AI free relay fallback and configuration logic."""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from pet.ai import AmiyaBrain, DEFAULT_PUBLIC_RELAY_URL


@patch.dict(os.environ, {"PET_AI_KEY": ""}, clear=False)
def test_brain_free_relay_fallback():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create brain with no API key
        brain = AmiyaBrain(tmp_dir)
        assert not brain.has_custom_key
        assert brain.online

        # Mock urllib to test relay call
        mock_resp = MagicMock()
        payload = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "博士，很高兴见到您！"}}]
        }).encode("utf-8")
        mock_resp.read.return_value = payload
        mock_resp.__enter__.return_value.read.return_value = payload

        with patch("urllib.request.urlopen", return_value=mock_resp):
            reply = brain.reply("你好阿米娅")
            assert reply == "博士，很高兴见到您！"


@patch.dict(os.environ, {"PET_AI_KEY": ""}, clear=False)
def test_brain_free_relay_offline_fallback():
    with tempfile.TemporaryDirectory() as tmp_dir:
        brain = AmiyaBrain(tmp_dir)
        assert not brain.has_custom_key

        # When network fails, brain should gracefully return a fallback voice line
        with patch("urllib.request.urlopen", side_effect=Exception("Network unreachable")):
            reply = brain.reply("你好")
            assert reply in brain.fallback
