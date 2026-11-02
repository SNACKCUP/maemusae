"use client";

import { FileText, Lock } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { UserAvatar } from "@/meerkit";
import { cn } from "@/lib/utils";

import { DocList } from "../../_components/DocList";
import { ProjectGuard } from "../../_components/ProjectGuard";
import { Btn, PageHead, Pill, card, fmtDate, fmtRange } from "../../_components/ui";
import { DOC_PROGRESS, DOC_STATUS, ROLE_LABEL, docStatus } from "../../_lib/labels";
import { useConfirmedDocs, useMembers, useRequirementsDoc } from "../../_lib/queries";

// 아직 열 수 없는 문서. 열리면 여기서 빼고 위의 문서 카드로 올린다
const COMING_FILES = [
  { slug: "spec", title: "기능정의서", desc: "확정한 요구사항으로 기능을 만들어요" },
  { slug: "report", title: "중간보고서", desc: "진행 상황을 정리해요" },
];

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const { data: doc } = useRequirementsDoc(id);
  const { data: history } = useConfirmedDocs(id);
  const sk = docStatus(doc?.status);
  const st = DOC_STATUS[sk];

  return (
    <ProjectGuard projectId={id}>
      {({ project, isAdmin }) => (
        <div className="grid gap-10">
          <PageHead eyebrow={fmtRange(project.start_date, project.end_date)} title={project.name}>
            {isAdmin && <Btn href={`/projects/${id}/members`}>멤버 권한 관리</Btn>}
          </PageHead>

          <section aria-labelledby="files" className="grid gap-4" data-rise>
            <h2 id="files" className="text-xl font-extrabold tracking-tight">문서</h2>
            <ul className="grid gap-5 md:grid-cols-3">
              <li>
                <FileCard
                  href={`/projects/${id}/requirements`}
                  title="요구사항정의서"
                  desc="문서를 올려 요구사항을 정리해요"
                  status={<Pill tone={st.tone}>{st.label}</Pill>}
                  progress={DOC_PROGRESS[sk]}
                  accent
                />
              </li>
              {COMING_FILES.map((f) => (
                <li key={f.slug}>
                  <FileCard title={f.title} desc={f.desc} status={<Pill>준비 중</Pill>} />
                </li>
              ))}
            </ul>
          </section>

          {history && history.length > 0 && <DocList projectId={id} docs={history} />}

          <MemberProfiles projectId={id} count={project.member_count} isAdmin={isAdmin} />
        </div>
      )}
    </ProjectGuard>
  );
}

// 문서 카드. href가 없으면 열 수 없는 카드(준비 중)로 그린다. 진행률은 열 수 있는 문서에만 보여 준다
function FileCard({ href, title, desc, status, progress, accent }: { href?: string; title: string; desc: string; status: React.ReactNode; progress?: number; accent?: boolean }) {
  const disabled = !href;
  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <span aria-hidden className={cn("grid size-12 place-items-center rounded-2xl border-2 border-[#111]", accent ? "bg-[#f2f69a]" : "bg-[#ebeae4]")}>
          {disabled ? <Lock className="size-5 text-[#6c6a62]" /> : <FileText className="size-5" />}
        </span>
        {status}
      </div>
      <div className="grid gap-1.5">
        <h3 className="text-xl font-extrabold tracking-tight">{title}</h3>
        <p className="text-sm leading-relaxed text-[#55534c]">{desc}</p>
      </div>
      {progress !== undefined && (
        <div className="mt-auto grid gap-1.5">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="text-[#6c6a62]">진행률</span>
            <span className="tabular-nums">{progress}%</span>
          </div>
          <div role="progressbar" aria-label={`${title} 진행률`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress} className="h-3 overflow-hidden rounded-full border-2 border-[#111] bg-white">
            <div className="h-full rounded-full bg-[#ff5a14] transition-[width] duration-700 ease-[cubic-bezier(0.34,1.56,0.64,1)]" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}
      {disabled ? (
        <span className="mt-auto text-sm font-semibold text-[#6c6a62]">곧 열려요</span>
      ) : (
        <span className="text-sm font-semibold">열기 <span className="inline-block transition-transform duration-300 group-hover:translate-x-1.5">→</span></span>
      )}
    </>
  );
  if (disabled)
    return (
      <div aria-disabled="true" className="flex h-full cursor-not-allowed flex-col gap-5 rounded-[24px] border-2 border-dashed border-[#111]/50 bg-white/60 p-6 opacity-70 select-none">
        {body}
      </div>
    );
  return (
    <Link
      href={href}
      className={cn(
        "group flex h-full flex-col gap-5 rounded-[24px] border-2 border-[#111] p-6 shadow-[5px_5px_0_#111] transition-[transform,box-shadow] duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)] hover:-translate-x-1 hover:-translate-y-1.5 hover:shadow-[9px_9px_0_#111] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a14] focus-visible:ring-offset-2",
        accent ? "bg-[#fbfcdc]" : "bg-white",
      )}
    >
      {body}
    </Link>
  );
}

// 멤버 프로필: 한 사람씩 카드로. 관리자가 앞에 온다
function MemberProfiles({ projectId, count, isAdmin }: { projectId: string; count: number; isAdmin: boolean }) {
  const { data: members = [] } = useMembers(projectId);
  const sorted = [...members].sort((a, b) => (a.role === b.role ? a.name.localeCompare(b.name, "ko") : a.role === "ADMIN" ? -1 : 1));
  return (
    <section aria-labelledby="members" className="grid gap-4" data-rise>
      <div className="flex items-center justify-between">
        <h2 id="members" className="text-xl font-extrabold tracking-tight">멤버 {count}명</h2>
        {isAdmin && <Btn size="sm" href={`/projects/${projectId}/members`}>관리</Btn>}
      </div>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {sorted.map((m) => (
          <li key={m.id} className={cn(card, "grid content-start gap-4 p-5")}>
            <UserAvatar user={{ name: m.name, nickname: null, avatar_url: null }} size="lg" className="size-14 border-2 border-[#111] text-lg" />
            <div className="min-w-0">
              <p className="flex min-w-0 items-center gap-2">
                <Pill tone={m.role === "ADMIN" ? "orange" : "plain"} className="shrink-0 px-2 py-0.5 text-[11px]">{ROLE_LABEL[m.role]}</Pill>
                <span className="truncate text-base font-extrabold">{m.name}</span>
              </p>
              <p className="mt-1 truncate text-xs text-[#6c6a62]">@{m.user_id}</p>
              <p className="mt-0.5 text-[11px] text-[#6c6a62]">{fmtDate(m.joined_at)} 합류</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
