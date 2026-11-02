import type { Metadata } from "next";

import View from "./view";

export const metadata: Metadata = {
  title: "요금제",
  description: "매무새 요금제를 비교해 보세요. 지금은 무료 플랜만 이용할 수 있습니다.",
  alternates: { canonical: "/maemusae/pricing" },
};

// 브라우저에서 움직이는 화면이라 서버에서 미리 그릴 내용이 없다. 즉시 이동 검사를 끈다.
export const instant = false;

export default function Page() {
  return <View />;
}
