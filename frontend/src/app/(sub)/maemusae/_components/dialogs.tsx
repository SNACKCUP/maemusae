"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DateRangePicker } from "@/meerkit";

import type { ApiSource } from "../_lib/api";
import { Btn, Pill } from "./ui";

const emailOk = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

/** 이메일을 하나씩 추가해 칩으로 모아 두는 입력 */
export function EmailChips({ value, onChange, id }: { value: string[]; onChange: (v: string[]) => void; id: string }) {
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  function add() {
    const t = text.trim();
    if (!t) return;
    if (!emailOk(t)) return setError("이메일 형식이 올바르지 않아요.");
    if (value.some((v) => v.toLowerCase() === t.toLowerCase())) return setError("이미 추가한 이메일이에요.");
    onChange([...value, t]);
    setText("");
    setError("");
  }
  return (
    <div className="grid gap-2">
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {value.map((v) => (
            <li key={v}>
              <Pill tone="yellow" className="gap-1.5">
                {v}
                <button type="button" aria-label={`${v} 빼기`} className="text-[#111]/70 hover:text-[#111]" onClick={() => onChange(value.filter((x) => x !== v))}>✕</button>
              </Pill>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <Input id={id} type="email" value={text} placeholder="name@company.com" onChange={(e) => { setText(e.target.value); setError(""); }} onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); add(); } }} className="h-10 rounded-full border-[#111] bg-white" />
        <Btn size="sm" className="h-10 w-max shrink-0 whitespace-nowrap" onClick={add}>추가</Btn>
      </div>
      {error && <p role="alert" className="text-xs text-[#b3261e]">{error}</p>}
    </div>
  );
}

export function ProjectFormDialog({ open, onOpenChange, onCreate }: { open: boolean; onOpenChange: (v: boolean) => void; onCreate: (v: { name: string; startDate: string; endDate: string; inviteEmails: string[] }) => Promise<string | null> }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [startDate, setStart] = useState("");
  const [endDate, setEnd] = useState("");
  const [emails, setEmails] = useState<string[]>([]);
  const [error, setError] = useState("");

  function reset() {
    setName(""); setStart(""); setEnd(""); setEmails([]); setError("");
  }
  // onCreate는 서버에 저장하고, 실패하면 보여 줄 문구를 돌려준다
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (!name.trim()) return setError("프로젝트명을 입력해 주세요.");
    if (!startDate || !endDate) return setError("프로젝트 기간을 골라 주세요.");
    if (endDate < startDate) return setError("종료일은 시작일 이후여야 해요.");
    setBusy(true);
    const err = await onCreate({ name: name.trim(), startDate, endDate, inviteEmails: emails });
    setBusy(false);
    if (err) return setError(err);
    reset();
    onOpenChange(false);
  }
  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) reset(); onOpenChange(v); }}>
      <DialogContent className="max-w-lg rounded-[28px] border-[1.5px] border-[#111]">
        <DialogHeader>
          <DialogTitle className="text-2xl font-extrabold tracking-tight">프로젝트 등록</DialogTitle>
          <DialogDescription>시작일, 종료일, 프로젝트명만 있으면 시작할 수 있어요. 팀 멤버는 나중에 초대해도 됩니다.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-4" noValidate>
          <Field label="프로젝트 기간" htmlFor="pf-range">
            <DateRangePicker id="pf-range" value={{ start: startDate, end: endDate }} onChange={(r) => { setStart(r.start); setEnd(r.end); }} placeholder="시작일 – 종료일" className="h-10 rounded-xl border-[#111] bg-white" />
          </Field>
          <Field label="프로젝트명" htmlFor="pf-name"><Input id="pf-name" value={name} maxLength={50} placeholder="예: 쇼핑몰 리뉴얼" onChange={(e) => setName(e.target.value)} className="h-10 rounded-xl border-[#111] bg-white" /></Field>
          <Field label="팀 멤버 추가 (선택)" htmlFor="pf-members"><EmailChips id="pf-members" value={emails} onChange={setEmails} /></Field>
          <p className="text-xs text-[#6c6a62]">추가한 멤버에게는 초대장이 발송되고, 수락하면 일반 멤버가 됩니다. 프로젝트를 만든 분은 이 프로젝트의 관리자가 됩니다.</p>
          {error && <p role="alert" className="text-sm font-medium text-[#b3261e]">{error}</p>}
          <div className="flex justify-end gap-2">
            <Btn onClick={() => { reset(); onOpenChange(false); }}>취소</Btn>
            <Btn variant="primary" type="submit" disabled={busy}>{busy ? "등록 중…" : "등록"}</Btn>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={htmlFor} className="text-xs font-bold">{label}</Label>
      {children}
    </div>
  );
}

export function InviteDialog({ open, onOpenChange, onInvite }: { open: boolean; onOpenChange: (v: boolean) => void; onInvite: (email: string) => Promise<string | null> }) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (!emailOk(email.trim())) return setError("이메일 형식이 올바르지 않아요.");
    setBusy(true);
    const err = await onInvite(email.trim());
    setBusy(false);
    if (err) return setError(err);
    setEmail("");
    setError("");
    onOpenChange(false);
  }
  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) { setEmail(""); setError(""); } onOpenChange(v); }}>
      <DialogContent className="max-w-md rounded-[28px] border-[1.5px] border-[#111]">
        <DialogHeader>
          <DialogTitle className="text-2xl font-extrabold tracking-tight">멤버 초대</DialogTitle>
          <DialogDescription>이메일로 초대장을 보내요. 가입하지 않은 분은 링크로 가입한 뒤 수락할 수 있고, 초대는 7일 동안 유효해요.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-4" noValidate>
          <Field label="이메일" htmlFor="inv-email"><Input id="inv-email" type="email" value={email} placeholder="name@company.com" autoFocus onChange={(e) => { setEmail(e.target.value); setError(""); }} className="h-10 rounded-xl border-[#111] bg-white" /></Field>
          {error && <p role="alert" className="text-sm font-medium text-[#b3261e]">{error}</p>}
          <div className="flex justify-end gap-2">
            <Btn onClick={() => onOpenChange(false)}>취소</Btn>
            <Btn variant="primary" type="submit" disabled={busy}>{busy ? "보내는 중…" : "초대장 보내기"}</Btn>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ConfirmDialog({ open, onOpenChange, title, body, confirmLabel, cancelLabel = "취소", danger, onConfirm }: { open: boolean; onOpenChange: (v: boolean) => void; title: string; body: ReactNode; confirmLabel: string; cancelLabel?: string; danger?: boolean; onConfirm: () => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-[28px] border-[1.5px] border-[#111]">
        <DialogHeader>
          <DialogTitle className="text-2xl font-extrabold tracking-tight">{title}</DialogTitle>
          <DialogDescription asChild><div className="text-sm text-[#6c6a62]">{body}</div></DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2">
          <Btn onClick={() => onOpenChange(false)}>{cancelLabel}</Btn>
          <Btn variant={danger ? "dark" : "primary"} onClick={() => { onConfirm(); onOpenChange(false); }}>{confirmLabel}</Btn>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 히스토리 보기를 누르면 나오는 Pro 안내. 실제 결제는 없다. */
export function ProDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg rounded-[28px] border-[1.5px] border-[#111]">
        <DialogHeader>
          <DialogTitle className="text-2xl font-extrabold tracking-tight">히스토리는 Pro에서 볼 수 있어요</DialogTitle>
          <DialogDescription>확정할 때마다 버전이 쌓이고, 이전 버전과 비교하거나 되돌릴 수 있어요.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-2xl border-[1.5px] border-[#111] p-4"><b className="block text-base">Free</b><ul className="mt-2 grid gap-1 text-[#6c6a62]"><li>프로젝트 3개</li><li>최신 버전만 보관</li></ul></div>
          <div className="rounded-2xl border-[1.5px] border-[#111] bg-[#f2f69a] p-4"><b className="block text-base">Pro</b><ul className="mt-2 grid gap-1"><li>프로젝트 무제한</li><li>버전 히스토리와 비교</li></ul></div>
        </div>
        <p className="text-xs text-[#6c6a62]">데모 화면이라 실제 결제는 진행되지 않아요.</p>
        <div className="flex justify-end gap-2">
          <Btn onClick={() => onOpenChange(false)}>닫기</Btn>
          <Btn variant="primary" onClick={() => onOpenChange(false)}>Pro로 업그레이드</Btn>
        </div>
      </DialogContent>
    </Dialog>
  );
}

const RESTART_PROMPT_MAX = 2000; // 서버 AnalyzeRequest.prompt 상한과 같게

/** 다시 분석 창: 경고 + 분석할 문서 목록 + 이번에 바랄 점(선택). 적은 글은 AI 지시로 함께 보낸다 */
export function RestartDialog({ open, onOpenChange, warning, sources, onConfirm }: { open: boolean; onOpenChange: (v: boolean) => void; warning: ReactNode; sources: ApiSource[]; onConfirm: (prompt: string) => void }) {
  const [prompt, setPrompt] = useState("");
  const close = (v: boolean) => {
    if (!v) setPrompt("");
    onOpenChange(v);
  };
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-w-lg rounded-[28px] border-[1.5px] border-[#111]">
        <DialogHeader>
          <DialogTitle className="text-2xl font-extrabold tracking-tight">처음부터 다시 분석할까요?</DialogTitle>
          <DialogDescription asChild><div className="text-sm text-[#6c6a62]">{warning}</div></DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <p className="text-sm font-bold">분석할 문서 {sources.length}개</p>
          <ul className="grid max-h-40 gap-1 overflow-y-auto rounded-2xl bg-[#f6f6f3] px-4 py-3 text-sm">
            {sources.map((s) => (
              <li key={s.id} className="flex min-w-0 justify-between gap-3">
                <span className="truncate font-semibold">{s.filename ?? "직접 입력한 내용"}</span>
                <span className="shrink-0 text-xs text-[#6c6a62]">{s.page_count}쪽 · {s.uploaded_by_name}</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-[#6c6a62]">문서를 더하거나 빼려면 창을 닫고 아래 &quot;올린 문서&quot;에서 바꿔 주세요.</p>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="restart-prompt" className="text-sm font-bold">이번 분석에 바라는 점 (선택)</Label>
          <textarea
            id="restart-prompt"
            rows={4}
            maxLength={RESTART_PROMPT_MAX}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="지난 결과에서 아쉬운 점이나 이번에 더 신경 쓸 방향을 적어 주세요. 예: 기능 요구사항이 너무 잘게 쪼개졌어요. 화면 단위로 묶어 주세요."
            className="w-full rounded-2xl border-[1.5px] border-[#111] bg-white px-4 py-3 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-[#ff5a14]/40"
          />
          <p className="text-right text-xs tabular-nums text-[#6c6a62]">{prompt.length} / {RESTART_PROMPT_MAX}</p>
        </div>
        <div className="flex justify-end gap-2">
          <Btn onClick={() => close(false)}>취소</Btn>
          <Btn variant="dark" onClick={() => { onConfirm(prompt.trim()); close(false); }}>다시 분석</Btn>
        </div>
      </DialogContent>
    </Dialog>
  );
}
