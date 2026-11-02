import type { CSSProperties } from "react";

// 매무새 전용 색. Meerkit 컴포넌트(입력창, 체크박스, 대화상자)도 이 값을 따라간다.
// 적용은 Shell에서 한 번만 한다. (CLAUDE.md의 "인라인 스타일 금지"의 예외: .claude/harness/rules/tailwind-v4.md 참고)
export const INK = "#111111";
export const ORANGE = "#ff5a14";
export const YELLOW = "#f2f69a";
export const SAND = "#e3dfd1";
export const PAPER = "#f6f6f3";

export const THEME_VARS: Record<string, string> = {
  "--mk-background": PAPER,
  "--mk-foreground": INK,
  "--mk-card": "#ffffff",
  "--mk-surface": "#ffffff",
  "--mk-muted": "#eceae2",
  "--mk-muted-foreground": "#6c6a62",
  "--mk-accent": "#eceae2",
  "--mk-border": "#d3d0c4",
  "--mk-primary": INK,
  "--mk-primary-foreground": "#ffffff",
  "--mk-brand": ORANGE,
  "--mk-radius": "1rem",
  "--mk-shadow-soft": "none",
};

export const FONT_STACK = '"Hanken Grotesk", "Pretendard Variable", Pretendard, "Helvetica Neue", Arial, sans-serif';

export const THEME_STYLE = { ...THEME_VARS, fontFamily: FONT_STACK } as CSSProperties;
