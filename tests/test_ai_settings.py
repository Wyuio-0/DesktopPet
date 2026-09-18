"""Unit tests for AI settings dialog, provider presets, and connectivity test."""

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from PyQt5 import QtCore, QtWidgets

from pet.ai_settings import (
    PROVIDERS,
    AiSettingsDialog,
    do_test_connection,
)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])
    return app


class TestProviderPresets:
    def test_providers_structure(self):
        assert len(PROVIDERS) >= 7
        names = [p[0] for p in PROVIDERS]
        assert "智谱 GLM" in names
        assert "DeepSeek" in names
        assert "Kimi" in names
        assert "通义千问" in names
        assert "OpenAI" in names
        assert "本地 Ollama" in names
        assert "自定义" in names

        # Check that preset entries have 4 elements: (name, url, model, tag)
        for p in PROVIDERS[:-1]:
            assert len(p) == 4
            name, url, model, tag = p
            assert name and url and model and tag


class TestConnectivity:
    def test_empty_inputs(self):
        ok, msg = do_test_connection("", "gpt-4o", "sk-xxx")
        assert not ok
        assert "不能为空" in msg

        ok, msg = do_test_connection("https://api.openai.com", "", "sk-xxx")
        assert not ok
        assert "不能为空" in msg

    @patch("urllib.request.urlopen")
    def test_success_200(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b'{"choices": [{"message": {"content": "pong"}}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        ok, msg = do_test_connection("https://api.deepseek.com", "deepseek-chat", "sk-123456")
        assert ok
        assert "连接成功" in msg
        assert "HTTP 200" in msg

    @patch("urllib.request.urlopen")
    def test_http_401_error(self, mock_urlopen):
        err_body = json.dumps({"error": {"message": "Invalid API Key"}}).encode("utf-8")
        fp = io.BytesIO(err_body)
        err = urllib.error.HTTPError("https://api.deepseek.com", 401, "Unauthorized", {}, fp)
        mock_urlopen.side_effect = err

        ok, msg = do_test_connection("https://api.deepseek.com", "deepseek-chat", "bad-key")
        assert not ok
        assert "HTTP 401" in msg
        assert "API Key 无效" in msg or "Invalid API Key" in msg

    @patch("urllib.request.urlopen")
    def test_timeout_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("timed out")

        ok, msg = do_test_connection("https://api.deepseek.com", "deepseek-chat", "key")
        assert not ok
        assert "连接超时" in msg

    @patch("urllib.request.urlopen")
    def test_connection_refused_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        ok, msg = do_test_connection("http://localhost:11434/v1", "qwen2.5:7b", "")
        assert not ok
        assert "连接被拒绝" in msg


class TestAiSettingsDialogUI:
    def test_dialog_chips_and_combobox_sync(self, qapp, tmp_path):
        char_dir = str(tmp_path)
        dlg = AiSettingsDialog(char_dir, effective_cfg={
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "api_key": "demo-key"
        })

        # Initially DeepSeek chip should be checked
        deepseek_idx = [i for i, p in enumerate(PROVIDERS[:-1]) if p[0] == "DeepSeek"][0]
        assert dlg.chip_buttons[deepseek_idx].isChecked()
        assert dlg.provider.currentIndex() == deepseek_idx

        # Click Zhipu GLM chip (index 0)
        dlg._on_chip_clicked(0)
        assert dlg.base_url.text() == "https://open.bigmodel.cn/api/paas/v4"
        assert dlg.model.text() == "glm-4-flash"
        assert dlg.chip_buttons[0].isChecked()
        assert not dlg.chip_buttons[deepseek_idx].isChecked()
        assert dlg.provider.currentIndex() == 0

        # Change URL to custom URL
        dlg.base_url.setText("https://custom.relay.com/v1")
        # All chips should be unchecked
        assert not any(b.isChecked() for b in dlg.chip_buttons)
        # Combobox should be "自定义" (last item)
        assert dlg.provider.currentIndex() == len(PROVIDERS) - 1

        dlg.close()
