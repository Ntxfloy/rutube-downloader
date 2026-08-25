"""
Модуль утилит для Rutube Downloader
Конфигурация, история скачиваний, файловые операции и валидация
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

APP_DIR_NAME = "RutubeDownloader"
RUTUBE_HOSTS = ("rutube.ru", "www.rutube.ru", "m.rutube.ru")
MAX_HISTORY_ENTRIES = 200

DEFAULT_THEME = "darkly"
# В ttkbootstrap нет тем "dark" и "light": с таким значением в config.json
# приложение падало на старте: ('dark', 'is not a valid theme.').
THEME_ALIASES = {
    "dark": "darkly",
    "light": "cosmo",
    "default": DEFAULT_THEME,
    "system": DEFAULT_THEME,
    "none": DEFAULT_THEME,
}


def normalize_theme(name: Any) -> str:
    """Приводит имя темы к виду, понятному ttkbootstrap.

    Закрытого списка тем здесь специально нет: иначе валидные темы
    (morph, litera, united и т.д.) сбрасывались бы на тему по умолчанию.
    Фактическую доступность темы проверяет gui.ui_compat.resolve_theme().
    """
    theme = str(name or "").strip().lower()
    if not theme:
        return DEFAULT_THEME
    return THEME_ALIASES.get(theme, theme)


def get_app_data_dir() -> Path:
    """Возвращает каталог для настроек и истории.

    Раньше использовался относительный путь ``data/config.json``, из-за чего
    настройки терялись при запуске приложения из другой рабочей директории
    или из собранного .exe. Теперь данные лежат в пользовательском профиле.
    """
    try:
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA") or Path.home())
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        app_dir = base / APP_DIR_NAME
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir
    except Exception:
        fallback = Path.cwd() / "data"
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except Exception:
            return Path.cwd()
        return fallback


def get_default_download_path() -> str:
    """Путь для скачивания по умолчанию (Загрузки/RutubeDownloads)."""
    try:
        home = Path.home()
        downloads = home / "Downloads"
        if downloads.exists():
            return str(downloads / "RutubeDownloads")
        return str(home / "RutubeDownloads")
    except Exception:
        return str(Path.cwd() / "downloads")


def format_bytes(value: Any) -> str:
    """Форматирует количество байт в читаемый вид."""
    try:
        size = float(value or 0)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def format_speed(speed: Any) -> str:
    """Форматирует скорость загрузки."""
    if not speed:
        return "—"
    return f"{format_bytes(speed)}/s"


def format_duration(seconds: Any) -> str:
    """Форматирует секунды в ЧЧ:ММ:СС или ММ:СС."""
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return "Неизвестно"
    if total < 0:
        return "Неизвестно"
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class ConfigManager:
    """Менеджер конфигурации приложения"""

    def __init__(self, config_path: Optional[str] = None):
        self._lock = threading.RLock()
        self.config_path = Path(config_path) if config_path else get_app_data_dir() / "config.json"
        self.config = self._load_default_config()
        self._load_config()

    # -- служебное ---------------------------------------------------------
    def _get_default_download_path(self) -> str:
        return get_default_download_path()

    def _load_default_config(self) -> Dict[str, Any]:
        return {
            "download_path": get_default_download_path(),
            "default_quality": "best",
            "max_concurrent_downloads": 2,
            "auto_start_download": False,
            "save_thumbnails": False,
            "save_subtitles": False,
            "show_success_popups": False,
            "theme": DEFAULT_THEME,
            "window_size": [980, 720],
            "window_position": [100, 100],
            "ffmpeg_location": None,
        }

    def _legacy_config_paths(self) -> List[Path]:
        return [Path("data/config.json"), Path.cwd() / "data" / "config.json"]

    def _load_config(self) -> None:
        """Загружает конфигурацию, при необходимости миграция из data/."""
        source: Optional[Path] = None
        if self.config_path.exists():
            source = self.config_path
        else:
            for legacy in self._legacy_config_paths():
                if legacy.exists():
                    source = legacy
                    break
        if source is None:
            return
        try:
            with open(source, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self.config.update(loaded)
            # Старые конфиги содержат theme="dark", которой в ttkbootstrap нет,
            # и приложение падало ещё до появления окна.
            normalized_theme = normalize_theme(self.config.get("theme"))
            theme_changed = normalized_theme != self.config.get("theme")
            self.config["theme"] = normalized_theme
            if source != self.config_path or theme_changed:
                self.save_config()
        except Exception as error:
            print(f"Ошибка при загрузке конфигурации: {error}")

    def save_config(self) -> None:
        """Сохраняет конфигурацию в файл (атомарно)."""
        with self._lock:
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self.config_path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as handle:
                    json.dump(self.config, handle, indent=2, ensure_ascii=False)
                tmp_path.replace(self.config_path)
            except Exception as error:
                print(f"Ошибка при сохранении конфигурации: {error}")

    # -- публичный API -----------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        if key == "theme":
            value = normalize_theme(value)
        with self._lock:
            if self.config.get(key) == value:
                return
            self.config[key] = value
        if save:
            self.save_config()

    def update(self, values: Dict[str, Any], save: bool = True) -> None:
        values = dict(values)
        if "theme" in values:
            values["theme"] = normalize_theme(values["theme"])
        with self._lock:
            self.config.update(values)
        if save:
            self.save_config()

    def get_download_path(self) -> str:
        """Путь для скачивания с проверкой доступности."""
        path = self.config.get("download_path") or get_default_download_path()
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return str(path)
        except Exception as error:
            print(f"Предупреждение: путь {path} недоступен ({error}). Используем путь по умолчанию.")
        default_path = get_default_download_path()
        try:
            Path(default_path).mkdir(parents=True, exist_ok=True)
        except Exception:
            default_path = str(Path.cwd() / "downloads")
        self.config["download_path"] = default_path
        self.save_config()
        return default_path

    def set_download_path(self, path: str) -> None:
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
        except Exception as error:
            raise ValueError(f"Не удалось создать директорию: {error}")
        self.set("download_path", str(path))


class HistoryManager:
    """Менеджер истории скачиваний"""

    def __init__(self, history_path: Optional[str] = None):
        self._lock = threading.RLock()
        self.history_path = Path(history_path) if history_path else get_app_data_dir() / "history.json"
        self.history = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        candidates = [self.history_path, Path("data/history.json"), Path.cwd() / "data" / "history.json"]
        for candidate in candidates:
            try:
                if candidate.exists():
                    with open(candidate, "r", encoding="utf-8") as handle:
                        data = json.load(handle)
                    if isinstance(data, list):
                        return data
            except Exception as error:
                print(f"Ошибка при загрузке истории: {error}")
        return []

    def _save_history(self) -> None:
        with self._lock:
            try:
                self.history_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self.history_path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as handle:
                    json.dump(self.history, handle, indent=2, ensure_ascii=False)
                tmp_path.replace(self.history_path)
            except Exception as error:
                print(f"Ошибка при сохранении истории: {error}")

    def add_download(self, url: str, content_info: Dict[str, Any],
                     start_episode: int = 1, end_episode: Optional[int] = None,
                     quality: str = "best", status: str = "queued") -> str:
        """Добавляет запись в историю и возвращает её идентификатор."""
        entry_id = uuid.uuid4().hex
        entry = {
            "id": entry_id,
            "url": url,
            "title": content_info.get("title", "Неизвестно"),
            "type": content_info.get("type", "unknown"),
            "start_episode": start_episode,
            "end_episode": end_episode or start_episode,
            "quality": quality,
            "status": status,
            "downloaded_at": datetime.now().isoformat(timespec="seconds"),
            "episodes_count": content_info.get("episodes", 1),
        }
        with self._lock:
            self.history.append(entry)
            if len(self.history) > MAX_HISTORY_ENTRIES:
                self.history = self.history[-MAX_HISTORY_ENTRIES:]
        self._save_history()
        return entry_id

    def update_status(self, entry_id: str, status: str) -> None:
        """Обновляет статус записи (queued -> completed/error/stopped)."""
        if not entry_id:
            return
        changed = False
        with self._lock:
            for entry in self.history:
                if entry.get("id") == entry_id:
                    entry["status"] = status
                    entry["finished_at"] = datetime.now().isoformat(timespec="seconds")
                    changed = True
                    break
        if changed:
            self._save_history()

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            data = list(reversed(self.history))
        if limit:
            return data[:limit]
        return data

    def clear_history(self) -> None:
        with self._lock:
            self.history.clear()
        self._save_history()

    def remove_by_id(self, entry_id: str) -> None:
        """Удаляет запись по идентификатору (устойчиво к сортировке в UI)."""
        with self._lock:
            before = len(self.history)
            self.history = [item for item in self.history if item.get("id") != entry_id]
            changed = before != len(self.history)
        if changed:
            self._save_history()

    def remove_entry(self, index: int) -> None:
        """Удаляет запись по индексу (обратная совместимость)."""
        with self._lock:
            if 0 <= index < len(self.history):
                del self.history[index]
                changed = True
            else:
                changed = False
        if changed:
            self._save_history()

    def get_download_stats(self) -> Dict[str, int]:
        with self._lock:
            entries = list(self.history)
        if not entries:
            return {"total_downloads": 0, "total_episodes": 0}
        total_episodes = 0
        for entry in entries:
            try:
                start = int(entry.get("start_episode", 1) or 1)
                end = int(entry.get("end_episode", start) or start)
            except (TypeError, ValueError):
                start, end = 1, 1
            total_episodes += max(1, end - start + 1)
        return {"total_downloads": len(entries), "total_episodes": total_episodes}


class FileManager:
    """Менеджер файлов и папок"""

    @staticmethod
    def ensure_directory(path: str) -> bool:
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as error:
            print(f"Ошибка при создании директории {path}: {error}")
            return False

    @staticmethod
    def get_file_size(file_path: str) -> str:
        try:
            return format_bytes(os.path.getsize(file_path))
        except Exception:
            return "Неизвестно"

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Очищает имя файла от недопустимых символов."""
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename or "")
        cleaned = cleaned.strip(" .")
        cleaned = re.sub(r"_{2,}", "_", cleaned)
        return (cleaned or "unknown")[:100]

    @staticmethod
    def get_available_space(path: str) -> int:
        """Свободное место на диске в байтах (кроссплатформенно).

        Раньше использовался os.statvfs, который отсутствует в Windows.
        """
        try:
            target = Path(path)
            while not target.exists() and target.parent != target:
                target = target.parent
            return int(shutil.disk_usage(str(target)).free)
        except Exception:
            return 0

    @staticmethod
    def format_bytes(bytes_value: Any) -> str:
        return format_bytes(bytes_value)

    @staticmethod
    def open_in_explorer(path: str) -> bool:
        """Открывает папку в системном файловом менеджере."""
        try:
            target = Path(path)
            target.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{target}"')
            else:
                os.system(f'xdg-open "{target}"')
            return True
        except Exception as error:
            print(f"Не удалось открыть папку {path}: {error}")
            return False


class ValidationUtils:
    """Утилиты для валидации"""

    @staticmethod
    def normalize_url(url: str) -> str:
        """Приводит ссылку к виду, понятному yt-dlp.

        Убирает пробелы/переводы строк (частая проблема при вставке из буфера)
        и добавляет схему https:// при её отсутствии.
        """
        if not url:
            return ""
        cleaned = " ".join(str(url).split()).strip().strip('"\'<>')
        if not cleaned:
            return ""
        if cleaned.startswith("//"):
            cleaned = "https:" + cleaned
        elif not re.match(r"^https?://", cleaned, re.IGNORECASE):
            cleaned = "https://" + cleaned.lstrip("/")
        return cleaned

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Проверяет, что ссылка ведёт на Rutube."""
        normalized = ValidationUtils.normalize_url(url)
        if not normalized:
            return False
        match = re.match(r"^https?://([^/:?#]+)", normalized, re.IGNORECASE)
        if not match:
            return False
        host = match.group(1).lower()
        return host in RUTUBE_HOSTS or host.endswith(".rutube.ru")

    @staticmethod
    def is_valid_episode_range(start: Any, end: Any, max_episodes: Any = 0) -> bool:
        """Проверяет диапазон серий."""
        try:
            start_num = int(start)
            end_num = int(end)
        except (TypeError, ValueError):
            return False
        if start_num < 1 or end_num < 1 or start_num > end_num:
            return False
        try:
            limit = int(max_episodes or 0)
        except (TypeError, ValueError):
            limit = 0
        if limit > 0 and end_num > limit:
            print(f"Предупреждение: запрошено {end_num} серий, доступно {limit}")
        return True

    @staticmethod
    def is_valid_quality(quality: str) -> bool:
        valid_qualities = ("best", "worst", "1080p", "720p", "480p", "360p", "240p")
        return (quality or "").strip().lower() in valid_qualities
