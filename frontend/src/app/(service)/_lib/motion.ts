"use client";

import gsap from "gsap";
import { useEffect, type RefObject } from "react";

// 화면 등장 순서: ① 제목([data-title], [data-hero])이 먼저 튀어 나오고, ② 그 뒤로 나머지([data-side], [data-rise], [data-reveal])는
// 화면에 보이는 순간 하나씩 나온다. 이미 보이는 것은 제목이 끝나자마자 차례로, 아래쪽은 스크롤해서 들어올 때 나온다.
// 데이터를 불러온 뒤에 생기는 요소도 놓치지 않도록 새로 생긴 요소를 감시하고, 제목이 끝나기 전에 생긴 것은 끝나길 기다린다.
// 움직임 끄기와 "동작 줄이기"에서는 가만히 둔다. 인쇄할 때는 모두 보이게 한다.
const BOUNCE = "back.out(1.7)";
const STEP = 0.09;
const motionOff = () => document.documentElement.dataset.mkMotion === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;

interface Pop {
  x?: number;
  y?: number;
  duration?: number;
  stagger?: number;
  ease?: string;
}

// 움직임(위치·크기)은 통통 튀는 곡선으로, 투명도는 부드러운 곡선으로 따로 준다. 튀는 곡선만 쓰면 투명도가 너무 빨리 1이 되어 등장이 안 보인다.
function pop(els: HTMLElement[], { x = 0, y = 0, duration = 0.8, stagger = STEP, ease = BOUNCE }: Pop = {}) {
  return gsap
    .timeline()
    .from(els, { x, y, scale: 0.9, duration, stagger, ease, clearProps: "transform" }, 0)
    .from(els, { opacity: 0, duration: duration * 0.6, stagger, ease: "power2.out", clearProps: "opacity" }, 0);
}

const fresh = (scope: HTMLElement, selector: string) => Array.from(scope.querySelectorAll<HTMLElement>(selector)).filter((n) => !n.dataset.rised);
const offset = (n: HTMLElement) => (n.hasAttribute("data-side") ? { x: -44 } : { y: n.hasAttribute("data-reveal") ? 56 : 44 });

interface State {
  armed: boolean; // 제목이 끝났는가
  queue: (() => void)[];
  observers: IntersectionObserver[];
}

function whenArmed(state: State, fn: () => void) {
  if (state.armed) fn();
  else state.queue.push(fn);
}

function play(scope: HTMLElement, state: State) {
  const titles = fresh(scope, "[data-title], [data-hero]");
  const others = fresh(scope, "[data-side], [data-rise], [data-reveal]");
  if (titles.length === 0 && others.length === 0) return;
  [...titles, ...others].forEach((n) => (n.dataset.rised = "1"));

  if (titles.length) {
    state.armed = false;
    pop(titles, { y: 44, duration: 0.85, stagger: 0.1, ease: "back.out(1.9)" }).eventCallback("onComplete", () => {
      state.armed = true;
      state.queue.splice(0).forEach((fn) => fn());
    });
  }
  if (others.length === 0) return;

  // 차례가 오기 전에는 숨겨 둔다
  gsap.set(others, { opacity: 0 });
  whenArmed(state, () => {
    const io = new IntersectionObserver(
      (entries) => {
        // 한꺼번에 보이게 된 것들은 위에서부터 하나씩
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top || a.boundingClientRect.left - b.boundingClientRect.left);
        visible.forEach((e, i) => {
          const n = e.target as HTMLElement;
          io.unobserve(n);
          gsap.set(n, { clearProps: "opacity,transform" }); // 숨겨 둔 상태를 풀고, 같은 시작점에서 튀어 나오게 한다
          pop([n], { ...offset(n), duration: 0.85 }).delay(i * STEP);
        });
      },
      { rootMargin: "0px 0px -6% 0px" },
    );
    state.observers.push(io);
    others.forEach((n) => io.observe(n));
  });
}

export function useRise(ref: RefObject<HTMLElement | null>, key?: unknown) {
  useEffect(() => {
    const scope = ref.current;
    if (!scope || motionOff()) return;
    const state: State = { armed: true, queue: [], observers: [] };
    const ctx = gsap.context(() => play(scope, state), scope);
    // 불러오기가 끝난 뒤에 생기는 요소(프로젝트 목록 등)도 같은 규칙으로 보여 준다
    const mo = new MutationObserver(() => ctx.add(() => play(scope, state)));
    mo.observe(scope, { childList: true, subtree: true });
    // 인쇄 미리보기에는 아직 나오지 않은 구역도 모두 보여야 한다
    const showAll = () => {
      state.observers.forEach((o) => o.disconnect());
      scope.querySelectorAll<HTMLElement>("[data-rised]").forEach((n) => gsap.set(n, { clearProps: "opacity,transform" }));
    };
    window.addEventListener("beforeprint", showAll);
    return () => {
      window.removeEventListener("beforeprint", showAll);
      mo.disconnect();
      state.observers.forEach((o) => o.disconnect());
      ctx.revert();
      // 개발 모드는 효과를 한 번 껐다 켜므로, 표시를 지워 두어야 다시 처음부터 보여 준다
      scope.querySelectorAll<HTMLElement>("[data-rised]").forEach((n) => delete n.dataset.rised);
    };
  }, [ref, key]);
}
