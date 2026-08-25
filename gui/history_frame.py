"""
Фрейм для отображения истории скачиваний
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from core.utils import HistoryManager

from .ui_compat import label_frame

STATUS_LABELS = {
    "queued": "В очереди",
    "in_progress": "Скачивается",
    "completed": "Готово",
    "stopped": "Остановлено",
    "error": "Ошибка",
}


class HistoryFrame:
    """Фрейм для отображения истории скачиваний"""

    def __init__(self, parent, config, history_manager=None, main_window=None):
        self.parent = parent
        self.config = config
        self.main_window = main_window
        self.history_manager = history_manager or HistoryManager()

        self._entries = []
        self._row_urls = {}

        self.frame = ttk.Frame(parent)
        self._create_widgets()
        self.refresh_history()

    # ------------------------------------------------------------------ UI
    def _create_widgets(self):
        """Создает виджеты фрейма"""
        main_container = ttk.Frame(self.frame)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)

        ttk.Label(
            main_container,
            text="История скачиваний",
            font=("Helvetica", 16, "bold"),
            anchor=W,
        ).pack(fill=X, pady=(0, 12))

        self.stats_frame = label_frame(main_container, "Статистика", 10)
        self.stats_frame.pack(fill=X, pady=(0, 12))

        self.stats_label = ttk.Label(
            self.stats_frame, text="Загрузка статистики…", font=("Helvetica", 10), anchor=W
        )
        self.stats_label.pack(fill=X)

        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=X, pady=(0, 12))

        ttk.Button(
            control_frame,
            text="Обновить",
            command=self.refresh_history,
            bootstyle="outline-primary",
        ).pack(side=LEFT)

        ttk.Button(
            control_frame,
            text="Повторить",
            command=self.repeat_download,
            bootstyle="outline-success",
        ).pack(side=LEFT, padx=(10, 0))

        ttk.Button(
            control_frame,
            text="Очистить историю",
            command=self.clear_history,
            bootstyle="outline-warning",
        ).pack(side=LEFT, padx=(10, 0))

        search_frame = ttk.Frame(control_frame)
        search_frame.pack(side=RIGHT)

        ttk.Label(search_frame, text="Поиск:").pack(side=LEFT)

        self.search_var = tk.StringVar()
        # trace("w", ...) устарел, используем современный API
        self.search_var.trace_add("write", self._on_search_change)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=24)
        search_entry.pack(side=LEFT, padx=(5, 0))

        history_frame = label_frame(main_container, "Записи истории", 10)
        history_frame.pack(fill=BOTH, expand=True)

        columns = ("date", "title", "type", "episodes", "quality", "status")
        headings = {
            "date": "Дата",
            "title": "Название",
            "type": "Тип",
            "episodes": "Серии",
            "quality": "Качество",
            "status": "Статус",
        }
        widths = {
            "date": 130,
            "title": 320,
            "type": 90,
            "episodes": 80,
            "quality": 90,
            "status": 110,
        }

        tree_container = ttk.Frame(history_frame)
        tree_container.pack(fill=BOTH, expand=True)

        self.history_tree = ttk.Treeview(
            tree_container, columns=columns, show="headings", height=15
        )
        for column in columns:
            self.history_tree.heading(column, text=headings[column])
            self.history_tree.column(column, width=widths[column], minwidth=70, stretch=(column == "title"))

        v_scrollbar = ttk.Scrollbar(tree_container, orient=VERTICAL, command=self.history_tree.yview)
        h_scrollbar = ttk.Scrollbar(history_frame, orient=HORIZONTAL, command=self.history_tree.xview)
        self.history_tree.configure(
            yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set
        )

        self.history_tree.pack(side=LEFT, fill=BOTH, expand=True)
        v_scrollbar.pack(side=RIGHT, fill=Y)
        h_scrollbar.pack(side=BOTTOM, fill=X)

        self.history_tree.bind("<Double-1>", self._on_item_double_click)
        self.history_tree.bind("<Button-3>", self._on_right_click)

        self.context_menu = tk.Menu(self.frame, tearoff=0)
        self.context_menu.add_command(label="Повторить скачивание", command=self.repeat_download)
        self.context_menu.add_command(label="Копировать ссылку", command=self.copy_url)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Удалить запись", command=self.remove_entry)

    # ---------------------------------------------------------------- data
    def refresh_history(self):
        """Обновляет историю из файла"""
        try:
            self._entries = self.history_manager.get_history()
            self._populate_tree()
            self._update_stats()
        except Exception as error:
            messagebox.showerror("Ошибка", f"Не удалось загрузить историю: {error}")

    @staticmethod
    def _format_date(value):
        try:
            return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")
        except (TypeError, ValueError):
            return "Неизвестно"

    @staticmethod
    def _format_episodes(entry):
        start = entry.get("start_episode", 1)
        end = entry.get("end_episode", start)
        return str(start) if start == end else f"{start}-{end}"

    def _populate_tree(self):
        """Заполняет таблицу с учётом поискового запроса.

        Раньше поиск делал detach/reattach, из-за чего строки теряли порядок
        и удаление по индексу било мимо.
        """
        search_term = (self.search_var.get() if hasattr(self, "search_var") else "").strip().lower()

        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        self._row_urls.clear()

        for index, entry in enumerate(self._entries):
            title = str(entry.get("title", "Неизвестно"))
            url = str(entry.get("url", ""))
            if search_term and search_term not in title.lower() and search_term not in url.lower():
                continue

            row_id = entry.get("id") or f"row-{index}"
            status = entry.get("status", "completed")
            self.history_tree.insert(
                "",
                "end",
                iid=row_id,
                values=(
                    self._format_date(entry.get("downloaded_at", "")),
                    title,
                    entry.get("type", "unknown"),
                    self._format_episodes(entry),
                    entry.get("quality", "best"),
                    STATUS_LABELS.get(status, status),
                ),
            )
            self._row_urls[row_id] = url

    def _update_stats(self):
        """Обновляет статистику"""
        try:
            stats = self.history_manager.get_download_stats()
            self.stats_label.config(
                text=(
                    f"Всего скачиваний: {stats.get('total_downloads', 0)}  |  "
                    f"Всего серий: {stats.get('total_episodes', 0)}"
                )
            )
        except Exception as error:
            self.stats_label.config(text=f"Ошибка загрузки статистики: {error}")

    def _on_search_change(self, *args):
        """Обработчик изменения поискового запроса"""
        self._populate_tree()

    # -------------------------------------------------------------- actions
    def _selected_url(self):
        selection = self.history_tree.selection()
        if not selection:
            return None
        return self._row_urls.get(selection[0])

    def _on_item_double_click(self, event):
        if self.history_tree.selection():
            self.repeat_download()

    def _on_right_click(self, event):
        row_id = self.history_tree.identify_row(event.y)
        if row_id:
            self.history_tree.selection_set(row_id)
            self.context_menu.tk_popup(event.x_root, event.y_root)
            self.context_menu.grab_release()

    def repeat_download(self):
        """Повторяет скачивание выбранной записи.

        Было: download_frame = notebook.children[notebook.tabs()[0]] — возвращался виджет,
        а не объект DownloadFrame, поэтому повтор скачивания не работал вообще.
        """
        url = self._selected_url()
        if url is None:
            messagebox.showwarning("Предупреждение", "Выберите запись для повторного скачивания")
            return
        if not url:
            messagebox.showerror("Ошибка", "В записи нет ссылки")
            return

        if self.main_window is not None and hasattr(self.main_window, "load_url_for_download"):
            self.main_window.load_url_for_download(url)
            return

        messagebox.showinfo(
            "Ссылка скопирована",
            "Откройте вкладку «Скачивание» и вставьте ссылку (Ctrl+V)",
        )
        self._copy_to_clipboard(url)

    def _copy_to_clipboard(self, text):
        try:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(text)
        except tk.TclError as error:
            print(f"Не удалось скопировать ссылку: {error}")

    def copy_url(self):
        """Копирует ссылку в буфер обмена"""
        url = self._selected_url()
        if not url:
            return
        self._copy_to_clipboard(url)
        if self.config.get("show_success_popups", False):
            messagebox.showinfo("Успешно", "Ссылка скопирована в буфер обмена")

    def remove_entry(self):
        """Удаляет выбранную запись"""
        selection = self.history_tree.selection()
        if not selection:
            return

        if not messagebox.askyesno(
            "Подтверждение", "Удалить эту запись из истории?"
        ):
            return

        try:
            self.history_manager.remove_by_id(selection[0])
            self.refresh_history()
        except Exception as error:
            messagebox.showerror("Ошибка", f"Не удалось удалить запись: {error}")

    def clear_history(self):
        """Очищает всю историю"""
        if not messagebox.askyesno(
            "Подтверждение",
            "Очистить всю историю? Действие нельзя отменить.",
        ):
            return
        try:
            self.history_manager.clear_history()
            self.refresh_history()
        except Exception as error:
            messagebox.showerror("Ошибка", f"Не удалось очистить историю: {error}")
