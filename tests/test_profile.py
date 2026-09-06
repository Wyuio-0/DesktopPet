"""Tests for Doctor Profile & Long-term Memory (博士档案本与长程记忆)."""

import os
import sys
import tempfile
import pytest
from PyQt5 import QtCore, QtWidgets

# Ensure a QApplication instance exists for UI tests
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

from pet.profile import DoctorProfile, get_doctor_profile, reload_doctor_profile
from pet.profile_ui import DoctorProfileDialog
from pet import actions, ai


@pytest.fixture
def tmp_profile(monkeypatch):
    """Fixture providing a temporary profile file isolated from user data."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    # Remove file so it tests creation
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    monkeypatch.setenv("PET_PROFILE_FILE", tmp_path)
    profile = reload_doctor_profile()
    yield profile
    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass


class TestDoctorProfileModel:
    def test_default_values(self, tmp_profile):
        assert tmp_profile.nickname == "博士"
        assert tmp_profile.identity == ""
        assert tmp_profile.preferences == ""
        assert tmp_profile.habits == ""
        assert tmp_profile.goals == ""
        assert tmp_profile.memories == []
        # Empty profile context should be empty
        assert tmp_profile.render_prompt_context() == ""

    def test_update_fields(self, tmp_profile):
        assert tmp_profile.update_field("称呼", "Wyuio博士") is True
        assert tmp_profile.nickname == "Wyuio博士"

        assert tmp_profile.update_field("identity", "计算机研一") is True
        assert tmp_profile.identity == "计算机研一"

        assert tmp_profile.update_field("喜好", "喜欢喝黑咖啡") is True
        assert tmp_profile.preferences == "喜欢喝黑咖啡"

        assert tmp_profile.update_field("习惯", "习惯熬夜写代码") is True
        assert tmp_profile.habits == "习惯熬夜写代码"

        assert tmp_profile.update_field("目标", "准备秋招面试") is True
        assert tmp_profile.goals == "准备秋招面试"

        # Reload from disk and verify persistence
        new_instance = DoctorProfile(tmp_profile.filepath)
        assert new_instance.nickname == "Wyuio博士"
        assert new_instance.identity == "计算机研一"
        assert new_instance.preferences == "喜欢喝黑咖啡"
        assert new_instance.habits == "习惯熬夜写代码"
        assert new_instance.goals == "准备秋招面试"

    def test_memories_add_delete_clear(self, tmp_profile):
        id1 = tmp_profile.add_memory("博士提到下周三有毕业设计开题答辩")
        assert id1
        assert len(tmp_profile.memories) == 1
        assert tmp_profile.memories[0]["content"] == "博士提到下周三有毕业设计开题答辩"

        # Adding same content consecutively is deduped
        id2 = tmp_profile.add_memory("博士提到下周三有毕业设计开题答辩")
        assert id2 == id1
        assert len(tmp_profile.memories) == 1

        id3 = tmp_profile.add_memory("博士今天去实验室测试了模型")
        assert id3 != id1
        assert len(tmp_profile.memories) == 2

        # Delete one
        assert tmp_profile.delete_memory(id1) is True
        assert len(tmp_profile.memories) == 1
        assert tmp_profile.memories[0]["id"] == id3

        # Clear
        assert tmp_profile.clear_memories() is True
        assert len(tmp_profile.memories) == 0

    def test_render_prompt_context(self, tmp_profile):
        tmp_profile.update_field("称呼", "文博博士")
        tmp_profile.update_field("目标", "备考408")
        tmp_profile.add_memory("周五下午有英语组会")

        ctx = tmp_profile.render_prompt_context()
        assert "文博博士" in ctx
        assert "备考408" in ctx
        assert "周五下午有英语组会" in ctx
        assert "博士档案与长程记忆" in ctx


class TestActionsIntegration:
    def test_actions_update_and_query(self, tmp_profile):
        res1 = actions.run_action("update_doctor_profile", {"field": "称呼", "value": "明日方舟博士"})
        assert "更新为「明日方舟博士」" in res1
        assert tmp_profile.nickname == "明日方舟博士"

        res2 = actions.run_action("remember_doctor_fact", {"fact": "博士最喜欢的干员是阿米娅"})
        assert "已将这件事情记在博士档案本中了" in res2
        assert len(tmp_profile.memories) == 1

        res3 = actions.run_action("query_doctor_profile", {"field": "称呼"})
        assert "明日方舟博士" in res3

        res4 = actions.run_action("query_doctor_profile", {})
        assert "明日方舟博士" in res4
        assert "最喜欢的干员是阿米娅" in res4


class TestAiBrainProfileContext:
    def test_brain_profile_context(self, tmp_profile, tmp_path):
        tmp_profile.update_field("称呼", "测试博士")
        tmp_profile.add_memory("测试记忆条目")

        # Instantiate AmiyaBrain with temporary dir
        brain = ai.AmiyaBrain(str(tmp_path))
        ctx = brain._profile_context()
        assert "测试博士" in ctx
        assert "测试记忆条目" in ctx


class TestDoctorProfileDialog:
    def test_dialog_load_and_save(self, tmp_profile):
        tmp_profile.update_field("称呼", "旧称呼")
        tmp_profile.add_memory("旧记忆条目")

        dlg = DoctorProfileDialog()
        assert dlg.edit_nickname.text() == "旧称呼"
        assert dlg.list_memories.count() == 1

        # Simulate editing fields
        dlg.edit_nickname.setText("新称呼")
        dlg.edit_identity.setText("新身份")
        dlg.edit_preferences.setText("新偏好")
        dlg.edit_habits.setText("新作息")
        dlg.edit_goals.setText("新目标")

        dlg._on_save()

        assert tmp_profile.nickname == "新称呼"
        assert tmp_profile.identity == "新身份"
        assert tmp_profile.preferences == "新偏好"
        assert tmp_profile.habits == "新作息"
        assert tmp_profile.goals == "新目标"
        dlg.close()
