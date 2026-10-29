import pytest

from whynot.create.locale import language_groups, language_of, unmapped


def test_groups_follow_countries_in_order():
    assert language_groups(["gb", "FR", "BE", "US", "DE"]) == {"en": ["GB", "US"], "fr": ["FR", "BE"], "de": ["DE"]}


def test_override_and_unknown():
    assert language_groups(["FR", "GB"], override="en") == {"en": ["FR", "GB"]}
    with pytest.raises(ValueError, match="unknown language"):
        language_groups(["FR"], override="klingon")
    assert language_of("JP") == "en" and unmapped(["JP", "FR"]) == ["JP"]
