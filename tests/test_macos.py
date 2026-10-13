from fshot.platforms.macos import (
    _ax_ancestry_has_any_role,
    _intersect_rects,
    _tuple_rect_contains,
)


def test_intersect_rects_clips_accessibility_bounds_to_window() -> None:
    assert _intersect_rects((10, 0, 678, 650), (10, 25, 678, 625)) == (
        10,
        25,
        678,
        625,
    )


def test_intersect_rects_rejects_disjoint_bounds() -> None:
    assert _intersect_rects((0, 0, 10, 10), (20, 20, 10, 10)) is None


def test_link_role_is_detected_on_accessibility_parent() -> None:
    class Accessibility:
        kAXErrorSuccess = 0
        kAXRoleAttribute = "role"
        kAXParentAttribute = "parent"

        @staticmethod
        def AXUIElementCopyAttributeValue(element, attribute, _placeholder):
            value = element.get(attribute)
            return (0, value) if value is not None else (1, None)

    link = {"role": "AXLink"}
    text = {"role": "AXStaticText", "parent": link}
    assert _ax_ancestry_has_any_role(text, {"AXLink", "AXWebArea"}, Accessibility)


def test_web_area_role_is_detected_above_nested_page_content() -> None:
    class Accessibility:
        kAXErrorSuccess = 0
        kAXRoleAttribute = "role"
        kAXParentAttribute = "parent"

        @staticmethod
        def AXUIElementCopyAttributeValue(element, attribute, _placeholder):
            value = element.get(attribute)
            return (0, value) if value is not None else (1, None)

    web_area = {"role": "AXWebArea"}
    group = {"role": "AXGroup", "parent": web_area}
    text = {"role": "AXStaticText", "parent": group}
    assert _ax_ancestry_has_any_role(text, {"AXWebArea"}, Accessibility)


def test_hit_test_target_must_contain_cursor() -> None:
    status_url = (0, 1030, 620, 20)
    assert not _tuple_rect_contains(status_url, 245, 290)
    assert _tuple_rect_contains(status_url, 245, 1035)


def test_public_ax_role_strings_work_without_exported_constants() -> None:
    class Accessibility:
        kAXErrorSuccess = 0
        kAXRoleAttribute = "role"
        kAXParentAttribute = "parent"

        @staticmethod
        def AXUIElementCopyAttributeValue(element, attribute, _placeholder):
            value = element.get(attribute)
            return (0, value) if value is not None else (1, None)

    assert not hasattr(Accessibility, "kAXLinkRole")
    assert _ax_ancestry_has_any_role(
        {"role": "AXLink"},
        {getattr(Accessibility, "kAXLinkRole", "AXLink")},
        Accessibility,
    )


def test_hit_test_uses_underlying_application_not_overlay(monkeypatch):
    import sys
    from types import SimpleNamespace
    from fshot.platforms import macos

    roots = []
    ax = SimpleNamespace(
        kAXErrorSuccess=0,
        AXUIElementCreateApplication=lambda pid: ("app", pid),
        AXUIElementCopyElementAtPosition=lambda root, *args: (roots.append(root) or (0, "control")),
        AXUIElementGetPid=lambda *args: (0, 123),
    )
    monkeypatch.setitem(sys.modules, "ApplicationServices", ax)
    monkeypatch.setattr(macos, "_frameworks", lambda: (None, None))
    monkeypatch.setattr(macos, "_window_target_at_point", lambda *args: ((0, 0, 500, 500), 456, 123))
    monkeypatch.setattr(macos, "_ax_element_bounds", lambda *args: (10, 20, 100, 40))
    bounds, target = macos.capture_target_at_point(20, 30)
    assert roots == [("app", 123)]
    assert bounds == (10, 20, 100, 40)
    assert target.element == "control"
