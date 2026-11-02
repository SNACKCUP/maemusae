"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useSyncExternalStore, type ReactNode } from "react";

import { UserMenu, useAuth, useLogout } from "@/meerkit";
import { cn } from "@/lib/utils";

import { useRise } from "../_lib/motion";
import { THEME_STYLE, THEME_VARS } from "../_lib/theme";
import { Logo } from "./Logo";

const NAV = [
  { href: "/maemusae/about", label: "소개" },
  { href: "/maemusae/guide", label: "가이드" },
  { href: "/maemusae/pricing", label: "요금제" },
  { href: "/maemusae/projects", label: "프로젝트" },
];

// 매무새 전체의 틀: 전용 색과 글꼴을 한 번만 입히고, 상단 바에 로그인 상태(킷 계정)를 보여 준다.
export function Shell({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const logout = useLogout();
  const qc = useQueryClient();
  const router = useRouter();
  const path = usePathname();

  const onLogout = () =>
    logout.mutate(undefined, {
      onSettled: () => {
        // 다른 계정으로 다시 로그인했을 때 앞 사람의 프로젝트가 잠깐 보이지 않게 지운다
        qc.removeQueries({ queryKey: ["mms"] });
        router.push("/maemusae");
      },
    });

  // 대화상자는 body 아래에 그려지므로, 색을 html에도 입혀 둔다 (떠날 때 되돌린다)
  useEffect(() => {
    const root = document.documentElement;
    for (const [k, v] of Object.entries(THEME_VARS)) root.style.setProperty(k, v);
    return () => {
      for (const k of Object.keys(THEME_VARS)) root.style.removeProperty(k);
    };
  }, []);

  // 화면은 브라우저에서만 그린다 (서버 HTML·하이드레이션 중에는 false). 서버가 그린 HTML에 등장 애니메이션(GSAP)이
  // 먼저 스타일을 입히면 하이드레이션이 어긋난다
  const ready = useSyncExternalStore(noop, () => true, () => false);

  // [예비 목 저장소] 서버 없이 확정을 흉내 내야 할 때 주석을 풀어 쓴다 (store.ts 맨 위 설명 참고).
  // 그때는 위 ready 대신 아래처럼 목 데이터를 불러온 뒤에 화면을 그린다. import { useMaemusae } from "../_lib/store" 도 다시 넣는다
  // const [ready, setReady] = useState(false);
  // useEffect(() => {
  //   let cancelled = false;
  //   Promise.resolve(useMaemusae.persist.rehydrate()).then(() => {
  //     if (!cancelled) setReady(true);
  //   });
  //   return () => {
  //     cancelled = true;
  //   };
  // }, []);

  return (
    <div style={THEME_STYLE} className="min-h-screen bg-[#d9d9d6] p-3 text-[#111] antialiased sm:p-6 print:bg-white print:p-0">
      {/* eslint-disable-next-line @next/next/no-page-custom-font */}
      <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@300;400;500;600;800&display=swap" />
      <div className="flex min-h-[calc(100vh-1.5rem)] w-full flex-col overflow-x-clip rounded-[32px] bg-[#f6f6f3] px-5 pb-8 pt-5 sm:min-h-[calc(100vh-3rem)] sm:px-12 sm:pt-7 print:min-h-0 print:rounded-none print:bg-white print:p-0">
        <header className="print:hidden grid items-center gap-x-5 gap-y-3 rounded-[28px] border-2 border-[#111] bg-white px-4 py-2.5 shadow-[5px_5px_0_#111] lg:rounded-full lg:pl-6 lg:pr-3 lg:grid-cols-[1fr_auto_1fr]">
          <Link href="/maemusae" aria-label="매무새 홈" className="flex w-fit items-center"><Logo /></Link>
          <nav className="flex flex-wrap items-center gap-2 text-[13px] lg:justify-self-center" aria-label="주요 메뉴">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} aria-current={path.startsWith(n.href) ? "page" : undefined} className={cn("rounded-full border-2 px-3.5 py-1 font-semibold transition-colors", path.startsWith(n.href) ? "border-[#111] bg-[#f2f69a]" : "border-transparent hover:border-[#111]")}>{n.label}</Link>
            ))}
          </nav>
          <div className="flex flex-wrap items-center gap-2 lg:justify-self-end">
            {isLoading ? (
              <span className="h-9 w-24 rounded-full bg-[#ebeae4]" aria-busy />
            ) : user ? (
              <UserMenu user={user} onLogout={onLogout} />
            ) : (
              <span className="flex items-center gap-1 text-[12px] font-semibold"><Link href="/maemusae/login" className="rounded-full px-3 py-1.5 hover:bg-[#ebeae4]">로그인</Link><Link href="/maemusae/signup" className="rounded-full border-2 border-[#111] bg-[#ff5a14] px-3.5 py-1 text-white shadow-[2px_2px_0_#111] transition-[transform,box-shadow] hover:-translate-x-px hover:-translate-y-px hover:shadow-[3px_3px_0_#111]">회원가입</Link></span>
            )}
          </div>
        </header>
        <main className="mt-12 flex-1 sm:mt-16 print:mt-0">{ready ? <Rise key={path}>{children}</Rise> : <div className="h-[50vh]" aria-busy />}</main>
        <footer className="print:hidden mt-16 flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-[#111]/15 pt-5 text-[12px] text-[#6c6a62]">
          <span>매무새 — Meerkit 위에 얹은 서브 서비스</span>
          {/* [예비 목 저장소] 목을 다시 쓸 때만 주석을 푼다
          <button type="button" className="underline underline-offset-4" onClick={() => { if (window.confirm("이 브라우저에 저장된 확정 목 데이터를 지울까요? 프로젝트, 올린 파일, 요구사항 후보는 서버에 그대로 있어요.")) useMaemusae.getState().reset(); }}>목 데이터 초기화</button>
          */}
        </footer>
      </div>
    </div>
  );
}

const noop = () => () => {};

function Rise({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useRise(ref);
  return <div ref={ref}>{children}</div>;
}
