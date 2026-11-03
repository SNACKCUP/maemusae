"""매무새 설정. 매무새 모듈만 읽습니다 (킷은 이 설정을 모름). 환경 변수 이름은 MMS_ 로 시작합니다."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class MaemusaeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mms_source_max_bytes: int = 10 * 1024 * 1024  # 올리는 파일 하나의 크기. 넘으면 413 FILE_TOO_LARGE
    mms_sources_per_document: int = 20  # 문서 하나에 올릴 수 있는 파일·직접 쓴 글 수
    mms_source_max_chars: int = 200_000  # 파일 하나에서 뽑은 본문 글자 수. 넘으면 422 DOCUMENT_TOO_LONG
    mms_page_max_chars: int = 4000  # 쪽 정보가 없는 형식(docx·txt·md·시트)을 글자 수로 나눌 때 한 조각의 크기

    # AI 분석 (M3). 묶음 하나가 AI 호출 1번이라 킷 입력 상한(LLM_MAX_INPUT_CHARS, 기본 20,000자) 안이어야 함
    mms_batch_chars: int = 12_000  # 묶음 하나에 넣는 본문 글자 수. 전체가 이 안이면 AI 1번(작은 문서)
    mms_batch_overlap_chars: int = 300  # 묶음이 바뀔 때 앞 쪽 끝을 다음 묶음 앞에 겹쳐 넣는 글자 수
    mms_analyze_max_batches: int = 40  # 묶음 수 상한. 넘으면 시작 전에 422 DOCUMENT_TOO_LARGE_TO_ANALYZE
    mms_analyze_stale_minutes: int = 15  # 진행이 이만큼 없으면 멈춘 분석으로 보고 실패 처리 (서버 재시작 등)
    # 보강: 뽑은 목록을 AI 에 한 번 더 보내 숨은 요구사항(예: 로그인 → 리프레시 토큰)을 찾음. AI 호출 +1번
    mms_analyze_expand: bool = True
    # 상세화: 뽑은 후보를 몇 개씩 보내 개발자가 바로 만들 수 있는 명세(목적·동작·규칙·예외·보안·완료 기준)로 씀
    mms_analyze_detail: bool = True
    # 묶음(뽑기)·보강 조각을 동시에 보내는 수. 1이면 하나씩. OpenAI 호출 한도(분당 요청·토큰)를 넘지 않게 정함
    mms_analyze_concurrency: int = 3
    # 묶음 하나가 시간 초과·일시 오류로 실패했을 때 그 묶음만 다시 보내는 횟수. 다 실패하면 분석 실패
    mms_batch_retries: int = 1
    # 단계별 모델. 비우면 LLM_MODEL. 공급자·키·temperature·시간 제한은 킷 설정(LLM_*)을 같이 씀
    mms_extract_model: str = ""
    mms_expand_model: str = ""
    mms_detail_model: str = ""

    # 지운 프로젝트 보관 기간. 지나면 정리 명령(app.features.maemusae.retention)이 원본 파일과 행을 실제로 지움
    mms_project_retention_days: int = 180


mms_settings = MaemusaeSettings()
