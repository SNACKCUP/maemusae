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
      gsap.from("[data-rise]", { y: 22, opacity: 0, duration: 0.7, stagger: 0.07, ease: "power3.out", clearProps: "transform,opacity" });
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
        gsap.from("[data-hero]", { y: 40, opacity: 0, duration: 0.9, stagger: 0.1, ease: "power4.out" });
        gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((n) => {
          gsap.from(n, { y: 48, opacity: 0, duration: 0.8, ease: "power3.out", clearProps: "transform,opacity", scrollTrigger: { trigger: n, start: "top 88%", once: true } });
        });
      }, scope);
    });
    return () => {
      cancelled = true;
      ctx?.revert();
    };
  }, [ref]);
}
