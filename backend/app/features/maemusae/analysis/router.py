"""매무새 AI 분석 API: /api/mms/projects/{project_id}/documents/{document_id}

| 경로                | 누가                    |
| POST /analyze       | 멤버 (202, 분석은 뒤에서) |
| POST /refine        | 멤버 (202, 다시 분류)    |
| GET  /analysis      | 멤버, 또는 MASTER 보기만  |

분석은 쓰기라 멤버만 합니다. 멤버가 아니면 404 이고, 보기 전용 MASTER 는 프로젝트를 이미 볼 수 있으므로
404 대신 403 PROJECT_MEMBER_REQUIRED 입니다 (10/29 결정). 그래서 project_viewer 로 받고 service 가 막습니다.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.maemusae.access import ProjectAccess, project_viewer
from app.features.maemusae.analysis import runner, service
from app.features.maemusae.analysis.schemas import (
    AnalysisRunRead,
    AnalysisStarted,
    AnalyzeRequest,
    RefineRequest,
)

router = APIRouter(prefix="/projects/{project_id}/documents/{document_id}", tags=["mms-analysis"])


@router.post(
    "/analyze",
    response_model=AnalysisStarted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="AI 분석 시작 (멤버, 응답 뒤 분석은 뒤에서)",
    description=(
        "분석 요청을 만들고 바로 202 를 돌려줍니다. 진행률은 GET /analysis 로 읽습니다. "
        "후보가 있으면 restart=true 일 때만 다시 분석합니다 (후보·직접 추가·입력을 모두 지우고 REQ-001 부터). "
        "오류: 400 ANALYSIS_NO_SOURCES, 403 PROJECT_MEMBER_REQUIRED(보기 전용 MASTER), 409 DOCUMENT_BUSY·DOCUMENT_CONFIRMED·ANALYSIS_RESTART_REQUIRED, "
        "422 DOCUMENT_TOO_LARGE_TO_ANALYZE"
    ),
)
def analyze(
    document_id: int,
    body: AnalyzeRequest,
    tasks: BackgroundTasks,
    access: ProjectAccess = Depends(project_viewer),
    db: Session = Depends(get_db),
):
    started = service.start_analysis(db, access, document_id, body)
    tasks.add_task(runner.run_analysis, started.run_id)
    return started


@router.post(
    "/refine",
    response_model=AnalysisStarted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="다시 분류 시작 (멤버, 응답 뒤 분류는 뒤에서)",
    description=(
        "반영 안 된 입력과 새로 올린 파일을 기존 후보에 반영합니다. 번호·id 는 그대로, 새 내용은 다음 번호로 추가. "
        "진행률은 GET /analysis (run_type=REFINE). 오류: 400 REFINE_NEEDS_REQUIREMENTS·REFINE_NOTHING_NEW, "
        "403 PROJECT_MEMBER_REQUIRED, 409 DOCUMENT_BUSY·DOCUMENT_CONFIRMED, 422 DOCUMENT_TOO_LARGE_TO_ANALYZE"
    ),
)
def refine(
    document_id: int,
    body: RefineRequest,
    tasks: BackgroundTasks,
    access: ProjectAccess = Depends(project_viewer),
    db: Session = Depends(get_db),
):
    started = service.start_refine(db, access, document_id, body)
    tasks.add_task(runner.run_refine, started.run_id)
    return started


@router.get(
    "/analysis",
    response_model=AnalysisRunRead | None,
    summary="마지막 분석 진행률 (멤버, 또는 MASTER 보기만). 분석한 적 없으면 null",
)
def get_analysis(document_id: int, access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.get_latest_run(db, access, document_id)
