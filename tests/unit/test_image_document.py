"""DEC-179: a picture is admitted and read as a one-page scanned document.

Organizer cases include images (a screenshot of a table, a scanned page). The PDF path already
renders a page without a text layer and hands it to the OCR model; an image is wrapped into
exactly such a page, so nothing downstream knows a picture from a scan. Pictures here are
drawn by the test; no network and no model.
"""

import io

import pytest
from PIL import Image
from test_pdf_ocr import FakeOcr

from kkb_agent.core import SourceRef
from kkb_agent.image_document import image_to_pdf
from kkb_agent.ingest.fetched import DOCUMENT_MEDIA_TYPES, load_document
from kkb_agent.ingestion_policy import (
    DEFAULT_LIMITS,
    AdmissionError,
    FileKind,
    RejectionCode,
    admit_upload,
)

SOURCE = SourceRef(source_id="upload:test", source_type="upload", locator="opaque:upload")


def picture(size=(640, 360), mode="RGB", fmt="PNG", color=(250, 250, 250)):
    image = Image.new(mode, size, color if mode == "RGB" else (*color, 0))
    output = io.BytesIO()
    image.save(output, format=fmt)
    return output.getvalue()


def rendered_size(pdf: bytes) -> tuple[int, int]:
    import pypdfium2 as pdfium

    with pdfium.PdfDocument(pdf) as document:
        assert len(document) == 1
        page = document[0]
        try:
            bitmap = page.render(scale=2.0)
            try:
                return bitmap.width, bitmap.height
            finally:
                bitmap.close()
        finally:
            page.close()


def test_a_picture_becomes_one_page_that_renders_back_to_its_own_pixels():
    pdf = image_to_pdf(picture((640, 360)), "png", DEFAULT_LIMITS)
    assert pdf.startswith(b"%PDF-") and rendered_size(pdf) == (640, 360)
    jpeg = image_to_pdf(picture((300, 200), fmt="JPEG"), "jpg", DEFAULT_LIMITS)
    assert rendered_size(jpeg) == (300, 200)
    # Transparency is flattened onto white, never onto black text-hiding pixels.
    assert image_to_pdf(picture((64, 64), mode="RGBA"), "png", DEFAULT_LIMITS).startswith(b"%PDF-")


def test_a_large_picture_is_reduced_to_what_one_ocr_page_may_hold():
    width, height = rendered_size(image_to_pdf(picture((4000, 3000)), "png", DEFAULT_LIMITS))
    assert width * height <= 4_000_000 and abs(width / height - 4 / 3) < 0.01


@pytest.mark.parametrize(
    ("content", "kind", "code"),
    [
        (b"GIF89a" + b"\0" * 64, "png", RejectionCode.FORMAT_MISMATCH),
        (picture()[:40], "png", RejectionCode.FORMAT_MISMATCH),
        (picture(fmt="JPEG"), "png", RejectionCode.FORMAT_MISMATCH),
        (picture(), "gif", RejectionCode.UNSUPPORTED_FORMAT),
    ],
)
def test_what_is_not_the_picture_it_claims_to_be_is_refused(content, kind, code):
    with pytest.raises(AdmissionError) as refused:
        image_to_pdf(content, kind, DEFAULT_LIMITS)
    assert refused.value.code is code


def test_an_uploaded_picture_is_admitted_as_the_page_it_was_wrapped_into():
    admitted = admit_upload(io.BytesIO(picture()), filename="ekran.png", content_type="image/png")
    assert admitted.kind is FileKind.PDF and admitted.content.startswith(b"%PDF-")
    with pytest.raises(AdmissionError):
        admit_upload(io.BytesIO(picture()), filename="ekran.png", content_type="image/jpeg")
    with pytest.raises(AdmissionError):
        admit_upload(io.BytesIO(b"not a picture"), filename="x.jpg", content_type="image/jpeg")


def test_a_picture_is_read_by_the_ocr_model_like_a_scanned_page():
    table = (
        "Altın işlemleri<table><tr><td>Ay</td><td>Hacim</td></tr>"
        "<tr><td>Ocak</td><td>10</td></tr><tr><td>Şubat</td><td>15</td></tr>"
        "<tr><td>Toplam</td><td>25</td></tr></table>"
    )
    ocr = FakeOcr(text=table)
    assert "image/png" in DOCUMENT_MEDIA_TYPES and "image/jpeg" in DOCUMENT_MEDIA_TYPES
    loaded = load_document(picture((800, 400)), "image/png", source=SOURCE, ocr=ocr)
    (page,) = loaded.document.pages
    assert len(ocr.calls) == 1 and "Altın işlemleri" in page.ocr_text
    (found,) = page.ocr_tables
    assert found.kind == "ocr" and ["Ocak", "10"] in [list(row) for row in found.rows]
    # Without an OCR model a picture has nothing to read, and says so like a scan does.
    unread = load_document(picture(), "image/png", source=SOURCE)
    assert (unread.status, unread.code) == ("rejected", "NO_TEXT_LAYER")


def test_the_upload_route_takes_a_picture_and_stores_the_page(tmp_path):
    from fastapi.testclient import TestClient
    from test_catalog_continuation import CATALOG, seed_prepared
    from test_conversation_persistence import open_conversation, owner
    from test_document_dataset import BASE

    from kkb_agent.api.app import create_app
    from kkb_agent.api.prepared import PreparedRunner
    from kkb_agent.api.service import AnalysisService
    from kkb_agent.api.store import DATABASE_NAME, ConversationStore
    from kkb_agent.llm import scripted

    root = tmp_path.resolve() / "prepared"
    seed_prepared(root)
    store = ConversationStore(tmp_path.resolve() / "state" / DATABASE_NAME)
    runner = PreparedRunner(
        scripted(),
        root,
        tmp_path.resolve() / "state" / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        document_uploads=True,
        store=store,
    )
    service = AnalysisService(
        runner, mode="scripted", document_store=runner.admit_document, store=store
    )
    with TestClient(create_app(service, prepared=runner.status), base_url=BASE) as client:
        sid, headers, _ = open_conversation(client, owner(client))
        sent = client.post(
            f"/v1/sessions/{sid}/documents",
            content=picture((320, 200), fmt="JPEG"),
            headers={**headers, "Content-Type": "image/jpeg"},
        )
        assert sent.status_code == 201, sent.text
        assert sent.json()["document_format"] == "pdf"
        refused = client.post(
            f"/v1/sessions/{sid}/documents",
            content=b"GIF89a" + b"\0" * 32,
            headers={**headers, "Content-Type": "image/gif"},
        )
        assert refused.status_code == 415
        broken = client.post(
            f"/v1/sessions/{sid}/documents",
            content=b"\x89PNG\r\n\x1a\n" + b"\0" * 32,
            headers={**headers, "Content-Type": "image/png"},
        )
        assert broken.status_code == 422
    store.close()
