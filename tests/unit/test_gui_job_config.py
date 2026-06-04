from gui_main import _optional_int_to_entry, _parse_optional_int_entry


def test_optional_max_age_none_displays_as_blank():
    assert _optional_int_to_entry(None) == ""


def test_optional_max_age_number_displays_as_number_text():
    assert _optional_int_to_entry(35) == "35"


def test_blank_max_age_saves_as_unlimited():
    assert _parse_optional_int_entry("", "最大年龄") is None
    assert _parse_optional_int_entry("   ", "最大年龄") is None


def test_invalid_max_age_is_rejected_with_field_name():
    try:
        _parse_optional_int_entry("None", "最大年龄")
    except ValueError as e:
        assert str(e) == "最大年龄必须为数字"
    else:
        raise AssertionError("invalid max age should raise ValueError")
