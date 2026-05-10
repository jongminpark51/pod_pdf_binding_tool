# Changelog

## 1.0.2 - 2026-05-10

- Added an internal default owner password so Streamlit Cloud works without secrets setup.
- Kept the owner password out of the repository as a plaintext string.
- Updated smoke tests to verify default password generation is available.

## 1.0.1 - 2026-05-10

- Restored `app.py` as valid UTF-8 source to fix Streamlit script execution failures.
- Kept Korean UI labels and watermark text in UTF-8.
- Made PDF owner password configurable through Streamlit secrets or the `OWNER_PASSWORD` environment variable.
- Updated smoke tests to use an explicit test owner password.

## 1.0.0 - 2026-05-08

- Added the operator-facing local Streamlit app for PDF sample binding.
- Added multi-PDF upload, merge ordering, front watermarking, and protected PDF download.
- Updated watermark text to `열람 출력 제본 확인용 복제 수정 배포금지`.
- Added watermark density selection: `보통`, `빽빽`, `매우 빽빽`.
- Added manual numeric order input in addition to up/down order controls.
- Added Windows install/run batch files and operator guide.
