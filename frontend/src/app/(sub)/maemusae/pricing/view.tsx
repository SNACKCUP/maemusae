"use client";

import { useRef } from "react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";

import { useReveal } from "../_lib/motion";
import { Btn, Pill, card } from "../_components/ui";

const FREE = ["프로젝트 등록", "문서 올리기와 AI 요구사항 후보", "근거 문장과 확인 질문", "관리자 확정과 수정 이력", "Excel · PDF 내보내기", "멤버 초대와 권한 관리"];
const PRO = ["무료 플랜의 모든 기능", "더 큰 파일과 더 많은 문서", "프로젝트 수 제한 없음", "우선 지원"];

const ROWS: [string, string, string][] = [
  ["프로젝트", "등록 가능", "—"],
  ["AI 요구사항 후보", "✓", "✓"],
  ["확정과 수정 이력", "✓", "✓"],
  ["Excel · PDF 내보내기", "✓", "✓"],
  ["멤버 초대와 권한", "✓", "✓"],
  ["우선 지원", "—", "—"],
];

const FAQ = [
  { q: "PRO는 언제 쓸 수 있나요?", a: "PRO는 제공하지 않는 서비스입니다. 매무새는 지금의 무료 플랜 그대로 쓰시면 됩니다." },
  { q: "무료 플랜에 숨은 제한이 있나요?", a: "없습니다. 소개와 가이드에 나온 기능은 모두 무료 플랜에 들어 있어요." },
];

// 요금제: 무료 플랜만 쓸 수 있다. PRO 버튼은 제공하지 않는 서비스라고 알려 준다.
export default function PricingView() {
  const root = useRef<HTMLElement>(null);
  useReveal(root);

  return (
    <article ref={root} className="mx-auto grid w-full max-w-[1080px] gap-20 sm:gap-28">
      <header className="grid gap-6 pt-4 text-center sm:pt-10">
        <div data-hero className="flex justify-center"><Pill tone="yellow" className="rotate-2 shadow-[2px_2px_0_#111]">✦ Pricing</Pill></div>
        <h1 data-hero className="text-[44px] leading-[1.05] tracking-[-0.05em] sm:text-[84px]">
          <span className="block font-light">고민할 것 없이</span>
          <span className="block font-extrabold">무료로 시작</span>
        </h1>
        <p data-hero className="mx-auto max-w-md text-base leading-relaxed text-[#55534c]">필요한 기능은 모두 무료 플랜에 있어요. 카드 등록도, 기간 제한도 없습니다.</p>
      </header>

      <section aria-label="요금제" className="grid items-stretch gap-8 md:grid-cols-2">
        <div data-reveal className={cn(card, "grid content-between gap-8 bg-[#f2f69a] sm:p-8")}>
          <div className="grid gap-5">
            <div className="flex items-center justify-between"><h2 className="text-2xl font-extrabold tracking-tight">FREE</h2><Pill tone="dark">이용 중</Pill></div>
            <p className="flex items-end gap-2"><span className="text-6xl font-extrabold tracking-[-0.05em]">₩0</span><span className="pb-2 text-sm text-[#55534c]">/ 월</span></p>
            <ul className="grid gap-2.5 text-sm">
              {FREE.map((f) => <li key={f} className="flex gap-2"><span aria-hidden className="font-extrabold">✓</span>{f}</li>)}
            </ul>
          </div>
          <Btn href="/maemusae/projects" variant="dark" size="lg" className="w-full">무료로 시작하기 →</Btn>
        </div>

        <div data-reveal className={cn(card, "grid content-between gap-8 sm:p-8 md:rotate-1")}>
          <div className="grid gap-5">
            <div className="flex items-center justify-between"><h2 className="text-2xl font-extrabold tracking-tight">PRO</h2><Pill tone="orange">준비 안 함</Pill></div>
            <p className="flex items-end gap-2"><span className="text-6xl font-extrabold tracking-[-0.05em] text-[#6c6a62]">₩?,???</span><span className="pb-2 text-sm text-[#55534c]">/ 월</span></p>
            <ul className="grid gap-2.5 text-sm">
              {PRO.map((f) => <li key={f} className="flex gap-2"><span aria-hidden className="font-extrabold text-[#ff5a14]">✓</span>{f}</li>)}
            </ul>
          </div>
          <Btn variant="primary" size="lg" className="w-full" onClick={() => toast.info("제공하지 않는 서비스입니다.")}>PRO 결제하기</Btn>
        </div>
      </section>

      <section aria-label="플랜 비교" data-reveal className="grid gap-6">
        <h2 className="text-3xl tracking-[-0.04em] sm:text-5xl"><span className="font-light">한눈에</span> <span className="font-extrabold">비교</span></h2>
        <div className={cn(card, "overflow-x-auto p-0")}>
          <table className="w-full min-w-[480px] text-left text-sm">
            <thead>
              <tr className="border-b-2 border-[#111] bg-[#f6f6f3]"><th scope="col" className="px-6 py-4 font-extrabold">기능</th><th scope="col" className="px-6 py-4 font-extrabold">FREE</th><th scope="col" className="px-6 py-4 font-extrabold">PRO</th></tr>
            </thead>
            <tbody>
              {ROWS.map(([name, a, b]) => (
                <tr key={name} className="border-b border-[#111]/15 last:border-0"><th scope="row" className="px-6 py-4 font-semibold">{name}</th><td className="px-6 py-4">{a}</td><td className="px-6 py-4 text-[#6c6a62]">{b}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-3xl gap-4">
        {FAQ.map((f) => (
          <details key={f.q} data-reveal className="group rounded-[20px] border-2 border-[#111] bg-white px-6 py-4 shadow-[4px_4px_0_#111] open:bg-[#f2f69a]">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-bold [&::-webkit-details-marker]:hidden">
              {f.q}
              <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full border-2 border-[#111] bg-white text-lg leading-none transition-transform group-open:rotate-45">+</span>
            </summary>
            <p className="pt-3 text-sm leading-relaxed text-[#55534c]">{f.a}</p>
          </details>
        ))}
      </section>
    </article>
  );
}
