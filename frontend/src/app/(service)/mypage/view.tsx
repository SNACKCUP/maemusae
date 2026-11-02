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
    <section id={id} aria-labelledby={`${id}-h`} data-rise className="grid scroll-mt-32 gap-4 xl:grid-cols-[240px_1fr] xl:gap-10">
      <div>
        <h2 id={`${id}-h`} className={cn("text-xl font-extrabold tracking-tight", danger && "text-[#b3261e]")}>{title}</h2>
        <p className="mt-1.5 text-sm leading-relaxed text-[#6c6a62]">{desc}</p>
      </div>
      <div className={cn(card, "min-w-0", SUBMIT_BUTTON, AVATAR_BUTTONS, danger && `border-[#b3261e] shadow-[5px_5px_0_#b3261e] ${DANGER_BUTTON}`)}>{children}</div>
    </section>
  );
}

// 킷 폼의 제출 버튼(비밀번호 변경·저장·탈퇴)을 매무새 버튼 모양으로 바꾸고 오른쪽 끝으로 보낸다
const SUBMIT_BUTTON = [
  "[&_button[type=submit]]:justify-self-end [&_button[type=submit]]:rounded-full [&_button[type=submit]]:border-2 [&_button[type=submit]]:border-[#111]",
  "[&_button[type=submit]]:bg-[#111] [&_button[type=submit]]:px-6 [&_button[type=submit]]:font-semibold [&_button[type=submit]]:text-white",
  "[&_button[type=submit]]:shadow-[3px_3px_0_#111] [&_button[type=submit]]:transition-[transform,box-shadow] [&_button[type=submit]]:duration-300",
  "[&_button[type=submit]]:ease-[cubic-bezier(0.34,1.56,0.64,1)] [&_button[type=submit]:enabled]:hover:-translate-y-1 [&_button[type=submit]:enabled]:hover:scale-[1.04]",
  "[&_button[type=submit]:enabled]:hover:shadow-[6px_6px_0_#111] [&_button[type=submit]:enabled]:active:scale-95 [&_button[type=submit]:enabled]:active:shadow-none",
  "[&_button[type=submit]:disabled]:opacity-40 [&_button[type=submit]:disabled]:shadow-none",
].join(" ");
// 탈퇴는 빨간색으로 한 번 더 경고한다
const DANGER_BUTTON = "[&_button[type=submit]]:bg-[#b3261e] [&_button[type=submit]]:shadow-[3px_3px_0_#111]";
// 프로필 이미지 [삭제]는 글자 버튼이 아니라 테두리 있는 작은 버튼으로
const AVATAR_BUTTONS = [
  "[&_[data-slot=avatar-change]]:rounded-full [&_[data-slot=avatar-change]]:border-2 [&_[data-slot=avatar-change]]:border-[#111] [&_[data-slot=avatar-change]]:bg-white [&_[data-slot=avatar-change]]:font-semibold",
  "[&_[data-slot=avatar-remove]]:rounded-full [&_[data-slot=avatar-remove]]:border-2 [&_[data-slot=avatar-remove]]:border-[#b3261e] [&_[data-slot=avatar-remove]]:bg-white [&_[data-slot=avatar-remove]]:font-semibold [&_[data-slot=avatar-remove]]:text-[#b3261e]",
  "[&_[data-slot=avatar-change]]:transition-transform [&_[data-slot=avatar-remove]]:transition-transform [&_[data-slot=avatar-change]]:duration-300 [&_[data-slot=avatar-remove]]:duration-300 [&_[data-slot=avatar-change]]:ease-[cubic-bezier(0.34,1.56,0.64,1)] [&_[data-slot=avatar-remove]]:ease-[cubic-bezier(0.34,1.56,0.64,1)]",
  "[&_[data-slot=avatar-change]:enabled]:hover:scale-105 [&_[data-slot=avatar-remove]:enabled]:hover:scale-105 [&_[data-slot=avatar-change]:enabled]:active:scale-95 [&_[data-slot=avatar-remove]:enabled]:active:scale-95",
  "[&_[data-slot=avatar-remove]:enabled]:hover:bg-[#ffd2b8]",
].join(" ");

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
    // 맨 아래까지 내려가면 마지막 구역이 읽는 구역이다 (짧은 마지막 구역은 위 검사에 걸리지 않는다)
    const onScroll = () => {
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 8) setActive(SECTIONS[SECTIONS.length - 1].id);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      io.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, []);
  return [active, setActive] as const;
}

export default function MyPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [active, setActive] = useActiveSection();

  if (isLoading) return <div className="h-[40vh]" aria-busy />;
  if (!isAuthenticated || !user)
    return (
      <div data-rise className={`${card} mx-auto grid max-w-lg justify-items-center gap-4 py-12 text-center`}>
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
    <div className="mx-auto grid w-full max-w-[1100px] gap-16">
      <PageHead eyebrow="Account settings" light="내" title="마이페이지">
        <Pill tone="yellow">{user.email}</Pill>
      </PageHead>

      <div className="grid gap-8 lg:grid-cols-[200px_1fr] lg:gap-12">
        <nav aria-label="설정 구역" data-side className="lg:sticky lg:top-32 lg:self-start">
          <ul className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <li key={id} className="shrink-0">
                <button
                  type="button"
                  onClick={() => go(id)}
                  aria-current={active === id ? "true" : undefined}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-full border-2 px-4 py-2 text-left text-[13px] font-semibold transition-[transform,background-color,border-color] duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)] hover:translate-x-1 active:scale-95",
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

        <div className="grid min-w-0 gap-14 pb-24 lg:pb-32">
          <Section id="profile" title="프로필" desc="다른 멤버에게 보이는 이름과 사진, 연락처를 관리해요.">
            <div className="flex flex-wrap items-center gap-4">
              <MeAvatarField showHint={false} />
              <div className="min-w-0">
                <p className="truncate text-lg font-extrabold">{name}</p>
                <p className="truncate text-sm text-[#6c6a62]">{user.email}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
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
