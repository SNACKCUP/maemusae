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

    # 지운 프로젝트 보관 기간. 지나면 정리 명령(app.features.maemusae.retention)이 원본 파일과 행을 실제로 지움
    mms_project_retention_days: int = 180


mms_settings = MaemusaeSettings()
