# PDF 제본 샘플 생성 도구

운영자가 로컬 PC에서 여러 PDF를 병합하고, 제본 확인용 워터마크와 PDF 권한 제한을 적용한 샘플 PDF를 생성하는 도구입니다.

## 운영자 사용법

1. 최초 1회 `install_windows.bat`을 실행합니다.
2. 이후에는 `run_windows.bat`을 실행합니다.
3. 브라우저가 열리면 PDF 파일을 업로드합니다.
4. 숫자 입력 또는 위/아래 버튼으로 병합 순서를 맞춥니다.
5. 워터마크 밀도를 선택한 뒤 `PDF 생성`을 누릅니다.
6. `다운로드` 버튼으로 최종 PDF를 저장합니다.
7. 워터마크를 제거해야 할 때는 `워터마크 제거` 탭에서 이 도구가 만든 PDF와 편집 비밀번호를 입력합니다.

## 현재 버전

- Version: `1.1.0`
- Watermark: `열람 출력 제본 확인용 복제 수정 배포금지`
- PDF 권한: 암호 없이 열람 가능, 인쇄/편집/복사/추출 제한

## Streamlit Cloud 설정

GitHub 저장소를 Streamlit Cloud에 연결할 때 main file path는 아래처럼 설정합니다.

```text
app.py
```

별도 Secrets 설정 없이 실행할 수 있습니다. PDF owner password는 앱 내부 기본값을 사용하되, 저장소에는 평문으로 노출하지 않습니다.

## 워터마크 제거 방식

Adobe Acrobat의 워터마크 제거 기능은 이 도구가 페이지 위에 직접 합성한 워터마크를 제거 대상으로 인식하지 못할 수 있습니다.

v1.1.0부터는 새로 생성되는 PDF 안에 워터마크 없는 병합본을 별도로 암호화해 보관합니다. `워터마크 제거` 탭에서 생성된 PDF를 다시 업로드하면 복원 가능한 PDF인지 인식하고, 편집 비밀번호를 입력하면 워터마크 없는 PDF를 다시 다운로드할 수 있습니다.

v1.0.x에서 이미 만든 PDF에는 복원 데이터가 없기 때문에 이 기능으로 제거할 수 없습니다.

## 개발자 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py
```

## 검증

```powershell
.\.venv\Scripts\python.exe tests\smoke_test.py
```

## 배포

GitHub에는 이 폴더의 내용만 별도 저장소로 올리는 것을 권장합니다.

```powershell
make_release_zip.bat
```

생성된 `dist/pdf_binding_sample_tool_v1.1.0.zip` 파일을 GitHub Release에 첨부하면 운영자가 ZIP을 내려받아 사용할 수 있습니다.
