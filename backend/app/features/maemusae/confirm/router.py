"""매무새 요구사항 확정 API (M4-1): /api/mms/projects/{project_id}

| 경로                                                      | 누가                    | 설명                              |
| POST /documents/{document_id}/confirm                     | 프로젝트 관리자          | 요구사항 확정 (체크된 후보만)       |
| POST /documents/{document_id}/reopen                      | 프로젝트 관리자          | 확정 후 수정 (문서를 다시 READY 로) |
| GET  /confirmed                                           | 멤버, 또는 MASTER 보기만 | 확정한 문서 목록 (최신순)           |
| GET  /documents/{document_id}/versions/{version_id}/excel | 멤버                    | 확정 기록을 Excel 로 받기           |

확정 내용은 버전 API(GET …/versions/{version_id})로 읽습니다. 관리자 검사는 analysis 와 같게 project_viewer 로 받고
service 가 막습니다: 보기 전용 MASTER 는 404 대신 403 PROJECT_MEMBER_REQUIRED, 일반 멤버는 403 PROJECT_ADMIN_REQUIRED.
"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.maemusae.access import ProjectAccess, project_viewer
from app.features.maemusae.confirm import service
from app.features.maemusae.confirm.schemas import ConfirmedDocument, ConfirmResult

router = APIRouter(prefix="/projects/{project_id}", tags=["mms-confirm"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post(
    "/documents/{document_id}/confirm",
    response_model=ConfirmResult,
    status_code=status.HTTP_201_CREATED,
    summary="요구사항 확정 (프로젝트 관리자). 체크된 후보·근거·입력을 확정 기록으로 남기고 문서를 확정됨으로",
    description=(
        "AI 질문·'AI 값 확인'이 남아 있어도 막지 않습니다 (문서 응답의 open_question_count·defaulted_count 로 미리 경고). "
        "확정한 후보의 'AI 값 확인' 표시는 풀립니다. "
        "오류: 400 NOTHING_TO_CONFIRM(체크된 후보 없음), 403 PROJECT_ADMIN_REQUIRED·PROJECT_MEMBER_REQUIRED(보기 전용 MASTER), "
        "409 DOCUMENT_BUSY(분석 중)·DOCUMENT_CONFIRMED(이미 확정)·DOCUMENT_NOT_READY(시작 전·분석 실패)"
    ),
)
def confirm(document_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.confirm(db, access, document_id)


@router.post(
    "/documents/{document_id}/reopen",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="확정 후 수정 (프로젝트 관리자). 문서를 다시 고칠 수 있게 함, 확정 기록은 그대로",
    description=(
        "다음 확정은 확정 번호가 1 올라갑니다 (수정 후 확정). "
        "오류: 403 PROJECT_ADMIN_REQUIRED·PROJECT_MEMBER_REQUIRED, 409 DOCUMENT_NOT_CONFIRMED"
    ),
)
def reopen(document_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    service.reopen(db, access, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/confirmed",
    response_model=list[ConfirmedDocument],
    summary="확정한 문서 목록 (멤버, 또는 MASTER 보기만). 확정할 때마다 한 줄, 최신순",
)
def list_confirmed(access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.list_confirmed(db, access)


@router.get(
    "/documents/{document_id}/versions/{version_id}/excel",
    response_class=Response,
    responses={200: {"content": {XLSX: {}}, "description": "요구사항정의서 .xlsx"}},
    summary="확정 기록을 Excel 로 받기 (멤버). 확정 뒤 후보를 고쳐도 이 파일은 그대로",
    description=(
        "로그인 토큰이 필요하므로 화면은 fetch 로 받아 저장합니다. "
        "오류: 403 PROJECT_MEMBER_REQUIRED(보기 전용 MASTER), 404 CONFIRMED_VERSION_NOT_FOUND(확정 기록이 아님)"
    ),
)
def download_excel(
    document_id: int, version_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)
):
    filename, data = service.build_excel(db, access, document_id, version_id)
    fallback = f"requirements_{version_id}.xlsx"
    return Response(
        data,
        media_type=XLSX,
        headers={
            # 한글 이름은 RFC 5987 형식으로. 고객 문서라 캐시하지 않음
            "Content-Disposition": f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
