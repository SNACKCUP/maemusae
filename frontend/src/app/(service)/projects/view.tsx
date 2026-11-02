"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ChevronDown, Clock, Search } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { useAuth } from "@/meerkit";
import { cn } from "@/lib/utils";

import { ProjectFormDialog } from "../_components/dialogs";
import { Btn, PageHead, Pill, card, fmtAgo, fmtRange } from "../_components/ui";
import { READY_DOC_KINDS, ROLE_LABEL, docStatus } from "../_lib/labels";
import { apiError } from "../_lib/api";
import { useCreateProject, useProjectDocuments, useProjects } from "../_lib/queries";
import type { ApiDocument, ApiProject } from "../_lib/api";

// 프로젝트 단계는 문서들을 합쳐서 본다: 쓸 수 있는 문서가 모두 확정되면 "확정 완료", 아니면 "진행 중"
type Stage = "active" | "done";
const FILTERS = [
  { key: "all", label: "전체" },
  { key: "active", label: "진행 중" },
  { key: "done", label: "모두 확정" },
] as const;
type Filter = (typeof FILTERS)[number]["key"];

const SORTS = [
  { key: "recent", label: "최근 업데이트순" },
  { key: "name", label: "이름순" },
  { key: "period", label: "기간순" },
] as const;
type SortKey = (typeof SORTS)[number]["key"];

const MAX_CHIPS = 3;

// 카드에 보일 문서들: 지금 쓸 수 있는 종류만, 확정했는지와 함께
function chipsOf(docs: ApiDocument[] | undefined) {
  return READY_DOC_KINDS.map(({ kind, label }) => ({ kind, label, done: docStatus(docs?.find((d) => d.kind === kind)?.status) === "confirmed" }));
}
const stageOf = (docs: ApiDocument[] | undefined): Stage => (chipsOf(docs).every((c) => c.done) ? "done" : "active");
// 프로젝트의 마지막 움직임: 문서를 가장 나중에 고친 때, 없으면 프로젝트를 만든 때
const lastTouched = (p: ApiProject, docs: ApiDocument[] | undefined) => [p.created_at, ...(docs ?? []).map((d) => d.updated_at)].sort().at(-1) ?? p.created_at;

export default function ProjectsPage() {
  const router = useRouter();
  const auth = useAuth();
  const { data, isLoading, error } = useProjects();
  const createProject = useCreateProject();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<SortKey>("recent");
  const [adminOnly, setAdminOnly] = useState(false);

  // 서버가 내가 멤버인 프로젝트만 준다 (초대 대기 중인 것은 수락 전이라 빠진다)
  const visible = useMemo(() => data?.items ?? [], [data]);
  // 카드의 문서 칩과 최근 수정 시각은 프로젝트마다 문서 목록에서 온다
  const docsByProject = useProjectDocuments(visible.map((p) => String(p.id)));
  const docsOf = (id: number) => docsByProject[String(id)];
  const mine = visible
    .filter((p) => p.name.toLowerCase().includes(q.trim().toLowerCase()))
    .filter((p) => filter === "all" || stageOf(docsOf(p.id)) === filter)
    .filter((p) => !adminOnly || p.my_role === "ADMIN")
    .sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name, "ko");
      if (sort === "period") return b.start_date.localeCompare(a.start_date) || b.end_date.localeCompare(a.end_date);
      return lastTouched(b, docsOf(b.id)).localeCompare(lastTouched(a, docsOf(a.id)));
    });
  const hasAny = visible.length > 0;

  if (auth.isLoading || (auth.isAuthenticated && isLoading)) return <div className="h-[40vh]" aria-busy />;
  if (!auth.isAuthenticated)
    return (
      <div data-rise className={`${card} mx-auto grid max-w-lg justify-items-center gap-4 py-12 text-center`}>
        <h2 className="text-2xl font-extrabold tracking-tight">로그인하고 프로젝트를 시작하세요</h2>
        <p className="text-sm text-[#6c6a62]">프로젝트는 로그인한 멤버만 볼 수 있어요.</p>
        <div className="flex gap-2"><Btn href="/login" variant="dark">로그인</Btn><Btn href="/signup">회원가입</Btn></div>
      </div>
    );
  if (error) return <p role="alert" className="py-10 text-center text-sm text-[#b3261e]">{apiError(error, "프로젝트 목록을 불러오지 못했어요.")}</p>;

  return (
    <div className="grid gap-8">
      <PageHead eyebrow="Projects" light="내" title="프로젝트">
        <Btn variant="primary" onClick={() => setOpen(true)}>+ 프로젝트 등록</Btn>
      </PageHead>

      {hasAny && (
        <div className="flex flex-wrap items-center gap-3" data-rise>
          <div className="relative w-full sm:w-80">
            <label htmlFor="project-search" className="sr-only">프로젝트 검색</label>
            <Search aria-hidden className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2" />
            <Input id="project-search" type="search" value={q} placeholder="프로젝트 검색" onChange={(e) => setQ(e.target.value)} className="h-11 rounded-full border-2 border-[#111] bg-white pl-11 pr-5 shadow-[3px_3px_0_#111]" />
          </div>
          <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
            <div role="group" aria-label="단계로 거르기" className="flex flex-wrap items-center gap-2">
              {FILTERS.map(({ key, label }) => {
                const on = filter === key;
                const count = key === "all" ? visible.length : visible.filter((p) => stageOf(docsOf(p.id)) === key).length;
                return (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setFilter(key)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border-2 border-[#111] px-3.5 py-1.5 text-[13px] font-semibold transition-[transform,box-shadow,background-color] duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]",
                      on ? "bg-[#f2f69a] shadow-[3px_3px_0_#111]" : "bg-white hover:-translate-y-0.5",
                    )}
                  >
                    {label}
                    <span className="text-[11px] tabular-nums opacity-70">{count}</span>
                  </button>
                );
              })}
              <button
                type="button"
                aria-pressed={adminOnly}
                onClick={() => setAdminOnly((v) => !v)}
                className={cn(
                  "inline-flex items-center rounded-full border-2 border-[#111] px-3.5 py-1.5 text-[13px] font-semibold transition-[transform,box-shadow,background-color] duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]",
                  adminOnly ? "bg-[#ff5a14] text-white shadow-[3px_3px_0_#111]" : "bg-white hover:-translate-y-0.5",
                )}
              >
                내가 관리
              </button>
            </div>
            <div className="relative">
              <label htmlFor="project-sort" className="sr-only">정렬</label>
              <select
                id="project-sort"
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                className="h-10 cursor-pointer appearance-none rounded-full border-2 border-[#111] bg-white pl-4 pr-10 text-[13px] font-semibold shadow-[3px_3px_0_#111] outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a14]"
              >
                {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select>
              <ChevronDown aria-hidden className="pointer-events-none absolute right-3.5 top-1/2 size-4 -translate-y-1/2" />
            </div>
          </div>
        </div>
      )}

      {!hasAny ? (
        <div className={`${card} grid justify-items-center gap-4 py-16 text-center`} data-rise>
          <h2 className="text-2xl font-extrabold tracking-tight">첫 프로젝트를 등록해 시작하세요</h2>
          <p className="text-sm leading-relaxed text-[#6c6a62]">고객 문서를 올리려면 먼저 프로젝트가 필요해요.<br />기간과 이름만 정하면 돼요.</p>
          <Btn variant="primary" size="lg" onClick={() => setOpen(true)}>프로젝트 등록</Btn>
        </div>
      ) : mine.length === 0 && (q.trim() || filter !== "all" || adminOnly) ? (
        <p className="py-10 text-center text-sm text-[#6c6a62]" data-rise>{q.trim() ? `“${q}”에 맞는` : "조건에 맞는"} 프로젝트가 없어요.</p>
      ) : (
        <ul className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3" data-rise>
          {mine.map((p) => {
            const role = p.my_role;
            const docs = docsOf(p.id);
            const chips = chipsOf(docs);
            const done = stageOf(docs) === "done";
            return (
              <li key={p.id}>
                <Link href={`/projects/${p.id}`} className="group flex h-full flex-col overflow-hidden rounded-[24px] border-2 border-[#111] bg-white shadow-[6px_6px_0_#111] transition-[transform,box-shadow] duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)] hover:-translate-x-1 hover:-translate-y-1.5 hover:shadow-[10px_10px_0_#111] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a14] focus-visible:ring-offset-2">
                  <div className={cn("flex items-center justify-between gap-2 border-b-2 border-[#111] px-5 py-3", done ? "bg-[#ffd2b8]" : "bg-[#e3dfd1]")}>
                    <Pill tone={role === "ADMIN" ? "orange" : "plain"}>{role ? ROLE_LABEL[role] : "보기 전용"}</Pill>
                    <span className="text-xs font-semibold text-[#55534c]">{done ? "모두 확정" : "진행 중"}</span>
                  </div>
                  <div className="grid flex-1 content-between gap-6 px-5 py-6">
                    <div className="grid gap-4">
                      <h2 className="text-[26px] font-extrabold leading-[1.15] tracking-[-0.04em]">{p.name}</h2>
                      <DocChips chips={chips} />
                    </div>
                    <div className="grid gap-2">
                      <p className="w-fit rounded-full bg-[#ebeae4] px-3 py-1 text-xs font-semibold tabular-nums text-[#55534c]">{fmtRange(p.start_date, p.end_date)}</p>
                      <p className="flex items-center gap-1.5 text-xs text-[#6c6a62]"><Clock aria-hidden className="size-3.5" /> 최근 수정 {fmtAgo(lastTouched(p, docs))}</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-3 border-t-2 border-dashed border-[#111] px-5 py-4">
                    <span className="text-xs font-semibold text-[#55534c]">멤버 {p.member_count}명</span>
                    <span aria-hidden className="grid size-9 place-items-center rounded-full border-2 border-[#111] bg-white text-base font-bold transition-colors group-hover:bg-[#ff5a14] group-hover:text-white">→</span>
                  </div>
                </Link>
              </li>
            );
          })}
          <li>
            <button type="button" onClick={() => setOpen(true)} className="grid h-full min-h-[220px] w-full place-items-center content-center gap-3 rounded-[24px] border-2 border-dashed border-[#111] bg-transparent p-6 text-center transition-colors hover:bg-[#f2f69a]">
              <span aria-hidden className="grid size-12 place-items-center rounded-full border-2 border-[#111] bg-white text-2xl font-bold shadow-[3px_3px_0_#111]">+</span>
              <span className="text-base font-extrabold">새 프로젝트</span>
              <span className="text-xs text-[#6c6a62]">이름과 기간만 정하면 돼요</span>
            </button>
          </li>
        </ul>
      )}

      <ProjectFormDialog
        open={open}
        onOpenChange={setOpen}
        onCreate={async (v) => {
          try {
            const { project, invited, failed } = await createProject.mutateAsync(v);
            if (failed.length) toast.warning(`프로젝트를 만들었어요. ${failed.join(", ")}에는 초대장을 보내지 못했어요. 멤버 화면에서 다시 초대해 주세요.`);
            else toast.success(invited ? `프로젝트를 만들고 ${invited}명에게 초대장을 보냈어요.` : "프로젝트를 만들었어요.");
            router.push(`/projects/${project.id}`);
            return null;
          } catch (e) {
            return apiError(e, "프로젝트를 만들지 못했어요.");
          }
        }}
      />
    </div>
  );
}

// 문서별 상태 칩: 확정 전은 빈 동그라미, 확정 후는 채운 동그라미. 3개를 넘으면 나머지는 "+n"으로 줄인다
function DocChips({ chips }: { chips: { kind: string; label: string; done: boolean }[] }) {
  const shown = chips.slice(0, MAX_CHIPS);
  const rest = chips.length - shown.length;
  return (
    <ul className="flex flex-wrap items-center gap-1.5" aria-label="문서 상태">
      {shown.map((c) => (
        <li key={c.kind} className={cn("inline-flex items-center gap-1.5 rounded-full border-[1.5px] border-[#111] px-2.5 py-1 text-xs font-semibold", c.done ? "bg-[#f2f69a]" : "bg-white")}>
          <span aria-hidden className={cn("size-2.5 rounded-full border-[1.5px] border-[#111]", c.done && "bg-[#111]")} />
          {c.label}
          <span className="sr-only">{c.done ? " 확정" : " 확정 전"}</span>
        </li>
      ))}
      {rest > 0 && <li className="rounded-full border-[1.5px] border-dashed border-[#111] px-2.5 py-1 text-xs font-bold">+{rest}</li>}
    </ul>
  );
}
