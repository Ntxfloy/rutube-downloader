"""
Логика скорости прокрутки колёсиком мыши.

Модуль сознательно не зависит от tkinter: так арифметику прокрутки можно
проверять тестами без графического окружения.
"""

# Сколько единиц прокрутки даёт один щелчок колёсика без ускорения
# (именно так себя ведёт штатный обработчик ttkbootstrap: delta // 120).
BASE_UNITS_PER_NOTCH = 1

# Требование: колёсико должно крутить в 1.7 раза быстрее обычного.
SCROLL_SPEED_FACTOR = 1.7

WHEEL_DELTA = 120


def wheel_notches(delta=0, num=None):
    """Переводит данные события колёсика в число щелчков.

    Положительное значение — прокрутка вверх (к началу содержимого).

    - Windows: event.delta кратен 120;
    - macOS: event.delta приходит маленькими числами (часто ±1);
    - X11: колёсико приходит как Button-4 / Button-5 без delta.
    """
    if num in (4, 5):
        return 1.0 if num == 4 else -1.0

    try:
        delta = float(delta or 0)
    except (TypeError, ValueError):
        return 0.0

    if delta == 0:
        return 0.0
    if abs(delta) >= WHEEL_DELTA:
        return delta / WHEEL_DELTA
    return delta


class ScrollAccumulator:
    """Пересчёт щелчков колёсика в целые единицы прокрутки.

    yview_scroll принимает только целые единицы, поэтому дробный остаток
    (1.7 → 1 + 0.7) не выбрасывается, а накапливается. Иначе округление
    дало бы либо 1x (отброс остатка), либо 2x вместо требуемых 1.7x.
    """

    def __init__(self, factor=SCROLL_SPEED_FACTOR, base_units=BASE_UNITS_PER_NOTCH):
        self.factor = float(factor)
        self.base_units = float(base_units)
        self._remainder = 0.0

    def reset(self):
        self._remainder = 0.0

    def units(self, notches):
        """Возвращает целое число единиц прокрутки для заданных щелчков."""
        notches = float(notches or 0)
        if notches == 0:
            return 0

        # При смене направления остаток от предыдущего направления не нужен.
        if self._remainder and (self._remainder > 0) != (notches > 0):
            self._remainder = 0.0

        # round(..., 9) гасит погрешность float: без неё 1.9999999 превращалось
        # в 1 единицу, и средняя скорость оказывалась ниже заявленной.
        exact = round(notches * self.base_units * self.factor + self._remainder, 9)
        units = int(exact)  # отброс к нулю
        self._remainder = exact - units

        if units == 0:
            # Любой щелчок должен двигать содержимое, иначе прокрутка залипает.
            units = 1 if notches > 0 else -1
            self._remainder = 0.0

        return units

    def scroll_units(self, delta=0, num=None):
        """Сразу из данных события — в аргумент yview_scroll.

        Знак инвертирован: колёсико вверх → отрицательное смещение view.
        """
        return -self.units(wheel_notches(delta=delta, num=num))
