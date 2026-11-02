"use client";

import { ApiKeyInput, MePage } from "@/meerkit";

// 킷의 내 정보 화면(프로필·비밀번호·탈퇴)에 매무새 고유 설정인 AI API 키 탭을 앞에 끼운다
export default function MyPage() {
  return (
    <MePage
      embedded
      title="마이페이지"
      extraTabs={[
        {
          value: "api-key",
          label: "AI API 키",
          content: (
            <div className="grid gap-3">
              <p className="text-sm text-muted-foreground">요구사항 분석에 쓸 내 AI API 키를 입력하세요. 아직은 이 브라우저에만 임시로 두며, 새로고침하면 지워져요.</p>
              <ApiKeyInput />
            </div>
          ),
        },
      ]}
    />
  );
}
