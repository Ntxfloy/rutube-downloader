"""
Слой совместимости с разными версиями ttkbootstrap и tkinter.

Здесь собрано то, из-за чего приложение падало ещё до появления окна:

1. Имя темы из конфига может быть невалидным ("dark" вместо "darkly"),
   и ttk.Window падает с ошибкой ('dark', 'is not a valid theme.').
2. ttk.LabelFrame в одних сборках принимает опцию ``padding``, а в других
   (особенно внутри ScrolledFrame) — только ``padx``/``pady``.
3. В ttkbootstrap 2.x модуля ``ttkbootstrap.scrolled`` больше нет, и жёсткий
   импорт ScrolledFrame ломает всё приложение на стадии import.

Заодно здесь живёт ускоренная прокрутка колёсиком мыши (в 1.7 раза
быстрее штатной), арифметика — в core/scrolling.py.
"""

import tkinter as tk

import ttkbootstrap as ttk

from core.scrolling import SCROLL_SPEED_FACTOR, ScrollAccumulator
from core.utils import DEFAULT_THEME, normalize_theme

WHEEL_SEQUENCES = ("<MouseWheel>", "<Button-4>", "<Button-5>")


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


class CanvasScrolledFrame(ttk.Frame):
    """Замена ScrolledFrame для сборок ttkbootstrap без ``ttkbootstrap.scrolled``.

    Сам экземпляр — это внутренний фрейм (в него кладутся дочерние виджеты),
    а методы геометрии переадресованы внешнему контейнеру — как в ttkbootstrap.
    """

    def __init__(self, master=None, **kwargs):
        self.container = ttk.Frame(master)
        self.canvas = tk.Canvas(self.container, highlightthickness=0, borderwidth=0)
        self.vscroll = ttk.Scrollbar(
            self.container, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.vscroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        super().__init__(self.canvas, **kwargs)
        self._window_id = self.canvas.create_window((0, 0), window=self, anchor="nw")

        self.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        for method in (
            "pack",
            "pack_forget",
            "pack_info",
            "grid",
            "grid_forget",
            "place",
            "place_forget",
        ):
            setattr(self, method, getattr(self.container, method))

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window_id, width=event.width)


def find_scroll_canvas(widget):
    """Ищет Canvas, который реально прокручивает содержимое контейнера."""
    for attribute in ("canvas", "_canvas"):
        candidate = getattr(widget, attribute, None)
        if isinstance(candidate, tk.Canvas):
            return candidate

    stack = [getattr(widget, "container", widget)]
    while stack:
        current = stack.pop(0)
        try:
            children = current.winfo_children()
        except tk.TclError:
            continue
        for child in children:
            if isinstance(child, tk.Canvas):
                return child
            stack.append(child)
    return None


def boost_mousewheel(widget, factor=SCROLL_SPEED_FACTOR):
    """Делает прокрутку колёсиком в ``factor`` раз быстрее штатной.

    Обработчик вешается через bind_all на время наведения мыши на контейнер
    (так же, как это делает сам ScrolledFrame) и возвращает "break", чтобы штатный
    обработчик не добавлял свою порцию прокрутки сверху.

    Возвращает аккумулятор (полезно в тестах) или None, если Canvas не нашёлся.
    """
    canvas = find_scroll_canvas(widget)
    if canvas is None:
        return None

    accumulator = ScrollAccumulator(factor=factor)

    def on_wheel(event):
        units = accumulator.scroll_units(
            delta=getattr(event, "delta", 0), num=getattr(event, "num", None)
        )
        if not units:
            return None
        try:
            canvas.yview_scroll(units, "units")
        except tk.TclError:
            return None
        return "break"

    def enable(_event=None):
        accumulator.reset()
        for sequence in WHEEL_SEQUENCES:
            widget.bind_all(sequence, on_wheel)

    def disable(_event=None):
        accumulator.reset()
        for sequence in WHEEL_SEQUENCES:
            try:
                widget.unbind_all(sequence)
            except tk.TclError:
                pass

    for target in {getattr(widget, "container", widget), canvas}:
        target.bind("<Enter>", enable, add="+")
        target.bind("<Leave>", disable, add="+")

    widget.scroll_accumulator = accumulator
    widget.scroll_handler = on_wheel
    return accumulator


def scrolled_frame(parent, autohide=True, factor=SCROLL_SPEED_FACTOR):
    """Прокручиваемый контейнер с ускоренным колёсиком мыши."""
    frame = None
    try:
        from ttkbootstrap.scrolled import ScrolledFrame

        frame = ScrolledFrame(parent, autohide=autohide)
    except Exception:
        # ttkbootstrap 2.x: модуля scrolled больше нет — используем свой контейнер.
        frame = CanvasScrolledFrame(parent)

    boost_mousewheel(frame, factor=factor)
    return frame
