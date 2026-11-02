"use client";

import gsap from "gsap";
import { useEffect, useRef } from "react";

const ITEMS = [
  { vague: "결제는 알아서 잘 되게요", code: "REQ-001", clear: "간편결제를 지원한다", tag: "높음" },
  { vague: "빨리 뜨면 좋겠어요", code: "REQ-002", clear: "목록은 3초 안에 응답한다", tag: "중간" },
  { vague: "회원은 대충 나눠서요", code: "REQ-003", clear: "등급별 혜택을 적용한다", tag: "중간" },
  { vague: "예쁘게 알려 주세요", code: "REQ-004", clear: "주문 알림 메일을 보낸다", tag: "낮음" },
];
// 흩어진 말풍선의 시작 자리(무대 크기에 대한 비율)와 기울기
const SCATTER = [
  { x: -0.12, y: -0.02, r: -10 },
  { x: 0.78, y: 0.04, r: 8 },
  { x: -0.08, y: 0.86, r: 7 },
  { x: 0.82, y: 0.9, r: -8 },
];
const ROW_H = 62; // 표의 한 줄 높이(h-[62px]와 같아야 한다)

// 매무새만의 연출: 고객이 흘린 모호한 말들이 흩어져 떠다니다가, 한 줄씩 정돈된 요구사항 표로 모이고 "확정" 도장이 찍힌다.
export function HeroStage() {
  const stage = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    const reduced = document.documentElement.dataset.mkMotion === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let ctx: gsap.Context | undefined;

    const build = () => {
      ctx?.revert();
      ctx = gsap.context(() => {
        const box = el.getBoundingClientRect();
        const rowW = Math.min(360, box.width - 48);
        const chips = gsap.utils.toArray<HTMLElement>("[data-chip]");
        const rows = gsap.utils.toArray<HTMLElement>("[data-row]");
        const vague = gsap.utils.toArray<HTMLElement>("[data-vague]");
        const clear = gsap.utils.toArray<HTMLElement>("[data-clear]");
        const tags = gsap.utils.toArray<HTMLElement>("[data-tag]");
        const stamp = el.querySelector<HTMLElement>("[data-stamp]");
        const card = el.querySelector<HTMLElement>("[data-card]");
        if (card) gsap.set(card, { width: rowW + 32 });

        const target = rows.map((row, i) => {
          const r = row.getBoundingClientRect();
          return { x: r.left - box.left + (r.width - rowW) / 2, y: r.top - box.top + (ROW_H - chips[i].offsetHeight) / 2 };
        });
        const home = chips.map((c, i) => ({
          x: SCATTER[i].x * box.width + (SCATTER[i].x > 0.5 ? -rowW * 0.55 : 0),
          y: SCATTER[i].y * (box.height - chips[i].offsetHeight),
          r: SCATTER[i].r,
        }));

        const place = (i: number, done: boolean) => ({ x: done ? target[i].x : home[i].x, y: done ? target[i].y : home[i].y, rotation: done ? 0 : home[i].r, width: done ? rowW : rowW * 0.8 });

        if (reduced) {
          chips.forEach((c, i) => gsap.set(c, { ...place(i, true), opacity: 1, backgroundColor: "#f2f69a" }));
          gsap.set(vague, { opacity: 0 });
          gsap.set(clear, { opacity: 1 });
          gsap.set(tags, { opacity: 1, scale: 1 });
          if (stamp) gsap.set(stamp, { opacity: 1, scale: 1, rotation: -8 });
          return;
        }

        chips.forEach((c, i) => gsap.set(c, { ...place(i, false), opacity: 0, scale: 0.7 }));
        gsap.set(tags, { opacity: 0, scale: 0.6 });
        if (stamp) gsap.set(stamp, { opacity: 0, scale: 2.4, rotation: -20 });

        const tl = gsap.timeline({ repeat: -1, repeatDelay: 0.4 });
        tl.to(chips, { opacity: 1, scale: 1, duration: 0.7, stagger: 0.14, ease: "back.out(1.8)" })
          // 떠다니는 느낌
          .to(chips, { y: "-=22", duration: 1.1, yoyo: true, repeat: 1, ease: "sine.inOut", stagger: 0.12 }, "<0.4")
          .addLabel("gather", "+=0.1")
          .to(chips, { x: (i) => target[i].x, y: (i) => target[i].y, rotation: 0, width: rowW, duration: 1.1, ease: "power3.inOut", stagger: 0.16 }, "gather")
          .to(vague, { opacity: 0, duration: 0.25, stagger: 0.16 }, "gather+=0.55")
          .to(clear, { opacity: 1, duration: 0.3, stagger: 0.16 }, "gather+=0.6")
          .to(chips, { backgroundColor: "#f2f69a", duration: 0.3, stagger: 0.16 }, "gather+=0.6")
          .to(tags, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2.4)", stagger: 0.16 }, "gather+=1.1")
          .addLabel("stamp", ">0.1")
          .to(stamp, { opacity: 1, scale: 1, rotation: -8, duration: 0.45, ease: "back.out(3)" }, "stamp")
          .to(card, { y: 4, duration: 0.08, yoyo: true, repeat: 1 }, "stamp+=0.3")
          .to({}, { duration: 1.8 })
          .to([chips, tags, stamp], { opacity: 0, duration: 0.5, stagger: 0 })
          .set(chips, { backgroundColor: "#ffffff" })
          .set(vague, { opacity: 1 })
          .set(clear, { opacity: 0 });
      }, el);
    };

    build();
    let t: ReturnType<typeof setTimeout>;
    const onResize = () => {
      clearTimeout(t);
      t = setTimeout(build, 200);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      clearTimeout(t);
      ctx?.revert();
    };
  }, []);

  return (
    <div ref={stage} className="relative mx-auto h-[480px] w-full max-w-[600px]" aria-hidden>
      {/* 정돈된 요구사항 표 */}
      <div data-card className="absolute left-1/2 top-[56px] -translate-x-1/2 rounded-[28px] border-2 border-[#111] bg-white p-4 shadow-[6px_6px_0_#111]">
        <div className="flex h-9 items-center justify-between px-2">
          <span className="text-sm font-extrabold">요구사항정의서</span>
          <span className="text-[11px] text-[#6c6a62]">쇼핑몰 리뉴얼</span>
        </div>
        <div className="grid">
          {ITEMS.map((it) => (
            <div key={it.code} data-row className="flex h-[62px] items-center justify-between border-t border-dashed border-[#111]/20 px-2">
              <span />
              <span data-tag className="rounded-full border-[1.5px] border-[#111] bg-white px-2.5 py-0.5 text-[11px] font-semibold">{it.tag}</span>
            </div>
          ))}
        </div>
        <span data-stamp className="absolute -right-3 -top-4 rounded-xl border-[2.5px] border-[#ff5a14] bg-white/90 px-3 py-1 text-base font-extrabold tracking-wider text-[#ff5a14]">확정</span>
      </div>

      {/* 흩어져 있다가 표로 모이는 말풍선 */}
      {ITEMS.map((it) => (
        <div key={it.code} data-chip className="absolute left-0 top-0 grid rounded-2xl border-[1.5px] border-[#111] bg-white px-4 py-3 text-sm shadow-[0_6px_0_#111]">
          <span data-vague className="col-start-1 row-start-1 font-medium">“{it.vague}”</span>
          <span data-clear className="col-start-1 row-start-1 flex items-center gap-2 font-semibold opacity-0"><span className="text-[11px] text-[#55534c]">{it.code}</span>{it.clear}</span>
        </div>
      ))}
    </div>
  );
}
