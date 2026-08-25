"""Тесты скорости прокрутки колёсиком мыши (без GUI)."""

from core.scrolling import (
    BASE_UNITS_PER_NOTCH,
    SCROLL_SPEED_FACTOR,
    ScrollAccumulator,
    wheel_notches,
)


class TestWheelNotches:
    def test_windows_delta(self):
        assert wheel_notches(delta=120) == 1
        assert wheel_notches(delta=-240) == -2

    def test_x11_buttons(self):
        assert wheel_notches(num=4) == 1
        assert wheel_notches(num=5) == -1

    def test_small_delta_is_used_as_is(self):
        assert wheel_notches(delta=3) == 3

    def test_no_movement(self):
        assert wheel_notches(delta=0) == 0
        assert wheel_notches(delta=None) == 0


class TestScrollAccumulator:
    def test_speed_factor_value(self):
        assert SCROLL_SPEED_FACTOR == 1.7

    def test_average_speed_is_exactly_factor(self):
        """За 10 щелчков — ровно 17 единиц вместо штатных 10."""
        accumulator = ScrollAccumulator()
        units = [accumulator.units(1) for _ in range(10)]
        assert sum(units) == 17
        assert sum(units) == int(10 * BASE_UNITS_PER_NOTCH * SCROLL_SPEED_FACTOR)

    def test_fraction_is_not_lost(self):
        """Округление на каждом щелчке давало бы 1x или 2x вместо 1.7x."""
        accumulator = ScrollAccumulator()
        units = {accumulator.units(1) for _ in range(10)}
        assert units == {1, 2}

    def test_every_notch_moves_content(self):
        accumulator = ScrollAccumulator(factor=0.1)
        assert accumulator.units(1) == 1
        assert accumulator.units(-1) == -1

    def test_direction_switch_resets_remainder(self):
        accumulator = ScrollAccumulator()
        accumulator.units(1)
        assert accumulator.units(-1) == -1

    def test_scroll_units_sign_is_inverted_for_yview(self):
        accumulator = ScrollAccumulator()
        assert accumulator.scroll_units(delta=120) == -1
        assert accumulator.scroll_units(num=5) == 2

    def test_zero_event_does_nothing(self):
        accumulator = ScrollAccumulator()
        assert accumulator.scroll_units(delta=0) == 0
