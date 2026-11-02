"""매무새 초대 메일 양식. 킷 템플릿 파일을 고치지 않고 register_template 로 등록합니다 (모듈을 불러올 때 한 번)."""

from html import escape
from typing import Any

from app.mail import Rendered, register_template

TEMPLATE = "mms_invite"
_ROLE_LABELS = {"ADMIN": "관리자", "MEMBER": "일반 멤버"}


def build_invite(data: dict[str, Any]) -> Rendered:
    project, inviter, link = str(data["project_name"]), str(data["inviter_name"]), str(data["link"])
    role, days = _ROLE_LABELS.get(str(data["role"]), "멤버"), int(data["expire_days"])
    return Rendered(
        subject=f"[매무새] {inviter}님이 '{project}' 프로젝트에 초대했어요",
        text=(
            f"{inviter}님이 매무새 '{project}' 프로젝트에 {role}(으)로 초대했어요.\n\n"
            f"아래 링크에서 초대를 수락해 주세요.\n{link}\n\n"
            f"링크는 {days}일 동안 한 번만 쓸 수 있고, 이 메일 주소로 가입하거나 로그인해야 수락할 수 있어요.\n"
            "모르는 초대라면 이 메일을 무시하세요."
        ),
        html=(
            '<!doctype html><html lang="ko"><body style="font-family:sans-serif">'
            f"<p>{escape(inviter)}님이 매무새 <strong>{escape(project)}</strong> 프로젝트에 {role}(으)로 초대했어요.</p>"
            f'<p><a href="{escape(link)}">초대 수락하기</a></p>'
            f"<p>링크는 {days}일 동안 한 번만 쓸 수 있고, 이 메일 주소로 가입하거나 로그인해야 수락할 수 있어요.</p>"
            "<p>모르는 초대라면 이 메일을 무시하세요.</p>"
            "</body></html>"
        ),
    )


register_template(TEMPLATE, build_invite)
