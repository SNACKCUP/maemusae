"""앱 로그 설정. app.* 로거를 표준 출력으로 내보내고, 모든 줄에 요청 ID를 붙입니다.

LOG_FORMAT=json 이면 한 줄에 JSON 하나(운영, 로그 수집용), text 면 사람이 읽기 쉬운 형식(로컬)입니다.
비밀번호·토큰·인증번호·업로드 문서 내용·개인정보(이메일·전화번호 등)는 로그 메시지에 넣지 않습니다.
그래도 실수로 들어간 이메일·전화번호 모양 글자는 PiiRedactFilter 가 가려서 내보냅니다 (안전망일 뿐, 이것만 믿지 않음).
"""

import json
import logging
import re
from datetime import UTC, datetime

from app.core.config import settings
from app.core.request_context import get_request_id

# 접근 로그 등에서 extra 로 넘기는 필드. JSON 로그에 그대로 실립니다.
_EXTRA_FIELDS = ("method", "path", "status", "duration_ms")


_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
# 한국 휴대폰·일반 전화 (010-1234-5678, 01012345678, +82 10 1234 5678, 02-123-4567). 앞뒤가 숫자면 건너뜀
_PHONE_RE = re.compile(r"(?<![\d])(?:\+?82[- ]?|0)(?:1[016789]|[2-6]\d?)[- ]?\d{3,4}[- ]?\d{4}(?![\d])")


def redact_pii(text: str) -> str:
    """이메일은 k***@example.com, 전화번호는 [전화번호] 로 가립니다"""
    text = _EMAIL_RE.sub(r"\1***@\2", text)
    return _PHONE_RE.sub("[전화번호]", text)


class PiiRedactFilter(logging.Filter):
    """로그 메시지와 접근 로그 path 의 이메일·전화번호 모양 글자를 가립니다 (계획 23 §10)"""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact_pii(message)
        if redacted != message:
            record.msg, record.args = redacted, None
        path = getattr(record, "path", None)
        if isinstance(path, str):
            record.path = redact_pii(path)
        return True


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key in _EXTRA_FIELDS:
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def log_format() -> str:
    if settings.log_format:
        return settings.log_format.lower()
    return "text" if settings.app_env == "local" else "json"


def setup_logging() -> None:
    logger = logging.getLogger("app")
    logger.setLevel(settings.log_level.upper())
    logger.propagate = False
    if getattr(logger, "_meerkit_configured", False):
        return
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.addFilter(PiiRedactFilter())
    if log_format() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")
        )
    logger.addHandler(handler)
    logger._meerkit_configured = True  # type: ignore[attr-defined]
    # 접근 로그는 app.access 가 남기므로 uvicorn 기본 접근 로그는 끕니다 (중복 방지)
    logging.getLogger("uvicorn.access").disabled = True
