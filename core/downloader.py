"""
Модуль для скачивания видео с Rutube
Использует yt-dlp для эффективного скачивания
"""

import os
import json
import threading
import time
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
        self.max_concurrent_downloads = 3   # Оптимально 3 одновременных загрузки
        self.active_downloads = 0  # Счетчик активных загрузок
        self.download_lock = threading.Lock()  # Блокировка для синхронизации
        
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
                episode_urls = content_info.get("episode_urls", [])
                
                if end_episode is None:
                    end_episode = episodes
                
                print(f"DEBUG: Добавляю в очередь серии {start_episode}-{end_episode}")
                print(f"DEBUG: Доступно URL серий: {len(episode_urls)}")
                
                # Создаем задачи для каждой серии
                for episode_num in range(start_episode, min(end_episode + 1, episodes + 1)):
                    # Используем URL конкретной серии, если доступен
                    episode_url = url
                    if episode_urls and episode_num <= len(episode_urls):
                        episode_url = episode_urls[episode_num - 1]  # Индексация с 0
                        print(f"DEBUG: Серия {episode_num}: URL = {episode_url}")
                    else:
                        print(f"DEBUG: Серия {episode_num}: используем URL плейлиста")
                    
                    task = {
                        "url": episode_url,
                        "content_info": content_info,
                        "episode": episode_num,
                        "quality": quality,
                        "type": "playlist_episode",
                        "original_url": url,  # Сохраняем оригинальный URL плейлиста
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
            # Проверяем, можем ли запустить новую загрузку
            with self.download_lock:
                if self.active_downloads >= self.max_concurrent_downloads:
                    # Ждем завершения одной загрузки перед запуском новой
                    time.sleep(1)
                    continue
                
                if not self.download_queue:
                    break
                    
                task = self.download_queue.pop(0)
                self.active_downloads += 1
                print(f"DEBUG: Запускаю загрузку серии {task.get('episode', 'N/A')}. Активных: {self.active_downloads}")
            
            # Запускаем загрузку в отдельном потоке
            download_thread = threading.Thread(
                target=self._download_single_item_wrapper,
                args=(task,)
            )
            download_thread.daemon = True
            download_thread.start()
            
            # Небольшая задержка между запусками потоков для стабильности
            time.sleep(1)
        
        # Ждем завершения всех активных загрузок
        while self.active_downloads > 0 and self.is_downloading:
            time.sleep(0.5)
        
        self.is_downloading = False
    
    def _download_single_item_wrapper(self, task: Dict):
        """Wrapper для скачивания с управлением счетчиком активных загрузок"""
        try:
            episode = task.get("episode", "N/A")
            print(f"DEBUG: Начинаю загрузку серии {episode}")
            self._download_single_item(task)
            print(f"DEBUG: Серия {episode} загружена успешно")
        except Exception as e:
            print(f"Ошибка при скачивании серии {episode}: {e}")
            if self.progress_callback:
                self.progress_callback(task, "error", str(e))
        finally:
            # Уменьшаем счетчик активных загрузок
            with self.download_lock:
                self.active_downloads -= 1
                print(f"DEBUG: Серия {episode} завершена. Активных загрузок: {self.active_downloads}")
    
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
            'writethumbnail': False,  # Отключаем обложки
            'writesubtitles': False,  # Отключаем субтитры
            'writeautomaticsub': False,  # Отключаем автосубтитры
            'ignoreerrors': True,
            'no_warnings': True,
            'progress_hooks': [self._progress_hook],
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
        }
        
        # Если это серия из плейлиста, используем специальные параметры
        if task.get("type") == "playlist_episode":
            # Для плейлистов используем playlist_items для скачивания конкретной серии
            # URL плейлиста берем из оригинального URL задачи
            playlist_url = task.get("original_url", url)  # URL плейлиста
            if playlist_url:
                # Скачиваем конкретную серию из плейлиста
                # Для Rutube используем playlist_items с номером серии
                ydl_opts['playlist_items'] = str(episode)
                url = playlist_url
                print(f"DEBUG: Скачиваю серию {episode} из плейлиста: {playlist_url}")
                print(f"DEBUG: Использую playlist_items = {episode}")
            else:
                print(f"DEBUG: Скачиваю серию {episode} по прямому URL: {url}")
        
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
            # Получаем информацию о текущей загрузке из yt-dlp
            filename = d.get('filename', '')
            episode = None
            
            # Пытаемся извлечь номер серии из имени файла
            if filename:
                import re
                match = re.search(r'(\d+)_', filename)
                if match:
                    episode = int(match.group(1))
            
            if self.progress_callback:
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0)
                speed = d.get('speed', 0)
                
                if total > 0:
                    progress = (downloaded / total) * 100
                    speed_mb = speed / 1024 / 1024 if speed else 0
                    
                    episode_text = f"серии {episode}" if episode else "видео"
                    self.progress_callback(
                        None,  # task не нужен для многопоточности
                        "progress", 
                        f"{episode_text} - Прогресс: {progress:.1f}% | Скорость: {speed_mb:.1f} MB/s"
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
