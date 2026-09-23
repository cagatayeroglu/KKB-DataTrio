"""An address the turn itself read is shown however markdown closes it; nothing else is.

Live 2026-09-23 an answer wrote the raw CSV address the turn had just read in backticks,
and the reader saw "[gizli bilgi kaldırıldı]": the address pattern runs to the next space,
so the match ended in the backtick and no longer equalled the address that was read.
"""

import pytest

from kkb_agent.api.projection import safe_text

READ = "https://raw.githubusercontent.com/jbrownlee/Datasets/master/airline-passengers.csv"
HIDDEN = "[gizli bilgi kaldırıldı]"


@pytest.mark.parametrize(
    "written",
    [f"`{READ}`", f"**{READ}**", f"<{READ}>", f"_{READ}_", f"({READ}),", f"`{READ}`."],
)
def test_the_address_the_turn_read_is_shown_however_it_is_closed(written):
    shown = safe_text(f"Kaynak adres okundu: {written} (sonuç a1)", shown_urls=frozenset({READ}))
    assert READ in shown and HIDDEN not in shown


def test_an_address_the_turn_did_not_read_is_still_hidden():
    other = "https://raw.githubusercontent.com/someone/else/data.csv"
    shown = safe_text(f"Bakınız `{other}`", shown_urls=frozenset({READ}))
    assert other not in shown and HIDDEN in shown


def test_a_query_is_still_hidden_even_on_the_read_address():
    shown = safe_text(f"`{READ}?token=abc123`", shown_urls=frozenset({READ}))
    assert "abc123" not in shown and HIDDEN in shown


def test_an_operator_secret_is_still_removed_beside_a_shown_address():
    secret = "sk-local-0123456789abcdef"
    shown = safe_text(f"`{READ}` anahtar {secret}", secrets=(secret,), shown_urls=frozenset({READ}))
    assert READ in shown and secret not in shown
