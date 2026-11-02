"""매무새 오류. 킷의 AppError 계열을 상속해서 전역 핸들러가 {"detail","code","request_id"} 로 응답합니다."""

from app.core.exceptions import (
    AppError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


class ProjectNotFoundError(NotFoundError):
    # 멤버가 아닌 사람에게는 프로젝트가 있는지조차 알리지 않으려고 403 대신 이 404 를 씁니다
    def __init__(self):
        super().__init__("PROJECT_NOT_FOUND", "프로젝트를 찾을 수 없습니다.")


class ProjectMemberRequiredError(ForbiddenError):
    # 보기 전용 MASTER 가 쓰기 기능을 누른 경우. MASTER 는 프로젝트가 있는 걸 이미 알기 때문에 404 대신 403 (10/29 결정)
    def __init__(self):
        super().__init__("PROJECT_MEMBER_REQUIRED", "프로젝트 멤버만 할 수 있습니다. 관리자는 보기만 할 수 있어요.")


class ProjectAdminRequiredError(ForbiddenError):
    def __init__(self):
        super().__init__("PROJECT_ADMIN_REQUIRED", "프로젝트 관리자만 할 수 있습니다.")


class MemberNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("PROJECT_MEMBER_NOT_FOUND", "프로젝트 멤버를 찾을 수 없습니다.")


class LastProjectAdminError(ConflictError):
    def __init__(self):
        super().__init__(
            "LAST_PROJECT_ADMIN", "프로젝트에는 관리자가 한 명 이상 있어야 합니다. 다른 멤버를 먼저 관리자로 지정하세요."
        )


class InvalidPeriodError(BadRequestError):
    def __init__(self):
        super().__init__("INVALID_PERIOD", "종료일은 시작일과 같거나 뒤여야 합니다.")


class InvitationInvalidError(NotFoundError):
    # 없는·만료된·취소된·이미 쓴 토큰을 구분하지 않고 같은 응답을 줍니다 (토큰 상태를 알려 주지 않음)
    def __init__(self):
        super().__init__("INVITATION_INVALID", "초대 링크가 만료되었거나 더 이상 쓸 수 없습니다. 관리자에게 다시 초대를 요청하세요.")


class InvitationNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("INVITATION_NOT_FOUND", "대기 중인 초대를 찾을 수 없습니다.")


class AlreadyMemberError(ConflictError):
    def __init__(self):
        super().__init__("ALREADY_MEMBER", "이미 이 프로젝트의 멤버입니다.")


class InvitationEmailMismatchError(ForbiddenError):
    def __init__(self):
        super().__init__(
            "INVITATION_EMAIL_MISMATCH", "초대받은 이메일과 로그인한 계정의 이메일이 다릅니다. 초대받은 이메일의 계정으로 로그인하세요."
        )


class DocumentNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("DOCUMENT_NOT_FOUND", "문서를 찾을 수 없습니다.")


class DocumentBusyError(ConflictError):
    def __init__(self):
        super().__init__("DOCUMENT_BUSY", "AI 분석이나 확정이 진행 중이라 지금은 파일을 바꿀 수 없습니다. 끝난 뒤 다시 시도하세요.")


class SourceNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("SOURCE_NOT_FOUND", "올린 파일을 찾을 수 없습니다.")


class SourceInputRequiredError(BadRequestError):
    def __init__(self):
        super().__init__("SOURCE_INPUT_REQUIRED", "파일 하나 또는 직접 쓴 글 중 하나만 보내세요.")


class FileTooLargeError(AppError):
    status_code = 413

    def __init__(self, max_mb: int):
        super().__init__("FILE_TOO_LARGE", f"파일은 {max_mb}MB 이하만 올릴 수 있습니다.")


class UnsupportedFileTypeError(AppError):
    status_code = 415

    def __init__(self):
        super().__init__(
            "UNSUPPORTED_FILE_TYPE", "PDF, Word(docx), PowerPoint(pptx), Excel(xlsx), txt, md 파일만 올릴 수 있습니다."
        )


class DocumentParseFailedError(ValidationError):
    def __init__(self):
        super().__init__(
            "DOCUMENT_PARSE_FAILED", "파일에서 글자를 읽을 수 없어요. 파일이 깨졌거나 스캔한 이미지인지 확인하세요."
        )


class DocumentTooLongError(ValidationError):
    def __init__(self, max_chars: int):
        super().__init__("DOCUMENT_TOO_LONG", f"파일 하나의 글자 수는 {max_chars:,}자까지입니다. 파일을 나눠서 올리세요.")


class SourceDuplicateError(ConflictError):
    def __init__(self):
        super().__init__("SOURCE_DUPLICATE", "같은 파일이 이미 올라가 있습니다.")


class SourceLimitError(ConflictError):
    def __init__(self, limit: int):
        super().__init__("SOURCE_LIMIT_REACHED", f"문서 하나에는 파일을 {limit}개까지 올릴 수 있습니다.")


class SourceDeleteForbiddenError(ForbiddenError):
    def __init__(self):
        super().__init__("SOURCE_DELETE_FORBIDDEN", "올린 사람이나 프로젝트 관리자만 지울 수 있습니다.")


class DocumentConfirmedError(ConflictError):
    def __init__(self):
        super().__init__("DOCUMENT_CONFIRMED", "확정된 문서입니다. 확정 뒤 수정을 먼저 눌러 주세요.")


class AnalysisNoSourcesError(BadRequestError):
    def __init__(self):
        super().__init__("ANALYSIS_NO_SOURCES", "분석할 문서를 먼저 올려 주세요.")


class AnalysisRestartRequiredError(ConflictError):
    # 후보가 있는 문서를 다시 분석하면 후보·직접 추가·입력을 모두 지우므로, 화면이 알림을 보여 준 뒤 restart=true 로 보냄
    def __init__(self):
        super().__init__(
            "ANALYSIS_RESTART_REQUIRED",
            "이미 후보가 있는 문서입니다. 다시 분석하면 지금 후보와 직접 입력한 내용이 사라지고 REQ-001부터 새로 만들어집니다.",
        )


class DocumentTooLargeToAnalyzeError(ValidationError):
    # 상한은 파일 하나가 아니라 문서에 올린 파일 전체 합계라서, 나눠 올리라는 안내는 하지 않음 (10/29)
    def __init__(self):
        super().__init__(
            "DOCUMENT_TOO_LARGE_TO_ANALYZE",
            "문서를 다 합친 용량이 너무 커요. 분석에 필요 없는 파일을 빼고 다시 시도해 주세요.",
        )


class RequirementNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("REQUIREMENT_NOT_FOUND", "요구사항 후보를 찾을 수 없습니다.")


class RequirementChangedError(ConflictError):
    # 낙관적 잠금: 화면이 보낸 version 이 DB 와 다르면 다른 사람이 먼저 고친 것
    def __init__(self, codes: list[str]):
        super().__init__(
            "REQUIREMENT_CHANGED",
            f"다른 사람이 먼저 고쳤어요 ({', '.join(codes)}). 새로 불러온 뒤 다시 고쳐 주세요.",
        )


class RequirementNotDeletableError(ConflictError):
    def __init__(self):
        super().__init__("REQUIREMENT_NOT_DELETABLE", "AI가 만든 후보는 지울 수 없어요. 체크를 해제하면 확정에서 빠집니다.")


class NoteNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("NOTE_NOT_FOUND", "남긴 입력을 찾을 수 없습니다.")


class NothingToVersionError(BadRequestError):
    # 후보가 하나도 없으면 남길 내용이 없음 (빈 버전이 기록에 쌓이지 않게)
    def __init__(self):
        super().__init__("NOTHING_TO_VERSION", "남길 후보가 없어요. 분석하거나 후보를 직접 추가한 뒤 눌러 주세요.")


class VersionNotFoundError(NotFoundError):
    def __init__(self):
        super().__init__("VERSION_NOT_FOUND", "버전 기록을 찾을 수 없습니다.")


class RefineNeedsRequirementsError(BadRequestError):
    # 다시 분류는 기존 후보에 반영하는 단계라 후보가 먼저 있어야 함
    def __init__(self):
        super().__init__("REFINE_NEEDS_REQUIREMENTS", "후보가 없어요. 먼저 AI 분석을 하거나 후보를 직접 추가해 주세요.")


class RefineNothingNewError(BadRequestError):
    def __init__(self):
        super().__init__("REFINE_NOTHING_NEW", "반영할 내용이 없어요. 입력을 남기거나 문서를 새로 올린 뒤 다시 분류해 주세요.")


class DocumentNotReadyError(ConflictError):
    # 시작 전·분석 실패처럼 확정할 후보 목록이 아직 없는 상태
    def __init__(self):
        super().__init__("DOCUMENT_NOT_READY", "아직 확정할 수 없는 상태예요. AI 분석을 마치거나 후보를 직접 추가해 주세요.")


class NothingToConfirmError(BadRequestError):
    def __init__(self):
        super().__init__("NOTHING_TO_CONFIRM", "체크된 후보가 없어요. 확정할 후보를 하나 이상 체크해 주세요.")


class DocumentNotConfirmedError(ConflictError):
    def __init__(self):
        super().__init__("DOCUMENT_NOT_CONFIRMED", "확정된 문서가 아니에요.")


class ConfirmedVersionNotFoundError(NotFoundError):
    # Excel 은 확정 기록에서만 만듦 (버전 추가·저장 기록은 받지 않음)
    def __init__(self):
        super().__init__("CONFIRMED_VERSION_NOT_FOUND", "확정 기록을 찾을 수 없습니다.")
