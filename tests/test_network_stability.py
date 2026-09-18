"""Unit tests for public relay failover and intelligent network diagnostics."""

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from pet.ai import (
    DEFAULT_PUBLIC_RELAY_URL,
    PUBLIC_RELAY_ENDPOINTS,
    AmiyaBrain,
    diagnose_network_error,
    get_candidate_relays,
    resolve_chat_endpoint,
)
from pet.ai_settings import do_test_connection


class TestRelayResolution:
    def test_candidate_relays_order(self):
        relays = get_candidate_relays()
        assert len(relays) >= 2
        assert "sealosbja.site" in relays[0]
        assert "workers.dev" in relays[1]

    def test_candidate_relays_with_custom(self):
        custom = "https://my-relay.example.com/v1"
        relays = get_candidate_relays(custom)
        assert relays[0] == "https://my-relay.example.com/v1/chat/completions"
        assert "sealosbja.site" in relays[1]
        assert "workers.dev" in relays[2]

    def test_resolve_chat_endpoint(self):
        assert resolve_chat_endpoint("https://api.deepseek.com") == "https://api.deepseek.com/v1/chat/completions"
        assert resolve_chat_endpoint("https://open.bigmodel.cn/api/paas/v4") == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        assert resolve_chat_endpoint("https://wmntwvrw57.sealosbja.site/v1/chat/completions") == "https://wmntwvrw57.sealosbja.site/v1/chat/completions"
        assert resolve_chat_endpoint("https://api.openai.com/v1") == "https://api.openai.com/v1/chat/completions"


class TestNetworkDiagnostics:
    def test_auth_401_error(self):
        err = urllib.error.HTTPError("https://api.deepseek.com", 401, "Unauthorized", {}, io.BytesIO(b""))
        diag = diagnose_network_error(err, url="https://api.deepseek.com", has_custom_key=True)
        assert "API 认证失败" in diag
        assert "401" in diag

    def test_rate_limit_429_error(self):
        err = urllib.error.HTTPError("https://api.deepseek.com", 429, "Too Many Requests", {}, io.BytesIO(b""))
        diag = diagnose_network_error(err, url="https://api.deepseek.com", has_custom_key=True)
        assert "请求频控" in diag
        assert "429" in diag

    def test_public_relay_503_error(self):
        err = urllib.error.HTTPError("https://wmntwvrw57.sealosbja.site", 503, "Service Unavailable", {}, io.BytesIO(b""))
        diag = diagnose_network_error(err, url="https://wmntwvrw57.sealosbja.site", has_custom_key=False)
        assert "公共免 Key 线路临时维护中" in diag
        assert "智谱 GLM" in diag

    def test_ssl_proxy_error(self):
        err = urllib.error.URLError("CERTIFICATE_VERIFY_FAILED: certificate verify failed")
        diag = diagnose_network_error(err, url="https://open.bigmodel.cn", has_custom_key=True)
        assert "安全握手失败" in diag
        assert "直连" in diag

    def test_dns_resolution_error(self):
        err = urllib.error.URLError("getaddrinfo failed")
        diag = diagnose_network_error(err, url="https://api.deepseek.com", has_custom_key=True)
        assert "域名解析失败" in diag

    def test_domestic_timeout_error(self):
        err = urllib.error.URLError("timed out")
        diag = diagnose_network_error(err, url="https://open.bigmodel.cn/api/paas/v4", has_custom_key=True)
        assert "国内模型接口响应超时" in diag
        assert "直连" in diag

    def test_local_ollama_refused(self):
        err = urllib.error.URLError("connection refused")
        diag = diagnose_network_error(err, url="http://127.0.0.1:11434/v1", has_custom_key=False)
        assert "本地服务未启动" in diag
        assert "Ollama" in diag


class TestFailoverExecution:
    @patch("urllib.request.urlopen")
    def test_public_relay_failover_post(self, mock_urlopen, tmp_path):
        brain = AmiyaBrain(str(tmp_path))
        brain.cfg["api_key"] = ""  # 使用公共线路

        resp_ok = MagicMock()
        resp_ok.__enter__.return_value = resp_ok
        resp_ok.read.return_value = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "来自备用节点阿米娅的回复"}}]
        }).encode("utf-8")

        # 第一次请求（主节点 Sealos）抛出 503 错误，第二次（备用节点 CF）成功
        err_503 = urllib.error.HTTPError("https://wmntwvrw57.sealosbja.site", 503, "Unavailable", {}, io.BytesIO(b""))
        mock_urlopen.side_effect = [err_503, resp_ok]

        reply = brain.reply("博士，你好")
        assert reply == "来自备用节点阿米娅的回复"
        assert mock_urlopen.call_count == 2

    @patch("urllib.request.urlopen")
    def test_public_relay_all_nodes_fail_503(self, mock_urlopen, tmp_path):
        brain = AmiyaBrain(str(tmp_path))
        brain.cfg["api_key"] = ""  # 使用公共线路

        err_503_1 = urllib.error.HTTPError("https://wmntwvrw57.sealosbja.site", 503, "Unavailable", {}, io.BytesIO(b""))
        err_503_2 = urllib.error.HTTPError("https://amiya-ai-relay.wyuio-0.workers.dev", 503, "Unavailable", {}, io.BytesIO(b""))
        mock_urlopen.side_effect = [err_503_1, err_503_2]

        reply = brain.reply("博士，你好")
        assert "公共免 Key" in reply
        assert "智谱 GLM" in reply

    @patch("urllib.request.urlopen")
    def test_public_relay_timeout_diagnostic(self, mock_urlopen, tmp_path):
        brain = AmiyaBrain(str(tmp_path))
        brain.cfg["api_key"] = ""
        mock_urlopen.side_effect = [urllib.error.URLError("timed out"), urllib.error.URLError("timed out")]
        reply = brain.reply("博士，你好")
        assert "超时" in reply
        assert "VPN" in reply
