"""매무새 API 묶음: /api/mms 아래에 매무새 기능별 라우터를 붙입니다. app/api.py 는 이것 하나만 등록합니다."""

from fastapi import APIRouter

from app.features.maemusae.analysis.router import router as analysis_router
from app.features.maemusae.confirm.router import router as confirm_router
from app.features.maemusae.documents.router import router as documents_router
from app.features.maemusae.invitations.router import (
    link_router as invitation_link_router,
)
from app.features.maemusae.invitations.router import (
    project_router as project_invitations_router,
)
from app.features.maemusae.projects.router import router as projects_router
from app.features.maemusae.review.router import router as review_router
from app.features.maemusae.versions.router import router as versions_router

router = APIRouter(prefix="/mms")
router.include_router(projects_router)
router.include_router(project_invitations_router)
router.include_router(invitation_link_router)
router.include_router(documents_router)
router.include_router(analysis_router)
router.include_router(review_router)
router.include_router(versions_router)
router.include_router(confirm_router)
