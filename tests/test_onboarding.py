"""First-run choices, navigation, persistence and safe dismissal."""
import json
from unittest.mock import patch

import pytest
from PyQt5 import QtWidgets

from pet.character import Character
from pet.onboarding import WelcomeDialog, available_characters
from pet.settings import Settings


@pytest.fixture(scope='module')
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def setup(tmp_path, monkeypatch):
    # Isolate preferences on Windows CI as well as Linux.
    monkeypatch.setattr('pet.settings._settings_path',
                        lambda: str(tmp_path / 'data' / 'settings.json'))
    chars = []
    for key in ('one', 'two'):
        folder = tmp_path / 'characters' / key
        folder.mkdir(parents=True)
        (folder / 'config.json').write_text(json.dumps({'display_name': key, 'actions': {}}))
        chars.append(Character(str(folder)))
    return chars, Settings()


def test_finish_persists_choices_after_local_interaction(app, setup):
    chars, prefs = setup
    d = WelcomeDialog(chars, chars[0].dir, prefs)
    d.character_box.setCurrentIndex(1)
    d.sound.setChecked(False)
    d.volume.setValue(25)
    d.advance()
    assert not d.next.isEnabled()
    d.say_hello()
    assert 'two' in d.reply.text()
    assert d.next.isEnabled()
    d.advance()
    stored = Settings()
    assert d.result() == QtWidgets.QDialog.Accepted
    assert stored.get('onboarding_completed') is True
    assert stored.get('character') == 'two'
    assert stored.get('voice_enabled') is False
    assert stored.get('volume') == .25


def test_dismiss_does_not_save_unfinished_choices(app, setup):
    chars, prefs = setup
    d = WelcomeDialog(chars, chars[0].dir, prefs)
    d.character_box.setCurrentIndex(1)
    d.reject()
    assert not Settings().get('onboarding_completed', False)
    assert Settings().get('character') is None


def test_back_and_change_character_requires_new_greeting(app, setup):
    chars, prefs = setup
    d = WelcomeDialog(chars, chars[0].dir, prefs)
    assert not d.listen.isEnabled()  # No audio assets is a supported state.
    d.advance()
    d.say_hello()
    d.set_page(0)
    d.character_box.setCurrentIndex(1)
    d.advance()
    assert not d.next.isEnabled()
    d.reject()


def test_preview_stops_on_change_and_close(app, setup):
    chars, prefs = setup
    with patch('pet.onboarding.VoicePlayer') as player:
        d = WelcomeDialog(chars, chars[0].dir, prefs)
        d.play_preview()
        player.return_value.play.assert_called_once_with('all')
        d.character_box.setCurrentIndex(1)
        d.audio_error()
        assert '播放失败' in d.status.text()
        d.reject()
        assert player.return_value.stop.call_count >= 2


def test_discovery_deduplicates_and_ignores_invalid_config(tmp_path):
    for root in ('primary', 'fallback'):
        folder = tmp_path / root / 'same'
        folder.mkdir(parents=True)
        (folder / 'config.json').write_text('{}')
    bad = tmp_path / 'primary' / 'broken'
    bad.mkdir()
    (bad / 'config.json').write_text('invalid')
    chars = available_characters([str(tmp_path / 'primary'), str(tmp_path / 'fallback')])
    assert len(chars) == 1
    assert chars[0].dir == str(tmp_path / 'primary' / 'same')
