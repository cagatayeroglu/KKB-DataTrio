"""QA-32: the digits of a web address in an answer are part of a name, not claims.

Live 2026-09-23 an answer that gave the right PDF's address was qualified for "2837",
"6161" and the "20" of "%20" in it. Only what lies inside an address is skipped: a figure
beside it, or in a link's label, is still a claim the tools must support.
"""

from kkb_agent.agent.trust_answer import _report
from kkb_agent.agent.verifier import extract_numbers

ODMD = (
    "https://www.odmd.org.tr/folders/2837/categorial1docs/6161/"
    "ODMD%20Bas%C4%B1n%20Bulteni%202%20Eyl%C3%BCl%202026.pdf"
)


def written(text: str) -> list[str]:
    return [number.text for number in extract_numbers(text)]


def test_an_address_alone_holds_no_claim():
    assert written(f"Kaynak: {ODMD}") == []
    reported, _, _ = _report(f"Kaynak: {ODMD}", {}, None, [])
    assert reported == []


def test_a_figure_beside_an_address_is_still_a_claim():
    assert written(f"{ODMD} raporuna göre satışlar 12.345 adet.") == ["12.345"]
    reported, _, _ = _report(f"{ODMD}\nSatışlar 12345 adet.", {}, None, [])
    assert any("12345" in item for item in reported)


def test_a_link_label_is_read_and_its_target_is_not():
    text = f"[Rapor, 20 sayfa]({ODMD}) ve toplam 81.031 adet."
    assert written(text) == ["20", "81.031"]


def test_an_address_ends_at_white_space_and_quotes():
    assert written('"https://example.org/a/2837" 45 adet') == ["45"]
