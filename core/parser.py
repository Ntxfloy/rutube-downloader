"""
Модуль для анализа ссылок Rutube
Определяет тип контента (видео/плейлист) и извлекает метаданные

Основной источник информации — yt-dlp (тот же движок, что качает видео),
поэтому список серий и их количество совпадают с реальностью.
HTML-парсинг оставлен как фолбэк.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    import yt_dlp
except Exception:  # pragma: no cover
    yt_dlp = None  # type: ignore[assignment]

try:
    from .utils import ValidationUtils, format_duration
except ImportError:  # pragma: no cover - запуск без пакета
    from core.utils import ValidationUtils, format_duration

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15
MAX_PLAYLIST_ITEMS = 1000


class RutubeParser:
    """Парсер для страниц Rutube"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })
        self.playlist_cache: Dict[str, Dict[str, Any]] = {}

    # ----------------------------------------------------------------- utils
    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[parser] {message}")

    @staticmethod
    def _dedupe(items: List[str]) -> List[str]:
        """Убирает дубликаты, сохраняя порядок."""
        seen = set()
        result = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    # ------------------------------------------------------------------ API
    def parse_url(self, url: str) -> Dict[str, Any]:
        """Анализирует ссылку и возвращает информацию о контенте."""
        try:
            url = ValidationUtils.normalize_url(url)
            if not url:
                return {"error": "Пустая ссылка"}
            if not ValidationUtils.is_valid_url(url):
                return {"error": "Ссылка должна вести на rutube.ru"}

            if url in self.playlist_cache:
                self._log(f"из кеша: {url}")
                return self.playlist_cache[url]

            info = self._parse_with_ytdlp(url)
            if info and "error" not in info:
                if info.get("type") == "playlist":
                    self.playlist_cache[url] = info
                return info

            # Фолбэк: разбор HTML-страницы
            content_type = self._detect_content_type(url)
            if content_type == "playlist":
                result = self._parse_playlist(url)
                if "error" not in result:
                    self.playlist_cache[url] = result
                return result
            return self._parse_video(url)

        except Exception as error:
            return {"error": f"Ошибка при парсинге: {error}"}

    def clear_cache(self) -> None:
        self.playlist_cache.clear()

    # ------------------------------------------------------------- yt-dlp
    def _parse_with_ytdlp(self, url: str) -> Optional[Dict[str, Any]]:
        """Получает информацию через yt-dlp без скачивания."""
        if yt_dlp is None:
            return None

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "playlistend": MAX_PLAYLIST_ITEMS,
            "socket_timeout": REQUEST_TIMEOUT,
        }

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as error:
            self._log(f"yt-dlp не смог разобрать ссылку: {error}")
            return None

        if not isinstance(info, dict):
            return None

        entries = [entry for entry in (info.get("entries") or []) if isinstance(entry, dict)]

        if entries:
            episode_urls: List[str] = []
            for entry in entries:
                entry_url = entry.get("url") or entry.get("webpage_url")
                if not entry_url:
                    entry_id = entry.get("id")
                    if entry_id:
                        entry_url = f"https://rutube.ru/video/{entry_id}/"
                if entry_url:
                    episode_urls.append(ValidationUtils.normalize_url(entry_url))

            episode_urls = self._dedupe(episode_urls)
            return {
                "type": "playlist",
                "url": url,
                "title": info.get("title") or "Неизвестный плейлист",
                "description": (info.get("description") or "")[:1000],
                "episodes": len(episode_urls) or len(entries),
                "episode_urls": episode_urls,
                "source": "yt-dlp",
            }

        if info.get("id") or info.get("title"):
            return {
                "type": "video",
                "url": info.get("webpage_url") or url,
                "title": info.get("title") or "Неизвестное видео",
                "description": (info.get("description") or "")[:1000],
                "duration": format_duration(info.get("duration")),
                "episodes": 1,
                "source": "yt-dlp",
            }

        return None

    # --------------------------------------------------------------- HTML
    def _detect_content_type(self, url: str) -> str:
        """Определяет тип контента по URL."""
        path = (urlparse(url).path or "").lower()
        if "/video/" in path or "/shorts/" in path:
            return "video"
        if any(marker in path for marker in ("/plst/", "/playlist/", "/rubric/", "/channel/", "/metainfo/")):
            return "playlist"
        return "video"

    def _get_soup(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")

    @staticmethod
    def _meta(soup: BeautifulSoup, prop: str, default: str = "") -> str:
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
        tag = soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
        return default

    def _parse_video(self, url: str) -> Dict[str, Any]:
        """Парсит информацию о видео из HTML."""
        try:
            soup = self._get_soup(url)
            duration_raw = self._meta(soup, "video:duration")
            return {
                "type": "video",
                "url": url,
                "title": self._meta(soup, "og:title", "Неизвестное видео"),
                "description": self._meta(soup, "og:description")[:1000],
                "duration": format_duration(duration_raw) if duration_raw else "Неизвестно",
                "episodes": 1,
                "source": "html",
            }
        except Exception as error:
            return {"error": f"Ошибка при парсинге видео: {error}"}

    def _parse_playlist(self, url: str) -> Dict[str, Any]:
        """Парсит информацию о плейлисте из HTML."""
        try:
            soup = self._get_soup(url)
            episode_urls = self._extract_episode_urls(soup, url)
            episodes = len(episode_urls) or self._count_episodes(soup)

            return {
                "type": "playlist",
                "url": url,
                "title": self._meta(soup, "og:title", "Неизвестный плейлист"),
                "description": self._meta(soup, "og:description")[:1000],
                "episodes": max(1, episodes),
                "episode_urls": episode_urls,
                "source": "html",
            }
        except Exception as error:
            return {"error": f"Ошибка при парсинге плейлиста: {error}"}

    def _count_episodes(self, soup: BeautifulSoup) -> int:
        """Оценивает количество серий в плейлисте.

        Раньше здесь была эвристика "взять максимальное число от 10 до 1000
        со страницы", которая ловила лайки, просмотры и года выпуска.
        """
        try:
            links = soup.find_all("a", href=re.compile(r"/video/"))
            if links:
                return len({link.get("href") for link in links if link.get("href")})

            page_text = soup.get_text(" ", strip=True)
            patterns = (
                r"(\d{1,4})\s*видео",
                r"(\d{1,4})\s*серий",
                r"(\d{1,4})\s*эпизодов",
            )
            for pattern in patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    return int(match.group(1))
            return 1
        except Exception:
            return 1

    def _extract_episode_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Извлекает ссылки на отдельные серии."""
        episode_urls: List[str] = []
        try:
            for link in soup.find_all("a", href=re.compile(r"/video/")):
                href = link.get("href")
                if not href:
                    continue
                # Было: f"{{https://rutube.ru{href}}}" — ссылка получалась в фигурных
                # скобках и была невалидной для yt-dlp.
                episode_urls.append(urljoin(base_url, href))

            # Дополнительно ищем ссылки в инлайн-скриптах (SPA-разметка)
            for script in soup.find_all("script"):
                text = script.string or script.get_text() or ""
                if not text or ("playlist" not in text.lower() and "video" not in text.lower()):
                    continue
                for video_id in re.findall(r'"/video/([0-9a-f]{16,})/?"', text):
                    episode_urls.append(f"https://rutube.ru/video/{video_id}/")
                for direct in re.findall(r'https?://rutube\.ru/video/[0-9a-f]{16,}/?', text):
                    episode_urls.append(direct)

            episode_urls = self._dedupe(episode_urls)
            self._log(f"найдено URL серий: {len(episode_urls)}")
            return episode_urls
        except Exception as error:
            self._log(f"ошибка при извлечении URL серий: {error}")
            return episode_urls

    def close(self) -> None:
        """Закрывает сетевую сессию."""
        try:
            self.session.close()
        except Exception:
            pass
