"""M7-18 literal quotation: fake I/O, real Session and proof binding."""

import io

import pytest
from openpyxl import Workbook
from pdf_builder import build, ruled_table
from test_document_check import QUESTION, FakeFetch, plan, run

from kkb_agent import live_check
from kkb_agent.agent import Session, ToolRegistry
from kkb_agent.agent.literal import literal_text
from kkb_agent.agent.loop import render_result
from kkb_agent.agent.verifier import Binding, gate_answer, verify_claims
from kkb_agent.core import ClaimKind, ResultKind, Scale
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.llm import scripted
from kkb_agent.tools.web_url import make_web_url_tool

QUOTE = "Kaynak hücredeki değer: 18,22. Kaynak birim veya ölçek belirtmiyor."
CSV = b"Tarih,Tutar\n2026-01-31,18.22\n"


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live calls")

    monkeypatch.setattr("socket.socket.connect", forbidden)
    monkeypatch.setattr(live_check.KloudeksProvider, "from_env", forbidden)


@pytest.mark.parametrize(
    "draft",
    [
        "18.22%",
        "18.22 USD",
        "18.22 million",
        QUOTE.replace("18,22", "18,23"),
        "result_id=wrong: " + QUOTE,
        "Enflasyondan arındırılmış " + QUOTE,
        QUOTE + " Enflasyondan arındırılmıştır.",
        QUOTE + " Endeks değeridir.",
        QUOTE + " TRY serisinden yüzde 7 arttı.",
        QUOTE + " Dönüştürülmüş değer.",
        "Kaynak okundu.",
        "18.22",
    ],
)
def test_unknown_requires_exact_uninterpreted_quotation(tmp_path, draft):
    report = run(tmp_path, draft, fetch=FakeFetch(CSV))
    assert not report["passed"]
    assert report["document_numeric_claims"] == 0


@pytest.fixture
def selected(tmp_path):
    with open_lakehouse(tmp_path / "proof") as lake:
        registry = ToolRegistry()
        registry.register(make_web_url_tool(fetch=FakeFetch(CSV), lineage=lake.lineage))
        answered = Session(scripted(plan(), QUOTE), registry).answer(QUESTION, lake.connection)
        yield answered, lake


def test_literal_identity_and_writer_context(selected):
    answered, lake = selected
    result = answered.results[0]
    assert result.claim_kind is ClaimKind.LITERAL_SOURCE_VALUE
    assert result.values[0].unit is None and result.values[0].scale is Scale.UNKNOWN
    assert QUOTE in render_result(result)
    assert "UNAVAILABLE" in render_result(result)
    claim = answered.answer.verdict.numbers[0]
    assert claim.supported and claim.binding is Binding.RESULT
    assert claim.result_id == result.result_id
    assert claim.lineage_node == result.evidence.lineage_node
    assert result.result_id not in answered.answer.text
    assert result.evidence.lineage_node not in answered.answer.text
    assert result.result_id not in render_result(result)
    assert not verify_claims(QUOTE, result).accepted  # no store is not proof


@pytest.mark.parametrize(
    "mutation",
    [
        "identity",
        "value",
        "row",
        "column",
        "header",
        "cell_text",
        "source",
        "node",
        "edge",
        "stored_snapshot",
        "kind",
        "method",
        "extra_transform",
    ],
)
def test_literal_proof_cannot_be_reused_or_tampered(selected, mutation):
    answered, lake = selected
    result = answered.results[0]
    if mutation == "identity":
        result = result.model_copy(update={"result_id": "other-result"})
    elif mutation == "value":
        result = result.model_copy(
            update={"values": [result.values[0].model_copy(update={"value": 18.23})]}
        )
    elif mutation in {"row", "column", "header", "cell_text"}:
        key = {"row": "row_index", "column": "column_index"}.get(mutation, mutation)
        result = result.model_copy(
            update={
                "parameters": {
                    **result.parameters,
                    key: 999 if mutation in {"row", "column"} else "other",
                }
            }
        )
    elif mutation == "source":
        result = result.model_copy(
            update={
                "evidence": result.evidence.model_copy(
                    update={
                        "sources": [
                            result.evidence.sources[0].model_copy(
                                update={"content_hash": "sha256:wrong"}
                            )
                        ]
                    }
                )
            }
        )
    elif mutation == "node":
        result = result.model_copy(
            update={"evidence": result.evidence.model_copy(update={"lineage_node": "missing"})}
        )
    elif mutation == "edge":
        lake.connection.execute("DELETE FROM lineage_edges")
    elif mutation == "stored_snapshot":
        lake.connection.execute("UPDATE lineage_nodes SET attributes='{}' WHERE kind='transform'")
    elif mutation == "kind":
        result = result.model_copy(update={"kind": ResultKind.CHANGE})
    elif mutation == "method":
        result = result.model_copy(update={"method": "deflation"})
    else:
        result = result.model_copy(
            update={"parameters": {**result.parameters, "transformation": "normalize"}}
        )
    assert not gate_answer(QUOTE, result, lake.connection).presentable


@pytest.mark.parametrize("unit,scale", [(None, Scale.ONE), ("USD", Scale.UNKNOWN)])
def test_analytical_permissions_never_inherit_literal(selected, unit, scale):
    answered, lake = selected
    original = answered.results[0]
    result = original.model_copy(
        update={
            "claim_kind": ClaimKind.ANALYTICAL_VALUE,
            "values": [original.values[0].model_copy(update={"unit": unit, "scale": scale})],
        }
    )
    assert literal_text(result) is None
    gated = gate_answer(QUOTE, result, lake.connection)
    assert "18,22" not in gated.text
    assert not any(item.supported for item in gated.verdict.numbers)


@pytest.mark.parametrize("kind", ["csv", "xlsx", "pdf"])
def test_formats_share_unknown_literal_policy(tmp_path, kind):
    rows = [["Tarih", "Tutar"], ["2026-01-31", "18.22"]]
    if kind == "csv":
        content, media = CSV, "text/csv"
    elif kind == "xlsx":
        book = Workbook()
        for row in rows:
            book.active.append(row)
        out = io.BytesIO()
        book.save(out)
        content, media = (
            out.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        content, media = build([ruled_table(50, 700, rows)]), "application/pdf"
    assert run(tmp_path, QUOTE, fetch=FakeFetch(content, media))["passed"]


def test_general_value_not_a_smoke_special_case(tmp_path):
    assert run(
        tmp_path, QUOTE.replace("18,22", "27,41"), fetch=FakeFetch(CSV.replace(b"18.22", b"27.41"))
    )["passed"]


def test_known_literal_preserves_unit_checks(tmp_path):
    csv = CSV.replace(b"Tutar", b"Tutar (USD)")
    assert run(tmp_path, "18,22 USD", fetch=FakeFetch(csv))["passed"]


def test_unknown_literal_document_is_supported(tmp_path):
    report = run(
        tmp_path,
        "Kaynak hücredeki değer: 18,22. Kaynak birim veya ölçek belirtmiyor.",
        fetch=FakeFetch(b"Tarih,Tutar\n2026-01-31,18.22\n"),
    )
    assert report["passed"] is True
    assert report["document_numeric_claims"] == 1


def test_internal_handles_are_withheld_even_without_a_claim(selected):
    answered, lake = selected
    result = answered.results[0]
    for handle in (result.result_id, result.evidence.lineage_node, result.evidence.input_refs[0]):
        gated = gate_answer(handle, result, lake.connection)
        assert not gated.presentable
        assert handle not in gated.text


def test_plain_analytical_known_unit_unchanged(selected):
    answered, lake = selected
    result = answered.results[0]
    analytical = result.model_copy(
        update={
            "claim_kind": ClaimKind.ANALYTICAL_VALUE,
            "tool": "analytical",
            "method": "test",
            "values": [result.values[0].model_copy(update={"unit": "USD", "scale": Scale.ONE})],
            "unresolved_semantics": [],
        }
    )
    assert gate_answer("18,22 USD", analytical, lake.connection).presentable
    assert not gate_answer("18,22 milyon USD", analytical, lake.connection).presentable


def test_explicit_transformation_and_missing_source_are_ineligible(selected):
    from kkb_agent.core import TransformationRecord

    answered, lake = selected
    result = answered.results[0]
    changed = result.model_copy(
        update={
            "evidence": result.evidence.model_copy(
                update={
                    "transformations": [
                        TransformationRecord(
                            operation="deflate", input_refs=["input"], output_ref="output"
                        )
                    ]
                }
            )
        }
    )
    assert not gate_answer(QUOTE, changed, lake.connection).presentable
    source_only = result.model_copy(
        update={"evidence": result.evidence.model_copy(update={"lineage_node": None})}
    )
    assert not gate_answer(QUOTE, source_only, lake.connection).presentable


def test_claim_mode_is_not_a_tool_argument():
    from pydantic import ValidationError

    from kkb_agent.tools.web_url import WebUrlArguments

    with pytest.raises(ValidationError):
        WebUrlArguments(url="https://example.test/file.csv", claim_kind="literal_source_value")
