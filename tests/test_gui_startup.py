"""Тесты старта приложения и совместимости LabelFrame.

Регрессия на две ошибки, после которых окно вообще не открывалось:
невалидная тема в config.json и опция padding у LabelFrame.
"""

import json

import pytest

tk = pytest.importorskip("tkinter")
ttkb = pytest.importorskip("ttkbootstrap")

from core.utils import DEFAULT_THEME, get_app_data_dir  # noqa: E402
from gui.ui_compat import available_themes, label_frame, resolve_theme  # noqa: E402


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
        from ttkbootstrap.scrolled import ScrolledFrame

        scrolled = ScrolledFrame(root, autohide=True)
        frame = label_frame(scrolled, "Тест", 15)
        assert frame.cget("text") == "Тест"


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
