from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.constants import UserAccessPermissions
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import UploadedPdf, build_binding_sample, PdfBindingError  # noqa: E402


def make_pdf(label: str, pagesize) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=pagesize)
    pdf.drawString(72, pagesize[1] - 72, label)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def assert_output_permissions(output: bytes) -> None:
    reader = PdfReader(BytesIO(output))
    assert reader.is_encrypted, "output PDF should be encrypted"
    assert reader.decrypt("") in (1, 2), "output PDF should open with empty password"

    permissions = reader.user_access_permissions
    blocked_permissions = [
        UserAccessPermissions.PRINT,
        UserAccessPermissions.MODIFY,
        UserAccessPermissions.EXTRACT,
        UserAccessPermissions.ADD_OR_MODIFY,
        UserAccessPermissions.FILL_FORM_FIELDS,
        UserAccessPermissions.EXTRACT_TEXT_AND_GRAPHICS,
        UserAccessPermissions.ASSEMBLE_DOC,
        UserAccessPermissions.PRINT_TO_REPRESENTATION,
    ]
    assert all(not (permissions & item) for item in blocked_permissions)


def test_merge_and_protection() -> None:
    first = make_pdf("first", A4)
    second = make_pdf("second", landscape(A4))
    output = build_binding_sample(
        [
            UploadedPdf("first", "first.pdf", first, len(first)),
            UploadedPdf("second", "second.pdf", second, len(second)),
        ],
        density_key="very_dense",
    )

    reader = PdfReader(BytesIO(output))
    reader.decrypt("")
    assert len(reader.pages) == 2
    assert_output_permissions(output)


def test_encrypted_input_rejected() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    encrypted = BytesIO()
    writer.encrypt(user_password="secret")
    writer.write(encrypted)
    encrypted_data = encrypted.getvalue()

    try:
        build_binding_sample(
            [UploadedPdf("encrypted", "encrypted.pdf", encrypted_data, len(encrypted_data))]
        )
    except PdfBindingError:
        return

    raise AssertionError("encrypted input should be rejected")


if __name__ == "__main__":
    test_merge_and_protection()
    test_encrypted_input_rejected()
    print("smoke ok")
