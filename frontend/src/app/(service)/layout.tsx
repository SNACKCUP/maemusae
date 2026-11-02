import { Suspense } from "react";

import { Shell } from "./_components/Shell";

export default function ServiceLayout({ children }: { children: React.ReactNode }) {
  // Shell이 현재 경로(usePathname)를 읽어서, 동적 경로에서는 Suspense 안에 두어야 빌드된다
  return (
    <Suspense fallback={null}>
      <Shell>{children}</Shell>
    </Suspense>
  );
}
