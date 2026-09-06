"""Tests for Weather & Ambient Sensing (本地天气感知与昼夜联动)."""

import json
import sys
import time
from unittest.mock import MagicMock, patch
import pytest
from PyQt5 import QtCore, QtWidgets

# Ensure a QApplication instance exists
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

import pet.weather
from pet.weather import (
    parse_weather_desc,
    fetch_weather_sync,
    WeatherWorker,
    PetWeatherCoordinator,
)
from pet import actions


@pytest.fixture
def mock_window():
    """Mock PetWindow for weather coordinator testing."""
    w = MagicMock()
    w.prefs = {
        "weather_care_enabled": True,
        "night_dim_enabled": True,
        "weather_city": "",
    }
    w.isVisible.return_value = True
    w._quitting = False
    w._dim_factor = 1.0
    return w


class TestWeatherParsingAndFetching:
    def test_parse_weather_desc(self):
        assert parse_weather_desc("Light rain", "") == "小雨"
        assert parse_weather_desc("Sunny", "") == "晴朗"
        assert parse_weather_desc("Heavy snow", "") == "大雪"
        assert parse_weather_desc("Thundery outbreaks possible", "") == "雷阵雨可能"
        # lang_zh priority
        assert parse_weather_desc("Clear", "晴空万里") == "晴空万里"

    def test_fetch_weather_sync_success(self):
        dummy_json = json.dumps({
            "current_condition": [{
                "temp_C": "22",
                "humidity": "60",
                "windspeedKmph": "15",
                "weatherDesc": [{"value": "Patchy light rain"}],
                "lang_zh": [{"value": "局部阵雨"}],
            }],
            "nearest_area": [{
                "areaName": [{"value": "上海"}],
            }]
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = dummy_json
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            info = fetch_weather_sync("上海")
            assert info is not None
            assert info["city"] == "上海"
            assert info["temp_c"] == 22
            assert info["desc"] == "局部阵雨"
            assert info["humidity"] == 60
            assert info["wind_kmph"] == 15

    def test_fetch_weather_sync_network_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("Timeout")):
            info = fetch_weather_sync("测试城市")
            assert info is None


class TestPetWeatherCoordinator:
    def test_day_night_dimming(self, mock_window):
        coord = PetWeatherCoordinator(mock_window)

        # Daytime: 14:00 -> factor = 1.0
        with patch("pet.weather.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 14
            coord._check_day_night()
            assert mock_window._dim_factor == 1.0

        # Nighttime: 23:30 -> factor = 0.75
        with patch("pet.weather.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 23
            coord._check_day_night()
            assert mock_window._dim_factor == 0.75

        # Nighttime: 03:00 -> factor = 0.75
        with patch("pet.weather.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 3
            coord._check_day_night()
            assert mock_window._dim_factor == 0.75

        # Disabled in prefs -> factor = 1.0 even at night
        mock_window.prefs["night_dim_enabled"] = False
        with patch("pet.weather.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 1
            coord._check_day_night()
            assert mock_window._dim_factor == 1.0

        coord.close()

    def test_evaluate_ambient_care_rain_and_snooze(self, mock_window):
        coord = PetWeatherCoordinator(mock_window)

        rain_info = {
            "city": "本地",
            "desc": "中雨",
            "temp_c": 18,
            "humidity": 80,
            "wind_kmph": 12,
        }

        # 1. Trigger rain reminder
        coord._evaluate_ambient_care(rain_info)
        mock_window._announce.assert_called_once()
        args, kwargs = mock_window._announce.call_args
        assert "雨伞" in args[0]
        assert coord._last_care_kind == "rain"
        assert coord._last_care_time > 0

        # 2. Snooze protection: second check within 4 hours should NOT repeat
        mock_window._announce.reset_mock()
        coord._evaluate_ambient_care(rain_info)
        mock_window._announce.assert_not_called()

        coord.close()

    def test_evaluate_ambient_care_snow_and_cold(self, mock_window):
        coord = PetWeatherCoordinator(mock_window)

        snow_info = {
            "city": "本地",
            "desc": "大雪",
            "temp_c": -2,
            "humidity": 70,
            "wind_kmph": 10,
        }

        coord._evaluate_ambient_care(snow_info)
        mock_window._announce.assert_called_once()
        args, _ = mock_window._announce.call_args
        assert "雪" in args[0]
        assert "外套" in args[0]

        coord.close()

    def test_evaluate_ambient_care_cold(self, mock_window):
        coord = PetWeatherCoordinator(mock_window)

        cold_info = {
            "city": "本地",
            "desc": "阴天",
            "temp_c": 3,
            "humidity": 45,
            "wind_kmph": 8,
        }

        coord._evaluate_ambient_care(cold_info)
        mock_window._announce.assert_called_once()
        args, _ = mock_window._announce.call_args
        assert "气温比较低" in args[0]
        assert "3°C" in args[0]

        coord.close()

    def test_get_weather_summary(self, mock_window):
        coord = PetWeatherCoordinator(mock_window)
        coord._current_weather = {
            "city": "北京",
            "desc": "晴朗",
            "temp_c": 25,
            "humidity": 40,
            "wind_kmph": 10,
        }

        summary = coord.get_weather_summary()
        assert "北京天气" in summary
        assert "晴朗" in summary
        assert "25°C" in summary
        assert "适宜出行" in summary

        coord.close()


class TestActionsWeatherTool:
    def test_actions_get_weather(self):
        dummy_info = {
            "city": "广州",
            "desc": "多云",
            "temp_c": 28,
            "humidity": 65,
            "wind_kmph": 14,
        }
        with patch("pet.weather.fetch_weather_sync", return_value=dummy_info):
            res = actions.run_action("get_weather", {"city": "广州"})
            assert "广州天气" in res
            assert "多云" in res
            assert "28°C" in res
