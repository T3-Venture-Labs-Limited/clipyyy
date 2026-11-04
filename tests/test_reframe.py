from clipyyy.reframe import Face, center_plan, dominant, face_box, smooth


def test_center_plan_for_landscape_source():
    plan = center_plan(1920, 1080, 9 / 16, None)
    box = plan["crop_boxes"][0]
    assert box["height"] == 1080 and box["width"] == 608
    assert box["x"] == (1920 - 608) // 2


def test_center_plan_square():
    box = center_plan(1920, 1080, 1.0, None)["crop_boxes"][0]
    assert box["width"] == box["height"] == 1080


def test_face_box_stays_inside_frame():
    face = Face(0.9, 0.1, 0.08, 0.15)
    box = face_box(face, 1920, 1080, 1900, 150, 9 / 16)
    assert box["x"] >= 0 and box["x"] + box["width"] <= 1920
    assert box["y"] >= 0 and box["y"] + box["height"] <= 1080


def test_dominant_prefers_largest_face():
    small, big = Face(0.1, 0.1, 0.05, 0.05), Face(0.6, 0.3, 0.2, 0.2)
    assert dominant([small, big]) is big
    assert dominant([]) is None


def test_smooth_averages_neighbours():
    assert smooth([(0, 0), (3, 3), (0, 0)])[1] == (1, 1)
