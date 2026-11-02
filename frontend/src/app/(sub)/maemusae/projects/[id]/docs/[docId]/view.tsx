"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ProjectGuard } from "../../../../_components/ProjectGuard";
import { ExcelButton, RequirementTable, versionRows } from "../../../../_components/Viewer";
import { Btn, PageHead, Pill, card, fmtDate } from "../../../../_components/ui";
import { apiError } from "../../../../_lib/api";
import { revisionLabel } from "../../../../_lib/labels";
import { useConfirmedDocs, useVersion } from "../../../../_lib/queries";

// 확정한 문서를 그 시점 모습 그대로 보는 화면. 주소의 docId는 확정 기록(버전) id다 (확정할 때마다 하나씩 생김)
export default function DocViewPage() {
  const { id, docId } = useParams<{ id: string; docId: string }>();
  const confirmed = useConfirmedDocs(id);
  const entry = confirmed.data?.find((d) => d.version_id === Number(docId));
  const version = useVersion(id, entry?.document_id, entry?.version_id);
  const back = `/maemusae/projects/${id}`;

  return (
    <ProjectGuard projectId={id}>
      {({ project, readOnly }) => {
        if (confirmed.isLoading || version.isLoading) return <div className="h-[40vh]" aria-busy />;
        if (!entry || !version.data)
          return (
            <div className={`${card} mx-auto max-w-lg text-center`} role="alert">
              <h1 className="text-2xl font-extrabold tracking-tight">문서를 찾을 수 없어요</h1>
              <p className="mt-2 text-sm text-[#6c6a62]">{apiError(confirmed.error ?? version.error, "주소가 잘못되었거나 볼 수 없는 문서예요.")}</p>
              <Btn href={back} variant="dark" className="mt-6">프로젝트로 돌아가기</Btn>
            </div>
          );
        const rows = versionRows(version.data.items.filter((it) => it.is_included));
        return (
          <div className="grid gap-6">
            <PageHead eyebrow={project.name} title={entry.title}>
              <div className="flex flex-wrap gap-2 print:hidden">
                <ExcelButton projectId={id} docId={entry.document_id} versionId={entry.version_id} baseName={`${project.name}_${entry.title}_확정${entry.revision}`} rows={rows} readOnly={readOnly} />
                <Btn size="sm" onClick={() => window.print()}>PDF로 저장</Btn>
              </div>
            </PageHead>
            <dl className="flex flex-wrap gap-x-8 gap-y-3 text-sm" data-rise>
              <div className="grid gap-1"><dt className="text-xs font-extrabold text-[#6c6a62]">종류</dt><dd><Pill>{entry.kind_label}</Pill></dd></div>
              <div className="grid gap-1"><dt className="text-xs font-extrabold text-[#6c6a62]">구분</dt><dd><Pill tone={entry.revision > 1 ? "yellow" : "plain"}>{revisionLabel(entry.revision)}</Pill></dd></div>
              <div className="grid gap-1"><dt className="text-xs font-extrabold text-[#6c6a62]">확정일</dt><dd className="font-semibold">{fmtDate(entry.confirmed_at)}</dd></div>
              <div className="grid gap-1"><dt className="text-xs font-extrabold text-[#6c6a62]">최종 확정인</dt><dd className="font-semibold">{entry.confirmed_by_name}</dd></div>
              <div className="grid gap-1"><dt className="text-xs font-extrabold text-[#6c6a62]">요구사항</dt><dd className="font-semibold">{rows.length}개</dd></div>
            </dl>
            <RequirementTable items={rows} />
            <Link href={back} className="text-sm underline print:hidden">프로젝트로 돌아가기</Link>
          </div>
        );
      }}
    </ProjectGuard>
  );
}
