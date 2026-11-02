import type { Metadata } from "next";

import View from "./view";

export const metadata: Metadata = {
  title: { absolute: "매무새 — 모호한 요청을 명확한 정의서로" },
  alternates: { canonical: "/maemusae" },
};

// 데모 데이터는 브라우저에만 있어서 서버에서 미리 그릴 내용이 없다. 즉시 이동 검사를 끈다.
export const instant = false;

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

// 검색 결과에 서비스 정보를 알려 주는 구조화 데이터
const JSON_LD = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "매무새",
  url: `${SITE_URL}/maemusae`,
  inLanguage: "ko",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description: "고객이 보낸 모호한 요구 문서를 올리면 AI가 요구사항을 가려내고, 팀이 확정해 요구사항정의서로 정리해 주는 서비스",
  image: `${SITE_URL}/maemusae/icon-512.png`,
};

export default function Page() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD).replace(/</g, "\\u003c") }} />
      <View />
    </>
  );
}
