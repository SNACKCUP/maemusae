import type { Metadata } from "next";

import View from "./view";

export const metadata: Metadata = {
  title: "소개",
  description: "매무새가 무엇을 하는지, 어떻게 쓰는지 한 페이지로 살펴보세요. 모호한 고객 요청이 요구사항정의서가 되기까지의 과정을 소개합니다.",
  alternates: { canonical: "/maemusae/about" },
};

// 소개는 브라우저에서 움직이는 화면이라 서버에서 미리 그릴 내용이 없다. 즉시 이동 검사를 끈다.
export const instant = false;

export default function Page() {
  return <View />;
}
