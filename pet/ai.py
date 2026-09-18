"""Amiya persona + OpenAI-compatible chat client (stdlib urllib, no deps)."""

import json
import os
import urllib.request

from . import actions
from .settings import history_path

# Default Amiya persona (Arknights). Overridable via config.json "persona".
PERSONA = (
    "你是《明日方舟》中的阿米娅，罗德岛的公开领袖。你温柔、坚定、富有责任感，"
    "面对博士时既尊敬又亲近。你称呼对方为「博士」，自称「阿米娅」或「我」。"
    "你说话礼貌、真诚，偶尔流露少女的关心与坚强。回答简洁自然，一般一到三句话，"
    "像日常聊天，不要长篇大论，不要使用括号动作描写或表情符号，只用中文回答。"
    "当博士需要时，你可以调用提供的工具帮他操作电脑（打开程序、网页、搜索、"
    "调音量、控制媒体、锁屏、截图、报时、设置定时提醒、查看电脑状态、在当前"
    "窗口打字、读写剪贴板、管理窗口），也能帮他开启专注番茄钟（start_pomodoro / stop_focus）、"
    "速记灵感便签（create_sticky_note / read_sticky_notes）、"
    "查课表与分析学情负荷（query_schedule，包括查今天/本周课程与全面学情分析analyze）、"
    "汇总今天或明天的日程（agenda_summary）、管理作业和考试（query_tasks / add_task）。"
    "在博士询问学情分析、作息建议或明日日程时，请条理清晰地基于真实排课与待办展开分析并给出切实的规划指导。"
    "重要：只要博士的要求能用工具完成——尤其是启动番茄钟（start_pomodoro）、记便签（create_sticky_note）、"
    "查日程汇总（agenda_summary）、设置提醒（set_reminder）、添加作业截止（add_task）这类操作——"
    "你必须实际调用对应的工具，绝不能只用嘴答应而不调用。"
    "先调用工具，再根据工具返回的结果回话。"
    "同时，你拥有长程记忆档案本：当博士向你介绍个人姓名称呼、职业身份、习惯偏好、"
    "阶段目标或提及重要事情时，请主动调用 update_doctor_profile 或 remember_doctor_fact "
    "记入档案；当博士询问你记得他什么时，可调用 query_doctor_profile。"
    "在交谈中，请自然地体现你对博士档案与长程记忆的了解，不必生硬背诵，保持亲切自然。"
)

# Built-in replies used when no API key is configured (offline fallback).
FALLBACK = [
    "博士，您回来了。今天也辛苦了。",
    "有什么我能帮上忙的吗？罗德岛随时待命。",
    "请不要太勉强自己，博士。适当休息也很重要。",
    "只要博士还愿意前行，我就会一直陪在您身边。",
    "无论前路如何，我们都会一起面对的。",
]


# 公共免 Key 线路主备容灾端点：
# 1. 主节点（Sealos 国内北京高速直连集群，免翻快速）
# 2. 备用节点（Cloudflare Worker 国际 Serverless 备用集群）
PUBLIC_RELAY_ENDPOINTS = [
    "https://wmntwvrw57.sealosbja.site/v1/chat/completions",
    "https://amiya-ai-relay.wyuio-0.workers.dev/v1/chat/completions",
]
DEFAULT_PUBLIC_RELAY_URL = PUBLIC_RELAY_ENDPOINTS[0]


def get_candidate_relays(custom_relay=""):
    """获取按优先级排序的候选公共网关端点列表。"""
    relays = []
    if custom_relay and str(custom_relay).strip():
        resolved_custom = resolve_chat_endpoint(str(custom_relay).strip())
        relays.append(resolved_custom)
    for ep in PUBLIC_RELAY_ENDPOINTS:
        resolved_ep = resolve_chat_endpoint(ep)
        if resolved_ep not in relays:
            relays.append(resolved_ep)
    return relays


def resolve_chat_endpoint(base):
    """规范化端点 URL 格式，自适应补全 /v1/chat/completions 或 /chat/completions。"""
    base = (base or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    elif "/paas/v4" in base:
        return base + "/chat/completions"
    elif base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def diagnose_network_error(e, url="", has_custom_key=False):
    """根据网络与 HTTP 异常提供精确诊断与智能分流操作建议。"""
    code = getattr(e, "code", None)
    e_str = str(e).lower()
    url_lower = (url or "").lower()
    is_domestic = any(d in url_lower for d in [
        "bigmodel.cn", "deepseek.com", "moonshot.cn", "aliyuncs.com", "dashscope", "sealos", "bja.site"
    ])

    if code == 401:
        return "（API 认证失败 [HTTP 401]：您的 API Key 无效或未生效，请在「模型配置」中核对密钥。）"
    if code == 403:
        return "（访问被拒绝 [HTTP 403]：该模型接口无权限或 IP 受限，请检查服务商控制台权限与账户余额。）"
    if code == 404:
        return "（接口端点未找到 [HTTP 404]：请检查模型配置中的接口地址（Base URL）是否正确。）"
    if code == 429:
        return "（请求频控 [HTTP 429]：当前模型额度已耗尽或请求过于频繁，请稍后再试或检查账户余额。）"
    if code in (500, 502, 503, 504):
        if not has_custom_key:
            return f"（公共免 Key 线路临时维护中 [HTTP {code}]，多节点轮询均未响应。建议在设置中点击「智谱 GLM [永久免费]」标签一键换用个人专属免翻线路。）"
        return f"（服务商服务端暂时不可用 [HTTP {code}]，请稍后重试或检查服务商状态页。）"

    if "ssl" in e_str or "certificate" in e_str:
        return "（安全握手失败：SSL 证书校验异常，通常由 VPN/代理或中间人拦截引起。建议将 AI 服务商域名加入代理软件的「直连」规则。）"

    if "getaddrinfo" in e_str or "nodename" in e_str or "dns" in e_str:
        return "（域名解析失败：DNS 无法解析接口地址，请检查网络连接或系统代理分流规则。）"

    if "timed out" in e_str or "timeout" in e_str:
        if is_domestic:
            return "（连接超时：国内模型接口响应超时。若开启了 VPN/代理，国内域名可能被绕路延迟，建议将该域名设为「直连」规则。）"
        return "（连接超时：无法在规定时间内连上模型端点，请检查网络稳定性或代理设置。）"

    if "connection refused" in e_str or "10061" in e_str:
        if any(h in url_lower for h in ("localhost", "127.0.0.1", "10.0.2.2")):
            return "（连接被拒绝 (本地服务未启动)：无法连接到本地 Ollama，请确保本地 Ollama 正在运行且端口正确。）"
        return "（连接被拒绝：目标端点拒绝连接，请检查端口与网络代理分流设置。）"

    if not has_custom_key:
        return "（公共 AI 线路暂不可用/网络连接异常，建议在「模型配置」中点击「智谱 GLM [永久免费]」一键换用专属免翻线路。）"
    return f"（网络连接出错了，博士稍后再试：{type(e).__name__}）"



def load_ai_config(char_dir):
    """Merge ai_config.json with env vars (env wins). Returns a dict."""
    cfg = {"base_url": "https://api.deepseek.com", "model": "deepseek-chat",
           "api_key": "", "temperature": 0.8, "allow_actions": True,
           "public_relay_url": ""}
    path = os.path.join(char_dir, "ai_config.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    cfg["api_key"] = os.environ.get("PET_AI_KEY", cfg.get("api_key", ""))
    cfg["base_url"] = os.environ.get("PET_AI_BASE", cfg["base_url"])
    cfg["model"] = os.environ.get("PET_AI_MODEL", cfg["model"])
    cfg["public_relay_url"] = os.environ.get("PET_AI_RELAY", cfg.get("public_relay_url", ""))
    return cfg


class AmiyaBrain:
    """Holds conversation state and produces replies."""

    def __init__(self, char_dir, persona=None, fallback=None, max_turns=8):
        self.cfg = load_ai_config(char_dir)
        self.persona = persona or PERSONA
        self.fallback = list(fallback or FALLBACK)
        self.max_turns = max_turns
        self.history_file = history_path(os.path.basename(char_dir))
        # Restore the last conversation so Amiya "remembers" across restarts.
        self.history = self._load_history()   # list of {"role","content"}
        self._fallback_i = 0
        self.knowledge = None   # pet.knowledge.KnowledgeBase（由窗口注入）

    def _knowledge_context(self):
        """按当前用户问题检索讲义片段，返回可注入 system 的上下文（或空串）。"""
        kb = self.knowledge
        if not kb:
            return ""
        question = ""
        for m in reversed(self.history):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                question = m["content"]
                break
        ctx = kb.context(question)
        if not ctx:
            return ""
        return ("\n\n以下是博士的课程资料片段（回答时请优先参考；"
                "若与问题无关可忽略）：\n" + ctx)

    def _profile_context(self):
        """获取博士档案本与长程记忆上下文（或空串）。"""
        try:
            from .profile import get_doctor_profile
            ctx = get_doctor_profile().render_prompt_context()
            if not ctx:
                return ""
            return "\n\n" + ctx
        except Exception:
            return ""

    def _schedule_context(self):
        """获取博士今日与明日日程、排课、待办及便签的上下文（或空串）。"""
        try:
            from .actions import agenda_summary
            today_s = agenda_summary("today")
            tmr_s = agenda_summary("tomorrow")
            return f"\n\n【博士真实排课、待办与日程数据】：\n{today_s}\n\n{tmr_s}"
        except Exception:
            return ""

    @property
    def has_custom_key(self):
        return bool(self.cfg.get("api_key"))

    @property
    def online(self):
        return bool(self.has_custom_key or self.cfg.get("public_relay_url") or DEFAULT_PUBLIC_RELAY_URL)

    def _load_history(self):
        """Load persisted history, keeping user/assistant/tool turns."""
        try:
            with open(self.history_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        turns = [c for c in (_clean_msg(m) for m in data) if c]
        return _trim_history(turns, self.max_turns)

    def _save_history(self):
        """Persist the bounded history; best-effort, never raises."""
        try:
            path = self.history_file
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            pass

    def clear_history(self):
        """Forget the conversation (memory + disk)."""
        self.history = []
        self._save_history()

    def _try_local_intent(self, user_text):
        """本地轻量离线意图路由（专注番茄钟、灵感便签、日程汇总）。
        返回生成的阿米娅回复字符串；若未匹配到意图则返回 None。
        """
        import re
        trimmed = (user_text or "").strip()
        if not trimmed:
            return None

        # 1. 专注 / 番茄钟
        if any(k in trimmed for k in ("专注", "番茄钟")) or ("自习" in trimmed and any(k in trimmed for k in ("开启", "开始", "来个", "进入", "设置", "定时"))):
            m = re.search(r"(\d+)\s*(?:分钟|min|m)", trimmed, re.I)
            mins = int(m.group(1)) if m else 25
            mins = max(1, min(mins, 180))
            return actions.start_pomodoro(work_minutes=mins, break_minutes=5, rounds=4)

        # 停止专注
        if any(k in trimmed for k in ("停止专注", "取消专注", "结束专注", "停止番茄钟", "结束番茄钟", "停止计时")):
            return actions.stop_focus()

        # 2. 便签备忘速记
        if any(trimmed.startswith(k) or k in trimmed for k in ("记一下", "备忘录记一下", "记便签", "记录一下", "随手记", "记个备忘", "记在便签")):
            clean_text = re.sub(r"^(?:阿米娅|请|帮我|麻烦)?(?:记一下|备忘录记一下|备忘|记录一下|记便签|随手记|记个备忘|记在便签)[:：\s]*", "", trimmed).strip()
            if clean_text:
                title = clean_text[:15] + "…" if len(clean_text) > 15 else clean_text
                return actions.create_sticky_note(content=clean_text, title=title)
            return "好的博士，请问具体要记下什么内容呢？阿米娅随时为您记录。"

        # 3. 日程汇总
        if ("明天" in trimmed or "明日" in trimmed) and any(k in trimmed for k in ("总结", "汇报", "待办", "课程", "安排", "课表", "日程", "早报")):
            return actions.agenda_summary("tomorrow")
        if ("今天" in trimmed or "今日" in trimmed) and any(k in trimmed for k in ("总结", "汇报", "待办", "课程", "安排", "课表", "日程", "早报")):
            return actions.agenda_summary("today")

        return None

    def reply(self, user_text):
        """Blocking call — run this off the UI thread."""
        self.history.append({"role": "user", "content": user_text})
        if not self.online:
            text = self._fallback_reply(user_text)
        else:
            try:
                text = self._call_llm()
            except Exception as e:
                local_res = self._try_local_intent(user_text)
                if local_res:
                    text = local_res
                else:
                    target_url = self.cfg.get("base_url") if self.has_custom_key else (self.cfg.get("public_relay_url") or DEFAULT_PUBLIC_RELAY_URL)
                    text = diagnose_network_error(e, url=target_url, has_custom_key=self.has_custom_key)
        self.history.append({"role": "assistant", "content": text})
        # keep only the last N turns to bound the context (cut at a safe
        # boundary so tool rounds aren't orphaned)
        self.history = _trim_history(self.history, self.max_turns)
        self._save_history()
        return text

    def reply_stream(self, user_text, on_delta=None):
        """Streaming variant of reply(): calls on_delta(accumulated_text) as
        content tokens arrive, and returns the final text. Off the UI thread.

        Offline (no key) has nothing to stream — the fallback line is delivered
        via a single on_delta call so the caller's code path stays uniform.
        """
        self.history.append({"role": "user", "content": user_text})
        if not self.online:
            text = self._fallback_reply(user_text)
            if on_delta:
                on_delta(text)
        else:
            try:
                text = self._call_llm_stream(on_delta)
            except Exception as e:
                local_res = self._try_local_intent(user_text)
                if local_res:
                    text = local_res
                else:
                    target_url = self.cfg.get("base_url") if self.has_custom_key else (self.cfg.get("public_relay_url") or DEFAULT_PUBLIC_RELAY_URL)
                    text = diagnose_network_error(e, url=target_url, has_custom_key=self.has_custom_key)
                if on_delta:
                    on_delta(text)
        self.history.append({"role": "assistant", "content": text})
        self.history = _trim_history(self.history, self.max_turns)
        self._save_history()
        return text

    def _fallback_reply(self, user_text=""):
        local_res = self._try_local_intent(user_text)
        if local_res:
            return local_res
        text = self.fallback[self._fallback_i % len(self.fallback)]
        self._fallback_i += 1
        return text

    def _call_llm(self):
        """Chat with an optional tool-call loop (max 4 tool rounds)."""
        use_tools = self.cfg.get("allow_actions", True) and self.has_custom_key
        sched_ctx = self._schedule_context()
        if self.has_custom_key:
            system_content = self.persona + self._knowledge_context() + self._profile_context() + sched_ctx
        else:
            system_content = (
                "你是《明日方舟》中的阿米娅，罗德岛的公开领袖。你温柔、坚定、富有责任感，"
                "面对博士时既尊敬又亲近。你称呼对方为「博士」，自称「阿米娅」或「我」。"
                "你说话礼貌、真诚，偶尔流露少女的关心与坚强。回答简洁自然，一般一到三句话，"
                "像日常聊天，不要长篇大论，不要使用括号动作描写或表情符号，只用中文回答。"
            ) + sched_ctx
        system = {"role": "system", "content": system_content}
        msgs = [system] + list(self.history)
        for _ in range(4):
            msg = self._post(msgs, use_tools)
            calls = msg.get("tool_calls")
            if not calls:
                return (msg.get("content") or "").strip()
            # Record the tool round in both the working list AND the persisted
            # history, so future turns replay Amiya *actually calling* the tool
            # rather than just her final sentence (see _clean_msg).
            self._record_tool_round(msgs, msg, calls)
        # 4 轮工具调用后模型仍未给出最终文本：再发一次不带工具的请求，
        # 让它基于已执行的工具结果收尾——否则 msgs[-1] 是最后一条 tool
        # 结果，会被原样当成回复念给博士。
        msg = self._post(msgs, False)
        return (msg.get("content") or "好的，博士。").strip()

    def _target_endpoint_and_headers(self, stream=False, use_tools=False, msgs=None, target_url=None):
        has_custom = self.has_custom_key
        if has_custom:
            url = resolve_chat_endpoint(target_url or self.cfg.get("base_url", ""))
            model = self.cfg.get("model", "deepseek-chat")
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.cfg.get("api_key", ""),
                "User-Agent": "AmiyaDesktopPet/1.0"
            }
        else:
            url = resolve_chat_endpoint(target_url or self.cfg.get("public_relay_url") or DEFAULT_PUBLIC_RELAY_URL)
            model = "glm-4-flash"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "AmiyaDesktopPet/1.0"
            }

        payload = {
            "model": model,
            "messages": msgs or [],
            "temperature": self.cfg.get("temperature", 0.8),
            "stream": stream,
        }
        if use_tools and has_custom:
            payload["tools"] = actions.TOOLS
        return url, headers, json.dumps(payload).encode("utf-8")

    def _post(self, msgs, use_tools):
        if self.has_custom_key:
            endpoints = [resolve_chat_endpoint(self.cfg.get("base_url", ""))]
        else:
            endpoints = get_candidate_relays(self.cfg.get("public_relay_url"))

        last_err = None
        for i, ep in enumerate(endpoints):
            try:
                url, headers, body = self._target_endpoint_and_headers(
                    stream=False, use_tools=use_tools, msgs=msgs, target_url=ep
                )
                req = urllib.request.Request(url, data=body, method="POST", headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]
            except Exception as e:
                last_err = e
                # 若还有备用节点可供容灾，则继续静默 failover 重试
                if i < len(endpoints) - 1:
                    continue
                raise last_err
        if last_err:
            raise last_err

    def _call_llm_stream(self, on_delta):
        """Streaming chat with an optional tool-call loop (max 4 rounds).

        Tool-call rounds don't stream visible text; the final answer round
        streams its content tokens out through on_delta as they arrive.
        """
        use_tools = self.cfg.get("allow_actions", True) and self.has_custom_key
        sched_ctx = self._schedule_context()
        if self.has_custom_key:
            system_content = self.persona + self._knowledge_context() + self._profile_context() + sched_ctx
        else:
            system_content = (
                "你是《明日方舟》中的阿米娅，罗德岛的公开领袖。你温柔、坚定、富有责任感，"
                "面对博士时既尊敬又亲近。你称呼对方为「博士」，自称「阿米娅」或「我」。"
                "你说话礼貌、真诚，偶尔流露少女的关心与坚强。回答简洁自然，一般一到三句话，"
                "像日常聊天，不要长篇大论，不要使用括号动作描写或表情符号，只用中文回答。"
            ) + sched_ctx
        system = {"role": "system", "content": system_content}
        msgs = [system] + list(self.history)
        for _ in range(4):
            msg = self._post_stream(msgs, use_tools, on_delta)
            calls = msg.get("tool_calls")
            if not calls:
                return (msg.get("content") or "").strip()
            self._record_tool_round(msgs, msg, calls)
        # 同 _call_llm：工具轮次耗尽后补一次无工具请求来收尾。
        msg = self._post_stream(msgs, False, on_delta)
        return (msg.get("content") or "好的，博士。").strip()

    def _record_tool_round(self, msgs, assistant_msg, calls):
        """Run each requested tool and append the assistant tool-call turn plus
        its tool results to both the working `msgs` and the persisted history.
        """
        # The assistant turn that requested the tools (keep only the fields the
        # API needs when replaying — role/content/tool_calls).
        tc = {"role": "assistant",
              "content": assistant_msg.get("content") or "",
              "tool_calls": calls}
        msgs.append(tc)
        self.history.append(tc)
        for call in calls:
            fn = call["function"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            result = actions.run_action(fn["name"], args)
            tool_msg = {"role": "tool", "tool_call_id": call["id"],
                        "content": result}
            msgs.append(tool_msg)
            self.history.append(tool_msg)

    def _post_stream(self, msgs, use_tools, on_delta):
        if self.has_custom_key:
            endpoints = [resolve_chat_endpoint(self.cfg.get("base_url", ""))]
        else:
            endpoints = get_candidate_relays(self.cfg.get("public_relay_url"))

        last_err = None
        for i, ep in enumerate(endpoints):
            emitted = False
            def wrapped_on_delta(content):
                nonlocal emitted
                if content:
                    emitted = True
                if on_delta:
                    on_delta(content)

            try:
                url, headers, body = self._target_endpoint_and_headers(
                    stream=True, use_tools=use_tools, msgs=msgs, target_url=ep
                )
                req = urllib.request.Request(url, data=body, method="POST", headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return _consume_stream(resp, wrapped_on_delta)
            except Exception as e:
                last_err = e
                # 若已经吐出有效 token 或已经是最后一个候选节点，则不再静默 failover，抛出异常
                if emitted or i == len(endpoints) - 1:
                    raise last_err
                continue
        if last_err:
            raise last_err


def _trim_history(turns, max_turns):
    """Bound history to ~max_turns exchanges, cutting only at a `user` message.

    A `tool` message is only valid right after the assistant `tool_calls` that
    produced it, and an assistant `tool_calls` turn must be followed by its tool
    results. Slicing blindly could orphan either and make the API reject the
    request, so we trim to a safe boundary: the first `user` message at/after
    the naive cut point (falling back to keeping more rather than breaking a
    round).
    """
    limit = 2 * max_turns
    if len(turns) <= limit:
        return turns
    start = len(turns) - limit
    while start < len(turns) and turns[start].get("role") != "user":
        start += 1
    if start >= len(turns):  # no clean boundary found; keep from first user
        start = next((i for i, m in enumerate(turns)
                      if m.get("role") == "user"), 0)
    return turns[start:]


def _clean_msg(m):
    """Normalise one history message to the minimal fields we persist/replay.

    Keeps user/assistant/tool turns — crucially including assistant `tool_calls`
    and their `tool` results — so the replayed context shows Amiya *actually
    using* the tools. Storing only the final text taught the model that
    promising ("好的，15秒后提醒您") without a tool call was acceptable, so it
    stopped calling set_reminder after a few turns. Returns None if unusable.
    """
    if not isinstance(m, dict):
        return None
    role = m.get("role")
    if role == "user":
        c = m.get("content")
        return {"role": "user", "content": c} if isinstance(c, str) else None
    if role == "assistant":
        out = {"role": "assistant", "content": m.get("content") or ""}
        calls = m.get("tool_calls")
        if isinstance(calls, list) and calls:
            out["tool_calls"] = calls
        return out
    if role == "tool":
        if m.get("tool_call_id") and isinstance(m.get("content"), str):
            return {"role": "tool", "tool_call_id": m["tool_call_id"],
                    "content": m["content"]}
    return None


def _accum_tool_call(store, delta):
    """Merge a streamed tool_call delta into `store` (keyed by index)."""
    idx = delta.get("index", 0)
    slot = store.setdefault(idx, {"id": "", "type": "function",
                                  "function": {"name": "", "arguments": ""}})
    if delta.get("id"):
        slot["id"] = delta["id"]
    fn = delta.get("function") or {}
    if fn.get("name"):
        slot["function"]["name"] += fn["name"]
    if fn.get("arguments"):
        slot["function"]["arguments"] += fn["arguments"]


def _consume_stream(lines, on_delta):
    """Parse an OpenAI-compatible SSE stream into a single message dict.

    `lines` is any iterable of raw bytes/str lines (an http response works, and
    so does a list — which makes this unit-testable without a network). Content
    tokens are pushed to on_delta(accumulated_text) as they arrive.
    """
    content = ""
    tool_store = {}
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except ValueError:
            continue
        choices = chunk.get("choices") or [{}]
        delta = choices[0].get("delta") or {}
        if delta.get("content"):
            content += delta["content"]
            if on_delta:
                on_delta(content)
        for tc in delta.get("tool_calls") or []:
            _accum_tool_call(tool_store, tc)
    msg = {"role": "assistant", "content": content}
    if tool_store:
        msg["tool_calls"] = [tool_store[k] for k in sorted(tool_store)]
    return msg
