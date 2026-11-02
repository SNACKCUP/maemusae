import type { Metadata } from "next";

import View from "./view";

export const metadata: Metadata = { title: "버전 보기", description: "남겨 둔 요구사항 버전을 읽기 전용으로 봅니다.", robots: { index: false, follow: false } };

// 로그인한 멤버만 볼 수 있어 서버에서 미리 그릴 내용이 없다. 즉시 이동 검사를 끈다.
export const instant = false;

export default function Page() {
  return <View />;
}
