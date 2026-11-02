import type { Metadata } from "next";

import View from "./view";

export const metadata: Metadata = { title: "프로젝트", description: "내가 참여한 프로젝트 목록. 프로젝트를 등록하고 요구사항정의서를 정리합니다.", robots: { index: false, follow: false } };

// 데모 데이터는 브라우저에만 있어서 서버에서 미리 그릴 내용이 없다. 즉시 이동 검사를 끈다.
export const instant = false;

export default function Page() {
  return <View />;
}
