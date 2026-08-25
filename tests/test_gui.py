"""GUI-тесты: буфер обмена, видимость кнопок и процент загрузки.

Запускаются в реальном Tk (в CI — под xvfb). Если дисплея нет, тесты пропускаются.
"""

import threading
from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")
ttkb = pytest.importorskip("ttkbootstrap")

from core.utils import ConfigManager, HistoryManager  # noqa: E402
from gui.download_frame import (  # noqa: E402
    COPY_KEYCODES,
    CUT_KEYCODES,
    PASTE_KEYCODES,
    SELECT_ALL_KEYCODES,
    DownloadFrame,
)

URL = "https://rutube.ru/video/abcdef/"


@pytest.fixture
def gui(isolated_home, tmp_path):
    try:
        root = ttkb.Window(themename="darkly")
    except tk.TclError as error:  # pragma: no cover - нет дисплея
        pytest.skip(f"Tk недоступен: {error}")
    root.withdraw()

    config = ConfigManager(config_path=str(tmp_path / "config.json"))
    config.set("download_path", str(tmp_path / "downloads"))
    history = HistoryManager(history_path=str(tmp_path / "history.json"))
    frame = DownloadFrame(root, config, history_manager=history)

    yield SimpleNamespace(root=root, frame=frame, config=config, history=history)

    try:
        root.destroy()
    except tk.TclError:
        pass


class TestImports:
    def test_gui_modules_import(self):
        import gui.download_frame  # noqa: F401
        import gui.history_frame  # noqa: F401
        import gui.main_window  # noqa: F401

    def test_keycodes_cover_layout_independent_shortcuts(self):
        assert 86 in PASTE_KEYCODES and 55 in PASTE_KEYCODES
        assert 67 in COPY_KEYCODES and 54 in COPY_KEYCODES
        assert 88 in CUT_KEYCODES and 53 in CUT_KEYCODES
        assert 65 in SELECT_ALL_KEYCODES and 38 in SELECT_ALL_KEYCODES


class TestControlButtons:
    def test_stop_and_clear_buttons_are_packed(self, gui):
        """Был баг: вместо кнопок паковался их контейнер, и кнопок не было видно."""
        assert gui.frame.stop_btn.winfo_manager() == "pack"
        assert gui.frame.clear_queue_btn.winfo_manager() == "pack"
        assert str(gui.frame.stop_btn.pack_info()["side"]) == "left"

    def test_buttons_start_disabled(self, gui):
        assert str(gui.frame.stop_btn.cget("state")) == "disabled"
        assert str(gui.frame.download_btn.cget("state")) == "disabled"


class TestClipboard:
    def test_paste_from_clipboard(self, gui):
        gui.root.clipboard_clear()
        gui.root.clipboard_append(URL)
        assert gui.frame._paste_from_clipboard() == "break"
        assert gui.frame.url_var.get() == URL

    def test_ctrl_v_with_russian_layout(self, gui):
        """Главный баг: при русской раскладке keysym — Cyrillic_em, а не 'v'."""
        gui.root.clipboard_clear()
        gui.root.clipboard_append(URL)
        event = SimpleNamespace(keysym="Cyrillic_em", keycode=86, widget=gui.frame.url_entry)
        assert gui.frame._on_control_key(event, gui.frame.url_entry) == "break"
        assert gui.frame.url_var.get() == URL

    def test_paste_collapses_newlines(self, gui):
        gui.root.clipboard_clear()
        gui.root.clipboard_append(f"  {URL}\n")
        gui.frame._paste_from_clipboard()
        assert gui.frame.url_var.get() == URL

    def test_paste_replaces_selection_only(self, gui):
        gui.frame.url_var.set("мусор")
        gui.frame.url_entry.select_range(0, tk.END)
        gui.root.clipboard_clear()
        gui.root.clipboard_append(URL)
        gui.frame._paste_from_clipboard()
        assert gui.frame.url_var.get() == URL

    def test_copy_and_cut(self, gui):
        gui.frame.url_var.set(URL)
        gui.frame._copy_to_clipboard()
        assert gui.frame.url_entry.clipboard_get() == URL
        gui.frame._cut_to_clipboard()
        assert gui.frame.url_var.get() == ""

    def test_select_all(self, gui):
        gui.frame.url_var.set(URL)
        event = SimpleNamespace(keysym="Cyrillic_ef", keycode=65, widget=gui.frame.url_entry)
        assert gui.frame._on_control_key(event, gui.frame.url_entry) == "break"
        assert gui.frame.url_entry.selection_present() is True

    def test_clear_url(self, gui):
        gui.frame.url_var.set(URL)
        gui.frame.clear_url()
        assert gui.frame.url_var.get() == ""
        assert str(gui.frame.download_btn.cget("state")) == "disabled"


class TestProgressUI:
    def test_percent_is_displayed(self, gui):
        """Был баг: процент не показывался вообще."""
        gui.frame._apply_progress(
            "progress",
            "Серия 1: 42.5%",
            {
                "percent": 42.5,
                "overall_percent": 50.0,
                "speed": 1024 * 1024,
                "eta": 65,
                "downloaded_bytes": 512,
                "total_bytes": 1024,
                "completed": 1,
                "total": 2,
            },
        )
        assert gui.frame.percent_label.cget("text") == "42.5%"
        assert gui.frame.progress_var.get() == pytest.approx(42.5)
        assert gui.frame.overall_label.cget("text") == "50.0%"
        assert gui.frame.overall_var.get() == pytest.approx(50.0)

        speed_text = gui.frame.speed_label.cget("text")
        assert "1.0 MB/s" in speed_text
        assert "01:05" in speed_text
        assert "1/2" in gui.frame.queue_label.cget("text")

    def test_indeterminate_mode_for_unknown_size(self, gui):
        gui.frame._apply_progress("progress", "Серия 1: загрузка…", {"percent": None})
        assert gui.frame._indeterminate is True
        assert gui.frame.percent_label.cget("text") == "…"
        gui.frame._apply_progress("progress", "Серия 1: 10.0%", {"percent": 10.0})
        assert gui.frame._indeterminate is False
        assert gui.frame.percent_label.cget("text") == "10.0%"

    def test_percent_is_clamped(self, gui):
        gui.frame._apply_progress("progress", "x", {"percent": 150.0})
        assert gui.frame.progress_var.get() == pytest.approx(100.0)

    def test_complete_sets_hundred(self, gui):
        gui.frame._apply_progress("complete", "Серия 1 скачана", {})
        assert gui.frame.percent_label.cget("text") == "100.0%"

    def test_callback_from_worker_thread_does_not_raise(self, gui):
        """Callback из рабочего потока не должен трогать Tk напрямую."""
        errors = []

        def worker():
            try:
                gui.frame._on_download_progress(
                    {"episode": 1}, "progress", "Серия 1: 30.0%", {"percent": 30.0}
                )
            except Exception as error:  # pragma: no cover
                errors.append(error)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        assert errors == []

    def test_callback_updates_ui_from_main_thread(self, gui):
        gui.frame._on_download_progress(
            {"episode": 1}, "progress", "Серия 1: 30.0%", {"percent": 30.0}
        )
        gui.root.update()
        assert gui.frame.percent_label.cget("text") == "30.0%"

    def test_all_done_updates_history_status(self, gui):
        entry_id = gui.history.add_download(
            URL, {"title": "A", "type": "video"}, 1, 1, "best", status="in_progress"
        )
        gui.frame._current_history_id = entry_id
        gui.frame.is_downloading = True
        gui.frame._apply_progress("all_done", "Готово", {})
        assert gui.frame.is_downloading is False
        assert gui.history.get_history()[0]["status"] == "completed"

    def test_stopped_marks_history(self, gui):
        entry_id = gui.history.add_download(
            URL, {"title": "A", "type": "video"}, 1, 1, "best", status="in_progress"
        )
        gui.frame._current_history_id = entry_id
        gui.frame._apply_progress("stopped", "Остановлено", {})
        assert gui.history.get_history()[0]["status"] == "stopped"


class TestContentInfo:
    def test_playlist_shows_episode_range(self, gui):
        gui.frame._apply_content_info(
            {"title": "Сериал", "type": "playlist", "episodes": 12, "description": "Описание"}
        )
        assert gui.frame.end_episode_var.get() == "12"
        assert "12" in gui.frame.details_label.cget("text")
        assert str(gui.frame.download_btn.cget("state")) == "normal"

    def test_error_info_does_not_crash(self, gui, monkeypatch):
        monkeypatch.setattr(
            "gui.download_frame.messagebox.showerror", lambda *args, **kwargs: None
        )
        gui.frame._apply_content_info({"error": "Не удалось разобрать страницу"})
        assert gui.frame.content_info is None
        assert str(gui.frame.download_btn.cget("state")) == "disabled"

    def test_none_info_does_not_crash(self, gui, monkeypatch):
        monkeypatch.setattr(
            "gui.download_frame.messagebox.showerror", lambda *args, **kwargs: None
        )
        gui.frame._apply_content_info(None)
        assert gui.frame.content_info is None

    def test_load_url_without_analyze(self, gui):
        gui.frame.load_url("  rutube.ru/video/xyz/  ", analyze=False)
        assert gui.frame.url_var.get() == "https://rutube.ru/video/xyz/"
