"""Тесты утилит, конфига и истории."""

from pathlib import Path

from core.utils import (
    MAX_HISTORY_ENTRIES,
    ConfigManager,
    FileManager,
    HistoryManager,
    ValidationUtils,
    format_bytes,
    format_duration,
    format_speed,
)


class TestFormatting:
    def test_format_bytes(self):
        assert format_bytes(0) == "0.0 B"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(1024 * 1024) == "1.0 MB"
        assert format_bytes(None) == "0.0 B"
        assert format_bytes("не число") == "0 B"

    def test_format_speed(self):
        assert format_speed(None) == "—"
        assert format_speed(0) == "—"
        assert format_speed(1024) == "1.0 KB/s"

    def test_format_duration(self):
        assert format_duration(0) == "00:00"
        assert format_duration(59) == "00:59"
        assert format_duration(65) == "01:05"
        assert format_duration(3661) == "01:01:01"
        assert format_duration(None) == "Неизвестно"
        assert format_duration(-1) == "Неизвестно"


class TestValidation:
    def test_normalize_url_trims_and_adds_scheme(self):
        assert ValidationUtils.normalize_url("  rutube.ru/video/abc/  ") == "https://rutube.ru/video/abc/"
        assert ValidationUtils.normalize_url("//rutube.ru/video/abc/") == "https://rutube.ru/video/abc/"
        assert ValidationUtils.normalize_url('"https://rutube.ru/video/abc/"') == "https://rutube.ru/video/abc/"
        assert ValidationUtils.normalize_url("") == ""
        assert ValidationUtils.normalize_url(None) == ""

    def test_is_valid_url(self):
        assert ValidationUtils.is_valid_url("https://rutube.ru/video/abc/") is True
        assert ValidationUtils.is_valid_url("rutube.ru/plst/123/") is True
        assert ValidationUtils.is_valid_url("https://m.rutube.ru/video/abc/") is True
        assert ValidationUtils.is_valid_url("https://youtube.com/watch?v=1") is False
        assert ValidationUtils.is_valid_url("https://rutube.ru.evil.com/video/1/") is False
        assert ValidationUtils.is_valid_url("") is False

    def test_is_valid_quality(self):
        for quality in ("best", "worst", "1080p", "720p", "480p", "360p", "240p"):
            assert ValidationUtils.is_valid_quality(quality) is True
        assert ValidationUtils.is_valid_quality("1080P") is True
        assert ValidationUtils.is_valid_quality("4k") is False
        assert ValidationUtils.is_valid_quality("") is False

    def test_is_valid_episode_range(self):
        assert ValidationUtils.is_valid_episode_range(1, 5, 10) is True
        assert ValidationUtils.is_valid_episode_range(5, 1, 10) is False
        assert ValidationUtils.is_valid_episode_range(0, 1, 10) is False
        assert ValidationUtils.is_valid_episode_range("a", 1, 10) is False


class TestConfigManager:
    def test_defaults(self, isolated_home, tmp_path):
        config = ConfigManager(config_path=str(tmp_path / "config.json"))
        assert config.get("default_quality") == "best"
        assert config.get("max_concurrent_downloads") == 2
        assert config.get("show_success_popups") is False

    def test_set_and_persist(self, isolated_home, tmp_path):
        path = tmp_path / "config.json"
        config = ConfigManager(config_path=str(path))
        config.set("theme", "superhero")
        config.update({"max_concurrent_downloads": 4}, save=True)
        assert path.exists()

        reloaded = ConfigManager(config_path=str(path))
        assert reloaded.get("theme") == "superhero"
        assert reloaded.get("max_concurrent_downloads") == 4

    def test_download_path_is_created(self, isolated_home, tmp_path):
        config = ConfigManager(config_path=str(tmp_path / "config.json"))
        target = tmp_path / "downloads" / "nested"
        config.set_download_path(str(target))
        assert Path(config.get_download_path()) == target
        assert target.is_dir()


class TestHistoryManager:
    def _manager(self, tmp_path):
        return HistoryManager(history_path=str(tmp_path / "history.json"))

    def test_add_and_read(self, isolated_home, tmp_path):
        history = self._manager(tmp_path)
        entry_id = history.add_download(
            "https://rutube.ru/video/1/",
            {"title": "Тест", "type": "video", "episodes": 1},
            1,
            1,
            "720p",
        )
        assert entry_id
        entries = history.get_history()
        assert len(entries) == 1
        assert entries[0]["id"] == entry_id
        assert entries[0]["quality"] == "720p"
        assert entries[0]["status"] == "queued"

    def test_update_status_and_remove_by_id(self, isolated_home, tmp_path):
        history = self._manager(tmp_path)
        first = history.add_download("u1", {"title": "A"}, 1, 1, "best")
        second = history.add_download("u2", {"title": "B"}, 1, 1, "best")

        history.update_status(second, "completed")
        by_id = {item["id"]: item for item in history.get_history()}
        assert by_id[second]["status"] == "completed"
        assert by_id[first]["status"] == "queued"

        history.remove_by_id(first)
        remaining = [item["id"] for item in history.get_history()]
        assert remaining == [second]

    def test_newest_first(self, isolated_home, tmp_path):
        history = self._manager(tmp_path)
        history.add_download("u1", {"title": "Старая"}, 1, 1, "best")
        history.add_download("u2", {"title": "Новая"}, 1, 1, "best")
        assert history.get_history()[0]["title"] == "Новая"

    def test_stats(self, isolated_home, tmp_path):
        history = self._manager(tmp_path)
        history.add_download("u1", {"title": "A"}, 1, 3, "best")
        history.add_download("u2", {"title": "B"}, 1, 1, "best")
        stats = history.get_download_stats()
        assert stats["total_downloads"] == 2
        assert stats["total_episodes"] == 4

    def test_limit(self, isolated_home, tmp_path):
        history = self._manager(tmp_path)
        for index in range(MAX_HISTORY_ENTRIES + 5):
            history.add_download(f"u{index}", {"title": str(index)}, 1, 1, "best")
        assert len(history.get_history()) == MAX_HISTORY_ENTRIES

    def test_persistence(self, isolated_home, tmp_path):
        history = self._manager(tmp_path)
        history.add_download("u1", {"title": "A"}, 1, 1, "best")
        assert len(self._manager(tmp_path).get_history()) == 1

    def test_clear(self, isolated_home, tmp_path):
        history = self._manager(tmp_path)
        history.add_download("u1", {"title": "A"}, 1, 1, "best")
        history.clear_history()
        assert history.get_history() == []


class TestFileManager:
    def test_sanitize_filename(self):
        assert FileManager.sanitize_filename('a<>:"/\\|?*b') == "a_b"
        assert FileManager.sanitize_filename("  имя.  ") == "имя"
        assert FileManager.sanitize_filename("") == "unknown"
        assert len(FileManager.sanitize_filename("я" * 300)) == 100

    def test_ensure_directory_and_space(self, tmp_path):
        target = tmp_path / "a" / "b"
        assert FileManager.ensure_directory(str(target)) is True
        assert target.is_dir()
        assert FileManager.get_available_space(str(target)) > 0
