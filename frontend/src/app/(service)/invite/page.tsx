import type { Metadata } from "next";
import { Suspense } from "react";

import View from "./view";

export const metadata: Metadata = { title: "프로젝트 초대", description: "프로젝트 초대를 수락합니다.", robots: { index: false, follow: false } };

// 초대 토큰은 주소의 ?token=에 있어서 브라우저에서만 읽는다. 즉시 이동 검사를 끈다.
export const instant = false;

export default function Page() {
  return (
    <Suspense fallback={<div className="h-[40vh]" aria-busy />}>
      <View />
    </Suspense>
  );
}
