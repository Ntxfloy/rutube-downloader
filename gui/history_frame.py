"""
Фрейм для отображения истории скачиваний
"""

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame
from datetime import datetime

from core.utils import HistoryManager


class HistoryFrame:
    """Фрейм для отображения истории скачиваний"""
    
    def __init__(self, parent, config):
        self.parent = parent
        self.config = config
        self.history_manager = HistoryManager()
        
        # Создаем фрейм
        self.frame = ttk.Frame(parent)
        self._create_widgets()
        
        # Загружаем историю
        self.refresh_history()
    
    def _create_widgets(self):
        """Создает виджеты фрейма"""
        # Главный контейнер
        main_container = ttk.Frame(self.frame)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # Заголовок
        title_label = ttk.Label(
            main_container,
            text="История скачиваний",
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # Статистика
        self.stats_frame = ttk.LabelFrame(main_container, text="Статистика", padding=10)
        self.stats_frame.pack(fill=X, pady=(0, 15))
        
        self.stats_label = ttk.Label(
            self.stats_frame,
            text="Загрузка статистики...",
            font=("Helvetica", 10)
        )
        self.stats_label.pack()
        
        # Панель управления
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=X, pady=(0, 15))
        
        refresh_btn = ttk.Button(
            control_frame,
            text="Обновить",
            command=self.refresh_history,
            bootstyle="outline-primary"
        )
        refresh_btn.pack(side=LEFT)
        
        clear_btn = ttk.Button(
            control_frame,
            text="Очистить историю",
            command=self.clear_history,
            bootstyle="outline-warning"
        )
        clear_btn.pack(side=LEFT, padx=(10, 0))
        
        # Поиск
        search_frame = ttk.Frame(control_frame)
        search_frame.pack(side=RIGHT)
        
        ttk.Label(search_frame, text="Поиск:").pack(side=LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search_change)
        search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=20
        )
        search_entry.pack(side=LEFT, padx=(5, 0))
        
        # Таблица истории
        history_frame = ttk.LabelFrame(main_container, text="Записи истории", padding=10)
        history_frame.pack(fill=BOTH, expand=True)
        
        # Создаем Treeview для истории
        columns = ("Дата", "Название", "Тип", "Серии", "Качество", "Статус")
        self.history_tree = ttk.Treeview(
            history_frame,
            columns=columns,
            show="headings",
            height=15
        )
        
        # Настраиваем колонки
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=100, minwidth=80)
        
        # Настраиваем ширину колонок
        self.history_tree.column("Дата", width=120)
        self.history_tree.column("Название", width=200)
        self.history_tree.column("Тип", width=80)
        self.history_tree.column("Серии", width=80)
        self.history_tree.column("Качество", width=80)
        self.history_tree.column("Статус", width=80)
        
        # Скроллбары
        v_scrollbar = ttk.Scrollbar(history_frame, orient=VERTICAL, command=self.history_tree.yview)
        h_scrollbar = ttk.Scrollbar(history_frame, orient=HORIZONTAL, command=self.history_tree.xview)
        
        self.history_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Размещаем элементы
        self.history_tree.pack(side=LEFT, fill=BOTH, expand=True)
        v_scrollbar.pack(side=RIGHT, fill=Y)
        h_scrollbar.pack(side=BOTTOM, fill=X)
        
        # Привязываем события
        self.history_tree.bind("<Double-1>", self._on_item_double_click)
        self.history_tree.bind("<Button-3>", self._on_right_click)
        
        # Контекстное меню
        self.context_menu = tk.Menu(self.frame, tearoff=0)
        self.context_menu.add_command(label="Повторить скачивание", command=self.repeat_download)
        self.context_menu.add_command(label="Копировать ссылку", command=self.copy_url)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Удалить запись", command=self.remove_entry)
    
    def refresh_history(self):
        """Обновляет историю"""
        try:
            # Очищаем таблицу
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            # Получаем историю
            history = self.history_manager.get_history()
            
            # Добавляем записи в таблицу
            for entry in history:
                # Форматируем дату
                try:
                    date_obj = datetime.fromisoformat(entry.get("downloaded_at", ""))
                    formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
                except:
                    formatted_date = "Неизвестно"
                
                # Форматируем серии
                start_ep = entry.get("start_episode", 1)
                end_ep = entry.get("end_episode", 1)
                if start_ep == end_ep:
                    episodes_str = str(start_ep)
                else:
                    episodes_str = f"{start_ep}-{end_ep}"
                
                # Добавляем в таблицу
                self.history_tree.insert("", "end", values=(
                    formatted_date,
                    entry.get("title", "Неизвестно"),
                    entry.get("type", "unknown"),
                    episodes_str,
                    entry.get("quality", "best"),
                    entry.get("status", "completed")
                ), tags=(entry.get("url", ""),))  # Сохраняем URL в тегах
            
            # Обновляем статистику
            self._update_stats()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить историю: {str(e)}")
    
    def _update_stats(self):
        """Обновляет статистику"""
        try:
            stats = self.history_manager.get_download_stats()
            total_downloads = stats.get("total_downloads", 0)
            total_episodes = stats.get("total_episodes", 0)
            
            stats_text = f"Всего скачиваний: {total_downloads} | Всего серий: {total_episodes}"
            self.stats_label.config(text=stats_text)
            
        except Exception as e:
            self.stats_label.config(text=f"Ошибка загрузки статистики: {str(e)}")
    
    def _on_search_change(self, *args):
        """Обработчик изменения поискового запроса"""
        search_term = self.search_var.get().lower()
        
        # Показываем/скрываем элементы в зависимости от поиска
        for item in self.history_tree.get_children():
            values = self.history_tree.item(item, "values")
            title = values[1].lower() if len(values) > 1 else ""
            
            if search_term in title:
                self.history_tree.reattach(item, "", "end")
            else:
                self.history_tree.detach(item)
    
    def _on_item_double_click(self, event):
        """Обработчик двойного клика по элементу"""
        selection = self.history_tree.selection()
        if selection:
            self.repeat_download()
    
    def _on_right_click(self, event):
        """Обработчик правого клика"""
        selection = self.history_tree.selection()
        if selection:
            # Показываем контекстное меню
            self.context_menu.post(event.x_root, event.y_root)
    
    def repeat_download(self):
        """Повторяет скачивание выбранной записи"""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите запись для повторного скачивания")
            return
        
        try:
            # Получаем URL из тегов
            item = selection[0]
            url = self.history_tree.item(item, "tags")[0]
            
            if not url:
                messagebox.showerror("Ошибка", "Не удалось получить ссылку")
                return
            
            # Переключаемся на вкладку скачивания
            notebook = self.parent
            notebook.select(0)  # Первая вкладка - скачивание
            
            # Вставляем URL в поле ввода
            download_frame = notebook.children[notebook.tabs()[0]]
            if hasattr(download_frame, 'url_var'):
                download_frame.url_var.set(url)
                # Автоматически запускаем анализ
                download_frame.analyze_url()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось повторить скачивание: {str(e)}")
    
    def copy_url(self):
        """Копирует ссылку в буфер обмена"""
        selection = self.history_tree.selection()
        if not selection:
            return
        
        try:
            item = selection[0]
            url = self.history_tree.item(item, "tags")[0]
            
            if url:
                self.frame.clipboard_clear()
                self.frame.clipboard_append(url)
                messagebox.showinfo("Успех", "Ссылка скопирована в буфер обмена")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось скопировать ссылку: {str(e)}")
    
    def remove_entry(self):
        """Удаляет выбранную запись"""
        selection = self.history_tree.selection()
        if not selection:
            return
        
        try:
            item = selection[0]
            index = self.history_tree.index(item)
            
            # Подтверждение удаления
            result = messagebox.askyesno(
                "Подтверждение",
                "Вы уверены, что хотите удалить эту запись из истории?"
            )
            
            if result:
                self.history_manager.remove_entry(index)
                self.refresh_history()
                messagebox.showinfo("Успех", "Запись удалена из истории")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось удалить запись: {str(e)}")
    
    def clear_history(self):
        """Очищает всю историю"""
        try:
            result = messagebox.askyesno(
                "Подтверждение",
                "Вы уверены, что хотите очистить всю историю? Это действие нельзя отменить."
            )
            
            if result:
                self.history_manager.clear_history()
                self.refresh_history()
                messagebox.showinfo("Успех", "История очищена")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось очистить историю: {str(e)}")
