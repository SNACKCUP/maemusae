"use client";

import gsap from "gsap";
import { useEffect, useRef } from "react";

import { HeroStage } from "./_components/HeroStage";
import { Btn } from "./_components/ui";

const LINES = [
  [{ t: "모호한", light: true }, { t: "요청을", light: true }],
  [{ t: "명확한", light: false }, { t: "정의서로", light: false }],
];
const MARQUEE = ["“대충 쇼핑몰처럼요”", "“빨리 되면 좋겠어요”", "“알아서 잘 부탁드려요”", "“그때 말씀드린 그거요”", "“예쁘게요”", "“일단 시작해 보죠”"];

// 시작하기: 로그인한 뒤 처음 만나는 소개 화면. 제목이 글자 단위로 솟아오르고, 오른쪽에서는 모호한 말이 요구사항 표로 모인다.
export default function MaemusaeHome() {
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    if (document.documentElement.dataset.mkMotion === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: "power4.out" } });
      tl.from("[data-char]", { yPercent: 115, rotate: 4, duration: 1, stagger: 0.045 })
        .from("[data-hero-sub]", { y: 24, opacity: 0, duration: 0.8 }, "-=0.5")
        .from("[data-hero-cta]", { y: 24, opacity: 0, scale: 0.9, duration: 0.8, ease: "back.out(2)" }, "-=0.55")
        .from("[data-marquee]", { opacity: 0, duration: 0.8 }, "-=0.4");
      // 끝없이 흐르는 띠
      gsap.to("[data-marquee-track]", { xPercent: -50, duration: 38, ease: "none", repeat: -1 });
      // 버튼이 마우스를 살짝 따라온다
      const cta = el.querySelector<HTMLElement>("[data-hero-cta] a");
      if (cta) {
        const move = (e: MouseEvent) => {
          const r = cta.getBoundingClientRect();
          gsap.to(cta, { x: (e.clientX - (r.left + r.width / 2)) * 0.25, y: (e.clientY - (r.top + r.height / 2)) * 0.35, duration: 0.4, ease: "power3.out" });
        };
        const leave = () => gsap.to(cta, { x: 0, y: 0, duration: 0.6, ease: "elastic.out(1,0.5)" });
        cta.addEventListener("mousemove", move);
        cta.addEventListener("mouseleave", leave);
      }
    }, el);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={root} className="grid gap-14">
      <div className="mx-auto grid w-full max-w-[1180px] items-center gap-10 lg:grid-cols-[1fr_1fr] lg:gap-16">
        <div className="lg:justify-self-center">
          <h1 className="text-[44px] leading-[1.1] tracking-[-0.04em] sm:text-[64px]" aria-label="모호한 요청을 명확한 정의서로">
            {LINES.map((line, li) => (
              <span key={li} className="block" aria-hidden>
                {line.map((w) => (
                  <span key={w.t} className="mr-[0.25em] inline-block overflow-hidden pb-[0.08em] align-bottom">
                    {[...w.t].map((ch, i) => (
                      <span key={i} data-char className={`inline-block ${w.light ? "font-light" : "font-extrabold"}`}>{ch}</span>
                    ))}
                  </span>
                ))}
              </span>
            ))}
          </h1>
          <p data-hero-sub className="mt-6 max-w-lg text-[15px] leading-relaxed text-[#55534c]">고객이 보낸 문서를 올리면 AI가 요구사항을 가려내고,<br />확정은 프로젝트 관리자가 하고, 기능정의서는 이어서 만들어져요.</p>
          <div data-hero-cta className="mt-8 flex flex-wrap items-center gap-4">
            <Btn href="/maemusae/projects" variant="primary" size="lg">시작하기 →</Btn>
            <span className="text-xs text-[#6c6a62]">프로젝트를 만들고 팀과 함께 정리해 보세요</span>
          </div>
        </div>
        <HeroStage />
      </div>

      <div data-marquee className="-mx-5 overflow-hidden border-y-[1.5px] border-[#111] py-4 sm:-mx-12" aria-hidden>
        <div data-marquee-track className="flex w-max gap-10 whitespace-nowrap text-xl font-extrabold tracking-tight sm:text-2xl">
          {[...MARQUEE, ...MARQUEE].map((m, i) => (
            <span key={i} className="flex items-center gap-10">{m}<span className="text-[#ff5a14]">✦</span></span>
          ))}
        </div>
      </div>
    </section>
  );
}
