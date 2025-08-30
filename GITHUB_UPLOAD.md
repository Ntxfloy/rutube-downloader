# 🚀 Загрузка проекта на GitHub

## 📋 Предварительные требования

1. **Установить Git**: https://git-scm.com/download/win
2. **Создать аккаунт на GitHub**: https://github.com
3. **Создать приватный репозиторий** на GitHub

## 🔧 Команды для загрузки

### 1. Инициализация Git репозитория
```bash
git init
```

### 2. Добавление всех файлов
```bash
git add .
```

### 3. Первый коммит
```bash
git commit -m "Initial commit: Rutube Downloader v1.0

- Полнофункциональное приложение для скачивания с Rutube
- Автоматическое определение типа контента (видео/плейлист)
- Поддержка диапазона серий для плейлистов
- Темная тема интерфейса
- История скачиваний
- Многопоточность
- Оптимизированная производительность"
```

### 4. Добавление удаленного репозитория
```bash
git remote add origin https://github.com/YOUR_USERNAME/rutube-downloader.git
```

### 5. Переименование основной ветки (если нужно)
```bash
git branch -M main
```

### 6. Отправка на GitHub
```bash
git push -u origin main
```

## 📁 Структура проекта для GitHub

```
Rutub_downloader/
├── main.py                 # 🚀 Точка входа
├── gui/                    # 🎨 Интерфейс
│   ├── __init__.py
│   ├── main_window.py      # Главное окно
│   ├── download_frame.py   # Фрейм скачивания
│   └── history_frame.py    # Фрейм истории
├── core/                   # ⚙️ Логика
│   ├── __init__.py
│   ├── parser.py           # Парсинг Rutube
│   ├── downloader.py       # Скачивание
│   └── utils.py            # Утилиты
├── data/                   # 💾 Данные
│   ├── config.json         # Настройки
│   ├── history.json        # История
│   └── downloads/          # Скачивания
├── requirements.txt         # 📦 Зависимости
├── README.md               # 📚 Документация
├── project_plan.md         # 📋 План проекта
└── GITHUB_UPLOAD.md        # 📤 Эта инструкция
```

## 🚫 Файлы для исключения (.gitignore)

Создайте файл `.gitignore`:
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# Данные приложения
data/downloads/
data/history.json
data/config.json

# Логи
*.log

# Временные файлы
*.tmp
*.temp

# IDE
.vscode/
.idea/
*.swp
*.swo

# Системные файлы
.DS_Store
Thumbs.db
```

## 🔐 Настройка приватного репозитория

1. **На GitHub**: Создайте новый репозиторий
2. **Название**: `rutube-downloader` (или любое другое)
3. **Приватность**: ✅ Private
4. **README**: ❌ Не создавать (у нас уже есть)
5. **.gitignore**: ❌ Не создавать (создадим сами)
6. **License**: Выберите подходящую (MIT, GPL, etc.)

## 📝 Описание репозитория

```
Rutube Downloader - Полнофункциональное приложение для скачивания видео и плейлистов с Rutube

✨ Возможности:
- Автоматическое определение типа контента
- Скачивание плейлистов с выбором диапазона серий
- Современный темный интерфейс
- История скачиваний
- Многопоточность
- Поддержка различных качеств видео

🛠️ Технологии:
- Python 3.8+
- tkinter + ttkbootstrap
- yt-dlp для скачивания
- requests + BeautifulSoup для парсинга

🚀 Быстрый старт:
1. pip install -r requirements.txt
2. python main.py
```

## 🔄 Последующие обновления

```bash
# Добавить изменения
git add .

# Создать коммит
git commit -m "Описание изменений"

# Отправить на GitHub
git push
```

## 📞 Поддержка

При возникновении проблем:
1. Проверьте, что Git установлен: `git --version`
2. Убедитесь, что репозиторий создан на GitHub
3. Проверьте правильность URL в remote origin
4. Убедитесь, что у вас есть права на запись в репозиторий

---

**Удачи с загрузкой проекта! 🎯✨**
