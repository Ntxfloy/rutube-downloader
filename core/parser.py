"""
Модуль для парсинга страниц Rutube
Определяет тип контента (видео/плейлист) и извлекает метаданные
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional, Tuple, List
from urllib.parse import urlparse, parse_qs


class RutubeParser:
    """Парсер для страниц Rutube"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def parse_url(self, url: str) -> Dict:
        """
        Анализирует URL и возвращает информацию о контенте
        
        Args:
            url: URL для анализа
            
        Returns:
            Dict с информацией о контенте
        """
        try:
            # Очищаем URL
            url = url.strip()
            
            # Определяем тип контента
            content_type = self._detect_content_type(url)
            
            if content_type == "video":
                return self._parse_video(url)
            elif content_type == "playlist":
                return self._parse_playlist(url)
            else:
                return {"error": "Неизвестный тип контента"}
                
        except Exception as e:
            return {"error": f"Ошибка при парсинге: {str(e)}"}
    
    def _detect_content_type(self, url: str) -> str:
        """Определяет тип контента по URL"""
        parsed = urlparse(url)
        
        # Проверяем паттерны URL
        if '/video/' in url:
            return "video"
        elif '/playlist/' in url or '/rubric/' in url:
            return "playlist"
        elif '/channel/' in url:
            return "playlist"
        else:
            # Пытаемся определить по содержимому страницы
            return self._detect_by_content(url)
    
    def _detect_by_content(self, url: str) -> str:
        """Определяет тип контента по содержимому страницы"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Ищем признаки плейлиста
            playlist_indicators = [
                'playlist',
                'плейлист',
                'серия',
                'сезон',
                'эпизод'
            ]
            
            page_text = soup.get_text().lower()
            for indicator in playlist_indicators:
                if indicator in page_text:
                    return "playlist"
            
            # Если не плейлист, то видео
            return "video"
            
        except Exception:
            return "video"  # По умолчанию считаем видео
    
    def _parse_video(self, url: str) -> Dict:
        """Парсит информацию о видео"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Извлекаем заголовок
            title = soup.find('meta', property='og:title')
            title = title['content'] if title else "Неизвестное видео"
            
            # Извлекаем описание
            description = soup.find('meta', property='og:description')
            description = description['content'] if description else ""
            
            # Извлекаем длительность (если доступно)
            duration = "Неизвестно"
            duration_elem = soup.find('meta', property='video:duration')
            if duration_elem:
                duration = duration_elem['content']
            
            return {
                "type": "video",
                "url": url,
                "title": title,
                "description": description,
                "duration": duration,
                "episodes": 1
            }
            
        except Exception as e:
            return {"error": f"Ошибка при парсинге видео: {str(e)}"}
    
    def _parse_playlist(self, url: str) -> Dict:
        """Парсит информацию о плейлисте"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Извлекаем заголовок плейлиста
            title = soup.find('meta', property='og:title')
            title = title['content'] if title else "Неизвестный плейлист"
            
            # Извлекаем описание
            description = soup.find('meta', property='og:description')
            description = description['content'] if description else ""
            
            # Пытаемся найти количество серий
            episodes = self._count_episodes(soup)
            print(f"DEBUG: Найдено серий в плейлисте: {episodes}")
            
            return {
                "type": "playlist",
                "url": url,
                "title": title,
                "description": description,
                "episodes": episodes,
                "episode_urls": self._extract_episode_urls(soup, url)
            }
            
        except Exception as e:
            return {"error": f"Ошибка при парсинге плейлиста: {str(e)}"}
    
    def _count_episodes(self, soup: BeautifulSoup) -> int:
        """Подсчитывает количество серий в плейлисте"""
        try:
            # Ищем различные паттерны для подсчета серий
            episode_patterns = [
                r'(\d+)\s*серия',
                r'(\d+)\s*эпизод',
                r'серия\s*(\d+)',
                r'эпизод\s*(\d+)',
                r'(\d+)\s*из\s*(\d+)'
            ]
            
            page_text = soup.get_text()
            
            # Специальная обработка для Rutube плейлистов
            # Ищем текст типа "396 видео" или "396 серий"
            rutube_patterns = [
                r'(\d+)\s*видео',
                r'(\d+)\s*серий',
                r'(\d+)\s*эпизодов'
            ]
            
            for pattern in rutube_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    return int(matches[0])
            
            # Обычные паттерны
            for pattern in episode_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    if len(matches[0]) == 2:  # формат "X из Y"
                        return int(matches[0][1])
                    else:
                        # Берем максимальное число
                        numbers = [int(match) for match in matches if match.isdigit()]
                        if numbers:
                            return max(numbers)
            
            # Если не удалось найти по паттернам, ищем по структуре страницы
            episode_links = soup.find_all('a', href=re.compile(r'/video/'))
            if episode_links:
                return len(episode_links)
            
            # Дополнительная проверка для Rutube
            # Ищем любые числа в тексте, которые могут быть количеством серий
            all_numbers = re.findall(r'\b(\d+)\b', page_text)
            if all_numbers:
                numbers = [int(num) for num in all_numbers if 10 <= int(num) <= 1000]
                if numbers:
                    return max(numbers)
            
            return 1  # По умолчанию 1 серия
            
        except Exception:
            return 1
    
    def _extract_episode_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Извлекает ссылки на отдельные серии"""
        try:
            episode_urls = []
            
            # Ищем ссылки на видео
            video_links = soup.find_all('a', href=re.compile(r'/video/'))
            
            for link in video_links:
                href = link.get('href')
                if href:
                    if href.startswith('/'):
                        full_url = f"https://rutube.ru{href}"
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        full_url = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                    
                    episode_urls.append(full_url)
            
            return episode_urls[:10]  # Ограничиваем первыми 10 сериями
            
        except Exception:
            return []
    
    def close(self):
        """Закрывает сессию"""
        self.session.close()
