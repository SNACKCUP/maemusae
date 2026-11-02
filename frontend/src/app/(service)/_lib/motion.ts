"use client";

import gsap from "gsap";
import { useEffect, type RefObject } from "react";

// 화면이 열릴 때 [data-rise] 요소가 차례로 떠오른다. 움직임 끄기와 "동작 줄이기"에서는 가만히 둔다.
export function useRise(ref: RefObject<HTMLElement | null>, key?: unknown) {
  useEffect(() => {
    const scope = ref.current;
    if (!scope) return;
    if (document.documentElement.dataset.mkMotion === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = gsap.context(() => {
      gsap.from("[data-rise]", { y: 36, scale: 0.94, opacity: 0, duration: 0.8, stagger: 0.09, ease: "back.out(1.7)", clearProps: "transform,opacity" });
    }, scope);
    return () => ctx.revert();
  }, [ref, key]);
}

// 스크롤해서 [data-reveal] 요소가 보이면 한 번 떠오른다. 움직임 끄기와 "동작 줄이기"에서는 가만히 둔다.
export function useReveal(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const scope = ref.current;
    if (!scope) return;
    if (document.documentElement.dataset.mkMotion === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let ctx: gsap.Context | undefined;
    let cancelled = false;
    void import("gsap/ScrollTrigger").then(({ ScrollTrigger }) => {
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);
      ctx = gsap.context(() => {
        gsap.from("[data-hero]", { y: 50, scale: 0.92, opacity: 0, duration: 1, stagger: 0.12, ease: "back.out(1.6)" });
        gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((n) => {
          gsap.from(n, { y: 56, scale: 0.95, opacity: 0, duration: 0.9, ease: "back.out(1.5)", clearProps: "transform,opacity", scrollTrigger: { trigger: n, start: "top 88%", once: true } });
        });
      }, scope);
    });
    return () => {
      cancelled = true;
      ctx?.revert();
    };
  }, [ref]);
}
