"use client";

import { ApiKeyInput, useAuth } from "@/meerkit";

import { Btn, PageHead, card } from "../_components/ui";

export default function MyPage() {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <div className="h-[40vh]" aria-busy />;
  if (!isAuthenticated || !user)
    return (
      <div className={`${card} mx-auto grid max-w-lg justify-items-center gap-4 py-12 text-center`}>
        <h2 className="text-2xl font-extrabold tracking-tight">로그인이 필요해요</h2>
        <p className="text-sm text-[#6c6a62]">마이페이지는 로그인한 멤버만 볼 수 있어요.</p>
        <div className="flex gap-2"><Btn href="/maemusae/login" variant="dark">로그인</Btn><Btn href="/maemusae/signup">회원가입</Btn></div>
      </div>
    );

  return (
    <div className="grid gap-8">
      <PageHead eyebrow="My page" light="내" title="마이페이지" />

      <section className={`${card} grid gap-4`} data-rise>
        <h2 className="text-xl font-extrabold tracking-tight">계정 정보</h2>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">닉네임</dt><dd className="mt-1 font-semibold">{user.nickname ?? "-"}</dd></div>
          <div><dt className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">이메일</dt><dd className="mt-1 font-semibold">{user.email ?? "-"}</dd></div>
        </dl>
        <p className="text-sm text-[#6c6a62]">닉네임·비밀번호 변경과 회원 탈퇴는 계정 설정에서 할 수 있어요.</p>
        <div><Btn href="/me" variant="dark">계정 설정</Btn></div>
      </section>

      <section className={`${card} grid gap-4`} data-rise>
        <div>
          <h2 className="text-xl font-extrabold tracking-tight">AI API 키</h2>
          <p className="mt-1 text-sm text-[#6c6a62]">요구사항 분석에 쓸 내 AI API 키를 입력하세요. 아직은 이 브라우저에만 임시로 두며, 새로고침하면 지워져요.</p>
        </div>
        <ApiKeyInput />
      </section>
    </div>
  );
}
