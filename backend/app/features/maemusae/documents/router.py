"""매무새 문서·올린 파일 API: /api/mms/projects/{project_id}/documents

| 경로                                         | 누가                      |
| GET  /documents, /documents/{id}             | 멤버, 또는 MASTER 보기만    |
| GET  /documents/{id}/sources                 | 멤버, 또는 MASTER 보기만    |
| POST /documents/{id}/sources                 | 멤버 (파일 또는 직접 쓴 글) |
| GET  /documents/{id}/sources/{sid}/pages     | 멤버만 (고객 문서 본문)     |
| GET  /documents/{id}/sources/{sid}/file      | 멤버만 (원본 내려받기)      |
| DELETE /documents/{id}/sources/{sid}         | 올린 사람 또는 프로젝트 관리자 |

본문·원본은 고객 문서라 MASTER 도 멤버가 아니면 못 봅니다 (project_member 는 멤버가 아니면 404).
"""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.maemusae.access import ProjectAccess, project_member, project_viewer
from app.features.maemusae.config import mms_settings
from app.features.maemusae.documents import service
from app.features.maemusae.documents.schemas import (
    DocumentRead,
    SourcePageRead,
    SourceRead,
)

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["mms-documents"])


@router.get("", response_model=list[DocumentRead], summary="문서(파일 카드) 목록 (멤버, 또는 MASTER 보기만)")
def list_documents(access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.list_documents(db, access)


@router.get("/{document_id}", response_model=DocumentRead, summary="문서 하나 (멤버, 또는 MASTER 보기만)")
def get_document(document_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.get_document(db, access, document_id)


@router.get(
    "/{document_id}/sources", response_model=list[SourceRead], summary="올린 파일 목록 (멤버, 또는 MASTER 보기만)"
)
def list_sources(document_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.list_sources(db, access, document_id)


@router.post(
    "/{document_id}/sources",
    response_model=SourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="파일 올리기 또는 직접 쓴 글 저장 (멤버)",
    description=(
        "multipart/form-data 로 `file` 하나 **또는** `text` 하나를 보냅니다. 파일은 마크다운으로 바꿔 쪽 단위로 "
        "저장하고 원본은 비공개 저장소에 둡니다. 형식: PDF, DOCX, PPTX, XLSX, TXT, MD. "
        "오류: 400 SOURCE_INPUT_REQUIRED, 409 SOURCE_DUPLICATE·SOURCE_LIMIT_REACHED·DOCUMENT_BUSY, "
        "413 FILE_TOO_LARGE, 415 UNSUPPORTED_FILE_TYPE, 422 DOCUMENT_PARSE_FAILED·DOCUMENT_TOO_LONG, "
        "503 STORAGE_NOT_CONFIGURED"
    ),
)
def add_source(
    document_id: int,
    file: Annotated[UploadFile | None, File(description="올릴 파일 (10MB 이하)")] = None,
    text: Annotated[str | None, Form(description="파일 없이 직접 쓴 요구사항 내용")] = None,
    access: ProjectAccess = Depends(project_member),
    db: Session = Depends(get_db),
):
    # 변환이 수 초 걸릴 수 있어 일반 def 로 둡니다 (FastAPI 가 스레드에서 실행, 이벤트 루프를 막지 않음)
    data = file.file.read(mms_settings.mms_source_max_bytes + 1) if file else None  # 한도 +1 바이트로 넘었는지만 확인
    return service.add_source(
        db, access, document_id, filename=file.filename if file else None, data=data, text=text
    )


@router.get(
    "/{document_id}/sources/{source_id}/pages",
    response_model=list[SourcePageRead],
    summary="쪽 단위 본문 (멤버만, 근거 확인용)",
)
def list_pages(
    document_id: int, source_id: int, access: ProjectAccess = Depends(project_member), db: Session = Depends(get_db)
):
    return service.list_pages(db, access, document_id, source_id)


@router.get(
    "/{document_id}/sources/{source_id}/file",
    response_class=Response,
    summary="원본 파일 내려받기 (멤버만)",
    responses={200: {"content": {"application/octet-stream": {}}, "description": "원본 파일"}},
)
def download_original(
    document_id: int, source_id: int, access: ProjectAccess = Depends(project_member), db: Session = Depends(get_db)
):
    source, data = service.read_original(db, access, document_id, source_id)
    fallback = source.filename.encode("ascii", "ignore").decode().replace('"', "") or "file"
    return Response(
        data,
        media_type=source.content_type,
        headers={
            # 항상 내려받기로 (브라우저가 열어 실행하지 않게). 한글 이름은 RFC 5987 형식으로
            "Content-Disposition": f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(source.filename)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete(
    "/{document_id}/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="올린 파일 지우기 (올린 사람 또는 프로젝트 관리자, 원본도 삭제)",
)
def delete_source(
    document_id: int, source_id: int, access: ProjectAccess = Depends(project_member), db: Session = Depends(get_db)
):
    service.delete_source(db, access, document_id, source_id)
