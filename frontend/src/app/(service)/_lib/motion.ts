"use client";

import gsap from "gsap";
import { useEffect, type RefObject } from "react";

// 화면 등장 순서: ① 제목([data-title], [data-hero]) → ② 사이드바([data-side]) → ③ 본문([data-rise])이 차례로 통통 튀며 나온다.
// 스크롤해야 보이는 구역([data-reveal])은 제목·사이드바·본문이 끝난 뒤부터, 화면에 들어올 때마다 한 번씩 나온다.
// 데이터를 불러온 뒤에 생기는 요소도 놓치지 않도록, 새로 생긴 요소를 감시해서 같은 순서로 보여 준다.
// 움직임 끄기와 "동작 줄이기"에서는 가만히 둔다.
const BOUNCE = "back.out(1.7)";
const motionOff = () => document.documentElement.dataset.mkMotion === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;

interface Pop {
  x?: number;
  y?: number;
  duration?: number;
  stagger?: number;
  ease?: string;
}

// 움직임(위치·크기)은 통통 튀는 곡선으로, 투명도는 부드러운 곡선으로 따로 준다. 튀는 곡선만 쓰면 투명도가 너무 빨리 1이 되어 등장이 안 보인다.
function pop(els: HTMLElement[], { x = 0, y = 0, duration = 0.8, stagger = 0.09, ease = BOUNCE }: Pop = {}) {
  return gsap
    .timeline()
    .from(els, { x, y, scale: 0.9, duration, stagger, ease, clearProps: "transform" }, 0)
    .from(els, { opacity: 0, duration: duration * 0.6, stagger, ease: "power2.out", clearProps: "opacity" }, 0);
}

const fresh = (scope: HTMLElement, selector: string) => Array.from(scope.querySelectorAll<HTMLElement>(selector)).filter((n) => !n.dataset.rised);

function play(scope: HTMLElement, observers: IntersectionObserver[]) {
  const titles = fresh(scope, "[data-title], [data-hero]");
  const sides = fresh(scope, "[data-side]");
  const rest = fresh(scope, "[data-rise]");
  const reveals = fresh(scope, "[data-reveal]");
  const all = [...titles, ...sides, ...rest, ...reveals];
  if (all.length === 0) return;
  all.forEach((n) => (n.dataset.rised = "1"));

  const tl = gsap.timeline();
  if (titles.length) tl.add(pop(titles, { y: 44, duration: 0.85, stagger: 0.1, ease: "back.out(1.9)" }));
  if (sides.length) tl.add(pop(sides, { x: -44, duration: 0.75, stagger: 0.07 }), titles.length ? ">-0.05" : 0);
  if (rest.length) tl.add(pop(rest, { y: 44 }), sides.length ? "<0.12" : ">-0.05");

  if (reveals.length) {
    // 앞 단계가 끝나기 전에는 숨겨 두었다가, 끝나면 화면에 들어온 구역부터 나온다
    gsap.set(reveals, { y: 56, scale: 0.9, opacity: 0 });
    const arm = () => {
      const io = new IntersectionObserver(
        (entries) =>
          entries.forEach((e) => {
            if (!e.isIntersecting) return;
            io.unobserve(e.target);
            const n = e.target as HTMLElement;
            gsap.set(n, { clearProps: "transform,opacity" }); // 숨겨 둔 상태를 풀고, 같은 시작점에서 튀어 나오게 한다
            pop([n], { y: 56, duration: 0.85 });
          }),
        { rootMargin: "0px 0px -8% 0px" },
      );
      observers.push(io);
      reveals.forEach((n) => io.observe(n));
    };
    if (tl.duration() === 0) arm();
    else tl.eventCallback("onComplete", arm);
  }
}

export function useRise(ref: RefObject<HTMLElement | null>, key?: unknown) {
  useEffect(() => {
    const scope = ref.current;
    if (!scope || motionOff()) return;
    const observers: IntersectionObserver[] = [];
    const ctx = gsap.context(() => play(scope, observers), scope);
    // 불러오기가 끝난 뒤에 생기는 요소(프로젝트 목록 등)도 같은 순서로 보여 준다
    const mo = new MutationObserver(() => ctx.add(() => play(scope, observers)));
    mo.observe(scope, { childList: true, subtree: true });
    return () => {
      mo.disconnect();
      observers.forEach((o) => o.disconnect());
      ctx.revert();
      // 개발 모드는 효과를 한 번 껐다 켜므로, 표시를 지워 두어야 다시 처음부터 보여 준다
      scope.querySelectorAll<HTMLElement>("[data-rised]").forEach((n) => delete n.dataset.rised);
    };
  }, [ref, key]);
}
