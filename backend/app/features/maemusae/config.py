"""매무새 설정. 매무새 모듈만 읽습니다 (킷은 이 설정을 모름). 환경 변수 이름은 MMS_ 로 시작합니다."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import settings as core_settings


class MaemusaeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mms_source_max_bytes: int = 10 * 1024 * 1024  # 올리는 파일 하나의 크기. 넘으면 413 FILE_TOO_LARGE
    mms_sources_per_document: int = 20  # 문서 하나에 올릴 수 있는 파일·직접 쓴 글 수
    mms_source_max_chars: int = 200_000  # 파일 하나에서 뽑은 본문 글자 수. 넘으면 422 DOCUMENT_TOO_LONG
    mms_page_max_chars: int = 4000  # 쪽 정보가 없는 형식(docx·txt·md·시트)을 글자 수로 나눌 때 한 조각의 크기

    # AI 분석 (M3). 묶음 하나가 AI 호출 1번이라 킷 입력 상한(LLM_MAX_INPUT_CHARS, 기본 20,000자) 안이어야 함
    # 묶음 하나에 넣는 본문 글자 수. 전체가 이 안이면 AI 1번(작은 문서). 11/3 과업지시서 시험: 12,000자 하나씩 25분 → 6,000자·동시 3개 11분, 품질 같음
    mms_batch_chars: int = 6_000
    mms_batch_overlap_chars: int = 300  # 묶음이 바뀔 때 앞 쪽 끝을 다음 묶음 앞에 겹쳐 넣는 글자 수
    mms_analyze_max_batches: int = 80  # 묶음 수 상한(6,000자 × 80 = 약 48만 자). 넘으면 시작 전에 422 DOCUMENT_TOO_LARGE_TO_ANALYZE
    mms_analyze_stale_minutes: int = 15  # 진행이 이만큼 없으면 멈춘 분석으로 보고 실패 처리 (서버 재시작 등)
    # 보강·상세화는 기본 끔: 요구사항정의서는 짧게 뽑는 원본 방식이 큰 문서에서도 안정적이고 싸다 (11/3 시험).
    # 두 단계(expand.md·detail.md)는 기능정의서(확정된 요구사항 → 상세 명세)에서 다시 쓸 예정
    # 보강: 뽑은 목록을 AI 에 한 번 더 보내 숨은 요구사항(예: 로그인 → 리프레시 토큰)을 찾음. AI 호출 +1번
    mms_analyze_expand: bool = False
    # 상세화: 뽑은 후보를 몇 개씩 보내 개발자가 바로 만들 수 있는 명세(목적·동작·규칙·예외·보안·완료 기준)로 씀
    mms_analyze_detail: bool = False
    # 묶음(뽑기)·보강 조각을 동시에 보내는 수. 1이면 하나씩. OpenAI 호출 한도(분당 요청·토큰)를 넘지 않게 정함
    mms_analyze_concurrency: int = 3
    # 묶음 하나가 시간 초과·일시 오류로 실패했을 때 그 묶음만 다시 보내는 횟수. 다 실패하면 분석 실패
    mms_batch_retries: int = 2
    # 단계별 모델. 비우면 LLM_MODEL. 공급자·키·temperature·시간 제한은 킷 설정(LLM_*)을 같이 씀
    mms_extract_model: str = ""
    mms_expand_model: str = ""
    mms_detail_model: str = ""
    # 큰 문서는 뽑기 모델을 바꿈: 본문이 MMS_LARGE_DOC_CHARS 자를 넘고 MMS_EXTRACT_MODEL_LARGE 가 있으면 그 모델. 0이면 끔
    mms_large_doc_chars: int = 0
    mms_extract_model_large: str = ""
    # 대체 모델: 다시 시도까지 끝내 실패한(시간 초과·일시 오류) 호출을 이 모델로 한 번 더. 비우면 끔
    mms_fallback_model: str = ""

    # 지운 프로젝트 보관 기간. 지나면 정리 명령(app.features.maemusae.retention)이 원본 파일과 행을 실제로 지움
    mms_project_retention_days: int = 180

    # 개인 AI 키 (11/03 결정: 사람마다, 서버에 암호화해 저장, 서버 키로 대신 돌리지 않음)
    # 스위치. 켜면 분석·다시 분류를 누른 사람의 키로 돌리고, 키가 없으면 시작하지 않음. 끄면 지금처럼 서버 키(OPENAI_API_KEY).
    # 문제가 생기면 이 값만 false 로 바꿔 다시 시작하면 원래대로 돌아감 (저장한 키는 그대로 남음)
    mms_user_ai_key_enabled: bool = False
    # 키 암호화 키 (Fernet). 쉼표로 여러 개를 넣으면 맨 앞 것으로 암호화하고 모두로 풀 수 있음 (키 교체용).
    # 만들기: uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # 비우면 키 저장 기능이 꺼짐 (503). 잃어버리면 저장한 키를 풀 수 없으니 비밀 저장소에 따로 보관
    mms_ai_key_encryption_key: SecretStr = SecretStr("")


mms_settings = MaemusaeSettings()


def production_problems() -> list[str]:
    """APP_ENV=production 에서 매무새 쪽 위험한 설정. main.py 가 다른 검사와 합쳐 시작 전에 확인합니다. 값은 넣지 않습니다."""
    if core_settings.app_env != "production":
        return []
    from app.features.maemusae.ai_keys.crypto import key_problem  # 순환 import 방지

    problem = key_problem()
    if problem:
        return [f"MMS_AI_KEY_ENCRYPTION_KEY: {problem}"]
    return []
