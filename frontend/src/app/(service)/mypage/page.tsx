import type { Metadata } from "next";

import View from "./view";

export const metadata: Metadata = { title: "마이페이지", description: "내 계정 정보와 AI API 키를 관리합니다.", robots: { index: false, follow: false } };

// 로그인 상태는 브라우저에서 확인하므로 서버에서 미리 그릴 내용이 없다. 즉시 이동 검사를 끈다.
export const instant = false;

export default function Page() {
  return <View />;
}
