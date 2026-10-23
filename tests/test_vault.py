import pytest

from gra import vault


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Introduction to tensor core arithmetic", "Introduction to tensor core arithmetic"),
        ("FlashAttention: fast & exact", "FlashAttention fast & exact"),
        ('a/b\\c:d*e?f"g<h>i|j', "abcdefghij"),
        ("C# [draft] ^1", "C draft 1"),
        ("  lots   of\tspace  ", "lots of space"),
        (".hidden", "hidden"),
        ("Résumé – naïve", "Résumé – naïve"),
    ],
)
def test_safe_filename(title, expected):
    assert vault.safe_filename(title) == expected


@pytest.mark.parametrize("title", ["", "   ", "///", "[#]", "..."])
def test_safe_filename_empty(title):
    with pytest.raises(ValueError):
        vault.safe_filename(title)
