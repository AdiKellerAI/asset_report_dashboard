from app.i18n import translate, translate_message


def test_translate_passes_through_english():
    assert translate("Home", "en") == "Home"


def test_translate_returns_hebrew_for_a_known_string():
    assert translate("Home", "he") == "בית"


def test_translate_falls_back_to_original_for_unknown_string():
    """A missing dict entry degrades gracefully instead of raising or
    showing a blank - important since the taxonomy/labels list will keep
    growing and not every future string will have a translation yet."""
    assert translate("Some Brand New Label Nobody Translated Yet", "he") == "Some Brand New Label Nobody Translated Yet"


def test_translate_message_fills_in_kwargs_after_translating_the_template():
    msg = translate_message("Tax payment for {year} recorded.", "he", year=2025)
    assert msg == "תשלום המס עבור 2025 נרשם."


def test_translate_message_english_passthrough():
    msg = translate_message("Tax payment for {year} recorded.", "en", year=2025)
    assert msg == "Tax payment for 2025 recorded."
