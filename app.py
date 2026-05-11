from __future__ import annotations

import hashlib
import math
import secrets as token_secrets
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import streamlit as st
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pypdf import PdfReader, PdfWriter
from pypdf.constants import UserAccessPermissions
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


APP_NAME = "PDF 제본 샘플 생성"
WATERMARK_TEXT = "열람 출력 제본 확인용 복제 수정 배포금지"
OUTPUT_MIME = "application/pdf"
DEFAULT_DENSITY_KEY = "dense"
RESTORE_ATTACHMENT_NAME = "pod_binding_clean_payload.v1.bin"
RESTORE_PAYLOAD_MAGIC = b"POD-PDF-CLEAN-V1\0"
RESTORE_KDF_ITERATIONS = 200_000
RESTORE_SALT_SIZE = 16
RESTORE_NONCE_SIZE = 12
OWNER_PASSWORD_MASK = (0x5B, 0x25, 0x70, 0x0E, 0x3F)
OWNER_PASSWORD_PAYLOAD = (
    0x69,
    0x15,
    0x42,
    0x38,
    0x0F,
    0x68,
    0x14,
    0x43,
    0x2F,
    0x7F,
    0x78,
)

FONT_CANDIDATES = (
    Path(__file__).parent / "assets" / "fonts" / "NanumGothic.ttf",
    Path("C:/Windows/Fonts/malgun.ttf"),
    Path("C:/Windows/Fonts/malgunbd.ttf"),
    Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    Path("/Library/Fonts/AppleGothic.ttf"),
    Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
)


@dataclass(frozen=True)
class WatermarkDensity:
    label: str
    x_gap: float
    y_multiplier: float
    alpha: float
    font_ratio: float
    min_font_size: float
    max_font_size: float


WATERMARK_DENSITIES = {
    "normal": WatermarkDensity(
        label="보통",
        x_gap=48,
        y_multiplier=2.7,
        alpha=0.22,
        font_ratio=0.048,
        min_font_size=20,
        max_font_size=34,
    ),
    "dense": WatermarkDensity(
        label="빽빽",
        x_gap=22,
        y_multiplier=2.0,
        alpha=0.26,
        font_ratio=0.05,
        min_font_size=21,
        max_font_size=36,
    ),
    "very_dense": WatermarkDensity(
        label="매우 빽빽",
        x_gap=8,
        y_multiplier=1.45,
        alpha=0.3,
        font_ratio=0.052,
        min_font_size=22,
        max_font_size=38,
    ),
}


class PdfBindingError(Exception):
    """Raised when an input PDF cannot be merged into the sample output."""


@dataclass(frozen=True)
class UploadedPdf:
    key: str
    name: str
    data: bytes
    size: int


def app_version() -> str:
    version_file = Path(__file__).with_name("VERSION")
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "unknown"


def default_owner_password() -> str:
    mask_size = len(OWNER_PASSWORD_MASK)
    return "".join(
        chr(value ^ OWNER_PASSWORD_MASK[index % mask_size])
        for index, value in enumerate(OWNER_PASSWORD_PAYLOAD)
    )


def derive_restore_key(password: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_restore_payload(clean_pdf: bytes, password: str) -> bytes:
    salt = token_secrets.token_bytes(RESTORE_SALT_SIZE)
    nonce = token_secrets.token_bytes(RESTORE_NONCE_SIZE)
    key = derive_restore_key(password, salt, RESTORE_KDF_ITERATIONS)
    compressed_pdf = zlib.compress(clean_pdf, level=9)
    ciphertext = AESGCM(key).encrypt(nonce, compressed_pdf, RESTORE_PAYLOAD_MAGIC)
    return (
        RESTORE_PAYLOAD_MAGIC
        + struct.pack(">I", RESTORE_KDF_ITERATIONS)
        + salt
        + nonce
        + ciphertext
    )


def decrypt_restore_payload(payload: bytes, password: str) -> bytes:
    if not payload.startswith(RESTORE_PAYLOAD_MAGIC):
        raise PdfBindingError("복원 데이터를 확인할 수 없습니다.")

    offset = len(RESTORE_PAYLOAD_MAGIC)
    header_size = 4 + RESTORE_SALT_SIZE + RESTORE_NONCE_SIZE
    if len(payload) <= offset + header_size:
        raise PdfBindingError("복원 데이터가 손상되었습니다.")

    iterations = struct.unpack(">I", payload[offset : offset + 4])[0]
    offset += 4
    salt = payload[offset : offset + RESTORE_SALT_SIZE]
    offset += RESTORE_SALT_SIZE
    nonce = payload[offset : offset + RESTORE_NONCE_SIZE]
    offset += RESTORE_NONCE_SIZE
    ciphertext = payload[offset:]

    try:
        key = derive_restore_key(password, salt, iterations)
        compressed_pdf = AESGCM(key).decrypt(
            nonce,
            ciphertext,
            RESTORE_PAYLOAD_MAGIC,
        )
        return zlib.decompress(compressed_pdf)
    except (InvalidTag, ValueError, zlib.error) as exc:
        raise PdfBindingError("편집 비밀번호가 맞지 않거나 복원 데이터가 손상되었습니다.") from exc


def build_pdf_key(name: str, data: bytes, occurrence: int) -> str:
    digest = hashlib.sha256(data).hexdigest()[:16]
    return f"{name}:{len(data)}:{digest}:{occurrence}"


def format_bytes(size: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{size} B"


def density_key_from_label(label: str) -> str:
    for key, density in WATERMARK_DENSITIES.items():
        if density.label == label:
            return key
    return DEFAULT_DENSITY_KEY


@lru_cache(maxsize=1)
def get_watermark_font_name() -> str:
    for font_path in FONT_CANDIDATES:
        if not font_path.exists():
            continue

        try:
            pdfmetrics.registerFont(TTFont("WatermarkKorean", str(font_path)))
            return "WatermarkKorean"
        except Exception:
            continue

    return "Helvetica"


@lru_cache(maxsize=256)
def make_watermark_pdf(width: float, height: float, density_key: str) -> bytes:
    density = WATERMARK_DENSITIES.get(
        density_key,
        WATERMARK_DENSITIES[DEFAULT_DENSITY_KEY],
    )
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    font_name = get_watermark_font_name()
    font_size = max(
        density.min_font_size,
        min(density.max_font_size, min(width, height) * density.font_ratio),
    )

    pdf.saveState()
    pdf.setFont(font_name, font_size)
    try:
        pdf.setFillAlpha(density.alpha)
    except Exception:
        pass
    pdf.setFillColor(colors.Color(0.8, 0.0, 0.0))
    pdf.translate(width / 2, height / 2)
    pdf.rotate(35)

    diagonal = math.hypot(width, height)
    text_width = pdf.stringWidth(WATERMARK_TEXT, font_name, font_size)
    x_step = max(text_width + density.x_gap, text_width * 1.03)
    y_step = max(font_size * density.y_multiplier, 34)

    y = -diagonal
    while y <= diagonal:
        x = -diagonal
        while x <= diagonal:
            pdf.drawString(x, y, WATERMARK_TEXT)
            x += x_step
        y += y_step

    pdf.restoreState()
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def make_watermark_page(width: float, height: float, density_key: str):
    watermark_pdf = make_watermark_pdf(round(width, 2), round(height, 2), density_key)
    return PdfReader(BytesIO(watermark_pdf)).pages[0]


def read_pdf(uploaded_pdf: UploadedPdf) -> PdfReader:
    try:
        reader = PdfReader(BytesIO(uploaded_pdf.data))
    except Exception as exc:
        raise PdfBindingError(f"{uploaded_pdf.name}: PDF 파일을 읽을 수 없습니다.") from exc

    if reader.is_encrypted:
        raise PdfBindingError(
            f"{uploaded_pdf.name}: 암호화된 PDF는 처리할 수 없습니다."
        )

    return reader


def build_clean_merged_pdf(pdfs: list[UploadedPdf]) -> bytes:
    writer = PdfWriter()

    for uploaded_pdf in pdfs:
        reader = read_pdf(uploaded_pdf)
        for page in reader.pages:
            try:
                page.transfer_rotation_to_content()
            except Exception:
                pass
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def build_binding_sample(
    pdfs: list[UploadedPdf],
    density_key: str = DEFAULT_DENSITY_KEY,
    owner_password: str | None = None,
) -> bytes:
    if not pdfs:
        raise PdfBindingError("PDF 파일을 1개 이상 선택해 주세요.")

    resolved_owner_password = owner_password or default_owner_password()
    clean_pdf = build_clean_merged_pdf(pdfs)

    writer = PdfWriter()

    for uploaded_pdf in pdfs:
        reader = read_pdf(uploaded_pdf)
        for page in reader.pages:
            try:
                page.transfer_rotation_to_content()
            except Exception:
                pass

            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            watermark_page = make_watermark_page(width, height, density_key)
            try:
                page.merge_page(watermark_page, over=True)
            except TypeError:
                page.merge_page(watermark_page)
            writer.add_page(page)

    writer.add_attachment(
        RESTORE_ATTACHMENT_NAME,
        encrypt_restore_payload(clean_pdf, resolved_owner_password),
    )
    writer.encrypt(
        user_password="",
        owner_password=resolved_owner_password,
        permissions_flag=UserAccessPermissions(0),
        algorithm="AES-256-R5",
    )

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def restore_clean_pdf_from_sample(sample_pdf: bytes, owner_password: str) -> bytes:
    if not owner_password:
        raise PdfBindingError("편집 비밀번호를 입력해 주세요.")

    try:
        reader = PdfReader(BytesIO(sample_pdf))
    except Exception as exc:
        raise PdfBindingError("PDF 파일을 읽을 수 없습니다.") from exc

    if reader.is_encrypted:
        if reader.decrypt(owner_password) == 0:
            reader.decrypt("")

    try:
        payloads = reader.attachments.get(RESTORE_ATTACHMENT_NAME)
    except Exception as exc:
        raise PdfBindingError("복원 데이터를 읽을 수 없습니다.") from exc

    if not payloads:
        raise PdfBindingError("복원 데이터가 없습니다. v1.1.0 이후 생성된 PDF만 복원할 수 있습니다.")

    return decrypt_restore_payload(payloads[0], owner_password)


def has_restore_payload(sample_pdf: bytes) -> bool:
    try:
        reader = PdfReader(BytesIO(sample_pdf))
        if reader.is_encrypted:
            reader.decrypt("")
        payloads = reader.attachments.get(RESTORE_ATTACHMENT_NAME)
    except Exception:
        return False

    return bool(payloads)


def current_uploaded_pdfs(uploaded_files) -> list[UploadedPdf]:
    if not uploaded_files:
        return []

    seen: dict[str, int] = {}
    result: list[UploadedPdf] = []

    for uploaded_file in uploaded_files:
        data = uploaded_file.getvalue()
        digest = hashlib.sha256(data).hexdigest()[:16]
        base_key = f"{uploaded_file.name}:{len(data)}:{digest}"
        occurrence = seen.get(base_key, 0) + 1
        seen[base_key] = occurrence

        result.append(
            UploadedPdf(
                key=build_pdf_key(uploaded_file.name, data, occurrence),
                name=uploaded_file.name,
                data=data,
                size=len(data),
            )
        )

    return result


def clear_generated_pdf() -> None:
    st.session_state.generated_pdf = None
    st.session_state.generated_filename = None


def sync_file_order(pdfs: list[UploadedPdf]) -> None:
    current_keys = [pdf.key for pdf in pdfs]
    old_signature = st.session_state.get("upload_signature")
    new_signature = "|".join(current_keys)

    if old_signature != new_signature:
        clear_generated_pdf()
        st.session_state.upload_signature = new_signature

    current_key_set = set(current_keys)
    order = [
        key
        for key in st.session_state.get("file_order", [])
        if key in current_key_set
    ]

    for key in current_keys:
        if key not in order:
            order.append(key)

    st.session_state.file_order = order


def ordered_pdfs(pdfs: list[UploadedPdf]) -> list[UploadedPdf]:
    by_key = {pdf.key: pdf for pdf in pdfs}
    return [by_key[key] for key in st.session_state.file_order if key in by_key]


def move_file(index: int, direction: int) -> None:
    order = st.session_state.file_order
    target_index = index + direction
    if target_index < 0 or target_index >= len(order):
        return

    order[index], order[target_index] = order[target_index], order[index]
    st.session_state.file_order = order
    st.session_state.order_input_signature = None
    clear_generated_pdf()


def position_input_key(pdf_key: str) -> str:
    return f"position_{hashlib.sha256(pdf_key.encode('utf-8')).hexdigest()[:16]}"


def sync_position_inputs(pdfs: list[UploadedPdf]) -> None:
    order_signature = "|".join(pdf.key for pdf in pdfs)
    if st.session_state.get("order_input_signature") == order_signature:
        return

    for index, pdf in enumerate(pdfs):
        st.session_state[position_input_key(pdf.key)] = index + 1

    st.session_state.order_input_signature = order_signature


def apply_manual_order(pdfs: list[UploadedPdf]) -> None:
    order_pairs = []
    for index, pdf in enumerate(pdfs):
        requested_order = int(st.session_state[position_input_key(pdf.key)])
        changed_priority = 0 if requested_order != index + 1 else 1
        order_pairs.append((requested_order, changed_priority, index, pdf.key))

    order_pairs.sort()
    st.session_state.file_order = [item[3] for item in order_pairs]
    st.session_state.order_input_signature = None
    clear_generated_pdf()


def render_file_order(pdfs: list[UploadedPdf]) -> None:
    st.subheader("병합 순서")
    sync_position_inputs(pdfs)

    with st.form("manual_order_form"):
        header_cols = st.columns([1, 5.4, 1.3])
        header_cols[0].caption("순서")
        header_cols[1].caption("파일명")
        header_cols[2].caption("크기")

        for pdf in pdfs:
            cols = st.columns([1, 5.4, 1.3])
            cols[0].number_input(
                "순서",
                min_value=1,
                max_value=len(pdfs),
                step=1,
                key=position_input_key(pdf.key),
                label_visibility="collapsed",
            )
            cols[1].write(pdf.name)
            cols[2].write(format_bytes(pdf.size))

        if st.form_submit_button("숫자 순서 적용"):
            apply_manual_order(pdfs)
            st.rerun()

    for index, pdf in enumerate(pdfs):
        cols = st.columns([0.55, 0.55, 5.2, 1.3])
        with cols[0]:
            if st.button("↑", key=f"up_{pdf.key}", disabled=index == 0):
                move_file(index, -1)
                st.rerun()
        with cols[1]:
            if st.button(
                "↓",
                key=f"down_{pdf.key}",
                disabled=index == len(pdfs) - 1,
            ):
                move_file(index, 1)
                st.rerun()
        cols[2].write(f"{index + 1}. {pdf.name}")
        cols[3].write(format_bytes(pdf.size))


def render_create_tab() -> None:
    density_labels = [density.label for density in WATERMARK_DENSITIES.values()]
    default_density_index = density_labels.index(
        WATERMARK_DENSITIES[DEFAULT_DENSITY_KEY].label
    )
    selected_density_label = st.selectbox(
        "워터마크 밀도",
        density_labels,
        index=default_density_index,
    )
    density_key = density_key_from_label(selected_density_label)

    uploaded_files = st.file_uploader(
        "PDF 파일",
        type=["pdf"],
        accept_multiple_files=True,
        key="pdf_uploads",
    )

    if "file_order" not in st.session_state:
        st.session_state.file_order = []
    if "generated_pdf" not in st.session_state:
        st.session_state.generated_pdf = None
    if "generated_filename" not in st.session_state:
        st.session_state.generated_filename = None

    pdfs = current_uploaded_pdfs(uploaded_files)
    sync_file_order(pdfs)
    ordered = ordered_pdfs(pdfs)

    if ordered:
        render_file_order(ordered)

        if st.button("PDF 생성", type="primary"):
            clear_generated_pdf()
            try:
                with st.spinner("PDF 생성 중"):
                    st.session_state.generated_pdf = build_binding_sample(
                        ordered,
                        density_key=density_key,
                    )
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.session_state.generated_filename = (
                        f"binding_sample_{timestamp}.pdf"
                    )
                st.success("생성 완료")
            except PdfBindingError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"PDF 생성 중 오류가 발생했습니다: {exc}")

    if st.session_state.generated_pdf:
        st.download_button(
            "다운로드",
            data=st.session_state.generated_pdf,
            file_name=st.session_state.generated_filename,
            mime=OUTPUT_MIME,
            type="primary",
        )


def render_restore_tab() -> None:
    uploaded_file = st.file_uploader(
        "복원할 PDF 파일",
        type=["pdf"],
        key="restore_pdf",
    )
    owner_password = st.text_input(
        "편집 비밀번호",
        type="password",
        key="restore_owner_password",
    )

    if uploaded_file is not None:
        if has_restore_payload(uploaded_file.getvalue()):
            st.success("복원 가능한 PDF로 인식했습니다.")
        else:
            st.warning("복원 데이터가 없는 PDF입니다. v1.1.0 이후 이 도구에서 생성한 PDF만 복원할 수 있습니다.")

    if "restored_pdf" not in st.session_state:
        st.session_state.restored_pdf = None
    if "restored_filename" not in st.session_state:
        st.session_state.restored_filename = None

    if st.button("워터마크 제거", type="primary"):
        st.session_state.restored_pdf = None
        st.session_state.restored_filename = None

        if uploaded_file is None:
            st.error("PDF 파일을 선택해 주세요.")
        else:
            try:
                with st.spinner("복원 중"):
                    st.session_state.restored_pdf = restore_clean_pdf_from_sample(
                        uploaded_file.getvalue(),
                        owner_password,
                    )
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    st.session_state.restored_filename = (
                        f"binding_clean_{timestamp}.pdf"
                    )
                st.success("복원 완료")
            except PdfBindingError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"복원 중 오류가 발생했습니다: {exc}")

    if st.session_state.restored_pdf:
        st.download_button(
            "워터마크 제거본 다운로드",
            data=st.session_state.restored_pdf,
            file_name=st.session_state.restored_filename,
            mime=OUTPUT_MIME,
            type="primary",
        )


def render_app() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide")

    st.title(APP_NAME)
    st.caption(f"v{app_version()}")

    create_tab, restore_tab = st.tabs(["PDF 생성", "워터마크 제거"])
    with create_tab:
        render_create_tab()
    with restore_tab:
        render_restore_tab()


if __name__ == "__main__":
    render_app()
