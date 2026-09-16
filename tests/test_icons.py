from fshot.icons import camera_icon, line_end_style_icon, tool_icon, tray_icon


def _opaque_rect(icon, size):
    image = icon.pixmap(size, size).toImage()
    opaque = [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 0
    ]
    left = min(x for x, _y in opaque)
    right = max(x for x, _y in opaque)
    top = min(y for _x, y in opaque)
    bottom = max(y for _x, y in opaque)
    return left, top, right, bottom


def _opaque_bounds(icon, size):
    left, top, right, bottom = _opaque_rect(icon, size)
    return right - left + 1, bottom - top + 1


def _opaque_points(icon, size):
    image = icon.pixmap(size, size).toImage()
    return {
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 0
    }


def test_window_icon_fills_the_taskbar_slot(qt_app):
    width, height = _opaque_bounds(camera_icon(), 32)

    assert width >= 27
    assert height >= 25


def test_tray_icon_fills_the_system_tray_slot(qt_app):
    width, height = _opaque_bounds(tray_icon(), 16)

    assert width >= 14
    assert height >= 13


def test_macos_tray_icon_fills_the_menu_bar_slot(qt_app):
    width, height = _opaque_bounds(tray_icon(macos=True), 16)

    assert width >= 15
    assert height >= 15


def test_pen_tool_icon_is_vertically_centered(qt_app):
    _left, top, _right, bottom = _opaque_rect(tool_icon("pen"), 32)

    assert abs(((top + bottom) / 2) - 15.5) <= 1.5


def test_rotate_icon_has_upper_left_arrow_and_right_tilted_image(qt_app):
    points = _opaque_points(tool_icon("rotate_clockwise"), 32)

    assert any(x <= 8 and y <= 15 for x, y in points)
    assert any(x >= 24 and y >= 20 for x, y in points)


def test_flip_icons_show_distinct_horizontal_and_vertical_axes(qt_app):
    horizontal = _opaque_points(tool_icon("flip_horizontal"), 32)
    vertical = _opaque_points(tool_icon("flip_vertical"), 32)

    assert horizontal != vertical
    assert len({point for point in horizontal if point[0] == 16}) >= 8
    assert len({point for point in vertical if point[1] == 16}) >= 8


def test_line_tool_icon_reflects_endpoint_styles(qt_app):
    plain = tool_icon("line")
    styled = tool_icon("line", line_start="arrow", line_end="circle")

    assert _opaque_points(styled, 32) != _opaque_points(plain, 32)
    assert len(_opaque_points(styled, 32)) > len(_opaque_points(plain, 32))


def test_line_endpoint_option_icons_show_the_style_on_the_correct_side(qt_app):
    plain = _opaque_points(line_end_style_icon("none", "start"), 64)
    start_arrow = _opaque_points(line_end_style_icon("arrow", "start"), 64)
    end_circle = _opaque_points(line_end_style_icon("circle", "end"), 64)

    assert start_arrow != plain
    assert end_circle != plain
    assert len({point for point in start_arrow - plain if point[0] < 24}) > 0
    assert len({point for point in end_circle - plain if point[0] > 40}) > 0
