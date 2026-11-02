"""매무새 요구사항정의서 버전 API: /api/mms/projects/{project_id}/documents/{document_id}/versions

| 경로                        | 누가                    | 설명                                                 |
| POST /versions              | 멤버                    | 버전 추가 (무조건 새 버전)                            |
| PUT  /versions/latest       | 멤버                    | 버전 저장 (이번 분석 이후 마지막 버전을 덮어씀, 없으면 새 버전) |
| GET  /versions              | 멤버, 또는 MASTER 보기만 | 버전 기록 목록 (최신순)                               |
| GET  /versions/{version_id} | 멤버, 또는 MASTER 보기만 | 그 버전 내용 (읽기 전용)                              |
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.maemusae.access import ProjectAccess, project_viewer
from app.features.maemusae.versions import service
from app.features.maemusae.versions.schemas import (
    VersionDetail,
    VersionListItem,
    VersionSaved,
)

router = APIRouter(prefix="/projects/{project_id}/documents/{document_id}/versions", tags=["mms-versions"])

WRITE_ERRORS = (
    "오류: 400 NOTHING_TO_VERSION(후보 없음), 403 PROJECT_MEMBER_REQUIRED(보기 전용 MASTER), "
    "409 DOCUMENT_BUSY(분석·확정 중)·DOCUMENT_CONFIRMED"
)


@router.post(
    "",
    response_model=VersionSaved,
    status_code=status.HTTP_201_CREATED,
    summary="버전 추가 (멤버). 지금 후보·근거·입력 전체를 새 버전으로 남김",
    description=WRITE_ERRORS,
)
def add_version(document_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.add_version(db, access, document_id)


@router.put(
    "/latest",
    response_model=VersionSaved,
    summary="버전 저장 (멤버). 이번 분석 이후 만든 마지막 버전을 덮어씀, 없으면 새 버전",
    description=f"덮어썼으면 `overwritten=true`. {WRITE_ERRORS}",
)
def save_version(document_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.save_version(db, access, document_id)


@router.get("", response_model=list[VersionListItem], summary="버전 기록 목록 (멤버, 또는 MASTER 보기만). 최신순")
def list_versions(document_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.list_versions(db, access, document_id)


@router.get(
    "/{version_id}",
    response_model=VersionDetail,
    summary="버전 내용 (멤버, 또는 MASTER 보기만). 읽기 전용, 번호는 그 버전의 REQ 번호",
)
def get_version(
    document_id: int, version_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)
):
    return service.get_version(db, access, document_id, version_id)
