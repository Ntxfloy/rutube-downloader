"""
Фрейм для скачивания видео
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame
import threading

from core.parser import RutubeParser
from core.downloader import RutubeDownloader
from core.utils import ValidationUtils, HistoryManager


class DownloadFrame:
    """Фрейм для скачивания видео"""
    
    def __init__(self, parent, config):
        self.parent = parent
        self.config = config
        self.parser = RutubeParser()
        self.downloader = RutubeDownloader(config.get_download_path())
        self.history_manager = HistoryManager()
        
        # Переменные
        self.content_info = None
        self.is_analyzing = False
        
        # Создаем фрейм
        self.frame = ttk.Frame(parent)
        self._create_widgets()
        
        # Устанавливаем callback для прогресса
        self.downloader.set_progress_callback(self._on_download_progress)
    
    def _create_widgets(self):
        """Создает виджеты фрейма"""
        # Главный контейнер
        main_container = ttk.Frame(self.frame)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # Секция ввода URL
        url_frame = ttk.LabelFrame(main_container, text="Ссылка на видео или плейлист", padding=15)
        url_frame.pack(fill=X, pady=(0, 15))
        
        # Поле ввода URL
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(
            url_frame,
            textvariable=self.url_var,
            font=("Helvetica", 12),
            width=60
        )
        url_entry.pack(fill=X, pady=(0, 10))
        
        # Добавляем поддержку Ctrl+V и контекстного меню
        url_entry.bind('<Control-v>', self._paste_from_clipboard)
        url_entry.bind('<Button-3>', self._show_context_menu)
        
        # Создаем контекстное меню
        self.context_menu = tk.Menu(url_entry, tearoff=0)
        self.context_menu.add_command(label="Вставить", command=self._paste_from_clipboard)
        self.context_menu.add_command(label="Копировать", command=self._copy_to_clipboard)
        self.context_menu.add_command(label="Вырезать", command=self._cut_to_clipboard)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Очистить", command=self.clear_url)
        
        # Кнопки
        button_frame = ttk.Frame(url_frame)
        button_frame.pack(fill=X)
        
        self.analyze_btn = ttk.Button(
            button_frame,
            text="Анализировать",
            command=self.analyze_url,
            bootstyle="primary"
        )
        self.analyze_btn.pack(side=LEFT, padx=(0, 10))
        
        self.clear_btn = ttk.Button(
            button_frame,
            text="Очистить",
            command=self.clear_url,
            bootstyle="outline-secondary"
        )
        self.clear_btn.pack(side=LEFT)
        
        # Секция информации о контенте
        self.info_frame = ttk.LabelFrame(main_container, text="Информация о контенте", padding=15)
        self.info_frame.pack(fill=X, pady=(0, 15))
        
        # Заголовок
        self.title_label = ttk.Label(
            self.info_frame,
            text="Вставьте ссылку и нажмите 'Анализировать'",
            font=("Helvetica", 11),
            wraplength=600
        )
        self.title_label.pack(pady=(0, 10))
        
        # Описание
        self.description_label = ttk.Label(
            self.info_frame,
            text="",
            wraplength=600,
            justify=LEFT
        )
        self.description_label.pack(pady=(0, 10))
        
        # Дополнительная информация
        self.details_label = ttk.Label(
            self.info_frame,
            text="",
            wraplength=600
        )
        self.details_label.pack()
        
        # Секция настроек скачивания
        self.settings_frame = ttk.LabelFrame(main_container, text="Настройки скачивания", padding=15)
        self.settings_frame.pack(fill=X, pady=(0, 15))
        
        # Качество видео
        quality_frame = ttk.Frame(self.settings_frame)
        quality_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(quality_frame, text="Качество:").pack(side=LEFT)
        
        self.quality_var = tk.StringVar(value=self.config.get("default_quality", "best"))
        quality_combo = ttk.Combobox(
            quality_frame,
            textvariable=self.quality_var,
            values=["best", "720p", "480p", "360p", "worst"],
            state="readonly",
            width=15
        )
        quality_combo.pack(side=LEFT, padx=(10, 0))
        
        # Настройки для плейлистов
        self.playlist_frame = ttk.Frame(self.settings_frame)
        self.playlist_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(self.playlist_frame, text="Диапазон серий:").pack(side=LEFT)
        
        self.start_episode_var = tk.StringVar(value="1")
        start_spin = ttk.Spinbox(
            self.playlist_frame,
            from_=1,
            to=999,
            textvariable=self.start_episode_var,
            width=8
        )
        start_spin.pack(side=LEFT, padx=(10, 5))
        
        ttk.Label(self.playlist_frame, text="до").pack(side=LEFT, padx=(5, 5))
        
        self.end_episode_var = tk.StringVar(value="1")
        end_spin = ttk.Spinbox(
            self.playlist_frame,
            from_=1,
            to=999,
            textvariable=self.end_episode_var,
            width=8
        )
        end_spin.pack(side=LEFT, padx=(5, 0))
        
        # Подсказка для пользователя
        hint_label = ttk.Label(
            self.playlist_frame,
            text="(например: 1 до 12 для скачивания серий 1-12)",
            font=("Helvetica", 9),
            bootstyle="secondary"
        )
        hint_label.pack(side=LEFT, padx=(10, 0))
        
        # Скрываем настройки плейлиста по умолчанию
        self.playlist_frame.pack_forget()
        
        # Путь для скачивания
        path_frame = ttk.Frame(self.settings_frame)
        path_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(path_frame, text="Папка:").pack(side=LEFT)
        
        self.path_var = tk.StringVar(value=self.config.get_download_path())
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=50)
        path_entry.pack(side=LEFT, fill=X, expand=True, padx=(10, 10))
        
        browse_btn = ttk.Button(
            path_frame,
            text="Обзор",
            command=self.browse_path,
            bootstyle="outline-secondary"
        )
        browse_btn.pack(side=RIGHT)
        
        # Кнопка скачивания
        self.download_btn = ttk.Button(
            self.settings_frame,
            text="Скачать",
            command=self.start_download,
            bootstyle="success",
            state=DISABLED
        )
        self.download_btn.pack(pady=(10, 0))
        
        # Секция прогресса
        self.progress_frame = ttk.LabelFrame(main_container, text="Прогресс скачивания", padding=15)
        self.progress_frame.pack(fill=X, pady=(0, 15))
        
        # Прогресс бар
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100,
            bootstyle="success-striped"
        )
        self.progress_bar.pack(fill=X, pady=(0, 10))
        
        # Статус
        self.status_label = ttk.Label(
            self.progress_frame,
            text="Готов к скачиванию",
            font=("Helvetica", 10)
        )
        self.status_label.pack()
        
        # Скрываем секцию прогресса по умолчанию
        self.progress_frame.pack_forget()
        
        # Секция управления
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=X)
        
        self.stop_btn = ttk.Button(
            control_frame,
            text="Остановить",
            command=self.stop_download,
            bootstyle="danger",
            state=DISABLED
        )
        control_frame.pack(side=LEFT)
        
        self.clear_queue_btn = ttk.Button(
            control_frame,
            text="Очистить очередь",
            command=self.clear_queue,
            bootstyle="outline-warning",
            state=DISABLED
        )
        control_frame.pack(side=LEFT, padx=(10, 0))
    
    def analyze_url(self):
        """Анализирует URL"""
        url = self.url_var.get().strip()
        
        if not url:
            messagebox.showwarning("Предупреждение", "Введите ссылку для анализа")
            return
        
        if not ValidationUtils.is_valid_url(url):
            messagebox.showerror("Ошибка", "Неверная ссылка. Убедитесь, что ссылка ведет на Rutube")
            return
        
        # Запускаем анализ в отдельном потоке
        self.is_analyzing = True
        self.analyze_btn.config(state=DISABLED, text="Анализирую...")
        self.status_label.config(text="Анализирую ссылку...")
        
        analysis_thread = threading.Thread(target=self._analyze_url_worker, args=(url,))
        analysis_thread.daemon = True
        analysis_thread.start()
    
    def _analyze_url_worker(self, url):
        """Рабочий поток для анализа URL"""
        try:
            # Анализируем URL
            self.content_info = self.parser.parse_url(url)
            
            # Обновляем интерфейс в главном потоке
            self.parent.after(0, self._update_content_info)
            
        except Exception as e:
            self.parent.after(0, lambda: self._show_error(f"Ошибка при анализе: {str(e)}"))
        finally:
            self.parent.after(0, self._finish_analysis)
    
    def _update_content_info(self):
        """Обновляет информацию о контенте"""
        if not self.content_info or "error" in self.content_info:
            self._show_error(self.content_info.get("error", "Неизвестная ошибка"))
            return
        
        # Обновляем заголовок
        title = self.content_info.get("title", "Неизвестно")
        self.title_label.config(text=title)
        
        # Обновляем описание
        description = self.content_info.get("description", "")
        if description:
            self.description_label.config(text=description)
        else:
            self.description_label.config(text="Описание недоступно")
        
        # Обновляем детали
        content_type = self.content_info.get("type", "unknown")
        episodes = self.content_info.get("episodes", 1)
        
        if content_type == "playlist":
            details = f"Тип: Плейлист | Серий: {episodes}"
            self.start_episode_var.set("1")
            self.end_episode_var.set(str(episodes))
            self.playlist_frame.pack(fill=X, pady=(0, 10))
        else:
            details = f"Тип: Видео | Длительность: {self.content_info.get('duration', 'Неизвестно')}"
            self.playlist_frame.pack_forget()
        
        self.details_label.config(text=details)
        
        # Активируем кнопку скачивания
        self.download_btn.config(state=NORMAL)
        
        # Показываем секцию настроек
        self.settings_frame.pack(fill=X, pady=(0, 15))
    
    def _show_error(self, message):
        """Показывает ошибку"""
        messagebox.showerror("Ошибка", message)
        self.title_label.config(text="Ошибка при анализе")
        self.description_label.config(text="")
        self.details_label.config(text="")
    
    def _finish_analysis(self):
        """Завершает анализ"""
        self.is_analyzing = False
        self.analyze_btn.config(state=NORMAL, text="Анализировать")
        self.status_label.config(text="Готов к скачиванию")
    
    def clear_url(self):
        """Очищает поле URL"""
        self.url_var.set("")
        self.content_info = None
        self.title_label.config(text="Вставьте ссылку и нажмите 'Анализировать'")
        self.description_label.config(text="")
        self.details_label.config(text="")
        self.download_btn.config(state=DISABLED)
        self.settings_frame.pack_forget()
        self.progress_frame.pack_forget()
        
        # Сбрасываем значения диапазона серий
        self.start_episode_var.set("1")
        self.end_episode_var.set("1")
    
    def browse_path(self):
        """Открывает диалог выбора папки"""
        path = filedialog.askdirectory(
            title="Выберите папку для скачивания",
            initialdir=self.path_var.get()
        )
        
        if path:
            self.path_var.set(path)
            self.downloader.set_download_path(path)
    
    def _paste_from_clipboard(self, event=None):
        """Вставляет текст из буфера обмена"""
        try:
            clipboard_text = self.parent.clipboard_get()
            if clipboard_text:
                # Очищаем поле и вставляем текст
                self.url_var.set(clipboard_text.strip())
                # Фокусируемся на поле ввода
                self.parent.focus_force()
        except Exception as e:
            print(f"Ошибка при вставке из буфера: {e}")
    
    def _copy_to_clipboard(self):
        """Копирует текст в буфер обмена"""
        try:
            selected_text = self.url_var.get()
            if selected_text:
                self.parent.clipboard_clear()
                self.parent.clipboard_append(selected_text)
        except Exception as e:
            print(f"Ошибка при копировании в буфер: {e}")
    
    def _cut_to_clipboard(self):
        """Вырезает текст в буфер обмена"""
        try:
            selected_text = self.url_var.get()
            if selected_text:
                self.parent.clipboard_clear()
                self.parent.clipboard_append(selected_text)
                self.url_var.set("")
        except Exception as e:
            print(f"Ошибка при вырезании в буфер: {e}")
    
    def _show_context_menu(self, event):
        """Показывает контекстное меню"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
    
    def start_download(self):
        """Начинает скачивание"""
        if not self.content_info:
            messagebox.showerror("Ошибка", "Сначала проанализируйте ссылку")
            return
        
        # Получаем настройки
        quality = self.quality_var.get()
        download_path = self.path_var.get()
        
        # Валидируем настройки
        if not ValidationUtils.is_valid_quality(quality):
            messagebox.showerror("Ошибка", "Неверное качество видео")
            return
        
        # Настройки для плейлистов
        start_episode = 1
        end_episode = 1
        
        if self.content_info.get("type") == "playlist":
            try:
                start_episode = int(self.start_episode_var.get())
                end_episode = int(self.end_episode_var.get())
                
                print(f"DEBUG: start_episode={start_episode}, end_episode={end_episode}")
                print(f"DEBUG: max_episodes={self.content_info.get('episodes', 1)}")
                
                # Проверяем, что начальная серия не больше конечной
                if start_episode > end_episode:
                    messagebox.showerror("Ошибка", "Начальная серия не может быть больше конечной")
                    return
                
                if not ValidationUtils.is_valid_episode_range(
                    start_episode, end_episode, 
                    self.content_info.get("episodes", 1)
                ):
                    messagebox.showerror("Ошибка", "Неверный диапазон серий")
                    return
            except ValueError:
                messagebox.showerror("Ошибка", "Неверный формат номера серии")
                return
        
        # Добавляем в очередь скачивания
        success = self.downloader.add_to_queue(
            self.url_var.get(),
            self.content_info,
            start_episode,
            end_episode,
            quality
        )
        
        if success:
            # Запускаем скачивание
            self.downloader.start_download()
            
            # Обновляем интерфейс
            self._show_progress_section()
            self.download_btn.config(state=DISABLED)
            self.stop_btn.config(state=NORMAL)
            self.clear_queue_btn.config(state=NORMAL)
            
            # Добавляем в историю
            self.history_manager.add_download(
                self.url_var.get(),
                self.content_info,
                start_episode,
                end_episode,
                quality
            )
            
            messagebox.showinfo("Успех", "Задача добавлена в очередь скачивания")
        else:
            messagebox.showerror("Ошибка", "Не удалось добавить задачу в очередь")
    
    def _show_progress_section(self):
        """Показывает секцию прогресса"""
        self.progress_frame.pack(fill=X, pady=(0, 15))
    
    def _on_download_progress(self, task, status, message):
        """Callback для прогресса скачивания"""
        if status == "start":
            self.status_label.config(text=message)
            self.progress_var.set(0)
        elif status == "progress":
            self.status_label.config(text=message)
            # Извлекаем прогресс из сообщения
            if "Прогресс:" in message:
                try:
                    progress_text = message.split("Прогресс:")[1].split("%")[0].strip()
                    progress = float(progress_text)
                    self.progress_var.set(progress)
                except:
                    pass
        elif status == "complete":
            self.status_label.config(text=message)
            self.progress_var.set(100)
        elif status == "error":
            self.status_label.config(text=f"Ошибка: {message}")
    
    def stop_download(self):
        """Останавливает скачивание"""
        self.downloader.stop_download()
        self.stop_btn.config(state=DISABLED)
        self.download_btn.config(state=NORMAL)
        self.status_label.config(text="Скачивание остановлено")
    
    def clear_queue(self):
        """Очищает очередь скачивания"""
        self.downloader.clear_queue()
        self.clear_queue_btn.config(state=DISABLED)
        self.stop_btn.config(state=DISABLED)
        self.download_btn.config(state=NORMAL)
        self.status_label.config(text="Очередь очищена")
        self.progress_var.set(0)
    
    def stop_all_downloads(self):
        """Останавливает все скачивания"""
        self.downloader.stop_download()
        self.downloader.clear_queue()
