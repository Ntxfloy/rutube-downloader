#!/usr/bin/env python3
"""
Rutube Downloader - Главный файл приложения
Приложение для скачивания видео и плейлистов с Rutube
"""

import sys
import os
import traceback
from pathlib import Path

# Добавляем текущую директорию в путь для импорта модулей
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from gui.main_window import MainWindow
    
    def main():
        """Главная функция приложения"""
        try:
            # Создаем и запускаем главное окно
            app = MainWindow()
            app.run()
            
        except Exception as e:
            print(f"Критическая ошибка: {e}")
            traceback.print_exc()
            
            # Показываем ошибку пользователю
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()  # Скрываем основное окно
            
            messagebox.showerror(
                "Критическая ошибка",
                f"Произошла критическая ошибка:\n{str(e)}\n\n"
                "Проверьте, что все зависимости установлены:\n"
                "pip install -r requirements.txt"
            )
            
            root.destroy()
            sys.exit(1)
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что все модули установлены:")
    print("pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"Неожиданная ошибка: {e}")
    traceback.print_exc()
    sys.exit(1)
