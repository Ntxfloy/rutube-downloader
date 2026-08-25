"""Тесты очереди загрузки и расчёта прогресса."""

import pytest

from core.downloader import DownloadCancelled, RutubeDownloader, build_format_selector


class TestFormatSelector:
    def test_best_and_worst(self):
        assert build_format_selector("best", True) == "bv*+ba/b"
        assert build_format_selector("best", False) == "b"
        assert build_format_selector("worst", True) == "wv*+wa/w"
        assert build_format_selector("worst", False) == "w"

    def test_height_selector_is_numeric(self):
        """Раньше получался невалидный фильтр best[height<=720p]."""
        selector = build_format_selector("720p", True)
        assert "height<=720" in selector
        assert "720p" not in selector
        assert build_format_selector("480p", False) == "b[height<=480]/b"

    def test_unknown_quality_falls_back(self):
        assert build_format_selector("что-то", True) == "bv*+ba/b"
        assert build_format_selector(None, True) == "bv*+ba/b"


@pytest.fixture
def downloader(isolated_home, tmp_path):
    return RutubeDownloader(download_path=str(tmp_path / "downloads"))


@pytest.fixture
def events(downloader):
    captured = []
    downloader.set_progress_callback(
        lambda task, status, message, info: captured.append((status, message, info))
    )
    return captured


class TestQueue:
    def test_single_video(self, downloader, events):
        assert downloader.add_to_queue(
            "https://rutube.ru/video/abc/",
            {"title": "Видео", "type": "video"},
            quality="720p",
        ) is True
        assert len(downloader.download_queue) == 1
        task = downloader.download_queue[0]
        assert task["type"] == "single_video"
        assert task["quality"] == "720p"
        assert task["use_playlist_items"] is False
        assert events[-1][0] == "queued"

    def test_playlist_uses_direct_episode_urls(self, downloader):
        content_info = {
            "title": "Сериал",
            "type": "playlist",
            "episodes": 3,
            "episode_urls": [
                "https://rutube.ru/video/e1/",
                "https://rutube.ru/video/e2/",
                "https://rutube.ru/video/e3/",
            ],
        }
        assert downloader.add_to_queue("https://rutube.ru/plst/1/", content_info, 2, 3) is True
        urls = [task["url"] for task in downloader.download_queue]
        assert urls == ["https://rutube.ru/video/e2/", "https://rutube.ru/video/e3/"]
        assert all(task["use_playlist_items"] is False for task in downloader.download_queue)
        assert [task["episode"] for task in downloader.download_queue] == [2, 3]

    def test_playlist_without_urls_uses_playlist_items(self, downloader):
        content_info = {"title": "Сериал", "type": "playlist", "episodes": 2}
        assert downloader.add_to_queue("https://rutube.ru/plst/1/", content_info, 1, 2) is True
        assert all(task["use_playlist_items"] is True for task in downloader.download_queue)

    def test_end_episode_is_clamped(self, downloader):
        content_info = {"title": "Сериал", "type": "playlist", "episodes": 2}
        downloader.add_to_queue("https://rutube.ru/plst/1/", content_info, 1, 50)
        assert len(downloader.download_queue) == 2

    def test_clear_queue_resets_counters(self, downloader):
        downloader.add_to_queue("u", {"title": "A", "type": "video"})
        downloader.clear_queue()
        assert downloader.download_queue == []
        assert downloader.get_queue_status()["total"] == 0


class TestPercent:
    def test_total_bytes(self, downloader):
        assert downloader._calculate_percent(
            {"downloaded_bytes": 50, "total_bytes": 100}
        ) == pytest.approx(50.0)

    def test_total_bytes_estimate(self, downloader):
        assert downloader._calculate_percent(
            {"downloaded_bytes": 25, "total_bytes_estimate": 100}
        ) == pytest.approx(25.0)

    def test_fragments_for_hls(self, downloader):
        """Главный случай Rutube: HLS без известного размера файла."""
        assert downloader._calculate_percent(
            {"fragment_index": 5, "fragment_count": 20}
        ) == pytest.approx(25.0)

    def test_percent_string_fallback(self, downloader):
        assert downloader._calculate_percent({"_percent_str": " 42.5%"}) == pytest.approx(42.5)
        assert downloader._calculate_percent({"_percent_str": "42,5%"}) == pytest.approx(42.5)

    def test_unknown_percent(self, downloader):
        assert downloader._calculate_percent({}) is None


class TestProgressHook:
    def _task(self, downloader):
        downloader.add_to_queue("https://rutube.ru/video/abc/", {"title": "A", "type": "video"})
        return downloader.download_queue[0]

    def test_hook_sends_structured_percent(self, downloader, events):
        task = self._task(downloader)
        downloader._progress_hook(
            {
                "status": "downloading",
                "downloaded_bytes": 50,
                "total_bytes": 100,
                "speed": 1024,
                "eta": 10,
            },
            task,
        )
        status, message, info = events[-1]
        assert status == "progress"
        assert info["percent"] == pytest.approx(50.0)
        assert info["indeterminate"] is False
        assert info["speed"] == 1024
        assert "50.0%" in message
        assert info["overall_percent"] == pytest.approx(50.0)

    def test_hook_marks_unknown_size_as_indeterminate(self, downloader, events):
        task = self._task(downloader)
        downloader._progress_hook({"status": "downloading", "downloaded_bytes": 10}, task)
        status, _message, info = events[-1]
        assert status == "progress"
        assert info["percent"] is None
        assert info["indeterminate"] is True

    def test_finished_sets_hundred(self, downloader, events):
        task = self._task(downloader)
        downloader._progress_hook({"status": "finished"}, task)
        _status, _message, info = events[-1]
        assert info["percent"] == pytest.approx(100.0)
        assert downloader._overall_percent() == pytest.approx(100.0)

    def test_overall_percent_across_tasks(self, downloader):
        content_info = {
            "title": "Сериал",
            "type": "playlist",
            "episodes": 2,
            "episode_urls": ["https://rutube.ru/video/e1/", "https://rutube.ru/video/e2/"],
        }
        downloader.add_to_queue("https://rutube.ru/plst/1/", content_info, 1, 2)
        first, second = downloader.download_queue
        downloader._progress_hook({"status": "finished"}, first)
        assert downloader._overall_percent() == pytest.approx(50.0)
        downloader._progress_hook(
            {"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100}, second
        )
        assert downloader._overall_percent() == pytest.approx(75.0)

    def test_stop_cancels_hook(self, downloader):
        task = self._task(downloader)
        downloader.stop_download()
        with pytest.raises(DownloadCancelled):
            downloader._progress_hook({"status": "downloading"}, task)


class TestCallbackCompatibility:
    def test_three_argument_callback_still_works(self, downloader):
        received = []
        downloader.set_progress_callback(
            lambda task, status, message: received.append((status, message))
        )
        downloader._notify(None, "queued", "тест")
        assert received == [("queued", "тест")]

    def test_broken_callback_does_not_crash(self, downloader):
        def broken(*_args, **_kwargs):
            raise RuntimeError("boom")

        downloader.set_progress_callback(broken)
        downloader._notify(None, "queued", "тест")


class TestPaths:
    def test_set_download_path(self, downloader, tmp_path):
        target = tmp_path / "other"
        downloader.set_download_path(str(target))
        assert downloader.get_download_path() == str(target)
        assert target.is_dir()

    def test_max_concurrent_downloads(self, downloader):
        downloader.set_max_concurrent_downloads(5)
        assert downloader.max_concurrent_downloads == 5
        downloader.set_max_concurrent_downloads("много")
        assert downloader.max_concurrent_downloads == 1
