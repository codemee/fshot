from PySide6.QtCore import QSize

from fshot.icons import camera_icon, line_end_style_icon, tool_icon, tray_icon


def _opaque_rect(icon, size):
    image = icon.pixmap(QSize(size, size), 1.0).toImage()
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
    image = icon.pixmap(QSize(size, size), 1.0).toImage()
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


def test_tool_icon_uses_one_48_px_source(qt_app):
    icon = tool_icon("pen")

    assert _opaque_bounds(icon, 20)[0] > 0
    assert icon.availableSizes() == [QSize(48, 48)]
    assert icon.pixmap(20, 20).size() == QSize(20, 20)
    assert icon.pixmap(40, 40).size() == QSize(40, 40)


def test_toolbar_edges_are_resampled_by_qt(qt_app):
    icon = tool_icon("rectangle")

    for dpr in (1, 1.25, 1.5, 1.75, 2):
        image = icon.pixmap(QSize(20, 20), dpr).toImage()
        # Inspect the straight section of the top edge, away from rounded corners.
        alpha = [image.pixelColor(image.width() // 2, y).alpha()
                 for y in range(image.height() // 2)]
        assert any(0 < value < 255 for value in alpha), (dpr, alpha)
        # Both opposite edges must be present, not a clipped high-DPI quadrant.
        bottom = [image.pixelColor(image.width() // 2, y).alpha()
                  for y in range(image.height() // 2, image.height())]
        assert max(bottom) > 0, (dpr, bottom)
        sides = [image.pixelColor(x, image.height() // 2).alpha()
                 for x in range(image.width())]
        assert max(sides) > 0, (dpr, sides)
        occupied = [x for x, alpha in enumerate(sides) if alpha]
        assert abs(occupied[-1] - occupied[0] + 1 - round(16 * dpr)) <= 1, (dpr, sides)

    globe = tool_icon("language", badge="system").pixmap(20, 20).toImage()
    assert any(0 < globe.pixelColor(x, y).alpha() < 255
               for y in range(globe.height()) for x in range(globe.width()))


def test_globe_curves_have_even_coverage_on_both_sides(qt_app):
    icon = tool_icon("language", badge="system")

    for dpr in (1, 1.25, 1.5, 1.75, 2, 2.5, 3):
        image = icon.pixmap(QSize(20, 20), dpr).toImage()
        occupied = [x for y in range(image.height()) for x in range(image.width())
                    if image.pixelColor(x, y).alpha()]
        left, right = min(occupied), max(occupied)
        # Thin-pen ellipse rendering left pale notches on opposing arc joins.
        # Filled contours should have matching coverage across the vertical axis.
        difference = max(
            abs(image.pixelColor(x, y).alpha()
                - image.pixelColor(left + right - x, y).alpha())
            for y in range(image.height()) for x in range(left, right + 1)
        )
        assert difference <= 3, (dpr, difference)


def test_tool_artwork_uses_16_px_with_larger_dense_icons(qt_app):
    icons = [(name, None) for name in (
        "pen", "line", "rectangle", "measure", "text", "mosaic", "style",
        "undo", "rotate_clockwise", "flip_horizontal", "flip_vertical", "resize_down",
        "copy", "save", "save_as", "zoom_in", "zoom_out", "cursor", "keyboard",
    )]
    icons += [("language", badge) for badge in ("system", "zh_TW", "en")]
    icons += [("theme", badge) for badge in ("system", "light", "dark")]
    icons += [("delay", badge) for badge in ("off", "5")]
    for name, badge in icons:
        width, height = _opaque_bounds(tool_icon(name, badge=badge), 20)
        expected = 20 if name in {"keyboard", "save_as"} else 16
        if name == "language" and badge == "en":
            assert 12 <= max(width, height) <= 14, (name, badge, width, height)
        elif name == "language" and badge == "zh_TW":
            assert 13 <= max(width, height) <= 15, (name, badge, width, height)
        else:
            assert max(width, height) == expected, (name, badge, width, height)
        left, top, right, bottom = _opaque_rect(tool_icon(name, badge=badge), 20)
        assert abs(left - (19 - right)) <= 1, (name, badge, left, right)
        assert abs(top - (19 - bottom)) <= 1, (name, badge, top, bottom)


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


def test_system_theme_icon_has_a_filled_left_half(qt_app):
    for dark in (False, True):
        image = tool_icon("theme", badge="system", dark=dark).pixmap(20, 20).toImage()
        for y in (6, 10, 13):
            assert image.pixelColor(7, y).alpha() > 240
            assert image.pixelColor(12, y).alpha() == 0


def test_mirror_dashes_are_centered_and_symmetric(qt_app):
    for name in ("flip_horizontal", "flip_vertical"):
        icon = tool_icon(name)
        for dpr in (1, 1.25, 1.5, 1.75, 2, 2.5, 3):
            image = icon.pixmap(QSize(20, 20), dpr).toImage()
            center = image.width() // 2

            def axis_strip(cross):
                return [image.pixelColor(cross, along).alpha()
                        if name == "flip_horizontal" else image.pixelColor(along, cross).alpha()
                        for along in range(image.height())]

            first = axis_strip(center)
            if image.width() % 2 == 0:
                assert max(abs(a - b) for a, b in zip(first, axis_strip(center - 1))) <= 3, (name, dpr)
            assert max(abs(a - b) for a, b in zip(first, reversed(first))) <= 3, (name, dpr)
            assert max(first) > 0, (name, dpr)


def test_line_endpoint_option_icons_show_the_style_on_the_correct_side(qt_app):
    plain = _opaque_points(line_end_style_icon("none", "start"), 64)
    start_arrow = _opaque_points(line_end_style_icon("arrow", "start"), 64)
    end_circle = _opaque_points(line_end_style_icon("circle", "end"), 64)

    assert start_arrow != plain
    assert end_circle != plain
    assert len({point for point in start_arrow - plain if point[0] < 24}) > 0
    assert len({point for point in end_circle - plain if point[0] > 40}) > 0
