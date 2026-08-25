"""
Модуль для скачивания видео с Rutube
Использует yt-dlp

Что важно в этой версии:
- процент загрузки считается корректно, в том числе для HLS-потоков,
  где yt-dlp не сообщает total_bytes (используются оценка и фрагменты);
- в GUI передаются структурированные данные о прогрессе, а не строка,
  которую приходилось парсить регулярками;
- считается общий прогресс по всей очереди;
- кнопка "Остановить" действительно прерывает загрузку.
"""

from __future__ import annotations

import re
import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yt_dlp

try:  # yt-dlp >= 2023.07
    from yt_dlp.utils import DownloadCancelled
except Exception:  # pragma: no cover - фолбэк для старых версий
    class DownloadCancelled(Exception):
        """Исключение отмены загрузки для старых версий yt-dlp."""


def find_ffmpeg() -> Optional[str]:
    """Ищет ffmpeg в PATH и рядом с приложением.

    Возвращает путь к папке с ffmpeg или None, если он не найден.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return str(Path(ffmpeg_path).parent)

    root = Path(__file__).resolve().parent.parent
    candidates = [
        root / "ffmpeg" / "ffmpeg.exe",
        root / "ffmpeg" / "bin" / "ffmpeg.exe",
        root / "bin" / "ffmpeg.exe",
        root / "ffmpeg.exe",
        root / "ffmpeg" / "ffmpeg",
        root / "ffmpeg" / "bin" / "ffmpeg",
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate.parent)
        except Exception:
            continue
    return None


def build_format_selector(quality: str, has_ffmpeg: bool = True) -> str:
    """Строит корректный селектор формата для yt-dlp.

    Раньше использовалась строка ``best[height<={quality}]``, из-за чего для
    качества "720p" получался невалидный фильтр ``best[height<=720p]``,
    а для "worst" — ``best[height<=worst]``.
    """
    normalized = (quality or "best").strip().lower()

    if normalized in ("", "best", "лучшее"):
        return "bv*+ba/b" if has_ffmpeg else "b"
    if normalized in ("worst", "худшее"):
        return "wv*+wa/w" if has_ffmpeg else "w"

    match = re.match(r"^(\d{3,4})\s*p?$", normalized)
    if match:
        height = int(match.group(1))
        if has_ffmpeg:
            return (
                f"bv*[height<={height}]+ba/b[height<={height}]/"
                f"bv*+ba/b"
            )
        return f"b[height<={height}]/b"

    return "bv*+ba/b" if has_ffmpeg else "b"


class RutubeDownloader:
    """Класс для скачивания видео с Rutube"""

    def __init__(self, download_path: Optional[str] = None,
                 ffmpeg_location: Optional[str] = None,
                 max_concurrent_downloads: int = 2):
        self.download_path = self._resolve_download_path(download_path)

        self.download_queue: List[Dict[str, Any]] = []
        self.is_downloading = False
        self.current_download: Optional[Dict[str, Any]] = None
        self.progress_callback: Optional[Callable[..., None]] = None
        self.max_concurrent_downloads = max(1, int(max_concurrent_downloads or 1))
        self.active_downloads = 0
        self.download_lock = threading.RLock()
        self._stop_event = threading.Event()

        # Прогресс по задачам: task_id -> доля выполнения (0.0 .. 1.0)
        self._task_fractions: Dict[str, float] = {}
        self._total_tasks = 0
        self._completed_tasks = 0
        self._failed_tasks = 0

        self.ffmpeg_location = ffmpeg_location or find_ffmpeg()
        if self.ffmpeg_location:
            print(f"ffmpeg найден: {self.ffmpeg_location}")
        else:
            print("ffmpeg не найден — слияние потоков и метаданные отключены.")

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _resolve_download_path(download_path: Optional[str]) -> Path:
        if not download_path:
            try:
                home = Path.home()
                downloads = home / "Downloads"
                base = downloads if downloads.exists() else home
                download_path = str(base / "RutubeDownloads")
            except Exception:
                download_path = "downloads"

        target = Path(download_path)
        try:
            target.mkdir(parents=True, exist_ok=True)
            return target
        except Exception as error:
            print(f"Предупреждение: не удалось создать {download_path}: {error}")

        try:
            fallback = Path.cwd() / "downloads"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
        except Exception:
            return Path.cwd()

    def set_progress_callback(self, callback: Callable[..., None]) -> None:
        """Устанавливает callback вида callback(task, status, message, info)."""
        self.progress_callback = callback

    def _overall_percent(self) -> float:
        with self.download_lock:
            if self._total_tasks <= 0:
                return 0.0
            done = sum(self._task_fractions.values())
            return max(0.0, min(100.0, done / self._total_tasks * 100.0))

    def _notify(self, task: Optional[Dict[str, Any]], status: str,
                message: str, info: Optional[Dict[str, Any]] = None) -> None:
        """Безопасно отправляет событие в GUI."""
        if not self.progress_callback:
            return
        payload: Dict[str, Any] = {
            "overall_percent": self._overall_percent(),
            "queue_length": len(self.download_queue),
            "active_downloads": self.active_downloads,
            "completed": self._completed_tasks,
            "failed": self._failed_tasks,
            "total": self._total_tasks,
        }
        if info:
            payload.update(info)
        try:
            self.progress_callback(task, status, message, payload)
        except TypeError:
            # Совместимость со старой сигнатурой callback(task, status, message)
            try:
                self.progress_callback(task, status, message)
            except Exception as error:
                print(f"Ошибка в progress_callback: {error}")
        except Exception as error:
            print(f"Ошибка в progress_callback: {error}")

    # ------------------------------------------------------------------ queue
    def add_to_queue(self, url: str, content_info: Dict[str, Any],
                     start_episode: int = 1, end_episode: Optional[int] = None,
                     quality: str = "best") -> bool:
        """Добавляет задачи в очередь скачивания."""
        try:
            new_tasks: List[Dict[str, Any]] = []

            if content_info.get("type") == "playlist":
                episode_urls = list(content_info.get("episode_urls") or [])
                episodes = int(content_info.get("episodes", 0) or 0)
                known_total = len(episode_urls) or episodes

                start = max(1, int(start_episode or 1))
                end = int(end_episode or known_total or start)
                end = max(start, end)
                if known_total:
                    end = min(end, known_total)

                for number in range(start, end + 1):
                    direct_url = episode_urls[number - 1] if number <= len(episode_urls) else None
                    new_tasks.append({
                        "id": uuid.uuid4().hex,
                        "url": direct_url or url,
                        "content_info": content_info,
                        "episode": number,
                        "quality": quality,
                        "type": "playlist_episode",
                        "original_url": url,
                        "use_playlist_items": direct_url is None,
                        "added_at": datetime.now().isoformat(timespec="seconds"),
                    })
            else:
                new_tasks.append({
                    "id": uuid.uuid4().hex,
                    "url": url,
                    "content_info": content_info,
                    "episode": 1,
                    "quality": quality,
                    "type": "single_video",
                    "original_url": url,
                    "use_playlist_items": False,
                    "added_at": datetime.now().isoformat(timespec="seconds"),
                })

            if not new_tasks:
                return False

            with self.download_lock:
                self.download_queue.extend(new_tasks)
                self._total_tasks += len(new_tasks)
                for task in new_tasks:
                    self._task_fractions[task["id"]] = 0.0

            self._notify(None, "queued",
                         f"В очередь добавлено задач: {len(new_tasks)}")
            return True

        except Exception as error:
            print(f"Ошибка при добавлении в очередь: {error}")
            return False

    def clear_queue(self) -> None:
        """Очищает очередь скачивания."""
        with self.download_lock:
            for task in self.download_queue:
                self._task_fractions.pop(task.get("id"), None)
                self._total_tasks = max(0, self._total_tasks - 1)
            self.download_queue.clear()

    def stop_download(self) -> None:
        """Останавливает скачивание и очищает очередь."""
        self._stop_event.set()
        self.is_downloading = False
        self.current_download = None
        self.clear_queue()

    def reset_progress(self) -> None:
        """Сбрасывает счётчики прогресса перед новой серией загрузок."""
        with self.download_lock:
            if self.active_downloads == 0 and not self.download_queue:
                self._task_fractions.clear()
                self._total_tasks = 0
                self._completed_tasks = 0
                self._failed_tasks = 0

    # -------------------------------------------------------------- download
    def start_download(self) -> None:
        """Запускает обработку очереди."""
        with self.download_lock:
            if self.is_downloading or not self.download_queue:
                return
            self.is_downloading = True
        self._stop_event.clear()
        worker = threading.Thread(target=self._download_worker, daemon=True)
        worker.start()

    def _download_worker(self) -> None:
        """Рабочий поток: раздаёт задачи и ждёт их завершения."""
        threads: List[threading.Thread] = []

        while not self._stop_event.is_set():
            with self.download_lock:
                if not self.download_queue:
                    break
                if self.active_downloads >= self.max_concurrent_downloads:
                    task = None
                else:
                    task = self.download_queue.pop(0)
                    self.active_downloads += 1

            if task is None:
                time.sleep(0.2)
                continue

            thread = threading.Thread(
                target=self._download_single_item_wrapper,
                args=(task,),
                daemon=True,
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        stopped = self._stop_event.is_set()
        self.is_downloading = False
        self.current_download = None

        if stopped:
            self._notify(None, "stopped", "Скачивание остановлено")
        else:
            message = f"Готово. Успешно: {self._completed_tasks}"
            if self._failed_tasks:
                message += f", с ошибками: {self._failed_tasks}"
            self._notify(None, "all_done", message)

    def _download_single_item_wrapper(self, task: Dict[str, Any]) -> None:
        episode = task.get("episode", "N/A")
        try:
            self._download_single_item(task)
            with self.download_lock:
                self._task_fractions[task["id"]] = 1.0
                self._completed_tasks += 1
            self._notify(task, "complete", f"Серия {episode} скачана",
                         {"percent": 100.0, "episode": episode})
        except DownloadCancelled:
            with self.download_lock:
                self._task_fractions[task["id"]] = 0.0
            print(f"Загрузка серии {episode} отменена пользователем")
        except Exception as error:
            with self.download_lock:
                self._failed_tasks += 1
            self._notify(task, "error",
                         f"Серия {episode}: {error}", {"episode": episode})
        finally:
            with self.download_lock:
                self.active_downloads = max(0, self.active_downloads - 1)

    def _download_single_item(self, task: Dict[str, Any]) -> None:
        """Скачивает один элемент очереди."""
        if self._stop_event.is_set():
            raise DownloadCancelled("Остановлено пользователем")

        url = task["url"]
        content_info = task.get("content_info", {})
        episode = task.get("episode", 1)
        quality = task.get("quality", "best")

        content_title = self._sanitize_filename(content_info.get("title", "unknown"))
        content_folder = self.download_path / content_title
        content_folder.mkdir(parents=True, exist_ok=True)

        has_ffmpeg = bool(self.ffmpeg_location)
        ydl_opts: Dict[str, Any] = {
            "format": build_format_selector(quality, has_ffmpeg),
            "outtmpl": str(content_folder / f"{episode:02d}_%(title)s.%(ext)s"),
            "writethumbnail": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "ignoreerrors": False,
            "no_warnings": True,
            "quiet": True,
            "noprogress": True,
            "retries": 5,
            "fragment_retries": 10,
            "continuedl": True,
            "progress_hooks": [lambda data, bound_task=task: self._progress_hook(data, bound_task)],
        }

        if has_ffmpeg:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_location
            ydl_opts["merge_output_format"] = "mp4"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegMetadata",
                "add_metadata": True,
            }]

        # Прямой URL серии предпочтительнее: playlist_items заставляет yt-dlp
        # каждый раз обходить весь плейлист целиком.
        if task.get("type") == "playlist_episode" and task.get("use_playlist_items"):
            playlist_url = task.get("original_url") or url
            ydl_opts["playlist_items"] = str(episode)
            url = playlist_url

        self.current_download = task
        self._notify(task, "start", f"Начинаю скачивание серии {episode}",
                     {"percent": 0.0, "episode": episode})

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    # -------------------------------------------------------------- progress
    @staticmethod
    def _parse_percent_string(value: Any) -> Optional[float]:
        if not value:
            return None
        match = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", str(value))
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None

    def _calculate_percent(self, data: Dict[str, Any]) -> Optional[float]:
        """Считает процент загрузки максимально надёжно.

        Rutube часто отдаёт HLS, где total_bytes отсутствует — в этом случае
        используются оценка размера или счётчик фрагментов.
        """
        downloaded = data.get("downloaded_bytes") or 0
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0

        if total:
            return max(0.0, min(100.0, downloaded / total * 100.0))

        fragment_index = data.get("fragment_index")
        fragment_count = data.get("fragment_count")
        if fragment_index and fragment_count:
            return max(0.0, min(100.0, fragment_index / fragment_count * 100.0))

        return self._parse_percent_string(data.get("_percent_str"))

    def _progress_hook(self, data: Dict[str, Any], task: Dict[str, Any]) -> None:
        """Хук прогресса yt-dlp, привязанный к конкретной задаче."""
        if self._stop_event.is_set():
            raise DownloadCancelled("Остановлено пользователем")

        status = data.get("status")
        task_id = task.get("id")
        episode = task.get("episode", 1)

        if status == "finished":
            with self.download_lock:
                self._task_fractions[task_id] = 1.0
            self._notify(task, "progress",
                         f"Серия {episode}: обработка файла…",
                         {"percent": 100.0, "episode": episode,
                          "indeterminate": False})
            return

        if status != "downloading":
            return

        percent = self._calculate_percent(data)
        if percent is not None:
            with self.download_lock:
                self._task_fractions[task_id] = percent / 100.0

        # Не спамим GUI: обновляем не чаще 4 раз в секунду
        now = time.monotonic()
        last_emit = task.get("_last_emit", 0.0)
        last_percent = task.get("_last_percent")
        percent_changed = (
            percent is not None
            and (last_percent is None or abs(percent - last_percent) >= 0.5)
        )
        if now - last_emit < 0.25 and not percent_changed:
            return
        task["_last_emit"] = now
        task["_last_percent"] = percent

        speed = data.get("speed")
        eta = data.get("eta")
        downloaded = data.get("downloaded_bytes") or 0
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0

        if percent is None:
            message = f"Серия {episode}: загрузка…"
        else:
            message = f"Серия {episode}: {percent:.1f}%"

        self._notify(task, "progress", message, {
            "percent": percent,
            "indeterminate": percent is None,
            "episode": episode,
            "speed": speed,
            "eta": eta,
            "downloaded_bytes": downloaded,
            "total_bytes": total,
            "filename": data.get("filename"),
        })

    # ----------------------------------------------------------------- misc
    def _sanitize_filename(self, filename: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename or "")
        cleaned = cleaned.strip(" .")
        cleaned = re.sub(r"_{2,}", "_", cleaned)
        return (cleaned or "unknown")[:100]

    def get_queue_status(self) -> Dict[str, Any]:
        with self.download_lock:
            return {
                "queue_length": len(self.download_queue),
                "is_downloading": self.is_downloading,
                "active_downloads": self.active_downloads,
                "completed": self._completed_tasks,
                "failed": self._failed_tasks,
                "total": self._total_tasks,
                "overall_percent": self._overall_percent(),
                "current_download": self.current_download,
            }

    def get_download_path(self) -> str:
        return str(self.download_path)

    def set_download_path(self, path: str) -> None:
        new_path = Path(path)
        try:
            new_path.mkdir(parents=True, exist_ok=True)
        except Exception as error:
            raise ValueError(f"Не удалось создать директорию: {error}")
        self.download_path = new_path

    def set_max_concurrent_downloads(self, value: int) -> None:
        try:
            self.max_concurrent_downloads = max(1, int(value))
        except (TypeError, ValueError):
            self.max_concurrent_downloads = 1
