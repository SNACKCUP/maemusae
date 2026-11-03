"""내 AI 키 API: /api/mms/me/ai-key (로그인 필요, 본인 것만). 키 원문은 응답에 넣지 않습니다."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import Principal, require_login
from app.features.maemusae.ai_keys import service
from app.features.maemusae.ai_keys.schemas import AiKeyRead, AiKeySave

router = APIRouter(prefix="/me/ai-key", tags=["mms-ai-key"], dependencies=[Depends(require_login)])


@router.get("", response_model=AiKeyRead, summary="내 AI 키 상태 (끝 4자리만)")
def get_my_key(principal: Principal = Depends(require_login), db: Session = Depends(get_db)):
    return service.get_my_key(db, principal.user_id)


@router.put("", response_model=AiKeyRead, summary="내 AI 키 저장 (있으면 바꿈, 서버에 암호화해 저장)")
def save_my_key(body: AiKeySave, principal: Principal = Depends(require_login), db: Session = Depends(get_db)):
    return service.save_my_key(db, principal.user_id, body)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="내 AI 키 지우기")
def delete_my_key(principal: Principal = Depends(require_login), db: Session = Depends(get_db)):
    service.delete_my_key(db, principal.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
