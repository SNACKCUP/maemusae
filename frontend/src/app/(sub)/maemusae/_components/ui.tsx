import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

export const card = "rounded-[24px] border-2 border-[#111] bg-white p-6 shadow-[5px_5px_0_#111]";
export const pill = "inline-flex items-center whitespace-nowrap rounded-full border-[1.5px] border-[#111] px-3 py-1 text-xs font-medium";

const btnBase = "inline-flex items-center justify-center gap-2 rounded-full border-2 border-[#111] font-semibold shadow-[3px_3px_0_#111] transition-[transform,box-shadow] duration-150 enabled:hover:-translate-x-0.5 enabled:hover:-translate-y-0.5 enabled:hover:shadow-[5px_5px_0_#111] enabled:active:translate-x-0.5 enabled:active:translate-y-0.5 enabled:active:shadow-none disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none";
const variants = {
  primary: "bg-[#ff5a14] text-white",
  dark: "bg-[#111] text-white",
  outline: "bg-white text-[#111]",
  ghost: "border-transparent bg-transparent text-[#111] shadow-none enabled:hover:translate-x-0 enabled:hover:translate-y-0 enabled:hover:bg-[#ebeae4] enabled:hover:shadow-none",
} as const;
const sizes = { sm: "px-3.5 py-1.5 text-xs", md: "px-5 py-2.5 text-sm", lg: "px-7 py-3.5 text-[15px]" } as const;

type BtnProps = { variant?: keyof typeof variants; size?: keyof typeof sizes; className?: string; children: ReactNode } & (
  | ({ href: string } & Omit<ComponentProps<typeof Link>, "className" | "children">)
  | ({ href?: undefined } & Omit<ComponentProps<"button">, "className" | "children">)
);

export function Btn({ variant = "outline", size = "md", className, children, ...rest }: BtnProps) {
  const cls = cn(btnBase, variants[variant], sizes[size], className);
  if ("href" in rest && rest.href !== undefined) return <Link {...(rest as ComponentProps<typeof Link>)} className={cls}>{children}</Link>;
  return <button type="button" {...(rest as ComponentProps<"button">)} className={cls}>{children}</button>;
}

export function Pill({ tone = "plain", className, children }: { tone?: "plain" | "yellow" | "dark" | "orange"; className?: string; children: ReactNode }) {
  const tones = { plain: "bg-white", yellow: "bg-[#f2f69a]", dark: "bg-[#111] text-white", orange: "border-[#ff5a14] bg-[#ff5a14] text-white" } as const;
  return <span className={cn(pill, tones[tone], className)}>{children}</span>;
}

export function PageHead({ eyebrow, title, light, children }: { eyebrow?: string; title: ReactNode; light?: string; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4" data-rise>
      <div>
        {eyebrow && <p className="mb-3 text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">{eyebrow}</p>}
        <h1 className="text-[34px] leading-[1.1] tracking-[-0.03em] sm:text-[44px]">
          {light && <span className="font-light">{light} </span>}
          <span className="font-extrabold">{title}</span>
        </h1>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function fmtDate(iso: string) {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${y}.${m}.${d}`;
}
export const fmtRange = (a: string, b: string) => `${fmtDate(a)} – ${fmtDate(b)}`;
export function fmtTime(iso: string) {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
