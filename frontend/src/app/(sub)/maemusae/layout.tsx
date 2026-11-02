import type { Metadata, Viewport } from "next";
import { Suspense } from "react";

import { Shell } from "./_components/Shell";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const TITLE = "매무새 — 모호한 요청을 명확한 정의서로";
const DESCRIPTION = "고객이 보낸 모호한 요구 문서를 올리면 AI가 요구사항을 가려내고, 팀이 함께 다듬어 확정하면 요구사항정의서로 정리해 주는 서비스입니다.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: TITLE, template: "%s | 매무새" },
  description: DESCRIPTION,
  applicationName: "매무새",
  keywords: ["매무새", "요구사항정의서", "요구사항 정리", "요구사항 분석", "AI 요구사항", "기능정의서", "SI 프로젝트", "기획 문서"],
  category: "productivity",
  alternates: { canonical: "/maemusae" },
  manifest: "/maemusae/manifest.webmanifest",
  openGraph: { type: "website", locale: "ko_KR", siteName: "매무새", url: "/maemusae", title: TITLE, description: DESCRIPTION },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION },
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = { themeColor: "#F6F6F3", colorScheme: "light" };

export default function MaemusaeLayout({ children }: { children: React.ReactNode }) {
  // Shell이 현재 경로(usePathname)를 읽어서, 동적 경로에서는 Suspense 안에 두어야 빌드된다
  return (
    <Suspense fallback={null}>
      <Shell>{children}</Shell>
    </Suspense>
  );
}
