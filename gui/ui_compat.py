"""
Слой совместимости с разными версиями ttkbootstrap и tkinter.

Здесь собрано то, из-за чего приложение падало ещё до появления окна:

1. Имя темы из конфига может быть невалидным ("dark" вместо "darkly"),
   и ttk.Window падает с ошибкой ('dark', 'is not a valid theme.').
2. ttk.LabelFrame в одних сборках принимает опцию ``padding``, а в других
   (особенно внутри ScrolledFrame) — только ``padx``/``pady``,
   и любой жёсткий вариант где-то даёт TclError: unknown option.
Соответственно, оба случая решаются подбором поддерживаемого варианта,
а не заменой одного жёсткого варианта на другой.
"""

import tkinter as tk

import ttkbootstrap as ttk

from core.utils import DEFAULT_THEME, normalize_theme


def available_themes():
    """Имена доступных тем ttkbootstrap.

    Список берётся из самого ttkbootstrap, а не из зашитого списка,
    иначе новые валидные темы (morph, litera, united и т.д.) были бы
    ошибочно сброшены на тему по умолчанию. Окно Tk не создаётся.
    """
    try:
        from ttkbootstrap.themes.standard import STANDARD_THEMES

        return {str(name).lower() for name in STANDARD_THEMES}
    except Exception:
        return set()


def resolve_theme(name, default=DEFAULT_THEME):
    """Возвращает имя темы, с которым ttk.Window гарантированно запустится."""
    theme = normalize_theme(name)
    themes = available_themes()
    if not themes or theme in themes:
        return theme
    if default in themes:
        return default
    return sorted(themes)[0]


def label_frame(parent, text, pad=10, **kwargs):
    """Создаёт LabelFrame с внутренними отступами, не завися от версии виджета."""
    frame = ttk.LabelFrame(parent, text=text, **kwargs)
    for options in ({"padding": pad}, {"padx": pad, "pady": pad}):
        try:
            frame.configure(**options)
            break
        except tk.TclError:
            continue
    return frame
