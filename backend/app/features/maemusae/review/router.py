"""매무새 요구사항 후보 검토 API: /api/mms/projects/{project_id}/documents/{document_id}

| 경로                                              | 누가                          |
| GET    /requirements, /requirements/{id}          | 멤버, 또는 MASTER 보기만        |
| PATCH  /requirements/{id}, PATCH /requirements    | 멤버 (version 필수)             |
| POST   /requirements                              | 멤버 (직접 추가)                |
| DELETE /requirements/{id}                         | 멤버 (직접 추가한 후보만)        |
| PUT·DELETE /requirements/{id}/notes/{field}       | 멤버 (내 입력, 사람마다 한 건)   |
| GET    /notes                                     | 멤버, 또는 MASTER 보기만        |
| GET    /categories                                | 멤버, 또는 MASTER 보기만        |

쓰기를 보기 전용 MASTER 가 부르면 403 PROJECT_MEMBER_REQUIRED, 멤버가 아니면 404 (project_viewer 규칙).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.maemusae.access import ProjectAccess, project_viewer
from app.features.maemusae.review import service
from app.features.maemusae.review.schemas import (
    CategoryPathRead,
    NoteField,
    NoteRead,
    NoteWrite,
    RequirementBulkUpdate,
    RequirementCreate,
    RequirementDetail,
    RequirementListItem,
    RequirementPage,
    RequirementUpdate,
)

router = APIRouter(prefix="/projects/{project_id}/documents/{document_id}", tags=["mms-requirements"])

WRITE_ERRORS = (
    "오류: 403 PROJECT_MEMBER_REQUIRED(보기 전용 MASTER), 404 REQUIREMENT_NOT_FOUND, "
    "409 DOCUMENT_BUSY(분석·확정 중)·DOCUMENT_CONFIRMED"
)


@router.get(
    "/requirements",
    response_model=RequirementPage,
    summary="요구사항 후보 목록 (멤버, 또는 MASTER 보기만)",
    description=(
        "번호 순. 가벼운 칸만 돌려줍니다(설명·근거는 상세). `next_cursor` 가 있으면 `cursor` 로 보내 다음 페이지. "
        "`q` 는 `REQ-012` 처럼 쓰면 번호, 그 밖은 이름으로 찾습니다. `needs_check=true` 는 답 없는 AI 질문·"
        "기본값 표시·위치 확인 필요 근거가 있는 후보만"
    ),
)
def list_requirements(
    document_id: int,
    kind: Annotated[str | None, Query(description="구분 코드")] = None,
    priority: Annotated[str | None, Query(description="우선순위 코드")] = None,
    category_major: Annotated[str | None, Query(max_length=100, description="대분류 (업무 영역) 이름")] = None,
    included: Annotated[bool | None, Query(description="체크된 것만(true) / 해제된 것만(false)")] = None,
    needs_check: Annotated[bool, Query(description="확인 필요만")] = False,
    q: Annotated[str | None, Query(max_length=200, description="번호(REQ-012) 또는 이름")] = None,
    cursor: Annotated[int | None, Query(ge=0, description="이전 응답의 next_cursor")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    access: ProjectAccess = Depends(project_viewer),
    db: Session = Depends(get_db),
):
    return service.list_requirements(
        db, access, document_id, kind=kind, priority=priority, category_major=category_major, included=included,
        needs_check=needs_check,
        q=q, cursor=cursor, limit=limit,
    )


@router.get(
    "/categories",
    response_model=list[CategoryPathRead],
    summary="이 문서에서 쓰는 대·중·소분류와 후보 수 (멤버, 또는 MASTER 보기만). 입력 자동완성·대분류 필터용",
)
def list_categories(document_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.list_categories(db, access, document_id)


@router.get(
    "/requirements/{requirement_id}",
    response_model=RequirementDetail,
    summary="요구사항 후보 상세: 설명, AI 질문, 근거 목록, 입력한 내용 (멤버, 또는 MASTER 보기만)",
)
def get_requirement(
    document_id: int, requirement_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)
):
    return service.get_requirement(db, access, document_id, requirement_id)


@router.patch(
    "/requirements/{requirement_id}",
    response_model=RequirementListItem,
    summary="후보 고치기 (멤버). 보낸 칸만 바뀌고 version +1",
    description=f"`version` 이 다르면 409 REQUIREMENT_CHANGED. 구분·우선순위가 목록에 없으면 400 INVALID_CODE. {WRITE_ERRORS}",
)
def update_requirement(
    document_id: int,
    requirement_id: int,
    body: RequirementUpdate,
    access: ProjectAccess = Depends(project_viewer),
    db: Session = Depends(get_db),
):
    return service.update_requirement(db, access, document_id, requirement_id, body)


@router.patch(
    "/requirements",
    response_model=list[RequirementListItem],
    summary="후보 일괄 고치기 (멤버, 최대 500개). 하나라도 실패하면 아무것도 안 바뀜",
    description=f"version 이 다른 후보가 있으면 409 REQUIREMENT_CHANGED (문구에 번호). {WRITE_ERRORS}",
)
def update_requirements(
    document_id: int,
    body: RequirementBulkUpdate,
    access: ProjectAccess = Depends(project_viewer),
    db: Session = Depends(get_db),
):
    return service.update_requirements(db, access, document_id, body)


@router.post(
    "/requirements",
    response_model=RequirementListItem,
    status_code=status.HTTP_201_CREATED,
    summary="후보 직접 추가 (멤버). 번호는 다음 번호",
    description=WRITE_ERRORS,
)
def create_requirement(
    document_id: int,
    body: RequirementCreate,
    access: ProjectAccess = Depends(project_viewer),
    db: Session = Depends(get_db),
):
    return service.create_requirement(db, access, document_id, body)


@router.delete(
    "/requirements/{requirement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="직접 추가한 후보 지우기 (멤버). AI 후보는 409 REQUIREMENT_NOT_DELETABLE",
)
def delete_requirement(
    document_id: int, requirement_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)
):
    service.delete_requirement(db, access, document_id, requirement_id)


@router.put(
    "/requirements/{requirement_id}/notes/{field}",
    response_model=NoteRead,
    summary="내 입력 남기기·고치기 (멤버, 사람마다 칸마다 한 건). DESCRIPTION 설명 / ANSWER AI 질문 답변",
)
def write_note(
    document_id: int,
    requirement_id: int,
    field: NoteField,
    body: NoteWrite,
    access: ProjectAccess = Depends(project_viewer),
    db: Session = Depends(get_db),
):
    return service.write_note(db, access, document_id, requirement_id, field, body.text)


@router.delete(
    "/requirements/{requirement_id}/notes/{field}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="내 입력 지우기 (멤버)",
)
def delete_note(
    document_id: int,
    requirement_id: int,
    field: NoteField,
    access: ProjectAccess = Depends(project_viewer),
    db: Session = Depends(get_db),
):
    service.delete_note(db, access, document_id, requirement_id, field)


@router.get(
    "/notes",
    response_model=list[NoteRead],
    summary="입력한 내용 목록 (멤버, 또는 MASTER 보기만). 최신순·오래된 순, 작성자, 번호·이름 검색",
)
def list_notes(
    document_id: int,
    order: Annotated[Literal["newest", "oldest"], Query()] = "newest",
    author_id: Annotated[int | None, Query(description="작성자 회원 id")] = None,
    q: Annotated[str | None, Query(max_length=200, description="후보 번호(REQ-012) 또는 이름")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    access: ProjectAccess = Depends(project_viewer),
    db: Session = Depends(get_db),
):
    return service.list_document_notes(
        db, access, document_id, author_id=author_id, q=q, newest_first=order == "newest", limit=limit
    )

