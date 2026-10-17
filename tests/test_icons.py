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


def test_tool_icon_has_native_toolbar_sizes(qt_app):
    icon = tool_icon("pen")

    assert _opaque_bounds(icon, 20)[0] > 0
    for dpr in (1, 1.25, 1.5, 1.75, 2, 2.5, 3):
        size = QSize(round(20 * dpr), round(20 * dpr))
        assert size in icon.availableSizes()
        pixmap = icon.pixmap(QSize(20, 20), dpr)
        assert pixmap.size() == size
        assert pixmap.devicePixelRatio() == dpr


def test_toolbar_straight_edges_use_solid_pixel_rows_at_each_dpi(qt_app):
    icon = tool_icon("rectangle")

    for dpr, stroke_pixels in ((1, 1), (1.25, 1), (1.5, 2), (1.75, 2),
                               (2, 2), (2.5, 3), (3, 3)):
        image = icon.pixmap(QSize(20, 20), dpr).toImage()
        # Inspect the straight section of the top edge, away from rounded corners.
        alpha = [image.pixelColor(image.width() // 2, y).alpha()
                 for y in range(image.height() // 2)]
        assert set(alpha) == {0, 255}, (dpr, alpha)
        assert alpha.count(255) == stroke_pixels, (dpr, alpha)
        # Both opposite edges must be present, not a clipped high-DPI quadrant.
        bottom = [image.pixelColor(image.width() // 2, y).alpha()
                  for y in range(image.height() // 2, image.height())]
        assert set(bottom) == {0, 255}, (dpr, bottom)
        assert bottom.count(255) == stroke_pixels, (dpr, bottom)
        sides = [image.pixelColor(x, image.height() // 2).alpha()
                 for x in range(image.width())]
        assert set(sides) == {0, 255}, (dpr, sides)
        assert sides.count(255) == 2 * stroke_pixels, (dpr, sides)
        occupied = [x for x, alpha in enumerate(sides) if alpha]
        assert occupied[-1] - occupied[0] + 1 == round(16 * dpr), (dpr, sides)

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


def test_mirror_dashes_are_centered_and_symmetric(qt_app):
    for name in ("flip_horizontal", "flip_vertical"):
        icon = tool_icon(name)
        for dpr in (1, 1.25, 1.5, 1.75, 2, 2.5, 3):
            image = icon.pixmap(QSize(20, 20), dpr).toImage()
            extent = round(16 * dpr)
            margin = (image.width() - extent) // 2
            center = margin + extent // 2

            def axis_strip(cross):
                return [image.pixelColor(cross, along).alpha()
                        if name == "flip_horizontal" else image.pixelColor(along, cross).alpha()
                        for along in range(margin, margin + extent)]

            first, second = axis_strip(center - 1), axis_strip(center)
            assert first == second, (name, dpr)
            assert first == first[::-1], (name, dpr)
            assert set(first) == {0, 255}, (name, dpr)


def test_line_endpoint_option_icons_show_the_style_on_the_correct_side(qt_app):
    plain = _opaque_points(line_end_style_icon("none", "start"), 64)
    start_arrow = _opaque_points(line_end_style_icon("arrow", "start"), 64)
    end_circle = _opaque_points(line_end_style_icon("circle", "end"), 64)

    assert start_arrow != plain
    assert end_circle != plain
    assert len({point for point in start_arrow - plain if point[0] < 24}) > 0
    assert len({point for point in end_circle - plain if point[0] > 40}) > 0
