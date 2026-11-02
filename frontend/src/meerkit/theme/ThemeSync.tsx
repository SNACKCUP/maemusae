"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { applyTheme, effectiveTheme } from "./theme";

// 화면을 옮길 때(서브 프로젝트는 항상 밝게)와 운영체제 설정이 바뀔 때 테마를 다시 맞춘다.
export function ThemeSync() {
  const pathname = usePathname();
  useEffect(() => {
    applyTheme(effectiveTheme(pathname));
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme(effectiveTheme(pathname));
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [pathname]);
  return null;
}
