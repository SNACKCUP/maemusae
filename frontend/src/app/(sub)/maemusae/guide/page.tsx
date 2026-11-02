import type { Metadata } from "next";

import View from "./view";

export const metadata: Metadata = {
  title: "사용 가이드",
  description: "프로젝트를 만들고 문서를 올려 요구사항정의서를 확정하기까지, 매무새 사용법을 순서대로 안내합니다.",
  alternates: { canonical: "/maemusae/guide" },
};

// 브라우저에서 움직이는 화면이라 서버에서 미리 그릴 내용이 없다. 즉시 이동 검사를 끈다.
export const instant = false;

export default function Page() {
  return <View />;
}
