"""
Модуль утилит для Rutube Downloader
Работа с файлами, конфигурацией и историей
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class ConfigManager:
    """Менеджер конфигурации приложения"""
    
    def __init__(self, config_path: str = "data/config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_default_config()
        self._load_config()
    
    def _load_default_config(self) -> Dict:
        """Загружает конфигурацию по умолчанию"""
        return {
            "download_path": "E:\\anime",
            "default_quality": "best",
            "max_concurrent_downloads": 1,
            "auto_start_download": False,
            "save_thumbnails": True,
            "save_subtitles": True,
            "theme": "dark",
            "window_size": [800, 600],
            "window_position": [100, 100]
        }
    
    def _load_config(self):
        """Загружает конфигурацию из файла"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
        except Exception as e:
            print(f"Ошибка при загрузке конфигурации: {e}")
    
    def save_config(self):
        """Сохраняет конфигурацию в файл"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при сохранении конфигурации: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получает значение конфигурации"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Устанавливает значение конфигурации"""
        self.config[key] = value
        self.save_config()
    
    def get_download_path(self) -> str:
        """Получает путь для скачивания"""
        return self.config.get("download_path", "E:\\anime")
    
    def set_download_path(self, path: str):
        """Устанавливает путь для скачивания"""
        self.config["download_path"] = path
        self.save_config()


class HistoryManager:
    """Менеджер истории скачиваний"""
    
    def __init__(self, history_path: str = "data/history.json"):
        self.history_path = Path(history_path)
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        """Загружает историю из файла"""
        try:
            if self.history_path.exists():
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Ошибка при загрузке истории: {e}")
        return []
    
    def _save_history(self):
        """Сохраняет историю в файл"""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при сохранении истории: {e}")
    
    def add_download(self, url: str, content_info: Dict, 
                    start_episode: int = 1, end_episode: int = None,
                    quality: str = "best", status: str = "completed"):
        """Добавляет запись о скачивании в историю"""
        history_entry = {
            "url": url,
            "title": content_info.get("title", "Неизвестно"),
            "type": content_info.get("type", "unknown"),
            "start_episode": start_episode,
            "end_episode": end_episode or start_episode,
            "quality": quality,
            "status": status,
            "downloaded_at": datetime.now().isoformat(),
            "episodes_count": content_info.get("episodes", 1)
        }
        
        self.history.append(history_entry)
        
        # Ограничиваем историю последними 100 записями
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        self._save_history()
    
    def get_history(self, limit: int = None) -> List[Dict]:
        """Получает историю скачиваний"""
        if limit:
            return self.history[-limit:]
        return self.history.copy()
    
    def clear_history(self):
        """Очищает историю"""
        self.history.clear()
        self._save_history()
    
    def remove_entry(self, index: int):
        """Удаляет запись из истории по индексу"""
        if 0 <= index < len(self.history):
            del self.history[index]
            self._save_history()
    
    def get_download_stats(self) -> Dict:
        """Получает статистику скачиваний"""
        if not self.history:
            return {"total_downloads": 0, "total_episodes": 0}
        
        total_downloads = len(self.history)
        total_episodes = sum(
            entry.get("end_episode", 1) - entry.get("start_episode", 1) + 1
            for entry in self.history
        )
        
        return {
            "total_downloads": total_downloads,
            "total_episodes": total_episodes
        }


class FileManager:
    """Менеджер файлов и папок"""
    
    @staticmethod
    def ensure_directory(path: str) -> bool:
        """Создает директорию если она не существует"""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"Ошибка при создании директории {path}: {e}")
            return False
    
    @staticmethod
    def get_file_size(file_path: str) -> str:
        """Возвращает размер файла в читаемом формате"""
        try:
            size_bytes = os.path.getsize(file_path)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} TB"
        except Exception:
            return "Неизвестно"
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Очищает имя файла от недопустимых символов"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:100]  # Ограничиваем длину
    
    @staticmethod
    def get_available_space(path: str) -> int:
        """Получает доступное место на диске в байтах"""
        try:
            return os.statvfs(path).f_frsize * os.statvfs(path).f_bavail
        except Exception:
            return 0
    
    @staticmethod
    def format_bytes(bytes_value: int) -> str:
        """Форматирует байты в читаемый вид"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"


class ValidationUtils:
    """Утилиты для валидации"""
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Проверяет валидность URL"""
        if not url:
            return False
        
        url = url.strip()
        
        # Простая проверка на Rutube URL
        if 'rutube.ru' not in url:
            return False
        
        # Проверяем наличие протокола
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return True
    
    @staticmethod
    def is_valid_episode_range(start: int, end: int, max_episodes: int) -> bool:
        """Проверяет валидность диапазона серий"""
        if start < 1 or end < 1:
            return False
        
        if start > end:
            return False
        
        # Убираем строгую проверку на максимальное количество серий
        # Позволяем пользователю скачивать доступные серии
        if max_episodes > 0 and end > max_episodes:
            print(f"Предупреждение: Запрошено {end} серий, доступно {max_episodes}")
            # Не блокируем, но предупреждаем
        
        return True
    
    @staticmethod
    def is_valid_quality(quality: str) -> bool:
        """Проверяет валидность качества видео"""
        valid_qualities = ['best', 'worst', '720p', '480p', '360p']
        return quality in valid_qualities
