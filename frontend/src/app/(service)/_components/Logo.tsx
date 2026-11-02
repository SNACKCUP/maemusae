import { cn } from "@/lib/utils";

// 매무새 로고: 깃털(새)에 확정 체크가 겹친 마크. 마크 그림은 public/maemusae/mark.svg와 같다.
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 220 250" fill="none" aria-hidden className={cn("h-full w-auto", className)}>
      <path d="M44 180C36 108 92 38 206 14C211 50 199 84 168 108C184 107 192 105 197 102C190 146 156 186 100 197C80 200 60 195 44 180Z" stroke="#111" strokeWidth="14" strokeLinejoin="round" />
      <path d="M33 214L17 238" stroke="#111" strokeWidth="14" strokeLinecap="round" />
      <path d="M30 184L48 204L127 108" stroke="#FF5A14" strokeWidth="14" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// 마크 + 글자 로고. 글자는 그림이 아니라 진짜 글자로 둔다(읽기·검색에 유리).
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="h-8 w-7 shrink-0"><LogoMark /></span>
      <span className="text-[20px] font-extrabold leading-none tracking-[-0.04em]">매무새</span>
    </span>
  );
}
