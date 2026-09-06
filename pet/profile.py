"""博士档案本与长程记忆数据管理模块。

数据保存在用户配置目录（Windows: %APPDATA%\\AmiyaPet\\doctor_profile.json），
与聊天历史、任务列表一致，不随打包分发，支持环境变量 PET_PROFILE_FILE 覆盖（测试用）。

档案结构包含：
- nickname: 博士称呼（默认「博士」）
- identity: 博士身份 / 阶段（如「计算机研一」「软件工程师」）
- preferences: 博士的偏好与喜好（如「喜欢喝无糖乌龙茶」「常听古典乐」）
- habits: 博士的生活与作息习惯（如「习惯熬夜写代码」「喜欢番茄工作法」）
- goals: 博士当前的阶段目标（如「准备秋招面试」「备考六级」）
- memories: 重要事项与随记列表 [{"id": str, "time": "YYYY-MM-DD HH:MM", "content": str}]
"""

import json
import os
import uuid
from datetime import datetime

from .settings import config_dir

_CURRENT_PROFILE = None


def profile_path():
    """获取 doctor_profile.json 的文件路径，支持 PET_PROFILE_FILE 覆盖。"""
    return os.environ.get("PET_PROFILE_FILE") or os.path.join(
        config_dir(), "doctor_profile.json"
    )


class DoctorProfile:
    """管理博士长程记忆与个人档案。"""

    def __init__(self, filepath=None):
        self.filepath = filepath or profile_path()
        self.nickname = "博士"
        self.identity = ""
        self.preferences = ""
        self.habits = ""
        self.goals = ""
        self.memories = []  # list of {"id": str, "time": str, "content": str}
        self.load()

    def load(self):
        """从 JSON 文件加载档案，容错处理缺失字段。"""
        if not os.path.isfile(self.filepath):
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.nickname = str(data.get("nickname") or "博士").strip() or "博士"
                self.identity = str(data.get("identity") or "").strip()
                self.preferences = str(data.get("preferences") or "").strip()
                self.habits = str(data.get("habits") or "").strip()
                self.goals = str(data.get("goals") or "").strip()
                mem = data.get("memories")
                if isinstance(mem, list):
                    clean_mem = []
                    for m in mem:
                        if isinstance(m, dict) and "content" in m:
                            clean_mem.append({
                                "id": str(m.get("id") or uuid.uuid4().hex[:8]),
                                "time": str(m.get("time") or datetime.now().strftime("%Y-%m-%d %H:%M")),
                                "content": str(m.get("content") or "").strip()
                            })
                    self.memories = [m for m in clean_mem if m["content"]]
        except Exception:
            pass

    def save(self) -> bool:
        """原子写入持久化文件，成功返回 True。"""
        data = {
            "nickname": self.nickname or "博士",
            "identity": self.identity or "",
            "preferences": self.preferences or "",
            "habits": self.habits or "",
            "goals": self.goals or "",
            "memories": self.memories,
        }
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            tmp = self.filepath + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.filepath)
            return True
        except Exception:
            return False

    def update_field(self, field: str, value: str) -> bool:
        """更新单个基础档案字段。"""
        field = str(field or "").strip().lower()
        val = str(value or "").strip()
        field_map = {
            "nickname": "nickname",
            "称呼": "nickname",
            "名字": "nickname",
            "name": "nickname",
            "identity": "identity",
            "身份": "identity",
            "阶段": "identity",
            "职业": "identity",
            "preferences": "preferences",
            "喜好": "preferences",
            "偏好": "preferences",
            "habits": "habits",
            "习惯": "habits",
            "作息": "habits",
            "goals": "goals",
            "目标": "goals",
            "重心": "goals",
        }
        attr = field_map.get(field)
        if not attr:
            return False
        if attr == "nickname" and not val:
            val = "博士"
        setattr(self, attr, val)
        return self.save()

    def add_memory(self, content: str) -> str:
        """添加一条新长程记忆，返回其 ID。"""
        content = str(content or "").strip()
        if not content:
            return ""
        # 避免完全重复的记忆连续刷入
        if self.memories and self.memories[-1].get("content") == content:
            return self.memories[-1].get("id", "")
        item_id = uuid.uuid4().hex[:8]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.memories.append({
            "id": item_id,
            "time": now_str,
            "content": content,
        })
        # 最多保留 50 条长程记忆，超出时保留最新
        if len(self.memories) > 50:
            self.memories = self.memories[-50:]
        self.save()
        return item_id

    def delete_memory(self, memory_id: str) -> bool:
        """根据 ID 删除一条长程记忆。"""
        memory_id = str(memory_id or "").strip()
        orig_len = len(self.memories)
        self.memories = [m for m in self.memories if m.get("id") != memory_id]
        if len(self.memories) != orig_len:
            self.save()
            return True
        return False

    def clear_memories(self) -> bool:
        """清空所有随记条目。"""
        self.memories = []
        return self.save()

    def reset_profile(self) -> bool:
        """重置整本档案为初始状态。"""
        self.nickname = "博士"
        self.identity = ""
        self.preferences = ""
        self.habits = ""
        self.goals = ""
        self.memories = []
        return self.save()

    def render_prompt_context(self) -> str:
        """将当前档案格式化为适合注入 System Prompt 的精简上下文。"""
        lines = ["【博士档案与长程记忆（请在交谈中自然融入，保持亲近与连贯）】："]
        if self.nickname and self.nickname != "博士":
            lines.append(f"- 称呼：博士希望被称为「{self.nickname}」")
        else:
            lines.append("- 称呼：「博士」")

        if self.identity:
            lines.append(f"- 身份/阶段：{self.identity}")
        if self.preferences:
            lines.append(f"- 偏好与喜好：{self.preferences}")
        if self.habits:
            lines.append(f"- 作息与习惯：{self.habits}")
        if self.goals:
            lines.append(f"- 当前重心与目标：{self.goals}")

        if self.memories:
            lines.append("- 近期记住的事情：")
            # 最多取最近 10 条记忆注入提示词，避免 context 膨胀
            for m in self.memories[-10:]:
                lines.append(f"  * [{m['time']}] {m['content']}")

        if len(lines) == 2 and self.nickname == "博士":
            # 只有默认称呼，无任何其他信息
            return ""

        return "\n".join(lines)


def get_doctor_profile() -> DoctorProfile:
    """获取单例 DoctorProfile 实例。"""
    global _CURRENT_PROFILE
    expected_path = profile_path()
    if _CURRENT_PROFILE is None or _CURRENT_PROFILE.filepath != expected_path:
        _CURRENT_PROFILE = DoctorProfile(expected_path)
    return _CURRENT_PROFILE


def reload_doctor_profile():
    """重新从磁盘加载档案。"""
    global _CURRENT_PROFILE
    _CURRENT_PROFILE = DoctorProfile(profile_path())
    return _CURRENT_PROFILE
