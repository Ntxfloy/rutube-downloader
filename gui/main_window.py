"""
Главное окно приложения Rutube Downloader
"""

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame

from .download_frame import DownloadFrame
from .history_frame import HistoryFrame
from core.utils import ConfigManager


class MainWindow:
    """Главное окно приложения"""
    
    def __init__(self):
        self.config = ConfigManager()
        
        # Создаем главное окно
        self.root = ttk.Window(
            title="Rutube Downloader",
            themename="darkly",
            size=(900, 700),
            resizable=(True, True)
        )
        
        # Устанавливаем позицию окна
        window_size = self.config.get("window_size", [900, 700])
        window_position = self.config.get("window_position", [100, 100])
        
        self.root.geometry(f"{window_size[0]}x{window_size[1]}+{window_position[0]}+{window_position[1]}")
        
        # Привязываем события
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Configure>", self.on_window_resize)
        
        # Создаем интерфейс
        self._create_widgets()
        self._create_menu()
        
        # Инициализируем фреймы
        self.download_frame = DownloadFrame(self.notebook, self.config)
        self.history_frame = HistoryFrame(self.notebook, self.config)
        
        # Добавляем фреймы в notebook
        self.notebook.add(self.download_frame.frame, text="Скачивание", padding=10)
        self.notebook.add(self.history_frame.frame, text="История", padding=10)
        
        # Устанавливаем фокус на первую вкладку
        self.notebook.select(0)
    
    def _create_widgets(self):
        """Создает основные виджеты"""
        # Создаем главный контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # Заголовок приложения
        title_label = ttk.Label(
            main_container,
            text="Rutube Downloader",
            font=("Helvetica", 24, "bold"),
            bootstyle="inverse-primary"
        )
        title_label.pack(pady=(0, 20))
        
        # Подзаголовок
        subtitle_label = ttk.Label(
            main_container,
            text="Скачивание видео и плейлистов с Rutube",
            font=("Helvetica", 12),
            bootstyle="inverse-secondary"
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Notebook для вкладок
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=BOTH, expand=True)
        
        # Статус бар
        self.status_bar = ttk.Label(
            main_container,
            text="Готов к работе",
            relief=SUNKEN,
            anchor=W,
            bootstyle="inverse-secondary"
        )
        self.status_bar.pack(side=BOTTOM, fill=X, pady=(10, 0))
    
    def _create_menu(self):
        """Создает меню приложения"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Настройки", command=self.show_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.on_closing)
        
        # Меню Справка
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)
        help_menu.add_command(label="Помощь", command=self.show_help)
    
    def show_settings(self):
        """Показывает окно настроек"""
        settings_window = SettingsWindow(self.root, self.config)
        self.root.wait_window(settings_window.window)
    
    def show_about(self):
        """Показывает окно 'О программе'"""
        messagebox.showinfo(
            "О программе",
            "Rutube Downloader v1.0\n\n"
            "Приложение для скачивания видео и плейлистов с Rutube\n\n"
            "Разработано с использованием Python и ttkbootstrap"
        )
    
    def show_help(self):
        """Показывает справку"""
        help_text = """
        Как использовать Rutube Downloader:
        
        1. Вставьте ссылку на видео или плейлист в поле ввода
        2. Нажмите кнопку "Анализировать" для получения информации
        3. Настройте параметры скачивания (качество, диапазон серий)
        4. Нажмите "Скачать" для начала загрузки
        
        Поддерживаемые форматы:
        - Одиночные видео
        - Плейлисты и сериалы
        - Каналы пользователей
        
        Для получения помощи посетите: https://github.com/your-repo
        """
        
        messagebox.showinfo("Справка", help_text)
    
    def update_status(self, message: str):
        """Обновляет статус бар"""
        self.status_bar.config(text=message)
    
    def on_window_resize(self, event):
        """Обработчик изменения размера окна"""
        if event.widget == self.root:
            # Сохраняем новый размер и позицию
            geometry = self.root.geometry()
            size_part = geometry.split('+')[0]
            width, height = map(int, size_part.split('x'))
            
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            
            self.config.set("window_size", [width, height])
            self.config.set("window_position", [x, y])
    
    def on_closing(self):
        """Обработчик закрытия окна"""
        try:
            # Останавливаем все скачивания
            if hasattr(self, 'download_frame'):
                self.download_frame.stop_all_downloads()
            
            # Сохраняем конфигурацию
            self.config.save_config()
            
            # Закрываем окно
            self.root.destroy()
            
        except Exception as e:
            print(f"Ошибка при закрытии: {e}")
            self.root.destroy()
    
    def run(self):
        """Запускает главное окно"""
        self.root.mainloop()
    



class SettingsWindow:
    """Окно настроек"""
    
    def __init__(self, parent, config):
        self.config = config
        self.parent = parent
        
        # Создаем окно настроек
        self.window = ttk.Toplevel(parent)
        self.window.title("Настройки")
        self.window.geometry("500x400")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        
        # Центрируем окно
        self.window.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Создает виджеты окна настроек"""
        # Главный контейнер
        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill=BOTH, expand=True)
        
        # Заголовок
        title_label = ttk.Label(
            main_frame,
            text="Настройки",
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Путь для скачивания
        path_frame = ttk.LabelFrame(main_frame, text="Путь для скачивания", padx=10, pady=10)
        path_frame.pack(fill=X, pady=(0, 15))
        
        self.path_var = tk.StringVar(value=self.config.get_download_path())
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=50)
        path_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        
        browse_btn = ttk.Button(
            path_frame,
            text="Обзор",
            command=self.browse_path,
            bootstyle="outline-secondary"
        )
        browse_btn.pack(side=RIGHT)
        
        # Качество по умолчанию
        quality_frame = ttk.LabelFrame(main_frame, text="Качество по умолчанию", padx=10, pady=10)
        quality_frame.pack(fill=X, pady=(0, 15))
        
        self.quality_var = tk.StringVar(value=self.config.get("default_quality", "best"))
        quality_combo = ttk.Combobox(
            quality_frame,
            textvariable=self.quality_var,
            values=["best", "720p", "480p", "360p", "worst"],
            state="readonly",
            width=20
        )
        quality_combo.pack()
        
        # Дополнительные настройки
        options_frame = ttk.LabelFrame(main_frame, text="Дополнительные настройки", padx=10, pady=10)
        options_frame.pack(fill=X, pady=(0, 20))
        
        self.save_thumbnails_var = tk.BooleanVar(value=self.config.get("save_thumbnails", True))
        thumbnails_check = ttk.Checkbutton(
            options_frame,
            text="Сохранять превью",
            variable=self.save_thumbnails_var
        )
        thumbnails_check.pack(anchor=W)
        
        self.save_subtitles_var = tk.BooleanVar(value=self.config.get("save_subtitles", True))
        subtitles_check = ttk.Checkbutton(
            options_frame,
            text="Сохранять субтитры",
            variable=self.save_subtitles_var
        )
        subtitles_check.pack(anchor=W)
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X, pady=(20, 0))
        
        save_btn = ttk.Button(
            button_frame,
            text="Сохранить",
            command=self.save_settings,
            bootstyle="success"
        )
        save_btn.pack(side=RIGHT, padx=(10, 0))
        
        cancel_btn = ttk.Button(
            button_frame,
            text="Отмена",
            command=self.window.destroy,
            bootstyle="outline-secondary"
        )
        cancel_btn.pack(side=RIGHT)
    
    def browse_path(self):
        """Открывает диалог выбора папки"""
        from tkinter import filedialog
        
        path = filedialog.askdirectory(
            title="Выберите папку для скачивания",
            initialdir=self.path_var.get()
        )
        
        if path:
            self.path_var.set(path)
    
    def save_settings(self):
        """Сохраняет настройки"""
        try:
            # Сохраняем путь для скачивания
            self.config.set_download_path(self.path_var.get())
            
            # Сохраняем качество
            self.config.set("default_quality", self.quality_var.get())
            
            # Сохраняем дополнительные настройки
            self.config.set("save_thumbnails", self.save_thumbnails_var.get())
            self.config.set("save_subtitles", self.save_subtitles_var.get())
            
            messagebox.showinfo("Успех", "Настройки сохранены!")
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки: {e}")
    

