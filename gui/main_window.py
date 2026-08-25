"""
Главное окно приложения Rutube Downloader
"""

import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from core.utils import DEFAULT_THEME, ConfigManager, HistoryManager

from .download_frame import DownloadFrame
from .history_frame import HistoryFrame
from .ui_compat import label_frame, resolve_theme

REPO_URL = "https://github.com/Ntxfloy/rutube-downloader"
GEOMETRY_SAVE_DELAY_MS = 600


class MainWindow:
    """Главное окно приложения"""

    def __init__(self):
        self.config = ConfigManager()
        self.history_manager = HistoryManager()
        self._geometry_timer = None

        window_size = self.config.get("window_size", [980, 720]) or [980, 720]
        window_position = self.config.get("window_position", [100, 100]) or [100, 100]

        # С невалидным именем темы (например, "dark") приложение раньше падало
        # с критической ошибкой ('dark', 'is not a valid theme.') до появления окна.
        theme_name = resolve_theme(self.config.get("theme", DEFAULT_THEME))
        if theme_name != self.config.get("theme"):
            self.config.set("theme", theme_name)

        try:
            self.root = ttk.Window(
                title="Rutube Downloader",
                themename=theme_name,
                resizable=(True, True),
            )
        except Exception as error:
            print(f"Тема '{theme_name}' недоступна ({error}), использую '{DEFAULT_THEME}'")
            self.config.set("theme", DEFAULT_THEME)
            self.root = ttk.Window(
                title="Rutube Downloader",
                themename=DEFAULT_THEME,
                resizable=(True, True),
            )

        self.root.minsize(760, 560)

        try:
            self.root.geometry(
                f"{int(window_size[0])}x{int(window_size[1])}"
                f"+{int(window_position[0])}+{int(window_position[1])}"
            )
        except (TypeError, ValueError, IndexError):
            self.root.geometry("980x720+100+100")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Configure>", self.on_window_resize)

        self._create_widgets()
        self._create_menu()

        # Фреймы делят один HistoryManager, иначе история не видит новые записи
        self.download_frame = DownloadFrame(
            self.notebook,
            self.config,
            history_manager=self.history_manager,
            status_callback=self.update_status,
        )
        self.history_frame = HistoryFrame(
            self.notebook,
            self.config,
            history_manager=self.history_manager,
            main_window=self,
        )

        self.notebook.add(self.download_frame.frame, text="Скачивание", padding=10)
        self.notebook.add(self.history_frame.frame, text="История", padding=10)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.notebook.select(0)

        self._bind_shortcuts()

    # ------------------------------------------------------------------ UI
    def _create_widgets(self):
        """Создает основные виджеты"""
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)

        header = ttk.Frame(main_container)
        header.pack(fill=X, pady=(0, 12))

        ttk.Label(
            header,
            text="Rutube Downloader",
            font=("Helvetica", 20, "bold"),
            bootstyle="primary",
            anchor=W,
        ).pack(fill=X)

        ttk.Label(
            header,
            text="Скачивание видео и плейлистов с Rutube",
            font=("Helvetica", 11),
            bootstyle="secondary",
            anchor=W,
        ).pack(fill=X)

        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=BOTH, expand=True)

        self.status_bar = ttk.Label(
            main_container,
            text="Готов к работе",
            relief=SUNKEN,
            anchor=W,
            padding=(8, 4),
        )
        self.status_bar.pack(side=BOTTOM, fill=X, pady=(10, 0))

    def _create_menu(self):
        """Создает меню приложения"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Настройки", command=self.show_settings)
        file_menu.add_command(label="Открыть папку загрузок", command=self.open_download_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", accelerator="Ctrl+Q", command=self.on_closing)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)
        help_menu.add_command(label="Помощь", command=self.show_help)

    def _bind_shortcuts(self):
        """Глобальные горячие клавиши"""
        self.root.bind_all("<F5>", lambda event: self.history_frame.refresh_history())
        self.root.bind_all("<Control-q>", lambda event: self.on_closing())
        self.root.bind_all("<Control-Q>", lambda event: self.on_closing())

    def _on_tab_changed(self, event=None):
        """При переходе на вкладку истории обновляем её содержимое"""
        try:
            if self.notebook.index("current") == 1:
                self.history_frame.refresh_history()
        except Exception:
            pass

    # --------------------------------------------------------------- actions
    def load_url_for_download(self, url, analyze=True):
        """Переключается на вкладку скачивания и подставляет ссылку."""
        self.notebook.select(0)
        self.download_frame.load_url(url, analyze=analyze)

    def open_download_folder(self):
        self.download_frame.open_download_folder()

    def show_settings(self):
        """Показывает окно настроек"""
        settings_window = SettingsWindow(self.root, self.config)
        self.root.wait_window(settings_window.window)
        # Подхватываем изменённые настройки без перезапуска приложения
        try:
            self.download_frame.path_var.set(self.config.get_download_path())
            self.download_frame.downloader.set_download_path(self.config.get_download_path())
            self.download_frame.downloader.set_max_concurrent_downloads(
                self.config.get("max_concurrent_downloads", 2)
            )
        except Exception as error:
            print(f"Не удалось применить настройки: {error}")

    def show_about(self):
        messagebox.showinfo(
            "О программе",
            "Rutube Downloader v1.1\n\n"
            "Приложение для скачивания видео и плейлистов с Rutube\n\n"
            "Python + yt-dlp + ttkbootstrap\n"
            f"{REPO_URL}",
        )

    def show_help(self):
        help_text = (
            "Как использовать Rutube Downloader:\n\n"
            "1. Вставьте ссылку в поле ввода (Ctrl+V или правая кнопка мыши)\n"
            "2. Нажмите «Анализировать» (или Enter в поле ввода)\n"
            "3. Выберите качество и диапазон серий\n"
            "4. Нажмите «Скачать» — прогресс и проценты видны в секции прогресса\n\n"
            "Горячие клавиши:\n"
            "Ctrl+V — вставить, Ctrl+A — выделить всё, F5 — обновить историю, Ctrl+Q — выход\n\n"
            "Поддерживаются одиночные видео, плейлисты и каналы.\n\n"
            f"Подробнее: {REPO_URL}"
        )
        messagebox.showinfo("Справка", help_text)

    def update_status(self, message):
        """Обновляет статус бар"""
        try:
            self.status_bar.config(text=str(message))
        except tk.TclError:
            pass

    # -------------------------------------------------------------- geometry
    def on_window_resize(self, event):
        """Обработчик изменения размера окна (с задержкой записи).

        Раньше config.json перезаписывался на каждое событие <Configure>,
        то есть десятки раз в секунду при перетаскивании окна.
        """
        if event.widget is not self.root:
            return
        if self._geometry_timer is not None:
            try:
                self.root.after_cancel(self._geometry_timer)
            except Exception:
                pass
        self._geometry_timer = self.root.after(GEOMETRY_SAVE_DELAY_MS, self._save_geometry)

    def _save_geometry(self):
        """Сохраняет размер и позицию окна"""
        self._geometry_timer = None
        try:
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            if width > 100 and height > 100:
                self.config.update(
                    {"window_size": [width, height], "window_position": [x, y]},
                    save=True,
                )
        except tk.TclError:
            pass

    def on_closing(self):
        """Обработчик закрытия окна"""
        try:
            if hasattr(self, "download_frame"):
                if self.download_frame.is_downloading:
                    if not messagebox.askyesno(
                        "Подтверждение",
                        "Скачивание ещё идёт. Закрыть приложение?",
                    ):
                        return
                self.download_frame.stop_all_downloads()

            self._save_geometry()
            self.config.save_config()
            self.root.destroy()
        except Exception as error:
            print(f"Ошибка при закрытии: {error}")
            self.root.destroy()

    def run(self):
        """Запускает главное окно"""
        self.root.mainloop()


class SettingsWindow:
    """Окно настроек"""

    def __init__(self, parent, config):
        self.config = config
        self.parent = parent

        self.window = ttk.Toplevel(parent)
        self.window.title("Настройки")
        self.window.geometry("560x520")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.geometry(
            "+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50)
        )

        self._create_widgets()

    def _create_widgets(self):
        """Создает виджеты окна настроек"""
        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill=BOTH, expand=True)

        ttk.Label(main_frame, text="Настройки", font=("Helvetica", 16, "bold")).pack(pady=(0, 20))

        path_frame = label_frame(main_frame, "Путь для скачивания", 10)
        path_frame.pack(fill=X, pady=(0, 12))

        self.path_var = tk.StringVar(value=self.config.get_download_path())
        ttk.Entry(path_frame, textvariable=self.path_var).pack(
            side=LEFT, fill=X, expand=True, padx=(0, 10)
        )
        ttk.Button(
            path_frame, text="Обзор", command=self.browse_path, bootstyle="outline-secondary"
        ).pack(side=RIGHT)

        quality_frame = label_frame(main_frame, "Качество по умолчанию", 10)
        quality_frame.pack(fill=X, pady=(0, 12))

        self.quality_var = tk.StringVar(value=self.config.get("default_quality", "best"))
        ttk.Combobox(
            quality_frame,
            textvariable=self.quality_var,
            values=["best", "1080p", "720p", "480p", "360p", "240p", "worst"],
            state="readonly",
            width=20,
        ).pack(anchor=W)

        ffmpeg_frame = label_frame(main_frame, "Папка с ffmpeg (необязательно)", 10)
        ffmpeg_frame.pack(fill=X, pady=(0, 12))

        self.ffmpeg_var = tk.StringVar(value=self.config.get("ffmpeg_location") or "")
        ttk.Entry(ffmpeg_frame, textvariable=self.ffmpeg_var).pack(
            side=LEFT, fill=X, expand=True, padx=(0, 10)
        )
        ttk.Button(
            ffmpeg_frame,
            text="Обзор",
            command=self.browse_ffmpeg,
            bootstyle="outline-secondary",
        ).pack(side=RIGHT)

        options_frame = label_frame(main_frame, "Дополнительные настройки", 10)
        options_frame.pack(fill=X, pady=(0, 12))

        concurrent_row = ttk.Frame(options_frame)
        concurrent_row.pack(fill=X, pady=(0, 8))
        ttk.Label(concurrent_row, text="Одновременных загрузок:").pack(side=LEFT)
        self.concurrent_var = tk.StringVar(
            value=str(self.config.get("max_concurrent_downloads", 2))
        )
        ttk.Spinbox(
            concurrent_row, from_=1, to=8, textvariable=self.concurrent_var, width=6
        ).pack(side=LEFT, padx=(10, 0))

        self.save_thumbnails_var = tk.BooleanVar(value=self.config.get("save_thumbnails", False))
        ttk.Checkbutton(
            options_frame, text="Сохранять превью", variable=self.save_thumbnails_var
        ).pack(anchor=W)

        self.save_subtitles_var = tk.BooleanVar(value=self.config.get("save_subtitles", False))
        ttk.Checkbutton(
            options_frame, text="Сохранять субтитры", variable=self.save_subtitles_var
        ).pack(anchor=W)

        self.show_popups_var = tk.BooleanVar(value=self.config.get("show_success_popups", False))
        ttk.Checkbutton(
            options_frame,
            text="Показывать всплывающие окна об успешных действиях",
            variable=self.show_popups_var,
        ).pack(anchor=W)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X, pady=(16, 0))

        ttk.Button(
            button_frame, text="Сохранить", command=self.save_settings, bootstyle="success"
        ).pack(side=RIGHT, padx=(10, 0))
        ttk.Button(
            button_frame,
            text="Отмена",
            command=self.window.destroy,
            bootstyle="outline-secondary",
        ).pack(side=RIGHT)

    def browse_path(self):
        path = filedialog.askdirectory(
            title="Выберите папку для скачивания", initialdir=self.path_var.get()
        )
        if path:
            self.path_var.set(path)

    def browse_ffmpeg(self):
        path = filedialog.askdirectory(
            title="Выберите папку с ffmpeg", initialdir=self.ffmpeg_var.get() or None
        )
        if path:
            self.ffmpeg_var.set(path)

    def save_settings(self):
        """Сохраняет настройки"""
        try:
            self.config.set_download_path(self.path_var.get())

            try:
                concurrent = max(1, min(8, int(self.concurrent_var.get())))
            except (TypeError, ValueError):
                concurrent = 2

            self.config.update(
                {
                    "default_quality": self.quality_var.get(),
                    "max_concurrent_downloads": concurrent,
                    "save_thumbnails": bool(self.save_thumbnails_var.get()),
                    "save_subtitles": bool(self.save_subtitles_var.get()),
                    "show_success_popups": bool(self.show_popups_var.get()),
                    "ffmpeg_location": self.ffmpeg_var.get().strip() or None,
                },
                save=True,
            )

            if self.config.get("show_success_popups", False):
                messagebox.showinfo("Успешно", "Настройки сохранены")
            self.window.destroy()
        except Exception as error:
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки: {error}")
