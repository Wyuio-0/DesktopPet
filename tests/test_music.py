"""Tests for Music Visualizer & Beats Reaction (听歌感知与音乐律动)."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt5 import QtCore, QtWidgets

# Ensure a single QApplication instance exists for tests
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

from pet.music import (
    WindowsAudioMeter,
    MusicTrackDetector,
    _FloatingNote,
    MusicNotesOverlay,
    PetMusicCoordinator,
)
from pet import actions


class TestMusicTrackDetector:
    def test_parse_track_netease(self):
        title, artist = MusicTrackDetector._parse_track("海阔天空 - Beyond - 网易云音乐", "网易云音乐")
        assert title == "海阔天空"
        assert artist == "Beyond"

    def test_parse_track_qqmusic(self):
        title, artist = MusicTrackDetector._parse_track("QQ音乐 - 晴天 - 周杰伦", "QQ音乐")
        assert title == "晴天"
        assert artist == "周杰伦"

    def test_parse_track_spotify(self):
        # Western format: Artist - Title
        title, artist = MusicTrackDetector._parse_track("Radiohead - Creep", "Spotify")
        assert title == "Creep"
        assert artist == "Radiohead"

    def test_parse_track_kugou(self):
        title, artist = MusicTrackDetector._parse_track("江南 - 林俊杰 - 酷狗音乐", "酷狗音乐")
        assert title == "江南"
        assert artist == "林俊杰"

    def test_parse_track_bilibili(self):
        title, artist = MusicTrackDetector._parse_track("明日方舟官方EP - 曼珠沙华_哔哩哔哩_bilibili", "Bilibili")
        assert title == "明日方舟官方EP"
        assert artist == "曼珠沙华"

    def test_parse_track_plain(self):
        title, artist = MusicTrackDetector._parse_track("网易云音乐", "网易云音乐")
        assert title == ""
        assert artist == ""

    def test_get_active_media_track(self):
        res = MusicTrackDetector.get_active_media_track()
        assert isinstance(res, dict)
        assert "playing" in res
        assert "title" in res
        assert "artist" in res
        assert "player" in res


class TestFloatingNote:
    def test_note_tick_playing(self):
        note = _FloatingNote(0)
        assert note.opacity == 0.0
        assert note.symbol in ["♪", "♫", "♩", "♬"]

        # Tick with active peak
        note.tick(peak=0.5, is_playing=True, delta_time=0.04)
        assert note.opacity > 0.0
        assert note.y < note.base_y  # Lifted upwards by music peak

    def test_note_tick_silence(self):
        note = _FloatingNote(1)
        note.opacity = 0.8
        note.y = 20.0

        # Tick with silence
        note.tick(peak=0.0, is_playing=False, delta_time=0.04)
        assert note.opacity < 0.8  # Fading out
        assert note.y > 20.0       # Sinking down towards base_y


class TestMusicNotesOverlay:
    def test_overlay_creation_and_energy(self):
        overlay = MusicNotesOverlay()
        assert overlay.isWindow()
        assert len(overlay.notes) == 4

        # Active energy shows overlay
        overlay.update_energy(peak=0.6, is_playing=True)
        assert overlay.isVisible()

        # Silence fades overlay out
        for _ in range(50):
            overlay.update_energy(peak=0.0, is_playing=False)
        assert not overlay.isVisible()
        overlay.close()


class TestWindowsAudioMeter:
    def test_meter_peak_range(self):
        meter = WindowsAudioMeter()
        peak = meter.get_peak()
        assert isinstance(peak, float)
        assert 0.0 <= peak <= 1.0
        meter.release()


@pytest.fixture
def mock_window():
    w = MagicMock()
    w.prefs = {"music_visualizer_enabled": True}
    w.isVisible.return_value = True
    w._quitting = False
    w._facing_left = False
    w.x.return_value = 100
    w.y.return_value = 200
    w.width.return_value = 120
    return w


class TestPetMusicCoordinator:
    def test_init_and_config(self, mock_window):
        coord = PetMusicCoordinator(mock_window)
        assert coord.window == mock_window
        assert coord._timer.isActive()

        # Disable via prefs
        mock_window.prefs["music_visualizer_enabled"] = False
        coord.reload_config()
        assert not coord._timer.isActive()
        assert not coord.overlay.isVisible()

        # Enable again
        mock_window.prefs["music_visualizer_enabled"] = True
        coord.reload_config()
        assert coord._timer.isActive()

        coord.close()

    def test_reposition(self, mock_window):
        coord = PetMusicCoordinator(mock_window)
        coord.reposition()
        # Default right-facing: target_x = 100 + 120 * 0.15 = 118, y = 200 - 45 = 155
        assert coord.overlay.x() == 118
        assert coord.overlay.y() == 155

        # Left-facing: target_x = 100 + 120 * 0.55 = 166
        mock_window._facing_left = True
        coord.reposition()
        assert coord.overlay.x() == 166

        coord.close()

    def test_get_current_music_info(self, mock_window):
        coord = PetMusicCoordinator(mock_window)
        info = coord.get_current_music_info()
        assert isinstance(info, dict)
        assert "has_audio" in info
        assert "peak_volume" in info
        coord.close()

    def test_action_get_current_music(self, mock_window):
        coord = PetMusicCoordinator(mock_window)
        res = actions.run_action("get_current_music", {})
        assert isinstance(res, str)
        assert len(res) > 0
        coord.close()
