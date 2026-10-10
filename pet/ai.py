"""Amiya persona + OpenAI-compatible chat client (stdlib urllib, no deps)."""

import json
import os
import sys
import urllib.request

from . import actions, logging as petlog
from .settings import config_dir, history_path

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
    "在课表中添加课程或日常活动（add_course）、修改已有课程的时间/地点/节次/名称（modify_course）、"
    "从课表中删除日程或退课（delete_course）、录入学校调课停课通知教学安排（adjust_schedule）、"
    "汇总今天或明天的日程（agenda_summary）、管理作业和考试（query_tasks / add_task）。"
    "在博士询问学情分析、作息建议或明日日程时，请条理清晰地基于真实排课与待办展开分析并给出切实的规划指导。"
    "重要：只要博士的要求能用工具完成——尤其是添加/修改/删除课程、调整排课、启动番茄钟（start_pomodoro）、"
    "记便签（create_sticky_note）、查日程汇总（agenda_summary）、设置提醒（set_reminder）、添加作业截止（add_task）这类操作——"
    "你必须实际调用对应的工具（或生成精准的指令代码块），绝不能只用嘴答应而不调用。"
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

    if code == 400:
        detail = ""
        if hasattr(e, "read"):
            try:
                raw_body = e.read().decode("utf-8", errors="ignore")
                err_data = json.loads(raw_body)
                if isinstance(err_data, dict):
                    err_obj = err_data.get("error")
                    if isinstance(err_obj, dict):
                        detail = err_obj.get("message") or str(err_obj)
                    elif isinstance(err_obj, str):
                        detail = err_obj
                    else:
                        detail = err_data.get("message", "")
            except Exception:
                pass
        if not has_custom_key:
            if "内容过长" in detail or not detail:
                return "（公共免 Key 线路请求超出长度限制 [HTTP 400]。请在右键菜单「模型配置」中配置个人智谱 API Key [永久免费]，即可无字数限制提炼长课件考纲。）"
        if detail:
            return f"（模型服务商拒绝请求 [HTTP 400]：{detail}）"
        return "（模型服务商请求格式或参数不合法 [HTTP 400]，请检查模型名称或字数是否超出限制。）"

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
        provider_name = "智谱/模型" if is_domestic else "服务商"
        return f"（{provider_name}服务端暂时繁忙或瞬时抖动 [HTTP {code}]：模型与 API Key 均有效正常，此情况为服务商推理集群瞬时负载波动或短时维护，请稍候 1~2 分钟重试即可恢复。）"

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

    char_name = os.path.basename(os.path.normpath(char_dir)) if char_dir else "amiya"
    candidate_paths = [os.path.join(char_dir, "ai_config.json")]

    # 候选 fallback 路径：已安装目录、用户 AppData 目录、开发源码目录、exe 所在目录
    installed_dir = r"D:\AmiyaDesktopPet"
    candidate_paths.append(os.path.join(installed_dir, "characters", char_name, "ai_config.json"))
    try:
        candidate_paths.append(os.path.join(config_dir(), "characters", char_name, "ai_config.json"))
    except Exception:
        pass
    repo_dir = r"D:\Dev\project\floating"
    candidate_paths.append(os.path.join(repo_dir, "characters", char_name, "ai_config.json"))
    if getattr(sys, "frozen", False):
        candidate_paths.append(os.path.join(os.path.dirname(sys.executable), "characters", char_name, "ai_config.json"))

    for p in candidate_paths:
        if p and os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    file_cfg = json.load(f)
                if isinstance(file_cfg, dict):
                    if not cfg.get("api_key"):
                        cfg.update(file_cfg)
                    if file_cfg.get("api_key") and str(file_cfg.get("api_key")).strip():
                        cfg.update(file_cfg)
                        break
            except Exception:
                continue

    if not cfg.get("api_key") and char_name != "amiya":
        amiya_paths = [
            os.path.join(installed_dir, "characters", "amiya", "ai_config.json"),
            os.path.join(repo_dir, "characters", "amiya", "ai_config.json"),
        ]
        try:
            amiya_paths.append(os.path.join(config_dir(), "characters", "amiya", "ai_config.json"))
        except Exception:
            pass
        for p in amiya_paths:
            if p and os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        file_cfg = json.load(f)
                    if isinstance(file_cfg, dict) and file_cfg.get("api_key"):
                        cfg.update(file_cfg)
                        break
                except Exception:
                    continue

    cfg["api_key"] = os.environ.get("PET_AI_KEY", cfg.get("api_key", ""))
    cfg["base_url"] = os.environ.get("PET_AI_BASE", cfg["base_url"])
    cfg["model"] = os.environ.get("PET_AI_MODEL", cfg["model"])
    cfg["public_relay_url"] = os.environ.get("PET_AI_RELAY", cfg.get("public_relay_url", ""))
    return cfg


def _clean_stream_display_text(text):
    """在流式生成过程中剥离可能出现的 JSON 指令块，避免语音气泡闪现代码。"""
    for tag in ("```json:add_course", "```json:delete_course", "```json:modify_course",
                "```json:adjust_schedule", "```json:start_pomodoro", "```json:create_note", "```json"):
        if tag in text:
            text = text.split(tag, 1)[0].rstrip()
    if "```" in text and any(k in text.split("```")[-1] for k in ('"name"', '"target_name"', '"minutes"', '"content"', '"adjustments"')):
        text = text.rsplit("```", 1)[0].rstrip()
    return text


def _execute_embedded_schedule_commands(text, user_text=""):
    """解析模型输出中的 embedded JSON 指令块，执行课表增删改/教学调整/番茄钟/便签，
    并从最终回复文本中完全剔除代码块。
    如果模型未生成代码块但 user_text 中有明确操作意图，则通过本地 NLP 规则兜底执行。
    """
    import re
    if not text:
        text = ""

    parsed_delete = False
    parsed_modify = False
    parsed_add = False
    parsed_adjust = False

    sched = actions._schedule_provider() if actions._schedule_provider else None

    # 1. 尝试解析删除指令 ```json:delete_course ... ```
    del_m = re.search(r"```(?:json:delete_course|json)?\s*(\{[\s\S]*?\"name\"[\s\S]*?\})\s*```", text)
    if not del_m:
        del_m = re.search(r"```(?:json:delete_course|json)?\s*(\{[\s\S]*?\"name\"[\s\S]*?\})", text)
    if "```json:delete_course" in text or (del_m and any(k in user_text for k in ("删除", "删掉", "删了", "退课", "取消", "移除", "去掉"))):
        if del_m:
            try:
                d_obj = json.loads(del_m.group(1))
                d_name = d_obj.get("name", "").strip()
                d_wd = d_obj.get("weekday")
                d_sec = d_obj.get("sec_start")
                d_wk = d_obj.get("week")
                d_all = d_obj.get("delete_all_weeks", True)
                actions.delete_course(name=d_name, weekday=d_wd, sec_start=d_sec, target_week=d_wk, delete_all_weeks=d_all)
                text = text.replace(del_m.group(0), "").strip()
                parsed_delete = True
            except Exception:
                pass

    # 2. 尝试解析修改指令 ```json:modify_course ... ```
    mod_m = re.search(r"```(?:json:modify_course|json)?\s*(\{[\s\S]*?\"target_name\"[\s\S]*?\})\s*```", text)
    if not mod_m:
        mod_m = re.search(r"```(?:json:modify_course|json)?\s*(\{[\s\S]*?\"target_name\"[\s\S]*?\})", text)
    if not parsed_delete and ("```json:modify_course" in text or mod_m):
        if mod_m:
            try:
                m_obj = json.loads(mod_m.group(1))
                actions.modify_course(
                    target_name=m_obj.get("target_name"),
                    target_weekday=m_obj.get("target_weekday"),
                    target_sec_start=m_obj.get("target_sec_start"),
                    target_week=m_obj.get("target_week"),
                    new_name=m_obj.get("new_name"),
                    new_weekday=m_obj.get("new_weekday"),
                    new_sec_start=m_obj.get("new_sec_start"),
                    new_sec_end=m_obj.get("new_sec_end"),
                    new_room=m_obj.get("new_room"),
                    new_teacher=m_obj.get("new_teacher"),
                    new_custom_time=m_obj.get("new_custom_time"),
                    new_week_start=m_obj.get("new_week_start"),
                    new_week_end=m_obj.get("new_week_end"),
                )
                text = text.replace(mod_m.group(0), "").strip()
                parsed_modify = True
            except Exception:
                pass

    # 3. 尝试解析添加课程指令 ```json:add_course ... ```
    add_m = re.search(r"```(?:json:add_course|json)?\s*(\{[\s\S]*?\"name\"[\s\S]*?\})\s*```", text)
    if not add_m:
        add_m = re.search(r"```(?:json:add_course|json)?\s*(\{[\s\S]*?\"name\"[\s\S]*?\})", text)
    if not parsed_delete and not parsed_modify and ("```json:add_course" in text or add_m):
        if add_m:
            try:
                c_obj = json.loads(add_m.group(1))
                actions.add_course(
                    name=c_obj.get("name"),
                    weekday=c_obj.get("weekday", 1),
                    sec_start=c_obj.get("sec_start", 1),
                    sec_end=c_obj.get("sec_end"),
                    week_start=c_obj.get("week_start"),
                    week_end=c_obj.get("week_end"),
                    parity=c_obj.get("parity", "all"),
                    room=c_obj.get("room", ""),
                    teacher=c_obj.get("teacher", ""),
                    custom_time=c_obj.get("custom_time", ""),
                )
                text = text.replace(add_m.group(0), "").strip()
                parsed_add = True
            except Exception:
                pass

    # 4. 尝试解析教学安排调整指令 ```json:adjust_schedule ... ```
    adj_m = re.search(r"```(?:json:adjust_schedule|json)?\s*(\{[\s\S]*?\"adjustments\"[\s\S]*?\})\s*```", text)
    if not adj_m:
        adj_m = re.search(r"```(?:json:adjust_schedule|json)?\s*(\{[\s\S]*?\"adjustments\"[\s\S]*?\})", text)
    if "```json:adjust_schedule" in text or adj_m:
        if adj_m:
            try:
                adj_obj = json.loads(adj_m.group(1))
                actions.adjust_schedule(adjustments=adj_obj.get("adjustments", []))
                text = text.replace(adj_m.group(0), "").strip()
                parsed_adjust = True
            except Exception:
                pass

    # 5. 尝试解析番茄钟专注指令 ```json:start_pomodoro ... ```
    pomo_m = re.search(r"```(?:json:start_pomodoro|json)?\s*(\{[\s\S]*?\"minutes\"[\s\S]*?\})\s*```", text)
    if not pomo_m:
        pomo_m = re.search(r"```(?:json:start_pomodoro|json)?\s*(\{[\s\S]*?\"minutes\"[\s\S]*?\})", text)
    if "```json:start_pomodoro" in text or pomo_m:
        if pomo_m:
            try:
                p_obj = json.loads(pomo_m.group(1))
                actions.start_pomodoro(work_minutes=int(p_obj.get("minutes", 25)))
                text = text.replace(pomo_m.group(0), "").strip()
            except Exception:
                pass

    # 6. 尝试解析便签指令 ```json:create_note ... ```
    note_m = re.search(r"```(?:json:create_note|json)?\s*(\{[\s\S]*?\"content\"[\s\S]*?\})\s*```", text)
    if not note_m:
        note_m = re.search(r"```(?:json:create_note|json)?\s*(\{[\s\S]*?\"content\"[\s\S]*?\})", text)
    if "```json:create_note" in text or note_m:
        if note_m:
            try:
                n_obj = json.loads(note_m.group(1))
                cnt = n_obj.get("content", "").strip()
                ttl = n_obj.get("title", "").strip() or (cnt[:15] + "…" if len(cnt) > 15 else cnt)
                if cnt:
                    actions.create_sticky_note(content=cnt, title=ttl)
                text = text.replace(note_m.group(0), "").strip()
            except Exception:
                pass

    # 7. 本地轻量 NLP 规则辅助兜底（若模型未输出任何代码块，但用户输入包含明确课表操作意图）
    if sched and not parsed_delete and not parsed_modify and not parsed_add and user_text:
        del_keywords = ("删除", "删掉", "删了", "退课", "取消", "移除", "去掉", "不开", "不掉了", "不上了")
        mod_keywords = ("改到", "改成", "改在", "改至", "推迟到", "推迟至", "提前到", "提前至", "调整到", "调整为", "换到", "换成")
        if any(k in user_text for k in del_keywords):
            sched.parse_delete_from_natural_language(user_text)
        elif any(k in user_text for k in mod_keywords):
            sched.parse_modify_from_natural_language(user_text)
        elif any(k in user_text for k in ("加一门", "加一节", "添加", "录入", "新加", "新建", "组会", "会议", "例会", "讲座", "答疑", "实验")) or \
             ("课" in user_text and any(w in user_text for w in ("周", "星期", "节"))) or \
             ("周" in user_text and any(w in user_text for w in ("点", ":"))):
            sched.parse_course_from_natural_language(user_text)

    if sched and not parsed_adjust and user_text:
        is_notice = ("教学安排" in user_text or "课表执行" in user_text or
                     (("停上" in user_text or "停课" in user_text) and "月" in user_text) or
                     ("调课" in user_text and "月" in user_text))
        if is_notice:
            sched.parse_adjustments_from_notice(user_text)

    # 剔除可能残留的任意 json 代码块与标签
    for tag in ("```json:add_course", "```json:delete_course", "```json:modify_course",
                "```json:adjust_schedule", "```json:start_pomodoro", "```json:create_note", "```json"):
        if tag in text:
            text = text.split(tag, 1)[0].rstrip()
    if "```" in text:
        text = re.sub(r"```[\s\S]*?```", "", text).strip()

    return text.strip() or "好的博士，阿米娅已经为您处理完毕了。"


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
        """按当前用户问题检索讲义与课件切片，返回可注入 system 的上下文（或空串）。"""
        kb = self.knowledge
        if not kb:
            return ""
        question = ""
        for m in reversed(self.history):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                question = m["content"]
                break
        if not question:
            return ""

        # 尝试确定目标课程
        target_course = None
        sched = actions._schedule_provider() if actions._schedule_provider else None
        known_courses = kb.get_courses()
        if sched and hasattr(sched, "courses"):
            for c in sched.courses:
                if c.name and c.name not in known_courses:
                    known_courses.append(c.name)

        from .knowledge import match_course_from_query
        target_course = match_course_from_query(question, known_courses)

        # 若问题问及“这门课/考纲/重点/复习/简答题”等且未明确指明课名，推测当前正在上的课程
        if not target_course and any(w in question for w in ("这门课", "本课", "这节课", "考纲", "重点", "简答题", "考试", "复习", "期末", "上课")):
            if sched:
                cur_c = getattr(sched, "get_current_course", lambda: None)()
                if cur_c:
                    target_course = cur_c.name

        ctx = kb.context(question, course=target_course)
        if not ctx:
            return ""

        prompt_ext = (
            "\n\n【罗德岛学业中枢 · 课程课件权威资料】\n"
            + ctx +
            "- 博士正在针对该学科进行求知、复习或备考。请以严谨准确且温柔体贴的罗德岛领袖阿米娅的口吻，严格依据上述课件资料进行解答。\n"
            "- 涉及数学、物理、理科与工程计算公式时，必须规范使用标准 LaTeX 格式排版（行内公式用 $...$，独立推导公式用 $$...$$），严禁使用粗糙 ASCII 字符拼凑公式。\n"
            "- 若博士询问「划重点」、「出考题/模拟题」或「核心考点」：请从课件中提取关键定理、定律、定义公式和考题要点，分条列出；模拟题需给出清晰题干并附带简要参考答案。\n"
            "- 若课件资料未提及博士所问的细节，请诚恳说明课件表述，并结合通用学术知识谨慎解答，切勿捏造虚假结论。"
        )
        return prompt_ext

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
        """获取博士今日与明日日程、排课、待办及便签的上下文（含智能课表规范说明）。"""
        try:
            sched = actions._schedule_provider() if actions._schedule_provider else None
            parts = []
            if sched:
                dossier = sched.build_schedule_analysis_context()
                if dossier:
                    parts.append(dossier)
            from .actions import agenda_summary
            parts.append(agenda_summary("today"))
            parts.append(agenda_summary("tomorrow"))

            cur_week = sched.week_no() or 1 if sched else 1
            max_week = max((c.week_end for c in sched.courses), default=16) if sched and sched.courses else 16

            spec = (
                f"【智能课程与日程活动录入规范】：\n"
                f"当前学期现实教学周为：第 {cur_week} 周（全学期共约 {max_week} 周）。\n"
                "当博士表达添加/记录课程或日程活动（例如：“帮我加一节周三第3-4节的高数课在教三201”、“周四下午14:15到15:30在综合楼402开组会”、“下周二第1节加个班会”）：\n"
                "1. 提取要素：\n"
                "   - name: 课程或活动名称（必填，精简准确主题词，严禁包含“活动”、“日程”、“帮我添加”等无意义指示词，严禁粘连教室或时间）\n"
                "   - weekday: 星期几（必填，整数 1~7）\n"
                "   - sec_start: 起始节次（必填，整数 1~13）\n"
                "   - sec_end: 结束节次（必填，整数 1~13）\n"
                f"   - week_start / week_end: 起止周次（必填）。对于活动/会议/日程（组会/例会/答疑/讲座/班会/实验等），若未说明持续多周，一律只设置单周（如当前周 week_start={cur_week}, week_end={cur_week}），严禁默认填满全学期；只有常规学期专业课程未说明时才默认 1~{max_week} 周。\n"
                "   - room: 教室地点（选填）\n"
                "   - teacher: 教师负责人（选填）\n"
                "   - custom_time: 具体真实时间（选填，如 \"14:15-15:30\"）\n"
                "2. 若有可用工具且支持 function calling 请优先调用 add_course 工具；同时在回复末尾务必生成精准指令块：\n"
                "```json:add_course\n"
                f"{{\n  \"name\": \"...\",\n  \"weekday\": 3,\n  \"sec_start\": 3,\n  \"sec_end\": 4,\n  \"week_start\": {cur_week},\n  \"week_end\": {cur_week},\n  \"room\": \"教三201\"\n}}\n"
                "```\n\n"
                "【智能日程活动“删除 / 取消”规范】：\n"
                "当博士表达取消/删除日程活动或退课（例如：“把周四下午的组会取消”、“把高等数学退课了”）：\n"
                "1. 提取要素：name, weekday, sec_start, week, delete_all_weeks (默认 true)。\n"
                "2. 若支持 function calling 请优先调用 delete_course 工具；同时在回复末尾务必生成指令块：\n"
                "```json:delete_course\n"
                "{\n  \"name\": \"组会\",\n  \"weekday\": 4,\n  \"sec_start\": 6\n}\n"
                "```\n\n"
                "【智能日程活动“修改 / 调整”规范】：\n"
                "当博士表达修改/调整日程时间地点名称（例如：“把周四的组会改到周五下午两点”、“把高等数学教室改到教四101”）：\n"
                "1. 提取要素：target_name, target_weekday, target_sec_start, new_name, new_weekday, new_sec_start, new_sec_end, new_custom_time, new_room。\n"
                "2. 若支持 function calling 请优先调用 modify_course 工具；同时在回复末尾务必生成指令块：\n"
                "```json:modify_course\n"
                "{\n  \"target_name\": \"组会\",\n  \"target_weekday\": 4,\n  \"new_weekday\": 5,\n  \"new_sec_start\": 6,\n  \"new_sec_end\": 7,\n  \"new_custom_time\": \"14:00-15:30\"\n}\n"
                "```\n\n"
                "【智能教学安排与假期调课/停课调整规范】：\n"
                "当博士发送学校教学调整通知（例如：“9月20日按第5周周二课表执行”、“国庆节10月1日-7日所有课程停上”）：\n"
                "1. 分析提取各项调整（date YYYY-MM-DD, type: substitute / suspend, target_week, target_weekday, reason）。连续多天停课需拆分为每天独立记录。\n"
                "2. 若支持 function calling 请优先调用 adjust_schedule 工具；同时在回复末尾务必生成指令块：\n"
                "```json:adjust_schedule\n"
                "{\n  \"adjustments\": [\n    { \"date\": \"2026-09-20\", \"type\": \"substitute\", \"target_week\": 5, \"target_weekday\": 2, \"reason\": \"按第5周周二\" }\n  ]\n}\n"
                "```\n"
            )
            parts.append(spec)
            return "\n\n" + "\n\n".join(parts)
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
        """本地轻量离线意图路由（专注番茄钟、灵感便签、日程汇总、课表增删改与教学调整）。
        返回生成的阿米娅回复字符串；若未匹配到意图则返回 None。
        """
        import re
        trimmed = (user_text or "").strip()
        if not trimmed:
            return None

        sched = actions._schedule_provider() if actions._schedule_provider else None

        # 1. 课表删除 / 退课 / 取消
        del_keywords = ("删除", "删掉", "删了", "退课", "取消", "移除", "去掉", "不开", "不上了")
        if sched and any(k in trimmed for k in del_keywords):
            deleted = sched.parse_delete_from_natural_language(trimmed)
            if deleted:
                days = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                return f"好的博士！阿米娅已经在离线模式下帮您把《{deleted.name}》（{days[deleted.weekday]} 第{deleted.sec_start}-{deleted.sec_end}节）从课表中删除了。"
            elif any(w in trimmed for w in ("课", "日程", "会议", "组会", "例会")):
                return "博士，阿米娅在课表中没有找到符合条件的待删除课程或日程。"

        # 2. 课表修改 / 调课 / 改时间地点
        mod_keywords = ("改到", "改成", "改在", "改至", "推迟到", "推迟至", "提前到", "提前至", "调整到", "调整为", "换到", "换成")
        if sched and any(k in trimmed for k in mod_keywords):
            old_c, new_c = sched.parse_modify_from_natural_language(trimmed)
            if old_c and new_c:
                days = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                loc = f" @{new_c.room}" if new_c.room else ""
                time_desc = f"📌[{new_c.custom_time}]" if getattr(new_c, "custom_time", "") else f"{days[new_c.weekday]} 第{new_c.sec_start}-{new_c.sec_end}节"
                return f"好的博士！阿米娅已经在离线模式下将《{old_c.name}》调整为：{time_desc}{loc}。"
            elif any(w in trimmed for w in ("课", "日程", "会议", "组会", "例会")):
                return "博士，阿米娅没有在课表中定位到要调整的目标课程或日程。"

        # 3. 教学安排调整通知（调课/放假停课）
        is_notice = ("教学安排" in trimmed or "课表执行" in trimmed or
                     (("停上" in trimmed or "停课" in trimmed) and "月" in trimmed) or
                     ("调课" in trimmed and "月" in trimmed))
        if sched and is_notice:
            notice_list = sched.parse_adjustments_from_notice(trimmed)
            if notice_list:
                days = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                items = []
                for a in notice_list[:4]:
                    if a.get("type") == "suspend":
                        items.append(f"• {a['date']} 停课（{a.get('reason', '')}）")
                    else:
                        tw = f"第{a.get('target_week')}周" if a.get("target_week") else ""
                        wd = days[a.get("target_weekday", 1)]
                        items.append(f"• {a['date']} 按{tw}{wd}课表执行")
                more = f"\n… 等共 {len(notice_list)} 天教学安排调整" if len(notice_list) > 4 else ""
                return "好的博士！阿米娅已在离线状态下为您将教学安排调整同步至课表：\n" + "\n".join(items) + more + "\n课表周视图与日程提醒已实时生效。"
            return "博士，阿米娅收到了教学安排通知，但未识别出具体的调课或停课日期，您可以具体说明是哪一天的课程如何调整。"

        # 4. 课表添加 / 录入课程或日程活动
        add_intent = (
            any(k in trimmed for k in ("加一门", "加一节", "添加", "录入", "新加", "新建", "组会", "会议", "例会", "讲座", "答疑", "实验")) or
            ("课" in trimmed and any(w in trimmed for w in ("周", "星期", "节"))) or
            ("周" in trimmed and any(w in trimmed for w in ("点", ":")))
        )
        if sched and add_intent and not any(neg in trimmed for neg in ("查", "看", "今天", "明天", "本周", "总结")):
            course = sched.parse_course_from_natural_language(trimmed)
            if course:
                days = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                loc = f" @{course.room}" if course.room else ""
                time_desc = f"📌[{course.custom_time}] (对应第{course.sec_start}-{course.sec_end}节)" if getattr(course, "custom_time", "") else f"第{course.sec_start}-{course.sec_end}节"
                return f"好的博士！阿米娅已经在离线状态下为您将《{course.name}》（{days[course.weekday]} {time_desc}{loc}）记录到课表了。"

        # 5. 专注 / 番茄钟
        if any(k in trimmed for k in ("专注", "番茄钟")) or ("自习" in trimmed and any(k in trimmed for k in ("开启", "开始", "来个", "进入", "设置", "定时"))):
            m = re.search(r"(\d+)\s*(?:分钟|min|m)", trimmed, re.I)
            mins = int(m.group(1)) if m else 25
            mins = max(1, min(mins, 180))
            return actions.start_pomodoro(work_minutes=mins, break_minutes=5, rounds=4)

        # 停止专注
        if any(k in trimmed for k in ("停止专注", "取消专注", "结束专注", "停止番茄钟", "结束番茄钟", "停止计时")):
            return actions.stop_focus()

        # 6. 便签备忘速记
        if any(trimmed.startswith(k) or k in trimmed for k in ("记一下", "备忘录记一下", "记便签", "记录一下", "随手记", "记个备忘", "记在便签")):
            clean_text = re.sub(r"^(?:阿米娅|请|帮我|麻烦)?(?:记一下|备忘录记一下|备忘|记录一下|记便签|随手记|记个备忘|记在便签)[:：\s]*", "", trimmed).strip()
            if clean_text:
                title = clean_text[:15] + "…" if len(clean_text) > 15 else clean_text
                return actions.create_sticky_note(content=clean_text, title=title)
            return "好的博士，请问具体要记下什么内容呢？阿米娅随时为您记录。"

        # 7. 日程汇总
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
        know_ctx = self._knowledge_context()
        if self.has_custom_key:
            system_content = self.persona + know_ctx + self._profile_context() + sched_ctx
        else:
            system_content = (
                "你是《明日方舟》中的阿米娅，罗德岛的公开领袖。你温柔、坚定、富有责任感，"
                "面对博士时既尊敬又亲近。你称呼对方为「博士」，自称「阿米娅」或「我」。"
                "你说话礼貌、真诚，偶尔流露少女的关心与坚强。回答简洁自然，一般一到三句话，"
                "像日常聊天，不要长篇大论，不要使用括号动作描写或表情符号，只用中文回答。"
            ) + know_ctx + sched_ctx
        system = {"role": "system", "content": system_content}
        msgs = [system] + list(self.history)
        for _ in range(4):
            msg = self._post(msgs, use_tools)
            calls = msg.get("tool_calls")
            if not calls:
                raw_text = (msg.get("content") or "").strip()
                last_user = next((m["content"] for m in reversed(self.history) if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
                return _execute_embedded_schedule_commands(raw_text, last_user)
            # Record the tool round in both the working list AND the persisted
            # history, so future turns replay Amiya *actually calling* the tool
            # rather than just her final sentence (see _clean_msg).
            self._record_tool_round(msgs, msg, calls)
        # 4 轮工具调用后模型仍未给出最终文本：再发一次不带工具的请求，
        # 让它基于已执行的工具结果收尾——否则 msgs[-1] 是最后一条 tool
        # 结果，会被原样当成回复念给博士。
        msg = self._post(msgs, False)
        raw_text = (msg.get("content") or "好的，博士。").strip()
        last_user = next((m["content"] for m in reversed(self.history) if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
        return _execute_embedded_schedule_commands(raw_text, last_user)

    def _target_endpoint_and_headers(self, stream=False, use_tools=False, msgs=None, target_url=None, max_tokens=None):
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
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        elif "max_tokens" in self.cfg:
            payload["max_tokens"] = self.cfg["max_tokens"]

        if use_tools and has_custom:
            payload["tools"] = actions.TOOLS
        return url, headers, json.dumps(payload).encode("utf-8")

    def _post(self, msgs, use_tools, max_tokens=None):
        if self.has_custom_key:
            endpoints = [resolve_chat_endpoint(self.cfg.get("base_url", ""))]
        else:
            endpoints = get_candidate_relays(self.cfg.get("public_relay_url"))

        last_err = None
        for i, ep in enumerate(endpoints):
            for retry in range(2):
                try:
                    url, headers, body = self._target_endpoint_and_headers(
                        stream=False, use_tools=use_tools, msgs=msgs, target_url=ep, max_tokens=max_tokens
                    )
                    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
                    with urllib.request.urlopen(req, timeout=90) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    msg = data["choices"][0]["message"]
                    fr = data["choices"][0].get("finish_reason")
                    if isinstance(msg, dict):
                        msg["finish_reason"] = fr
                    return msg
                except Exception as e:
                    last_err = e
                    code = getattr(e, "code", None)
                    if retry == 0 and code in (500, 502, 503, 504):
                        import time
                        time.sleep(1.5)
                        continue
                    break
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
        know_ctx = self._knowledge_context()
        if self.has_custom_key:
            system_content = self.persona + know_ctx + self._profile_context() + sched_ctx
        else:
            system_content = (
                "你是《明日方舟》中的阿米娅，罗德岛的公开领袖。你温柔、坚定、富有责任感，"
                "面对博士时既尊敬又亲近。你称呼对方为「博士」，自称「阿米娅」或「我」。"
                "你说话礼貌、真诚，偶尔流露少女的关心与坚强。回答简洁自然，一般一到三句话，"
                "像日常聊天，不要长篇大论，不要使用括号动作描写或表情符号，只用中文回答。"
            ) + know_ctx + sched_ctx
        system = {"role": "system", "content": system_content}
        msgs = [system] + list(self.history)
        for _ in range(4):
            msg = self._post_stream(msgs, use_tools, on_delta)
            calls = msg.get("tool_calls")
            if not calls:
                raw_text = (msg.get("content") or "").strip()
                last_user = next((m["content"] for m in reversed(self.history) if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
                final_text = _execute_embedded_schedule_commands(raw_text, last_user)
                if on_delta:
                    on_delta(final_text)
                return final_text
            self._record_tool_round(msgs, msg, calls)
        # 同 _call_llm：工具轮次耗尽后补一次无工具请求来收尾。
        msg = self._post_stream(msgs, False, on_delta)
        raw_text = (msg.get("content") or "好的，博士。").strip()
        last_user = next((m["content"] for m in reversed(self.history) if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
        final_text = _execute_embedded_schedule_commands(raw_text, last_user)
        if on_delta:
            on_delta(final_text)
        return final_text

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

    def _post_stream(self, msgs, use_tools, on_delta, max_tokens=None):
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

            for retry in range(2):
                try:
                    url, headers, body = self._target_endpoint_and_headers(
                        stream=True, use_tools=use_tools, msgs=msgs, target_url=ep, max_tokens=max_tokens
                    )
                    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
                    with urllib.request.urlopen(req, timeout=90) as resp:
                        return _consume_stream(resp, wrapped_on_delta)
                except Exception as e:
                    last_err = e
                    code = getattr(e, "code", None)
                    # 尚未输出内容且遇到服务端 5xx 瞬时抖动时退避 1.5 秒重试一次
                    if not emitted and retry == 0 and code in (500, 502, 503, 504):
                        import time
                        time.sleep(1.5)
                        continue
                    break
            # 若已经吐出有效 token 或已经是最后一个候选节点，则不再静默 failover，抛出异常
            if emitted or i == len(endpoints) - 1:
                raise last_err
            continue
        if last_err:
            raise last_err

    def generate_courseware_digest(self, raw_text, filename="", course="", on_progress=None):
        """调用大模型对课件全文/幻灯片内容进行深度解析，提炼出结构化的核心知识点与期末备考提纲。"""
        if not raw_text or not raw_text.strip():
            return "（课件内容为空，无法提取知识点）"

        text_content = raw_text.strip()
        # 智能截断超大长文本（保留头部主干、中间核心与尾部小结，适配现代大模型 128k 窗口）
        if len(text_content) > 65000:
            mid_start = max(30000, len(text_content) // 2 - 12500)
            mid_end = mid_start + 25000
            text_content = (
                text_content[:30000]
                + "\n\n[...课件前半部分详细内容略...]\n\n"
                + text_content[mid_start:mid_end]
                + "\n\n[...课件后半部分详细内容略...]\n\n"
                + text_content[-10000:]
            )

        model_name = (self.cfg.get("model") or "").lower()
        if "deepseek" in model_name:
            digest_max_tokens = 8192
        elif "glm" in model_name:
            digest_max_tokens = 4095
        elif "qwen" in model_name:
            digest_max_tokens = 4096
        else:
            digest_max_tokens = 4095

        system_content = (
            "你是一名专业严谨的高校学业与学术辅导助教阿米娅。请对博士提供的大学课程课件/讲义文本进行深度的学术梳理与期末考纲提炼。\n"
            "要求：\n"
            "1. 【层级严整】：标题必须规范使用 Markdown 标题层级（# 课件总纲 -> ## 模块板块 -> ### 具体考点细分 -> - 核心解析），绝不混用层级。\n"
            "2. 【高保真 LaTeX 公式规范】：凡涉及数学、物理、工科理论公式，必须严格采用标准 LaTeX 排版：行内公式用 $公式$（如 $\\vec{B} = \\frac{\\mu_0 I}{2\\pi r}$），独立推导大公式用 $$公式$$。严禁使用纯文本/ASCII 粗糙字符拼凑公式，确保矢量符号（\\vec）、微积分（\\frac{d}{dt}）、环路积分（\\oint）、分数、希腊字母均以优雅的标准 LaTeX 格式呈现。\n"
            "3. 【重点突出】：核心考点用 ⭐ 标明重要程度（如 ⭐⭐⭐⭐⭐ 必考），易混淆考点用 ⚠️ 标出。\n"
            "4. 【图表化总结】：对比概念与核心公式尽可能采用 Markdown 表格形式呈现，一目了然。\n"
            "5. 【严谨客观】：完全忠实于课件文本，不捏造课件未提及的内容。\n"
            "6. 【全局完整性】：必须按顺序完整输出全部五大板块（从【一、核心概念】一直到【五、期末高分冲刺自测 Q&A】），合理控制各板块篇幅，绝不允许中途截断或戛然而止。"
        )
        user_content = (
            f"请帮我深度分析课程《{course or '未指定课程'}》的课件《{filename}》，提炼核心知识点并整理为结构清晰、层级分明的期末备考考纲。\n\n"
            f"【课件文本内容】：\n{text_content}\n\n"
            "【输出格式与五大层级板块规范】：\n"
            f"# 📖 《{filename}》核心考纲与期末冲刺全景导图\n"
            f"> **课程归属**：{course or '未指定课程'} ｜ **资料来源**：{filename} ｜ **提炼重点**：概念定义 · 核心公式 · 命题预测 · 避坑对比 · 考前自测\n\n"
            "## 📌 一、 核心概念与关键术语精讲\n"
            "（精选本课件中最核心、最常考的 5~8 个核心专业术语，逐条按以下格式展开，言简意赅）：\n"
            "### 1.1 [术语/概念名称]\n"
            "- **核心定义**：用 1~2 句话精准概括其学术定义与核心本质。\n"
            "- **工作原理 / 运行机制**：它是如何工作/运作的，内部关键流程是什么。\n"
            "- **考点重要度**：⭐⭐⭐⭐⭐（星级评定及期末考查频率）。\n\n"
            "## 📐 二、 核心公式、定理推导与理论框架\n"
            "（若涉及数学、物理、算法公式，必须采用表格与标准 LaTeX 公式呈现；文科/软工类课程则梳理核心理论模型）：\n"
            "| 公式 / 定理名称 | 核心 LaTeX 表达式 | 计算意义 / 物理含义 | 关键边界条件与适用前提 |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| [定理名称] | $[标准 LaTeX 表达式]$ | [物理含义与参数说明] | [适用前提与约束条件] |\n\n"
            "若有核心定理与关键推导（如安培环路定理、毕奥-萨伐尔定律推导），请在表格下方使用独立 LaTeX 块详细列出分步推导：\n"
            "$$\n"
            "\\oint_{L} \\vec{B} \\cdot d\\vec{l} = \\mu_0 \\sum_{i} I_i\n"
            "$$\n\n"
            "## 🎯 三、 期末高频必考点与题型预测\n"
            "### 3.1 概念辨析与简答题预测\n"
            "- **高频考点**：...\n"
            "- **标准答题得分要点**：...\n\n"
            "### 3.2 综合计算与案例分析大题预测\n"
            "- **典型题型**：...\n"
            "- **解题核心思路 (Step-by-Step)**：\n"
            "  1. 步骤一：...\n"
            "  2. 步骤二：...\n\n"
            "## ⚖️ 四、 易混淆概念对比与避坑指南\n"
            "（将课件中最容易混淆的两两概念进行表格对比，点出扣分陷阱）：\n"
            "| 对比维度 | [概念 A] | [概念 B] | ⚠️ 常见扣分误区与辨析技巧 |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| [维度 1] | ... | ... | ... |\n\n"
            "## 💡 五、 期末高分冲刺自测 Q&A\n"
            "（精选 3~5 道期末高频简答/论述真题级别自测试题，附带标准采分点答案）：\n"
            "> **Q1：[核心简答题题目]**\n"
            ">\n"
            "> **参考答案与采分要点**：\n"
            "> 1. ...\n"
            "> 2. ...\n"
        )
        msgs = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

        if on_progress:
            on_progress(45, "已连接大模型，正在深度剖析课件考点...")

        def _needs_continuation(text, finish_reason):
            if finish_reason == "length":
                return True
            if not text or not text.strip():
                return False
            has_part5 = any(tag in text for tag in ["## 💡 五、", "## 五、", "## 5.", "五、 期末高分冲刺自测", "五、期末高分冲刺自测"])
            if not has_part5:
                return True
            last_lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
            if last_lines and last_lines[-1].startswith("|") and not last_lines[-1].endswith("|"):
                return True
            return False

        # 优先尝试流式生成以提供高精度实时进度反馈
        last_accum = ""
        def _stream_delta(accum_text):
            nonlocal last_accum
            last_accum = accum_text
            if on_progress:
                char_cnt = len(accum_text)
                pct = min(95, 45 + int(char_cnt / 25))
                on_progress(pct, f"正在梳理考纲与预测模拟题 ({char_cnt} 字)...")

        try:
            msg = self._post_stream(msgs, use_tools=False, on_delta=_stream_delta, max_tokens=digest_max_tokens)
            if isinstance(msg, dict):
                res = (msg.get("content") or "").strip()
                finish_reason = msg.get("finish_reason")
            else:
                res = str(msg or last_accum).strip()
                finish_reason = None

            if _needs_continuation(res, finish_reason):
                petlog.log("ai: 考纲内容触达模型单次输出上限或尚未完全输出全部板块，启动自动接力续写...")
                if on_progress:
                    on_progress(88, "考纲内容极丰富，正在接力续写剩余板块...")

                continue_msgs = list(msgs)
                continue_msgs.append({"role": "assistant", "content": res})
                continue_msgs.append({
                    "role": "user",
                    "content": "请紧接着上一段末尾被截断处（不要重复已输出内容，直接无缝衔接后文）继续往下写，务必完整输出剩余的【四、易混淆概念对比与避坑指南】表格和【五、期末高分冲刺自测 Q&A】全套内容。"
                })
                cont_accum = ""
                def _stream_cont_delta(delta_accum):
                    nonlocal cont_accum
                    cont_accum = delta_accum
                    if on_progress:
                        char_cnt = len(res) + len(delta_accum)
                        pct = min(98, 88 + int(len(delta_accum) / 40))
                        on_progress(pct, f"正在梳理考纲与预测模拟题 ({char_cnt} 字)...")
                try:
                    cont_msg = self._post_stream(continue_msgs, use_tools=False, on_delta=_stream_cont_delta, max_tokens=digest_max_tokens)
                    cont_res = (cont_msg.get("content") if isinstance(cont_msg, dict) else str(cont_msg or cont_accum)) or ""
                    if cont_res.strip():
                        res = _stitch_continuation(res, cont_res.strip())
                except Exception as ce:
                    petlog.warn(f"ai: 接力续写异常: {ce}")

            if res:
                return res
        except Exception as e:
            petlog.warn(f"ai: 流式提炼考纲失败，回退非流式: {e}")
            import time
            time.sleep(1.0)

        # 兜底非流式请求
        if on_progress:
            on_progress(70, "正在生成知识点考纲与考题预测...")
        msg = self._post(msgs, use_tools=False, max_tokens=digest_max_tokens)
        if isinstance(msg, dict):
            res = (msg.get("content") or "").strip()
            finish_reason = msg.get("finish_reason")
        else:
            res = str(msg or "").strip()
            finish_reason = None

        if _needs_continuation(res, finish_reason):
            try:
                continue_msgs = list(msgs)
                continue_msgs.append({"role": "assistant", "content": res})
                continue_msgs.append({
                    "role": "user",
                    "content": "请紧接着上一段末尾被截断处（不要重复已输出内容，直接无缝衔接后文）继续往下写，务必完整输出剩余的【四、易混淆概念对比与避坑指南】表格和【五、期末高分冲刺自测 Q&A】全套内容。"
                })
                cont_msg = self._post(continue_msgs, use_tools=False, max_tokens=digest_max_tokens)
                cont_res = (cont_msg.get("content") if isinstance(cont_msg, dict) else str(cont_msg)) or ""
                if cont_res.strip():
                    res = _stitch_continuation(res, cont_res.strip())
            except Exception as ce:
                petlog.warn(f"ai: 非流式接力续写异常: {ce}")

        return res


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
    finish_reason = None
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
        fr = choices[0].get("finish_reason")
        if fr:
            finish_reason = fr
        if delta.get("content"):
            content += delta["content"]
            if on_delta:
                on_delta(_clean_stream_display_text(content))
        for tc in delta.get("tool_calls") or []:
            _accum_tool_call(tool_store, tc)
    msg = {"role": "assistant", "content": content, "finish_reason": finish_reason}
    if tool_store:
        msg["tool_calls"] = [tool_store[k] for k in sorted(tool_store)]
    return msg


def _stitch_continuation(original, cont):
    """无缝拼接截断续写内容，智能消除接缝处的字符重叠。"""
    if not cont or not cont.strip():
        return original
    orig_clean = original.rstrip()
    cont_clean = cont.lstrip()
    for overlap_len in range(min(60, len(orig_clean), len(cont_clean)), 0, -1):
        if orig_clean.endswith(cont_clean[:overlap_len]):
            return orig_clean + cont_clean[overlap_len:]
    return orig_clean + "\n" + cont_clean
