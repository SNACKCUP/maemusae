"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";

import { UserAvatar } from "@/meerkit";

import { DocList } from "../../_components/DocList";
import { ProjectGuard } from "../../_components/ProjectGuard";
import { Btn, PageHead, Pill, card, fmtRange } from "../../_components/ui";
import { DOC_STATUS, ROLE_LABEL, docStatus } from "../../_lib/labels";
import { useConfirmedDocs, useMembers, useRequirementsDoc } from "../../_lib/queries";

const OTHER_FILES = [
  { slug: "spec", title: "기능정의서", desc: "확정한 요구사항으로 기능을 만들어요" },
  { slug: "report", title: "중간보고서", desc: "진행 상황을 정리해요" },
  { slug: "export", title: "내보내기", desc: "Excel, PDF로 받아요" },
];

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const { data: doc } = useRequirementsDoc(id);
  const { data: history } = useConfirmedDocs(id);
  const st = DOC_STATUS[docStatus(doc?.status)];

  return (
    <ProjectGuard projectId={id}>
      {({ project, role, isAdmin }) => (
        <div className="grid gap-8">
          <PageHead eyebrow={fmtRange(project.start_date, project.end_date)} title={project.name}>
            <Pill tone={isAdmin ? "yellow" : "plain"}>{role ? `내 권한 · ${ROLE_LABEL[role]}` : "보기 전용 (서비스 관리자)"}</Pill>
            {isAdmin && <Btn href={`/maemusae/projects/${id}/members`}>멤버 권한 관리</Btn>}
          </PageHead>

          <section aria-labelledby="files" className="grid gap-4" data-rise>
            <h2 id="files" className="text-xl font-extrabold tracking-tight">파일</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <Link2 href={`/maemusae/projects/${id}/requirements`} title="요구사항정의서" desc="문서를 올려 요구사항을 정리해요" status={<Pill tone={st.tone}>{st.label}</Pill>} primary />
              {OTHER_FILES.slice(0, 2).map((f) => (
                <Link2 key={f.slug} href={`/maemusae/projects/${id}/${f.slug}`} title={f.title} desc={f.desc} status={<Pill>준비 중</Pill>} />
              ))}
            </div>
          </section>

          {history && history.length > 0 && <DocList projectId={id} docs={history} />}

          <MemberChips projectId={id} count={project.member_count} isAdmin={isAdmin} />
        </div>
      )}
    </ProjectGuard>
  );
}

function MemberChips({ projectId, count, isAdmin }: { projectId: string; count: number; isAdmin: boolean }) {
  const { data: members = [] } = useMembers(projectId);
  return (
    <section aria-labelledby="members" className={`${card} grid gap-4`} data-rise>
      <div className="flex items-center justify-between">
        <h2 id="members" className="text-xl font-extrabold tracking-tight">멤버 {count}명</h2>
        {isAdmin && <Btn size="sm" href={`/maemusae/projects/${projectId}/members`}>관리</Btn>}
      </div>
      <ul className="flex flex-wrap gap-3">
        {members.map((m) => (
          <li key={m.id} className="flex items-center gap-2 rounded-full border-[1.5px] border-[#111] py-1 pl-1 pr-4 text-sm">
            <UserAvatar user={{ name: m.name, nickname: null, avatar_url: null }} size="sm" />
            {m.name}
            <span className="text-xs text-[#6c6a62]">{ROLE_LABEL[m.role]}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Link2({ href, title, desc, status, primary }: { href: string; title: string; desc: string; status: ReactNode; primary?: boolean }) {
  return (
    <Link href={href} className={`group grid gap-3 rounded-[28px] border-[1.5px] border-[#111] p-6 transition-transform hover:-translate-y-1 ${primary ? "bg-[#f2f69a]" : "bg-white"}`}>
      <div className="flex items-center justify-between"><span className="text-lg font-extrabold tracking-tight">{title}</span>{status}</div>
      <p className="text-sm text-[#55534c]">{desc}</p>
      <span className="text-sm font-semibold">열기 <span className="inline-block transition-transform group-hover:translate-x-1">→</span></span>
    </Link>
  );
}
