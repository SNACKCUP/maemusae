"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ProjectGuard } from "../../../../../_components/ProjectGuard";
import { ExcelButton, RequirementTable, downloadCsv, versionRows } from "../../../../../_components/Viewer";
import { Btn, PageHead, Pill, card, fmtDate, fmtTime } from "../../../../../_components/ui";
import { apiError } from "../../../../../_lib/api";
import { usePriorities, useReqKinds, useRequirementsDoc, useVersion } from "../../../../../_lib/queries";

// 버전 추가·버전 저장으로 남긴 순간의 요구사항을 읽기 전용으로 보는 화면. 번호는 "v2 · REQ-015"처럼 버전과 함께 보인다
export default function VersionViewPage() {
  const { id, versionId } = useParams<{ id: string; versionId: string }>();
  const { data: doc } = useRequirementsDoc(id);
  const { data: version, error, isLoading } = useVersion(id, doc?.id, Number(versionId));
  const kinds = useReqKinds();
  const priorities = usePriorities();
  const back = `/maemusae/projects/${id}/requirements`;

  return (
    <ProjectGuard projectId={id}>
      {({ project, readOnly }) =>
        !doc || isLoading ? (
          <div className="h-[40vh]" aria-busy />
        ) : error || !version ? (
          <div className={`${card} mx-auto max-w-lg text-center`} role="alert">
            <h1 className="text-2xl font-extrabold tracking-tight">버전을 찾을 수 없어요</h1>
            <p className="mt-2 text-sm text-[#6c6a62]">{apiError(error, "주소가 잘못되었거나 볼 수 없는 버전이에요.")}</p>
            <Btn href={back} variant="dark" className="mt-6">요구사항정의서로 돌아가기</Btn>
          </div>
        ) : (
          (() => {
            const tag = version.kind === "CONFIRMED" ? `확정 ${version.revision}` : `v${version.version_no}`;
            const rows = versionRows(version.items, tag);
            const included = rows.filter((_, i) => version.items[i].is_included);
            const baseName = `${project.name}_요구사항정의서_${tag}`;
            return (
              <div className="grid gap-6">
                <PageHead eyebrow={project.name} title={`요구사항정의서 ${tag}`}>
                  {/* 서버 Excel은 확정 기록에서만 만든다. 버전 기록은 CSV로 받는다 */}
                  {version.kind === "CONFIRMED" ? (
                    <ExcelButton projectId={id} docId={doc.id} versionId={version.id} baseName={`${project.name}_요구사항정의서_확정${version.revision}`} rows={versionRows(version.items.filter((it) => it.is_included))} readOnly={readOnly} />
                  ) : (
                    <Btn size="sm" className="print:hidden" onClick={() => downloadCsv(baseName, included, kinds.label, priorities.label)}>CSV 받기</Btn>
                  )}
                </PageHead>
                <dl className="flex flex-wrap gap-x-8 gap-y-3 text-sm" data-rise>
                  <div className="grid gap-1"><dt className="text-xs font-extrabold text-[#6c6a62]">구분</dt><dd><Pill tone="yellow">{version.kind === "CONFIRMED" ? "확정" : "버전"}</Pill></dd></div>
                  <div className="grid gap-1"><dt className="text-xs font-extrabold text-[#6c6a62]">남긴 시각</dt><dd className="font-semibold">{fmtDate(version.updated_at)} {fmtTime(version.updated_at)}</dd></div>
                  <div className="grid gap-1"><dt className="text-xs font-extrabold text-[#6c6a62]">남긴 사람</dt><dd className="font-semibold">{version.updated_by_name ?? version.created_by_name}</dd></div>
                  <div className="grid gap-1"><dt className="text-xs font-extrabold text-[#6c6a62]">체크한 후보</dt><dd className="font-semibold">{included.length} / {rows.length}개</dd></div>
                </dl>
                <p className="text-sm text-[#6c6a62]" data-rise>읽기 전용이에요. 아래 표는 체크한 후보만 보여 줘요.</p>
                <RequirementTable items={included} />
                <Link href={back} className="text-sm underline">요구사항정의서로 돌아가기</Link>
              </div>
            );
          })()
        )
      }
    </ProjectGuard>
  );
}
