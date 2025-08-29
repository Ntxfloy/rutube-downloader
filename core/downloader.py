"""
Модуль для скачивания видео с Rutube
Использует yt-dlp для эффективного скачивания
"""

import os
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
from pathlib import Path
import yt_dlp


class RutubeDownloader:
    """Класс для скачивания видео с Rutube"""
    
    def __init__(self, download_path: str = "E:\\anime"):
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.download_queue = []
        self.is_downloading = False
        self.current_download = None
        self.progress_callback = None
        
    def set_progress_callback(self, callback: Callable):
        """Устанавливает callback для отслеживания прогресса"""
        self.progress_callback = callback
    
    def add_to_queue(self, url: str, content_info: Dict, 
                    start_episode: int = 1, end_episode: int = None,
                    quality: str = "best") -> bool:
        """
        Добавляет задачу в очередь скачивания
        
        Args:
            url: URL для скачивания
            content_info: Информация о контенте
            start_episode: Начальная серия (для плейлистов)
            end_episode: Конечная серия (для плейлистов)
            quality: Качество видео
            
        Returns:
            True если успешно добавлено
        """
        try:
            if content_info.get("type") == "playlist":
                episodes = content_info.get("episodes", 1)
                if end_episode is None:
                    end_episode = episodes
                
                # Создаем задачи для каждой серии
                for episode_num in range(start_episode, min(end_episode + 1, episodes + 1)):
                    task = {
                        "url": url,
                        "content_info": content_info,
                        "episode": episode_num,
                        "quality": quality,
                        "type": "playlist_episode",
                        "added_at": datetime.now().isoformat()
                    }
                    self.download_queue.append(task)
            else:
                # Одиночное видео
                task = {
                    "url": url,
                    "content_info": content_info,
                    "episode": 1,
                    "quality": quality,
                    "type": "single_video",
                    "added_at": datetime.now().isoformat()
                }
                self.download_queue.append(task)
            
            return True
            
        except Exception as e:
            print(f"Ошибка при добавлении в очередь: {e}")
            return False
    
    def start_download(self):
        """Запускает процесс скачивания"""
        if not self.is_downloading and self.download_queue:
            self.is_downloading = True
            download_thread = threading.Thread(target=self._download_worker)
            download_thread.daemon = True
            download_thread.start()
    
    def _download_worker(self):
        """Рабочий поток для скачивания"""
        while self.download_queue and self.is_downloading:
            task = self.download_queue.pop(0)
            self.current_download = task
            
            try:
                self._download_single_item(task)
            except Exception as e:
                print(f"Ошибка при скачивании: {e}")
                if self.progress_callback:
                    self.progress_callback(task, "error", str(e))
            
            self.current_download = None
        
        self.is_downloading = False
    
    def _download_single_item(self, task: Dict):
        """Скачивает один элемент"""
        url = task["url"]
        content_info = task["content_info"]
        episode = task.get("episode", 1)
        quality = task.get("quality", "best")
        
        # Создаем папку для контента
        content_title = self._sanitize_filename(content_info.get("title", "unknown"))
        content_folder = self.download_path / content_title
        content_folder.mkdir(exist_ok=True)
        
        # Настройки yt-dlp
        ydl_opts = {
            'format': f'best[height<={quality}]' if quality != "best" else 'best',
            'outtmpl': str(content_folder / f'{episode:02d}_%(title)s.%(ext)s'),
            'writethumbnail': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'progress_hooks': [self._progress_hook],
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
        }
        
        if self.progress_callback:
            self.progress_callback(task, "start", f"Начинаю скачивание серии {episode}")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            if self.progress_callback:
                self.progress_callback(task, "complete", f"Серия {episode} скачана успешно")
                
        except Exception as e:
            if self.progress_callback:
                self.progress_callback(task, "error", f"Ошибка при скачивании серии {episode}: {str(e)}")
            raise
    
    def _progress_hook(self, d):
        """Callback для отслеживания прогресса yt-dlp"""
        if d['status'] == 'downloading':
            if self.progress_callback and self.current_download:
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0)
                speed = d.get('speed', 0)
                
                if total > 0:
                    progress = (downloaded / total) * 100
                    speed_mb = speed / 1024 / 1024 if speed else 0
                    
                    self.progress_callback(
                        self.current_download, 
                        "progress", 
                        f"Прогресс: {progress:.1f}% | Скорость: {speed_mb:.1f} MB/s"
                    )
    
    def _sanitize_filename(self, filename: str) -> str:
        """Очищает имя файла от недопустимых символов"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:100]  # Ограничиваем длину
    
    def get_queue_status(self) -> Dict:
        """Возвращает статус очереди скачивания"""
        return {
            "queue_length": len(self.download_queue),
            "is_downloading": self.is_downloading,
            "current_download": self.current_download
        }
    
    def clear_queue(self):
        """Очищает очередь скачивания"""
        self.download_queue.clear()
    
    def stop_download(self):
        """Останавливает текущее скачивание"""
        self.is_downloading = False
        self.current_download = None
    
    def get_download_path(self) -> str:
        """Возвращает путь для скачивания"""
        return str(self.download_path)
    
    def set_download_path(self, path: str):
        """Устанавливает новый путь для скачивания"""
        new_path = Path(path)
        new_path.mkdir(parents=True, exist_ok=True)
        self.download_path = new_path
