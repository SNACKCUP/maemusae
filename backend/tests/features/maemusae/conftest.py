import pytest

from app.features.maemusae.analysis import runner
from app.features.maemusae.config import mms_settings


@pytest.fixture(autouse=True)
def _analysis_defaults(monkeypatch):
    # 가짜 LLM 은 응답을 넣은 순서대로 내주므로 기본은 하나씩·다시 시도 없음·보강·상세화 끔 (둘 다 AI 호출을 늘림).
    # 동시 처리·다시 시도·보강을 보는 테스트에서만 켭니다
    monkeypatch.setattr(mms_settings, "mms_analyze_expand", False)
    monkeypatch.setattr(mms_settings, "mms_analyze_detail", False)
    monkeypatch.setattr(mms_settings, "mms_analyze_concurrency", 1)
    monkeypatch.setattr(mms_settings, "mms_batch_retries", 0)
    monkeypatch.setattr(runner, "RETRY_BACKOFF_SECONDS", (0,))  # 테스트는 기다리지 않음
