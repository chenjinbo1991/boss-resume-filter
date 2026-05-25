from gui_main import (
    _calculate_effective_scale,
    _enable_high_dpi_awareness,
    _place_main_window,
    _place_window_centered,
    _show_main_window_centered,
)
from updater import _place_dialog_centered


class FakeWindow:
    def __init__(
        self,
        width=100,
        height=100,
        screen_width=1920,
        screen_height=1080,
        root_x=0,
        root_y=0,
    ):
        self._width = width
        self._height = height
        self._screen_width = screen_width
        self._screen_height = screen_height
        self._root_x = root_x
        self._root_y = root_y
        self.geometry_value = None
        self.alpha_values = []
        self.after_calls = []
        self.deiconified = False

    def update_idletasks(self):
        pass

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height

    def winfo_reqwidth(self):
        return self._width

    def winfo_reqheight(self):
        return self._height

    def winfo_screenwidth(self):
        return self._screen_width

    def winfo_screenheight(self):
        return self._screen_height

    def winfo_rootx(self):
        return self._root_x

    def winfo_rooty(self):
        return self._root_y

    def geometry(self, value):
        self.geometry_value = value

    def attributes(self, name, value):
        if name == "-alpha":
            self.alpha_values.append(value)

    def after(self, delay_ms, callback):
        self.after_calls.append(delay_ms)
        callback()

    def deiconify(self):
        self.deiconified = True


def test_place_window_centered_clamps_oversized_window_to_screen_ratio():
    window = FakeWindow(screen_width=1000, screen_height=800)

    width, height, x, y = _place_window_centered(window, 1600, 1000, screen_width=1000, screen_height=800)

    assert (width, height) == (900, 680)
    assert (x, y) == (50, 60)
    assert window.geometry_value == "900x680+50+60"


def test_place_window_centered_keeps_parent_center_inside_visible_screen():
    parent = FakeWindow(width=500, height=300, screen_width=1000, screen_height=800, root_x=-200, root_y=-100)
    dialog = FakeWindow(screen_width=1000, screen_height=800)

    width, height, x, y = _place_window_centered(
        dialog,
        400,
        300,
        parent=parent,
        screen_width=1000,
        screen_height=800,
    )

    assert (width, height) == (400, 300)
    assert (x, y) == (0, 0)
    assert dialog.geometry_value == "400x300+0+0"


def test_place_window_centered_uses_non_zero_screen_origin():
    window = FakeWindow()

    width, height, x, y = _place_window_centered(
        window,
        1200,
        800,
        screen_left=1920,
        screen_top=0,
        screen_width=2560,
        screen_height=1440,
    )

    assert (width, height) == (1200, 800)
    assert (x, y) == (2600, 320)
    assert window.geometry_value == "1200x800+2600+320"


def test_place_main_window_uses_fixed_startup_monitor_area():
    window = FakeWindow(width=1200, height=800)

    width, height, x, y = _place_main_window(window, (1920, 0, 2560, 1440))

    assert (width, height) == (1200, 800)
    assert (x, y) == (2600, 320)
    assert window.geometry_value == "1200x800+2600+320"


def test_show_main_window_centered_reveals_after_delayed_centering(monkeypatch=None):
    window = FakeWindow(width=1200, height=800)

    _show_main_window_centered(window, (1920, 0, 2560, 1440))

    assert window.deiconified
    assert window.alpha_values in ([], [0.0, 1.0])
    assert window.after_calls == [50, 250]
    assert window.geometry_value == "1200x800+2600+320"


def test_update_dialog_centering_clamps_to_visible_screen():
    parent = FakeWindow(width=300, height=200, screen_width=800, screen_height=600, root_x=700, root_y=500)
    dialog = FakeWindow(screen_width=800, screen_height=600)

    _place_dialog_centered(dialog, parent, 400, 300)

    assert dialog.geometry_value == "400x300+400+300"


def test_effective_scale_grows_on_large_standard_dpi_screen():
    scale = _calculate_effective_scale(1.0, 3840, 2160, platform="win32")

    assert 1.63 < scale < 1.65


def test_effective_scale_uses_compact_target_on_2560x1440_screen():
    scale = _calculate_effective_scale(1.0, 2560, 1440, platform="win32")

    assert 1.08 < scale < 1.11


def test_effective_scale_reduces_high_dpi_150_percent():
    # 150% > 130%，触发 high_dpi_reduction: 1.5 × 0.6 = 0.9
    scale = _calculate_effective_scale(1.5, 2560, 1440, platform="win32")
    assert 0.89 < scale < 0.91


def test_effective_scale_reduces_4k_175():
    # 175% > 130%，触发 high_dpi_reduction: 1.75 × 0.6 = 1.05
    scale = _calculate_effective_scale(1.75, 3840, 2160, platform="win32")
    assert 1.04 < scale < 1.06


def test_effective_scale_no_reduction_below_130_percent():
    # 125% ≤ 130%，不触发缩减
    scale = _calculate_effective_scale(1.25, 1920, 1200, platform="win32")
    assert 1.24 < scale < 1.26


def test_effective_scale_keeps_existing_default_on_normal_screen():
    scale = _calculate_effective_scale(1.0, 1920, 1080, platform="win32")
    assert scale == 1.0


def test_enable_high_dpi_awareness_is_noop_off_windows():
    _enable_high_dpi_awareness()
