"""Тесты старта приложения и слоя совместимости UI.

Регрессия на ошибки, после которых окно вообще не открывалось:
невалидная тема в config.json, опция padding у LabelFrame и исчезнувший
в ttkbootstrap 2.x модуль ttkbootstrap.scrolled.
"""

import json

import pytest

tk = pytest.importorskip("tkinter")
ttkb = pytest.importorskip("ttkbootstrap")

from core.scrolling import SCROLL_SPEED_FACTOR
from core.utils import DEFAULT_THEME, get_app_data_dir
from gui.ui_compat import (
    available_themes,
    boost_mousewheel,
    find_scroll_canvas,
    label_frame,
    resolve_theme,
    scrolled_frame,
)


def _skip_if_no_display(error):
    if "display" in str(error).lower():
        pytest.skip(f"Tk недоступен: {error}")


@pytest.fixture
def root():
    try:
        window = ttkb.Window(themename="darkly")
    except tk.TclError as error:  # pragma: no cover - нет дисплея
        pytest.skip(f"Tk недоступен: {error}")
    window.withdraw()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


class TestResolveTheme:
    def test_theme_list_is_loaded_without_window(self):
        themes = available_themes()
        assert "darkly" in themes and "cosmo" in themes

    def test_alias_is_resolved(self):
        assert resolve_theme("dark") == "darkly"
        assert resolve_theme("light") == "cosmo"

    def test_unknown_theme_falls_back_to_default(self):
        assert resolve_theme("нет-такой-темы") == DEFAULT_THEME

    def test_valid_theme_is_kept(self):
        assert resolve_theme("cosmo") == "cosmo"


class TestLabelFrameCompatibility:
    def test_label_frame_inside_plain_frame(self, root):
        frame = label_frame(ttkb.Frame(root), "Тест", 15)
        assert frame.cget("text") == "Тест"

    def test_label_frame_inside_scrolled_frame(self, root):
        """Именно здесь padding давал TclError: unknown option \"-padding\"."""
        scrolled = scrolled_frame(root)
        frame = label_frame(scrolled, "Тест", 15)
        assert frame.cget("text") == "Тест"


class TestScrolledFrameCompatibility:
    def test_scrolled_frame_works_on_any_ttkbootstrap(self, root):
        """В ttkbootstrap 2.x импорт ttkbootstrap.scrolled падал с ImportError."""
        scrolled = scrolled_frame(root)
        scrolled.pack(fill="both", expand=True)
        assert find_scroll_canvas(scrolled) is not None

    def test_mousewheel_is_boosted(self, root):
        scrolled = scrolled_frame(root)
        accumulator = boost_mousewheel(scrolled)
        assert accumulator is not None
        assert accumulator.factor == SCROLL_SPEED_FACTOR
        units = [accumulator.units(1) for _ in range(10)]
        assert sum(units) == 17


class TestMainWindowStartup:
    def test_window_starts_with_invalid_theme_in_config(self, isolated_home, tmp_path):
        """С theme='dark' приложение падало с критической ошибкой."""
        config_path = get_app_data_dir() / "config.json"
        config_path.write_text(
            json.dumps(
                {"theme": "dark", "download_path": str(tmp_path / "downloads")},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        from gui.main_window import MainWindow

        try:
            window = MainWindow()
        except tk.TclError as error:
            _skip_if_no_display(error)
            raise

        try:
            assert window.root.winfo_exists()
            assert window.config.get("theme") == "darkly"
            assert window.notebook.index("end") == 2
        finally:
            window.download_frame.stop_all_downloads()
            window.root.destroy()
