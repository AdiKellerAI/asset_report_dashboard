from app.i18n import translate, translate_message


def test_translate_passes_through_english():
    assert translate("Dashboard", "en") == "Dashboard"


def test_translate_returns_hebrew_for_a_known_string():
    assert translate("Dashboard", "he") == "לוח בקרה"


def test_translate_falls_back_to_original_for_unknown_string():
    """A missing dict entry degrades gracefully instead of raising or
    showing a blank - important since the taxonomy/labels list will keep
    growing and not every future string will have a translation yet."""
    assert translate("Some Brand New Label Nobody Translated Yet", "he") == "Some Brand New Label Nobody Translated Yet"


def test_translate_message_fills_in_kwargs_after_translating_the_template():
    msg = translate_message("Mortgage updated for {name}.", "he", name="Brunswick")
    assert msg == "המשכנתא עודכנה עבור Brunswick."


def test_translate_message_english_passthrough():
    msg = translate_message("Mortgage updated for {name}.", "en", name="Brunswick")
    assert msg == "Mortgage updated for Brunswick."
