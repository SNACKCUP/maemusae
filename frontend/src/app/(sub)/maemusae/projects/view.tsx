"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { useAuth } from "@/meerkit";
import { cn } from "@/lib/utils";

import { ProjectFormDialog } from "../_components/dialogs";
import { Btn, PageHead, Pill, card, fmtRange } from "../_components/ui";
import { DOC_STATUS, ROLE_LABEL, docStatus } from "../_lib/labels";
import { apiError } from "../_lib/api";
import { useCreateProject, useProjects, useRequirementsDocStatuses } from "../_lib/queries";
import type { DocStatus } from "../_lib/types";

// 카드 윗띠와 상태 필터 버튼이 같은 색을 쓴다
const STATUS_BAND: Record<DocStatus, string> = {
  empty: "bg-[#e3dfd1]",
  analyzing: "bg-[#c9e4ff]",
  ready: "bg-[#f2f69a]",
  confirming: "bg-[#ffd2b8]",
  confirmed: "bg-[#ff5a14]",
};
const STATUS_ORDER: DocStatus[] = ["empty", "analyzing", "ready", "confirming", "confirmed"];

export default function ProjectsPage() {
  const router = useRouter();
  const auth = useAuth();
  const { data, isLoading, error } = useProjects();
  const createProject = useCreateProject();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<DocStatus | "all">("all");

  // 서버가 내가 멤버인 프로젝트만 준다 (초대 대기 중인 것은 수락 전이라 빠진다)
  const visible = useMemo(() => data?.items ?? [], [data]);
  // 카드 상태는 프로젝트마다 요구사항정의서의 서버 상태
  const serverStatus = useRequirementsDocStatuses(visible.map((p) => String(p.id)));
  const statusOf = (id: number): DocStatus => docStatus(serverStatus[String(id)]);
  const mine = visible.filter((p) => p.name.toLowerCase().includes(q.trim().toLowerCase())).filter((p) => status === "all" || statusOf(p.id) === status);
  const hasAny = visible.length > 0;

  if (auth.isLoading || (auth.isAuthenticated && isLoading)) return <div className="h-[40vh]" aria-busy />;
  if (!auth.isAuthenticated)
    return (
      <div className={`${card} mx-auto grid max-w-lg justify-items-center gap-4 py-12 text-center`}>
        <h2 className="text-2xl font-extrabold tracking-tight">로그인하고 프로젝트를 시작하세요</h2>
        <p className="text-sm text-[#6c6a62]">프로젝트는 로그인한 멤버만 볼 수 있어요.</p>
        <div className="flex gap-2"><Btn href="/maemusae/login" variant="dark">로그인</Btn><Btn href="/maemusae/signup">회원가입</Btn></div>
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
          <div role="group" aria-label="상태로 거르기" className="flex flex-wrap items-center gap-2 sm:ml-auto">
            {(["all", ...STATUS_ORDER] as const).map((k) => {
              const on = status === k;
              const count = k === "all" ? visible.length : visible.filter((p) => statusOf(p.id) === k).length;
              return (
                <button
                  key={k}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setStatus(k)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border-2 border-[#111] px-3.5 py-1.5 text-[13px] font-semibold transition-[transform,box-shadow] duration-150",
                    k === "all" ? "bg-white" : STATUS_BAND[k],
                    on ? "shadow-[3px_3px_0_#111]" : "hover:-translate-y-0.5",
                  )}
                >
                  {k === "all" ? "전체" : DOC_STATUS[k].label}
                  <span className="text-[11px] tabular-nums opacity-70">{count}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {!hasAny ? (
        <div className={`${card} grid justify-items-center gap-4 py-16 text-center`} data-rise>
          <h2 className="text-2xl font-extrabold tracking-tight">첫 프로젝트를 등록해 시작하세요</h2>
          <p className="text-sm leading-relaxed text-[#6c6a62]">고객 문서를 올리려면 먼저 프로젝트가 필요해요.<br />기간과 이름만 정하면 돼요.</p>
          <Btn variant="primary" size="lg" onClick={() => setOpen(true)}>프로젝트 등록</Btn>
        </div>
      ) : mine.length === 0 && q.trim() ? (
        <p className="py-10 text-center text-sm text-[#6c6a62]" data-rise>“{q}”에 맞는 프로젝트가 없어요.</p>
      ) : (
        <ul className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3" data-rise>
          {mine.map((p) => {
            const role = p.my_role;
            const sk = statusOf(p.id);
            const st = DOC_STATUS[sk];
            return (
              <li key={p.id}>
                <Link href={`/maemusae/projects/${p.id}`} className="group flex h-full flex-col overflow-hidden rounded-[24px] border-2 border-[#111] bg-white shadow-[6px_6px_0_#111] transition-[transform,box-shadow] duration-150 hover:-translate-x-1 hover:-translate-y-1 hover:shadow-[10px_10px_0_#111]">
                  <div className={cn("flex items-center justify-between gap-2 border-b-2 border-[#111] px-5 py-3", STATUS_BAND[sk])}>
                    <Pill tone={sk === "confirmed" ? "plain" : "dark"}>{st.label}</Pill>
                    <Pill tone={role === "ADMIN" ? "orange" : "plain"}>{role ? ROLE_LABEL[role] : "보기 전용"}</Pill>
                  </div>
                  <div className="grid flex-1 content-between gap-10 px-5 py-6">
                    <h2 className="text-[26px] font-extrabold leading-[1.15] tracking-[-0.04em]">{p.name}</h2>
                    <p className="w-fit rounded-full bg-[#ebeae4] px-3 py-1 text-xs font-semibold tabular-nums text-[#55534c]">{fmtRange(p.start_date, p.end_date)}</p>
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
            router.push(`/maemusae/projects/${project.id}`);
            return null;
          } catch (e) {
            return apiError(e, "프로젝트를 만들지 못했어요.");
          }
        }}
      />
    </div>
  );
}
