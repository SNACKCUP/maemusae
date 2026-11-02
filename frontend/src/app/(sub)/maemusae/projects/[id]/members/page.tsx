import type { Metadata } from "next";

import View from "./view";

export const metadata: Metadata = { title: "멤버 권한 관리", description: "프로젝트 멤버를 초대하고 권한을 관리합니다.", robots: { index: false, follow: false } };

// 데모 데이터는 브라우저에만 있어서 서버에서 미리 그릴 내용이 없다. 즉시 이동 검사를 끈다.
export const instant = false;

export default function Page() {
  return <View />;
}
