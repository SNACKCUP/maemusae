"use client";

import { KeyRound, ShieldCheck, Trash2, UserRound, type LucideIcon } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { ApiKeyInput, MeAvatarField, MeNicknameForm, MePasswordForm, MeProfileForm, MeWithdrawForm, useAuth } from "@/meerkit";
import { cn } from "@/lib/utils";

import { Btn, PageHead, Pill, card } from "../_components/ui";

const SECTIONS: { id: string; label: string; icon: LucideIcon }[] = [
  { id: "profile", label: "프로필", icon: UserRound },
  { id: "security", label: "보안", icon: ShieldCheck },
  { id: "api-key", label: "AI API 키", icon: KeyRound },
  { id: "danger", label: "계정 삭제", icon: Trash2 },
];

// 설정 한 덩어리: 왼쪽에 제목과 설명, 오른쪽에 내용 (좁은 화면에서는 위아래)
function Section({ id, title, desc, danger, children }: { id: string; title: string; desc: string; danger?: boolean; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="grid scroll-mt-8 gap-4 xl:grid-cols-[240px_1fr] xl:gap-10">
      <div>
        <h2 id={`${id}-h`} className={cn("text-xl font-extrabold tracking-tight", danger && "text-[#b3261e]")}>{title}</h2>
        <p className="mt-1.5 text-sm leading-relaxed text-[#6c6a62]">{desc}</p>
      </div>
      <div className={cn(card, "min-w-0", danger && "border-[#b3261e] shadow-[5px_5px_0_#b3261e]")}>{children}</div>
    </section>
  );
}

const Divider = () => <hr className="my-6 border-[#111]/15" />;

// 읽고 있는 구역을 왼쪽 메뉴에 표시한다
function useActiveSection() {
  const [active, setActive] = useState(SECTIONS[0].id);
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        const top = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (top) setActive(top.target.id);
      },
      { rootMargin: "-20% 0px -60% 0px" },
    );
    SECTIONS.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) io.observe(el);
    });
    return () => io.disconnect();
  }, []);
  return [active, setActive] as const;
}

export default function MyPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [active, setActive] = useActiveSection();

  if (isLoading) return <div className="h-[40vh]" aria-busy />;
  if (!isAuthenticated || !user)
    return (
      <div className={`${card} mx-auto grid max-w-lg justify-items-center gap-4 py-12 text-center`}>
        <h2 className="text-2xl font-extrabold tracking-tight">로그인이 필요해요</h2>
        <p className="text-sm text-[#6c6a62]">마이페이지는 로그인한 멤버만 볼 수 있어요.</p>
        <div className="flex gap-2"><Btn href="/login" variant="dark">로그인</Btn><Btn href="/signup">회원가입</Btn></div>
      </div>
    );

  const name = user.nickname?.trim() || user.name;
  const go = (id: string) => {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="grid gap-10">
      <PageHead eyebrow="Account settings" light="내" title="마이페이지">
        <Pill tone="yellow">{user.email}</Pill>
      </PageHead>

      <div className="grid gap-8 lg:grid-cols-[200px_1fr] lg:gap-12">
        <nav aria-label="설정 구역" className="lg:sticky lg:top-8 lg:self-start">
          <ul className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <li key={id} className="shrink-0">
                <button
                  type="button"
                  onClick={() => go(id)}
                  aria-current={active === id ? "true" : undefined}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-full border-2 px-4 py-2 text-left text-[13px] font-semibold transition-colors",
                    active === id ? "border-[#111] bg-[#f2f69a]" : "border-transparent text-[#6c6a62] hover:bg-[#ebeae4] hover:text-[#111]",
                    id === "danger" && active !== id && "hover:text-[#b3261e]",
                  )}
                >
                  <Icon className="size-4" aria-hidden /> {label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="grid min-w-0 gap-14">
          <Section id="profile" title="프로필" desc="다른 멤버에게 보이는 이름과 사진, 연락처를 관리해요.">
            <div className="flex flex-wrap items-center gap-4">
              <MeAvatarField />
              <div className="min-w-0">
                <p className="truncate text-lg font-extrabold">{name}</p>
                <p className="truncate text-sm text-[#6c6a62]">{user.email}</p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {user.roles.map((r) => <Pill key={r.id} tone="yellow" className="px-2 py-0.5 text-[10px]">{r.name}</Pill>)}
                  <span className="text-xs text-[#6c6a62]">가입일 {user.created_at.slice(0, 10)}</span>
                </div>
              </div>
            </div>
            <Divider />
            <MeNicknameForm />
            <Divider />
            <MeProfileForm />
          </Section>

          <Section id="security" title="보안" desc="주기적으로 비밀번호를 바꾸면 계정을 더 안전하게 지킬 수 있어요.">
            <MePasswordForm />
          </Section>

          <Section id="api-key" title="AI API 키" desc="요구사항 분석에 쓸 내 AI API 키를 연결해요. 서버에 암호화해 저장하는 기능은 준비 중이에요.">
            <div className="mb-4 flex flex-wrap gap-1.5">
              <Pill tone="dark">OpenAI</Pill>
              <Pill className="text-[#6c6a62]">Claude · 준비 중</Pill>
              <Pill className="text-[#6c6a62]">Gemini · 준비 중</Pill>
            </div>
            <ApiKeyInput />
          </Section>

          <Section id="danger" danger title="계정 삭제" desc="탈퇴하면 로그인할 수 없게 되고, 보관 기간이 지나면 개인정보가 지워져요.">
            <MeWithdrawForm />
          </Section>
        </div>
      </div>
    </div>
  );
}
