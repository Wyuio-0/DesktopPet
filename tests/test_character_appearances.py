"""Appearance variants share character identity and preserve legacy assets."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt5 import QtWidgets

from pet.character import Character
from pet.menu import PetContextMenuBuilder
from pet.settings import Settings
from pet.tray import PetTrayCoordinator


@pytest.fixture
def character_dir(tmp_path):
    directory = tmp_path / "amiya"
    (directory / "idle").mkdir(parents=True)
    (directory / "idle" / "original.webm").write_bytes(b"original animation")
    (directory / "illustrated").mkdir()
    (directory / "illustrated" / "idle.png").write_bytes(b"illustration")
    config = {
        "name": "Amiya", "display_name": "阿米娅", "scale": 0.765,
        "default_appearance_name": "基建小人",
        "voice": {"enabled": True}, "persona": "same persona",
        "actions": {"idle": {"folder": "idle", "loop": True}},
        "interactions": {"on_click": "idle"},
        "appearances": {"illustrated": {
            "display_name": "插画阿米娅", "scale": 0.5,
            "actions": {"idle": {"clip": "illustrated/idle.png", "loop": True}},
            # Identity or voice fields in a custom skin cannot change these.
            "name": "different", "voice": {"enabled": False},
        }},
    }
    (directory / "config.json").write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return directory


def test_variant_changes_only_presentation(character_dir):
    original = Character(str(character_dir))
    illustrated = Character(str(character_dir), appearance="illustrated")
    assert original.appearance_key == "default"
    assert original.appearance_name == "基建小人"
    assert illustrated.appearance_name == "插画阿米娅"
    assert original.available_appearances == (
        ("default", "基建小人"), ("illustrated", "插画阿米娅"))
    assert original.action("idle").pick_clip().endswith("original.webm")
    assert illustrated.action("idle").pick_clip().endswith("idle.png")
    assert original.scale == 0.765
    assert illustrated.scale == 0.5
    assert illustrated.key == original.key == "amiya"
    assert illustrated.dir == original.dir
    assert illustrated.name == original.name == "Amiya"
    assert illustrated.display_name == original.display_name == "阿米娅"
    assert illustrated.cfg["voice"] == original.cfg["voice"] == {"enabled": True}
    assert illustrated.cfg["persona"] == original.cfg["persona"]
    assert illustrated.interaction("on_click") == "idle"
    assert (character_dir / "idle" / "original.webm").read_bytes() == b"original animation"


@pytest.mark.parametrize("saved", ["removed-skin", None, [], {}])
def test_removed_or_invalid_preference_uses_original(character_dir, saved):
    restored = Character(str(character_dir), appearance=saved)
    assert restored.appearance_key == "default"
    assert restored.action("idle").pick_clip().endswith("original.webm")


def test_characters_without_variants_keep_legacy_behavior(character_dir):
    path = character_dir / "config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config.pop("appearances")
    path.write_text(json.dumps(config), encoding="utf-8")
    character = Character(str(character_dir), appearance="illustrated")
    assert character.appearance_key == "default"
    assert len(character.available_appearances) == 1
    assert character.action("idle").pick_clip().endswith("original.webm")


def test_sprite_actions_expose_metadata_without_requiring_video(character_dir):
    path = character_dir / "config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    sprite = {"sheet": "appearances/illustrated/sprites.png", "grid": [3, 2],
              "cells": [0, 0, 1, 0], "motion": "breathe"}
    config["appearances"]["illustrated"]["actions"]["idle"] = {
        "sprite": sprite, "loop": True}
    path.write_text(json.dumps(config), encoding="utf-8")
    action = Character(str(character_dir), "illustrated").action("idle")
    assert action.sprite == sprite
    assert action.loop is True


@pytest.fixture
def qt_app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_menu_marks_current_appearance_and_switches_back(character_dir, qt_app):
    window = SimpleNamespace(char=Character(str(character_dir), "illustrated"),
                             _switch_appearance=Mock())
    builder = PetContextMenuBuilder(window)
    parent = QtWidgets.QMenu()
    submenu = builder.add_appearance_menu(parent)
    assert submenu.title() == "切换形象"
    original, illustrated = submenu.actions()
    assert original.text() == "基建小人"
    assert illustrated.text() == "插画阿米娅"
    assert not original.isChecked() and illustrated.isChecked()
    original.trigger()
    window._switch_appearance.assert_called_once_with("default")
    assert original.isChecked() and not illustrated.isChecked()


def test_tray_uses_the_same_appearance_menu(character_dir, qt_app, monkeypatch):
    monkeypatch.setattr(QtWidgets.QSystemTrayIcon, "isSystemTrayAvailable", lambda: False)
    window = SimpleNamespace(
        char=Character(str(character_dir)), _switch_appearance=Mock(),
        isVisible=lambda: True, show_knowledge_page=Mock(), voice=SimpleNamespace(enabled=True),
        _tts_supported=False, _tts_on=False, _use_clone=False,
        _set_tts=Mock(), _toggle_mute=Mock(), _quit=Mock(),
    )
    window.menu_builder = PetContextMenuBuilder(window)
    tray = PetTrayCoordinator(window)
    tray._tray_menu = QtWidgets.QMenu()
    monkeypatch.setattr("pet.web_launcher.is_server_listening", lambda: False)
    tray.rebuild_menu()
    submenu = next(action.menu() for action in tray._tray_menu.actions()
                   if action.text() == "切换形象")
    submenu.actions()[1].trigger()
    window._switch_appearance.assert_called_once_with("illustrated")


def test_preferences_keep_appearance_during_migration(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema_version": 1, "appearance_amiya": "illustrated",
                                "obsolete_setting": True}), encoding="utf-8")
    monkeypatch.setattr("pet.settings._settings_path", lambda: str(path))
    settings = Settings()
    assert settings.get("appearance_amiya") == "illustrated"
    assert "obsolete_setting" not in settings.data
    settings.set("appearance_amiya", "default")
    assert Settings().get("appearance_amiya") == "default"
