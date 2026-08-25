"""
Фрейм для скачивания видео
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from core.downloader import RutubeDownloader
from core.parser import RutubeParser
from core.utils import (
    FileManager,
    HistoryManager,
    ValidationUtils,
    format_bytes,
    format_duration,
    format_speed,
)

from .ui_compat import label_frame, scrolled_frame

# Коды клавиш (Windows VK и X11 keycode) — нужны, чтобы Ctrl+V работал
# при любой раскладке клавиатуры: при русской раскладке Tk присылает
# keysym вида "Cyrillic_em", и бинд <Control-v> просто не срабатывает.
PASTE_KEYCODES = {86, 55}
COPY_KEYCODES = {67, 54}
CUT_KEYCODES = {88, 53}
SELECT_ALL_KEYCODES = {65, 38}


class DownloadFrame:
    """Фрейм для скачивания видео"""

    def __init__(self, parent, config, history_manager=None, status_callback=None):
        self.parent = parent
        self.config = config
        self.status_callback = status_callback
        self.parser = RutubeParser()
        self.downloader = RutubeDownloader(
            download_path=config.get_download_path(),
            ffmpeg_location=config.get("ffmpeg_location", None),
            max_concurrent_downloads=config.get("max_concurrent_downloads", 2),
        )
        self.history_manager = history_manager or HistoryManager()

        # Переменные состояния
        self.content_info = None
        self.is_analyzing = False
        self.is_downloading = False
        self._indeterminate = False
        self._current_history_id = None

        self.frame = ttk.Frame(parent)
        self._create_widgets()

        # Устанавливаем callback для прогресса
        self.downloader.set_progress_callback(self._on_download_progress)

    # ------------------------------------------------------------------ UI
    def _create_widgets(self):
        """Создает виджеты фрейма"""
        # scrolled_frame() вместо прямого ScrolledFrame: в ttkbootstrap 2.x модуля
        # ttkbootstrap.scrolled больше нет, а ещё здесь включается ускоренное
        # колёсико мыши (в 1.7 раза быстрее штатного).
        self.scrolled = scrolled_frame(self.frame, autohide=True)
        self.scrolled.pack(fill=BOTH, expand=True)
        main_container = self.scrolled

        # --- Секция ввода URL -------------------------------------------
        # LabelFrame создаём через label_frame(): внутри ScrolledFrame опция
        # padding в части версий ttkbootstrap даёт TclError и окно не открывается.
        url_frame = label_frame(main_container, "Ссылка на видео или плейлист", 15)
        url_frame.pack(fill=X, padx=5, pady=(5, 15))

        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(
            url_frame,
            textvariable=self.url_var,
            font=("Helvetica", 12),
        )
        self.url_entry.pack(fill=X, pady=(0, 10))
        self.url_entry.bind("<Return>", lambda event: self.analyze_url())

        self._bind_clipboard_shortcuts(self.url_entry)

        # Контекстное меню
        self.context_menu = tk.Menu(self.url_entry, tearoff=0)
        self.context_menu.add_command(label="Вставить", command=self._paste_from_clipboard)
        self.context_menu.add_command(label="Вставить и анализировать", command=self._paste_and_analyze)
        self.context_menu.add_command(label="Копировать", command=self._copy_to_clipboard)
        self.context_menu.add_command(label="Вырезать", command=self._cut_to_clipboard)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Выделить всщ1", command=self._select_all)
        self.context_menu.add_command(label="Очистить", command=self.clear_url)

        button_frame = ttk.Frame(url_frame)
        button_frame.pack(fill=X)

        self.analyze_btn = ttk.Button(
            button_frame,
            text="Анализировать",
            command=self.analyze_url,
            bootstyle="primary",
        )
        self.analyze_btn.pack(side=LEFT, padx=(0, 10))

        self.paste_btn = ttk.Button(
            button_frame,
            text="Вставить",
            command=self._paste_from_clipboard,
            bootstyle="outline-primary",
        )
        self.paste_btn.pack(side=LEFT, padx=(0, 10))

        self.clear_btn = ttk.Button(
            button_frame,
            text="Очистить",
            command=self.clear_url,
            bootstyle="outline-secondary",
        )
        self.clear_btn.pack(side=LEFT)

        # --- Информация о контенте -----------------------------------
        self.info_frame = label_frame(main_container, "Информация о контенте", 15)
        self.info_frame.pack(fill=X, padx=5, pady=(0, 15))

        self.title_label = ttk.Label(
            self.info_frame,
            text="Вставьте ссылку (Ctrl+V) и нажмите 'Анализировать'",
            font=("Helvetica", 11, "bold"),
            wraplength=760,
            justify=LEFT,
            anchor=W,
        )
        self.title_label.pack(fill=X, pady=(0, 8))

        self.description_label = ttk.Label(
            self.info_frame,
            text="",
            wraplength=760,
            justify=LEFT,
            anchor=W,
        )
        self.description_label.pack(fill=X, pady=(0, 8))

        self.details_label = ttk.Label(
            self.info_frame,
            text="",
            wraplength=760,
            justify=LEFT,
            anchor=W,
            bootstyle="secondary",
        )
        self.details_label.pack(fill=X)

        # --- Настройки скачивания -------------------------------------
        self.settings_frame = label_frame(main_container, "Настройки скачивания", 15)
        self.settings_frame.pack(fill=X, padx=5, pady=(0, 15))

        quality_frame = ttk.Frame(self.settings_frame)
        quality_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(quality_frame, text="Качество:").pack(side=LEFT)

        self.quality_var = tk.StringVar(value=self.config.get("default_quality", "best"))
        self.quality_combo = ttk.Combobox(
            quality_frame,
            textvariable=self.quality_var,
            values=["best", "1080p", "720p", "480p", "360p", "240p", "worst"],
            state="readonly",
            width=15,
        )
        self.quality_combo.pack(side=LEFT, padx=(10, 0))

        self.playlist_frame = ttk.Frame(self.settings_frame)
        self.playlist_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(self.playlist_frame, text="Диапазон серий:").pack(side=LEFT)

        self.start_episode_var = tk.StringVar(value="1")
        ttk.Spinbox(
            self.playlist_frame,
            from_=1,
            to=9999,
            textvariable=self.start_episode_var,
            width=8,
        ).pack(side=LEFT, padx=(10, 5))

        ttk.Label(self.playlist_frame, text="до").pack(side=LEFT, padx=(5, 5))

        self.end_episode_var = tk.StringVar(value="1")
        ttk.Spinbox(
            self.playlist_frame,
            from_=1,
            to=9999,
            textvariable=self.end_episode_var,
            width=8,
        ).pack(side=LEFT, padx=(5, 0))

        ttk.Label(
            self.playlist_frame,
            text="(например: с 1 по 12)",
            font=("Helvetica", 9),
            bootstyle="secondary",
        ).pack(side=LEFT, padx=(10, 0))

        self.playlist_frame.pack_forget()

        path_frame = ttk.Frame(self.settings_frame)
        path_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(path_frame, text="Папка:").pack(side=LEFT)

        self.path_var = tk.StringVar(value=self.config.get_download_path())
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var)
        path_entry.pack(side=LEFT, fill=X, expand=True, padx=(10, 10))
        self._bind_clipboard_shortcuts(path_entry)

        ttk.Button(
            path_frame,
            text="Обзор",
            command=self.browse_path,
            bootstyle="outline-secondary",
        ).pack(side=LEFT)

        ttk.Button(
            path_frame,
            text="Открыть папку",
            command=self.open_download_folder,
            bootstyle="outline-secondary",
        ).pack(side=LEFT, padx=(10, 0))

        self.download_btn = ttk.Button(
            self.settings_frame,
            text="Скачать",
            command=self.start_download,
            bootstyle="success",
            state=DISABLED,
        )
        self.download_btn.pack(pady=(10, 0))

        # --- Прогресс -----------------------------------------------------
        self.progress_frame = label_frame(main_container, "Прогресс скачивания", 15)
        self.progress_frame.pack(fill=X, padx=5, pady=(0, 15))
        self.progress_frame.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100,
            bootstyle="success-striped",
        )
        self.progress_bar.grid(row=0, column=0, sticky=EW, pady=(0, 6))

        self.percent_label = ttk.Label(
            self.progress_frame,
            text="0.0%",
            font=("Helvetica", 14, "bold"),
            width=8,
            anchor=E,
        )
        self.percent_label.grid(row=0, column=1, sticky=E, padx=(12, 0), pady=(0, 6))

        self.speed_label = ttk.Label(
            self.progress_frame,
            text="Скорость: —   Осталось: —",
            font=("Helvetica", 9),
            bootstyle="secondary",
            anchor=W,
        )
        self.speed_label.grid(row=1, column=0, columnspan=2, sticky=EW, pady=(0, 10))

        self.overall_var = tk.DoubleVar(value=0.0)
        self.overall_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.overall_var,
            maximum=100,
            bootstyle="info",
        )
        self.overall_bar.grid(row=2, column=0, sticky=EW, pady=(0, 6))

        self.overall_label = ttk.Label(
            self.progress_frame,
            text="0.0%",
            font=("Helvetica", 10),
            width=8,
            anchor=E,
        )
        self.overall_label.grid(row=2, column=1, sticky=E, padx=(12, 0), pady=(0, 6))

        self.queue_label = ttk.Label(
            self.progress_frame,
            text="Общий прогресс очереди",
            font=("Helvetica", 9),
            bootstyle="secondary",
            anchor=W,
        )
        self.queue_label.grid(row=3, column=0, columnspan=2, sticky=EW, pady=(0, 10))

        self.status_label = ttk.Label(
            self.progress_frame,
            text="Готов к скачиванию",
            font=("Helvetica", 10),
            wraplength=760,
            justify=LEFT,
            anchor=W,
        )
        self.status_label.grid(row=4, column=0, columnspan=2, sticky=EW)

        self.progress_frame.pack_forget()

        # --- Управление -------------------------------------------------
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=X, padx=5, pady=(0, 10))

        self.stop_btn = ttk.Button(
            control_frame,
            text="Остановить",
            command=self.stop_download,
            bootstyle="danger",
            state=DISABLED,
        )
        # Было control_frame.pack(side=LEFT) — из-за этого кнопки вообще не было видно.
        self.stop_btn.pack(side=LEFT)

        self.clear_queue_btn = ttk.Button(
            control_frame,
            text="Очистить очередь",
            command=self.clear_queue,
            bootstyle="outline-warning",
            state=DISABLED,
        )
        self.clear_queue_btn.pack(side=LEFT, padx=(10, 0))

    # ------------------------------------------------------------- clipboard
    def _bind_clipboard_shortcuts(self, widget):
        """Навешивает работающие горячие клавиши буфера обмена."""
        widget.bind("<Button-3>", self._show_context_menu)
        widget.bind("<Control-KeyPress>", lambda event: self._on_control_key(event, widget))
        widget.bind("<Command-KeyPress>", lambda event: self._on_control_key(event, widget))
        widget.bind("<Shift-Insert>", lambda event: self._paste_from_clipboard(event, widget))
        widget.bind("<Control-Insert>", lambda event: self._copy_to_clipboard(event, widget))

    def _on_control_key(self, event, widget=None):
        """Обрабатывает Ctrl+V/C/X/A независимо от раскладки клавиатуры.

        При русской раскладке keysym равен "Cyrillic_em", поэтому проверяем
        ещё и keycode — именно из-за этого Ctrl+V раньше не работал.
        """
        widget = widget or event.widget
        keysym = (getattr(event, "keysym", "") or "").lower()
        keycode = getattr(event, "keycode", None)

        if keysym == "v" or keycode in PASTE_KEYCODES:
            return self._paste_from_clipboard(event, widget)
        if keysym == "c" or keycode in COPY_KEYCODES:
            return self._copy_to_clipboard(event, widget)
        if keysym == "x" or keycode in CUT_KEYCODES:
            return self._cut_to_clipboard(event, widget)
        if keysym == "a" or keycode in SELECT_ALL_KEYCODES:
            return self._select_all(event, widget)
        return None

    def _get_clipboard_text(self):
        """Читает текст из буфера обмена."""
        try:
            return self.url_entry.clipboard_get()
        except tk.TclError:
            pass
        try:
            return self.frame.selection_get(selection="CLIPBOARD")
        except tk.TclError:
            return ""

    def _target_entry(self, widget=None):
        if widget is None:
            widget = self.url_entry
        if not hasattr(widget, "insert"):
            widget = self.url_entry
        return widget

    def _paste_from_clipboard(self, event=None, widget=None):
        """Вставляет текст из буфера обмена в позицию курсора."""
        entry = self._target_entry(widget or (event.widget if event else None))
        text = self._get_clipboard_text()
        if not text:
            return "break"

        # Ссылки часто копируются с переводом строки и пробелами
        text = " ".join(str(text).split())

        try:
            if entry.selection_present():
                entry.delete("sel.first", "sel.last")
        except (tk.TclError, AttributeError):
            pass

        try:
            entry.insert(tk.INSERT, text)
            entry.icursor(tk.END)
            entry.focus_set()
        except tk.TclError as error:
            print(f"Ошибка при вставке: {error}")
        return "break"

    def _paste_and_analyze(self):
        """Вставляет ссылку из буфера и сразу анализирует её."""
        text = self._get_clipboard_text()
        if not text:
            return
        self.url_var.set(" ".join(str(text).split()))
        self.analyze_url()

    def _copy_to_clipboard(self, event=None, widget=None):
        """Копирует выделение (или всё поле) в буфер обмена."""
        entry = self._target_entry(widget or (event.widget if event else None))
        try:
            if entry.selection_present():
                text = entry.selection_get()
            else:
                text = entry.get()
            if not text:
                return "break"
            entry.clipboard_clear()
            entry.clipboard_append(text)
        except tk.TclError as error:
            print(f"Ошибка при копировании: {error}")
        return "break"

    def _cut_to_clipboard(self, event=None, widget=None):
        """Вырезает выделение (или всё поле) в буфер обмена."""
        entry = self._target_entry(widget or (event.widget if event else None))
        self._copy_to_clipboard(event, entry)
        try:
            if entry.selection_present():
                entry.delete("sel.first", "sel.last")
            else:
                entry.delete(0, tk.END)
        except tk.TclError as error:
            print(f"Ошибка при вырезании: {error}")
        return "break"

    def _select_all(self, event=None, widget=None):
        """Выделяет весь текст в поле."""
        entry = self._target_entry(widget or (event.widget if event else None))
        try:
            entry.select_range(0, tk.END)
            entry.icursor(tk.END)
        except tk.TclError:
            pass
        return "break"

    def _show_context_menu(self, event):
        """Показывает контекстное меню"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
        return "break"

    # --------------------------------------------------------------- analyze
    def load_url(self, url, analyze=True):
        """Подставляет ссылку извне (например, из истории)."""
        self.url_var.set(ValidationUtils.normalize_url(url))
        if analyze:
            self.analyze_url()

    def analyze_url(self):
        """Анализирует URL"""
        if self.is_analyzing:
            return

        url = ValidationUtils.normalize_url(self.url_var.get())
        if not url:
            messagebox.showwarning("Предупреждение", "Введите ссылку для анализа")
            return

        if not ValidationUtils.is_valid_url(url):
            messagebox.showerror("Ошибка", "Неверная ссылка. Убедитесь, что ссылка ведет на Rutube")
            return

        self.url_var.set(url)
        self.is_analyzing = True
        self.analyze_btn.config(state=DISABLED, text="Анализирую…")
        self.status_label.config(text="Анализирую ссылку…")
        self._set_app_status("Анализирую ссылку…")

        thread = threading.Thread(target=self._analyze_url_worker, args=(url,), daemon=True)
        thread.start()

    def _analyze_url_worker(self, url):
        """Рабочий поток для анализа URL"""
        try:
            info = self.parser.parse_url(url)
            self._run_in_ui(lambda: self._apply_content_info(info))
        except Exception as error:
            message = str(error)
            self._run_in_ui(lambda: self._show_error(f"Ошибка при анализе: {message}"))
        finally:
            self._run_in_ui(self._finish_analysis)

    def _apply_content_info(self, info):
        """Обновляет информацию о контенте"""
        self.content_info = info

        if not isinstance(info, dict) or "error" in info:
            error_text = info.get("error") if isinstance(info, dict) else "Неизвестная ошибка"
            self.content_info = None
            self._show_error(error_text or "Неизвестная ошибка")
            return

        self.title_label.config(text=info.get("title", "Неизвестно"))
        description = (info.get("description") or "").strip()
        self.description_label.config(text=description or "Описание недоступно")

        episodes = int(info.get("episodes", 1) or 1)
        if info.get("type") == "playlist":
            details = f"Тип: Плейлист  |  Серий: {episodes}"
            self.start_episode_var.set("1")
            self.end_episode_var.set(str(episodes))
            if not self.playlist_frame.winfo_ismapped():
                self.playlist_frame.pack(fill=X, pady=(0, 10), after=self.quality_combo.master)
        else:
            details = f"Тип: Видео  |  Длительность: {info.get('duration', 'Неизвестно')}"
            self.playlist_frame.pack_forget()

        self.details_label.config(text=details)
        self.download_btn.config(state=DISABLED if self.is_downloading else NORMAL)

        # Секцию настроек перепаковываем только если она скрыта,
        # иначе она каждый раз прыгала в конец окна.
        self._show_section(self.settings_frame, after=self.info_frame)

    # Обратная совместимость
    def _update_content_info(self):
        self._apply_content_info(self.content_info)

    def _show_error(self, message):
        """Показывает ошибку"""
        messagebox.showerror("Ошибка", str(message))
        self.title_label.config(text="Ошибка при анализе")
        self.description_label.config(text=str(message))
        self.details_label.config(text="")
        self.download_btn.config(state=DISABLED)

    def _finish_analysis(self):
        """Завершает анализ"""
        self.is_analyzing = False
        self.analyze_btn.config(state=NORMAL, text="Анализировать")
        if not self.is_downloading:
            self.status_label.config(text="Готов к скачиванию")
            self._set_app_status("Готов")

    def clear_url(self):
        """Очищает поле URL"""
        self.url_var.set("")
        self.content_info = None
        self.title_label.config(text="Вставьте ссылку (Ctrl+V) и нажмите 'Анализировать'")
        self.description_label.config(text="")
        self.details_label.config(text="")
        self.download_btn.config(state=DISABLED)
        self.playlist_frame.pack_forget()
        self.start_episode_var.set("1")
        self.end_episode_var.set("1")
        self.url_entry.focus_set()

    def browse_path(self):
        """Открывает диалог выбора папки"""
        path = filedialog.askdirectory(
            title="Выберите папку для скачивания",
            initialdir=self.path_var.get(),
        )
        if not path:
            return
        try:
            self.downloader.set_download_path(path)
            self.path_var.set(path)
            self.config.set("download_path", path)
        except ValueError as error:
            messagebox.showerror("Ошибка", str(error))

    def open_download_folder(self):
        """Открывает папку скачивания в файловом менеджере"""
        if not FileManager.open_in_explorer(self.path_var.get()):
            messagebox.showerror("Ошибка", "Не удалось открыть папку")

    # -------------------------------------------------------------- download
    def start_download(self):
        """Начинает скачивание"""
        if not self.content_info:
            messagebox.showerror("Ошибка", "Сначала проанализируйте ссылку")
            return

        quality = self.quality_var.get()
        if not ValidationUtils.is_valid_quality(quality):
            messagebox.showerror("Ошибка", "Неверное качество видео")
            return

        download_path = self.path_var.get().strip()
        if download_path:
            try:
                self.downloader.set_download_path(download_path)
                self.config.set("download_path", download_path)
            except ValueError as error:
                messagebox.showerror("Ошибка", str(error))
                return

        start_episode = 1
        end_episode = 1
        max_episodes = int(self.content_info.get("episodes", 1) or 1)

        if self.content_info.get("type") == "playlist":
            try:
                start_episode = int(self.start_episode_var.get())
                end_episode = int(self.end_episode_var.get())
            except ValueError:
                messagebox.showerror("Ошибка", "Неверный формат номера серии")
                return

            if start_episode > end_episode:
                messagebox.showerror("Ошибка", "Начальная серия не может быть больше конечной")
                return
            if end_episode > max_episodes:
                messagebox.showerror(
                    "Ошибка",
                    f"В плейлисте только {max_episodes} серий",
                )
                return
            if not ValidationUtils.is_valid_episode_range(start_episode, end_episode, max_episodes):
                messagebox.showerror("Ошибка", "Неверный диапазон серий")
                return

        self.downloader.reset_progress()
        added = self.downloader.add_to_queue(
            self.url_var.get(),
            self.content_info,
            start_episode,
            end_episode,
            quality,
        )

        if not added:
            messagebox.showerror("Ошибка", "Не удалось добавить задачу в очередь")
            return

        self._current_history_id = self.history_manager.add_download(
            self.url_var.get(),
            self.content_info,
            start_episode,
            end_episode,
            quality,
            status="in_progress",
        )

        self.is_downloading = True
        self._reset_progress_ui()
        self._show_section(self.progress_frame, after=self.settings_frame)
        self.download_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.clear_queue_btn.config(state=NORMAL)
        self.status_label.config(text="Задача добавлена в очередь, начинаю скачивание…")
        self._set_app_status("Скачивание запущено")

        self.downloader.start_download()

        if self.config.get("show_success_popups", False):
            messagebox.showinfo("Успешно", "Задача добавлена в очередь скачивания")

    def stop_download(self):
        """Останавливает скачивание"""
        self.downloader.stop_download()
        self._finish_downloading("Скачивание остановлено", history_status="stopped")

    def clear_queue(self):
        """Очищает очередь скачивания"""
        self.downloader.clear_queue()
        self.status_label.config(text="Очередь очищена")
        self.clear_queue_btn.config(state=DISABLED)
        self._set_app_status("Очередь очищена")

    def stop_all_downloads(self):
        """Останавливает все скачивания (вызывается при закрытии окна)"""
        try:
            self.downloader.stop_download()
            self.parser.close()
        except Exception:
            pass

    # -------------------------------------------------------------- progress
    def _run_in_ui(self, function):
        """Выполняет функцию в главном потоке Tk."""
        try:
            self.frame.after(0, function)
        except (RuntimeError, tk.TclError):
            pass

    def _set_app_status(self, text):
        if self.status_callback:
            try:
                self.status_callback(text)
            except Exception:
                pass

    def _show_section(self, widget, after=None):
        if widget.winfo_ismapped():
            return
        try:
            if after is not None:
                widget.pack(fill=X, padx=5, pady=(0, 15), after=after)
            else:
                widget.pack(fill=X, padx=5, pady=(0, 15))
        except tk.TclError:
            widget.pack(fill=X, padx=5, pady=(0, 15))

    def _set_indeterminate(self, enabled):
        """Переключает бар в режим бегущей полосы, когда размер неизвестен."""
        if enabled == self._indeterminate:
            return
        try:
            if enabled:
                self.progress_bar.config(mode="indeterminate")
                self.progress_bar.start(15)
            else:
                self.progress_bar.stop()
                self.progress_bar.config(mode="determinate")
        except tk.TclError:
            return
        self._indeterminate = enabled

    def _reset_progress_ui(self):
        self._set_indeterminate(False)
        self.progress_var.set(0.0)
        self.overall_var.set(0.0)
        self.percent_label.config(text="0.0%")
        self.overall_label.config(text="0.0%")
        self.speed_label.config(text="Скорость: —   Осталось: —")
        self.queue_label.config(text="Общий прогресс очереди")

    def _on_download_progress(self, task, status, message, info=None):
        """Callback для прогресса скачивания (вызывается из рабочих потоков).

        Всё обновление интерфейса откладывается в главный поток Tk.
        """
        payload = dict(info or {})
        self._run_in_ui(lambda: self._apply_progress(status, message, payload))

    def _apply_progress(self, status, message, info):
        """Применяет событие прогресса к интерфейсу."""
        try:
            overall = info.get("overall_percent")
            if overall is not None:
                self.overall_var.set(float(overall))
                self.overall_label.config(text=f"{float(overall):.1f}%")

            total = info.get("total") or 0
            completed = info.get("completed") or 0
            failed = info.get("failed") or 0
            queue_text = f"Общий прогресс очереди: {completed}/{total}"
            if failed:
                queue_text += f"  (с ошибками: {failed})"
            self.queue_label.config(text=queue_text)

            if status in ("queued", "start"):
                self.status_label.config(text=message)
                if status == "start":
                    self.progress_var.set(0.0)
                    self.percent_label.config(text="0.0%")
                self._set_app_status(message)

            elif status == "progress":
                percent = info.get("percent")
                if percent is None:
                    self._set_indeterminate(True)
                    self.percent_label.config(text="…")
                else:
                    self._set_indeterminate(False)
                    percent = max(0.0, min(100.0, float(percent)))
                    self.progress_var.set(percent)
                    self.percent_label.config(text=f"{percent:.1f}%")

                speed_text = format_speed(info.get("speed"))
                eta = info.get("eta")
                eta_text = format_duration(eta) if eta else "—"
                downloaded = info.get("downloaded_bytes") or 0
                total_bytes = info.get("total_bytes") or 0
                size_text = ""
                if total_bytes:
                    size_text = f"   {format_bytes(downloaded)} / {format_bytes(total_bytes)}"
                elif downloaded:
                    size_text = f"   {format_bytes(downloaded)}"
                self.speed_label.config(
                    text=f"Скорость: {speed_text}   Осталось: {eta_text}{size_text}"
                )
                self.status_label.config(text=message)

            elif status == "complete":
                self._set_indeterminate(False)
                self.progress_var.set(100.0)
                self.percent_label.config(text="100.0%")
                self.status_label.config(text=message)
                self._set_app_status(message)

            elif status == "error":
                self._set_indeterminate(False)
                self.status_label.config(text=f"Ошибка: {message}")
                self._set_app_status("Ошибка скачивания")

            elif status == "all_done":
                self._finish_downloading(message, history_status="completed")

            elif status == "stopped":
                self._finish_downloading(message or "Скачивание остановлено", history_status="stopped")

        except tk.TclError:
            pass

    def _finish_downloading(self, message, history_status=None):
        """Возвращает интерфейс в состояние покоя после скачивания."""
        self.is_downloading = False
        self._set_indeterminate(False)
        self.status_label.config(text=message)
        self.stop_btn.config(state=DISABLED)
        self.clear_queue_btn.config(state=DISABLED)
        self.download_btn.config(state=NORMAL if self.content_info else DISABLED)
        self._set_app_status(message)

        if history_status and self._current_history_id:
            self.history_manager.update_status(self._current_history_id, history_status)
            self._current_history_id = None
