"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

import { Btn, Pill, card } from "../_components/ui";

const MARQUEE = ["모호한 요청", "요구사항 후보", "확인이 필요한 질문", "관리자 확정", "요구사항정의서", "기능정의서"];

const STEPS = [
  { no: "01", title: "문서를 올리세요", body: "고객이 보낸 요청서, 회의 메모, 메신저 캡처 어떤 것이든 좋아요. 정리해 줬으면 하는 방향을 한 줄 적어도 됩니다.", chip: "쇼핑몰_요청서.docx" },
  { no: "02", title: "AI가 후보를 가려내요", body: "문서에서 요구사항 후보를 뽑고, 근거가 된 문장을 함께 보여 줘요. 애매한 곳은 확인이 필요한 질문으로 따로 표시합니다.", chip: "REQ-001 · 기능 · 높음" },
  { no: "03", title: "팀이 다듬고 확정해요", body: "이름, 구분, 우선순위를 고치고 질문에 답한 뒤 관리자가 확정하면 요구사항정의서가 만들어져요.", chip: "확정됨 ✓" },
];

const FEATURES = [
  { title: "근거와 함께 보여 줘요", body: "후보마다 문서에서 찾은 원문을 붙여서, 왜 이 요구사항이 나왔는지 바로 확인할 수 있어요.", tone: "bg-[#f2f69a]", span: "lg:col-span-2" },
  { title: "물어볼 건 물어봐요", body: "“3초는 평균인가요, 최대인가요?” 같은 질문을 후보마다 남겨요.", tone: "bg-white", span: "" },
  { title: "확정은 관리자만", body: "누가 언제 확정했는지 남고, 고치면 수정 이력이 쌓여요.", tone: "bg-[#ff5a14] text-white", span: "" },
  { title: "Excel · PDF로 내보내요", body: "확정한 정의서는 표 그대로 받아 가서 고객과 공유하세요.", tone: "bg-white", span: "" },
  { title: "초대로 함께해요", body: "이메일로 초대하면 7일 안에 수락해 합류해요.", tone: "bg-white", span: "" },
  { title: "팀 단위 프로젝트", body: "프로젝트마다 멤버를 초대하고 관리자와 일반 권한을 나눠요. 일반 멤버는 확정 외의 모든 작업을 할 수 있어요.", tone: "bg-[#111] text-white", span: "lg:col-span-3" },
];

const FAQ = [
  { q: "어떤 문서를 올릴 수 있나요?", a: "요청서, 회의 메모, 이메일처럼 글로 된 문서를 올릴 수 있어요. 파일이 없어도 내용을 직접 적어서 정리할 수 있습니다." },
  { q: "AI가 뽑은 후보를 그대로 믿어도 되나요?", a: "아니요. 후보는 출발점이에요. 근거 문장과 질문을 보고 팀이 고치고 답한 뒤, 관리자가 확정해야 정의서가 됩니다." },
  { q: "확정한 뒤에 고칠 수 있나요?", a: "수정하면 이력이 남고, 다시 확정하면 새 판으로 저장돼요. 이전 판은 이력에서 볼 수 있습니다." },
  { q: "지금 입력한 데이터는 어디에 저장되나요?", a: "지금은 화면을 확인하기 위한 예시 데이터로 동작하며, 이 브라우저에만 저장돼요. 서버에는 올라가지 않습니다." },
];

// 소개: 서비스가 무엇인지 한 페이지로 보여 주는 화면. 스크롤하면 구역이 차례로 떠오른다.
export default function AboutView() {
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    if (document.documentElement.dataset.mkMotion === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    gsap.registerPlugin(ScrollTrigger);
    const ctx = gsap.context(() => {
      gsap.from("[data-hero]", { y: 40, opacity: 0, duration: 0.9, stagger: 0.1, ease: "power4.out" });
      gsap.to("[data-marquee-track]", { xPercent: -50, duration: 32, ease: "none", repeat: -1 });
      gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((n) => {
        gsap.from(n, { y: 48, opacity: 0, duration: 0.8, ease: "power3.out", clearProps: "transform,opacity", scrollTrigger: { trigger: n, start: "top 88%", once: true } });
      });
    }, el);
    return () => ctx.revert();
  }, []);

  return (
    <article ref={root} className="mx-auto grid w-full max-w-[1180px] gap-24 sm:gap-32">
      {/* 첫 화면 */}
      <header className="grid gap-8 pt-4 text-center sm:pt-10">
        <div data-hero className="flex justify-center"><Pill tone="yellow" className="-rotate-2 shadow-[2px_2px_0_#111]">✦ 요구사항 정리 도우미</Pill></div>
        <h1 data-hero className="text-[48px] leading-[1.02] tracking-[-0.05em] sm:text-[96px]">
          <span className="block font-light">말은 모호해도</span>
          <span className="block font-extrabold">정의서는 <span className="relative inline-block bg-[#ff5a14] px-3 text-white sm:px-5">명확하게</span></span>
        </h1>
        <p data-hero className="mx-auto max-w-xl text-base leading-relaxed text-[#55534c] sm:text-lg">“대충 쇼핑몰처럼요.” 이런 요청에서 요구사항을 가려내고, 팀이 함께 확정해 문서로 남기는 곳, 매무새입니다.</p>
        <div data-hero className="flex flex-wrap items-center justify-center gap-3">
          <Btn href="/maemusae/projects" variant="primary" size="lg">지금 시작하기 →</Btn>
          <Btn href="#how" variant="outline" size="lg">어떻게 쓰나요</Btn>
        </div>
      </header>

      {/* 숫자로 보기 */}
      <section aria-label="매무새 한눈에" data-reveal className="grid gap-4 sm:grid-cols-3">
        {[["3단계", "올리고, 가려내고, 확정해요"], ["3종 문서", "요구사항정의서 · 기능정의서 · 중간보고서"], ["2가지 권한", "관리자와 일반 멤버"]].map(([n, d], i) => (
          <div key={n} className={cn(card, i === 1 && "bg-[#f2f69a] sm:-rotate-1", i === 2 && "sm:rotate-1")}>
            <p className="text-3xl font-extrabold tracking-[-0.04em] sm:text-4xl">{n}</p>
            <p className="mt-3 text-sm text-[#55534c]">{d}</p>
          </div>
        ))}
      </section>

      {/* 흐르는 띠 */}
      <div className="-mx-5 overflow-hidden border-y-2 border-[#111] bg-[#111] py-4 text-white sm:-mx-12" aria-hidden>
        <div data-marquee-track className="flex w-max gap-10 whitespace-nowrap text-xl font-extrabold tracking-tight sm:text-2xl">
          {[...MARQUEE, ...MARQUEE, ...MARQUEE, ...MARQUEE].map((m, i) => (
            <span key={i} className="flex items-center gap-10">{m}<span className="text-[#ff5a14]">✦</span></span>
          ))}
        </div>
      </div>

      {/* 사용 방법 */}
      <section id="how" className="grid scroll-mt-8 gap-10">
        <div data-reveal className="grid gap-3">
          <p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">How it works</p>
          <h2 className="text-4xl leading-[1.1] tracking-[-0.04em] sm:text-6xl"><span className="font-light">세 걸음이면</span><br /><span className="font-extrabold">정의서가 됩니다</span></h2>
        </div>
        <ol className="grid gap-6 lg:grid-cols-3">
          {STEPS.map((s) => (
            <li key={s.no} data-reveal className={`${card} grid content-between gap-8`}>
              <div className="grid gap-4">
                <span className="grid size-12 place-items-center rounded-full border-2 border-[#111] bg-[#ff5a14] text-lg font-extrabold text-white">{s.no}</span>
                <h3 className="text-2xl font-extrabold tracking-tight">{s.title}</h3>
                <p className="text-sm leading-relaxed text-[#55534c]">{s.body}</p>
              </div>
              <span className="w-fit rounded-xl border-2 border-dashed border-[#111] bg-[#f6f6f3] px-3 py-2 text-xs font-semibold">{s.chip}</span>
            </li>
          ))}
        </ol>
      </section>

      {/* 전과 후 */}
      <section aria-label="변환 예시" className="grid gap-8">
        <div data-reveal className="grid gap-3 text-center">
          <p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">Before → After</p>
          <h2 className="text-4xl leading-[1.1] tracking-[-0.04em] sm:text-6xl"><span className="font-light">이렇게</span> <span className="font-extrabold">바뀌어요</span></h2>
        </div>
        <div className="grid items-stretch gap-6 lg:grid-cols-[1fr_auto_1fr]">
          <div data-reveal className="grid content-center gap-3 rounded-[24px] border-2 border-dashed border-[#111] p-6 sm:-rotate-1">
            <Pill className="w-fit">고객의 말</Pill>
            <p className="text-lg font-semibold leading-snug tracking-tight sm:text-xl lg:whitespace-nowrap lg:text-[19px]">“로그인 안 해도 일단 담아 둘 수 있었으면 해요”</p>
          </div>
          <span aria-hidden className="grid place-items-center text-4xl font-extrabold text-[#ff5a14] max-lg:rotate-90">→</span>
          <div data-reveal className={cn(card, "grid gap-3 bg-[#f2f69a] sm:rotate-1")}>
            <div className="flex flex-wrap items-center gap-2"><Pill tone="dark">REQ-001</Pill><Pill>기능</Pill><Pill>높음</Pill></div>
            <p className="text-lg font-extrabold leading-snug tracking-tight sm:text-xl lg:whitespace-nowrap lg:text-[19px]">비회원도 장바구니에 상품을 담을 수 있다</p>
            <p className="text-sm text-[#55534c]">로그인하지 않아도 상품을 담고, 로그인하면 그대로 이어진다.</p>
          </div>
        </div>
      </section>

      {/* 기능 */}
      <section className="grid gap-10">
        <div data-reveal className="grid gap-3">
          <p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">Features</p>
          <h2 className="text-4xl leading-[1.1] tracking-[-0.04em] sm:text-6xl"><span className="font-light">필요한 건</span><br /><span className="font-extrabold">다 들어 있어요</span></h2>
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} data-reveal className={cn(card, f.tone, f.span, "grid content-between gap-10 transition-transform hover:-translate-y-1")}>
              <span aria-hidden className="text-2xl">✦</span>
              <div className="grid gap-2">
                <h3 className="text-xl font-extrabold tracking-tight sm:text-2xl">{f.title}</h3>
                <p className="text-sm leading-relaxed opacity-80">{f.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 자주 묻는 질문 */}
      <section className="mx-auto grid w-full max-w-3xl gap-8">
        <div data-reveal className="grid gap-3 text-center">
          <p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">FAQ</p>
          <h2 className="text-4xl leading-[1.1] tracking-[-0.04em] sm:text-5xl"><span className="font-light">자주 묻는</span> <span className="font-extrabold">질문</span></h2>
        </div>
        <div className="grid gap-4">
          {FAQ.map((f) => (
            <details key={f.q} data-reveal className="group rounded-[20px] border-2 border-[#111] bg-white px-6 py-4 shadow-[4px_4px_0_#111] open:bg-[#f2f69a]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-bold [&::-webkit-details-marker]:hidden">
                {f.q}
                <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full border-2 border-[#111] bg-white text-lg leading-none transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="pt-3 text-sm leading-relaxed text-[#55534c]">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* 마무리 */}
      <section data-reveal className="grid gap-6 rounded-[32px] border-2 border-[#111] bg-[#ff5a14] px-6 py-14 text-center text-white shadow-[8px_8px_0_#111] sm:py-20">
        <h2 className="text-4xl leading-[1.05] tracking-[-0.05em] sm:text-7xl"><span className="font-light">모호함은 여기까지,</span><br /><span className="font-extrabold">이제 정리해요</span></h2>
        <div className="flex justify-center"><Btn href="/maemusae/projects" variant="dark" size="lg">프로젝트 만들러 가기 →</Btn></div>
      </section>
    </article>
  );
}
