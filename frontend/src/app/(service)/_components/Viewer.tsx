"use client";

import { useState } from "react";
import { toast } from "sonner";

import { apiError, type ApiDocument, type ApiProject, type ApiVersionItem } from "../_lib/api";
import { downloadConfirmedExcel, useConfirmedDocs, usePriorities, useReopen, useReqKinds, useVersion } from "../_lib/queries";
import { revisionLabel } from "../_lib/labels";
import { Btn, Pill, card, fmtDate } from "./ui";

const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;

/** 표에 보일 요구사항 한 줄 (확정 문서, 버전 기록이 같이 쓴다) */
export interface TableRow {
  key: string | number;
  code: string;
  name: string;
  kind: string;
  priority: string;
  description: string;
  /** 근거 문장 (여러 개면 줄을 나눠 이어 붙임) */
  quote: string;
  categoryMajor: string | null;
  categoryMiddle: string | null;
  categoryMinor: string | null;
}

/** 버전·확정 기록의 후보를 표 줄로. tag를 주면 번호 앞에 붙인다 (예: "v2 · REQ-015") */
export const versionRows = (items: ApiVersionItem[], tag?: string): TableRow[] =>
  items.map((it) => ({
    key: it.code,
    code: tag ? `${tag} · ${it.code}` : it.code,
    name: it.name,
    kind: it.kind,
    priority: it.priority,
    description: it.description,
    quote: it.sources.map((s) => s.quote).join("\n"),
    categoryMajor: it.category_major ?? null,
    categoryMiddle: it.category_middle ?? null,
    categoryMinor: it.category_minor ?? null,
  }));

/**
 * 표를 브라우저에서 CSV로 내려 Excel에서 열 수 있게 한다. 구분·우선순위는 코드 대신 이름으로.
 * 확정 문서는 서버 Excel(.xlsx)을 쓰고, 이건 서버 Excel을 받지 못했을 때와 버전 기록(확정 전)용 예비 방법이다.
 */
export function downloadCsv(fileName: string, items: TableRow[], kindLabel: (code: string) => string, priorityLabel: (code: string) => string) {
  const rows = [
    ["ID", "대분류", "중분류", "소분류", "이름", "구분", "우선순위", "설명", "근거"],
    ...items.map((c) => [c.code, c.categoryMajor ?? "", c.categoryMiddle ?? "", c.categoryMinor ?? "", c.name, kindLabel(c.kind), priorityLabel(c.priority), c.description, c.quote]),
  ];
  const blob = new Blob(["﻿" + rows.map((r) => r.map(esc).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${fileName}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * 확정 기록 Excel 받기. 서버가 만든 .xlsx를 받고, 실패하면 같은 내용을 CSV로 받을 수 있게 알림에 버튼을 띄운다.
 * 고객 문서라 프로젝트 멤버만 받을 수 있다 (보기 전용 서비스 관리자는 버튼 대신 안내).
 */
export function ExcelButton({ projectId, docId, versionId, baseName, rows, readOnly }: { projectId: string; docId: number; versionId: number; baseName: string; rows: TableRow[]; readOnly: boolean }) {
  const kinds = useReqKinds();
  const priorities = usePriorities();
  const [busy, setBusy] = useState(false);
  if (readOnly) return <span className="inline-flex items-center text-xs text-[#6c6a62]">Excel은 프로젝트 멤버만 받을 수 있어요</span>;

  const download = async () => {
    setBusy(true);
    try {
      await downloadConfirmedExcel(projectId, docId, versionId, `${baseName}.xlsx`);
    } catch (e) {
      toast.error(apiError(e, "Excel 파일을 받지 못했어요."), {
        description: "같은 내용을 CSV로 받아 Excel에서 열 수 있어요.",
        action: { label: "CSV로 받기", onClick: () => downloadCsv(baseName, rows, kinds.label, priorities.label) },
        duration: 10_000,
      });
    } finally {
      setBusy(false);
    }
  };
  return <Btn size="sm" disabled={busy} onClick={download}>{busy ? "받는 중…" : "Excel 받기"}</Btn>;
}

const category = (c: TableRow) => [c.categoryMajor, c.categoryMiddle].filter(Boolean).join(" > ");

export function RequirementTable({ items }: { items: TableRow[] }) {
  const kinds = useReqKinds();
  const priorities = usePriorities();
  return (
    <div className={`${card} overflow-x-auto p-0 print:overflow-visible print:shadow-none`} data-rise>
      <table className="w-full min-w-[760px] text-left text-sm print:min-w-0">
        <thead>
          <tr className="border-b-[1.5px] border-[#111] text-xs font-extrabold text-[#6c6a62]">
            {["ID", "분류", "이름", "구분", "우선순위", "설명"].map((h) => <th key={h} scope="col" className="px-5 py-3">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.key} className="break-inside-avoid border-b border-[#111]/10 align-top last:border-0">
              <td className="whitespace-nowrap px-5 py-3 text-xs text-[#6c6a62]">{c.code}</td>
              <td className="px-5 py-3 text-xs text-[#55534c]">{category(c) || "-"}{c.categoryMinor && <span className="block">{c.categoryMinor}</span>}</td>
              <td className="px-5 py-3 font-semibold">{c.name}</td>
              <td className="px-5 py-3"><Pill>{kinds.label(c.kind)}</Pill></td>
              <td className="px-5 py-3"><Pill tone={c.priority === "HIGH" ? "yellow" : "plain"}>{priorities.label(c.priority)}</Pill></td>
              <td className="whitespace-pre-line px-5 py-3 text-[#55534c]">{c.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// 확정된 요구사항정의서: 마지막 확정 기록을 그대로 보여 준다. 관리자만 다시 열 수 있고, 멤버는 Excel을 받을 수 있다.
export function Viewer({ project, doc, isAdmin, readOnly }: { project: ApiProject; doc: ApiDocument; isAdmin: boolean; readOnly: boolean }) {
  const pid = String(project.id);
  const confirmed = useConfirmedDocs(pid);
  const latest = confirmed.data?.find((d) => d.document_id === doc.id);
  const version = useVersion(pid, doc.id, latest?.version_id);
  const reopen = useReopen(pid, doc.id);
  const included = (version.data?.items ?? []).filter((it) => it.is_included);
  const rows = versionRows(included);

  // 막 확정했으면 확정 목록을 새로 받는 중일 수 있다
  if (confirmed.isLoading || version.isLoading || (!latest && confirmed.isFetching)) return <div className="h-[30vh]" aria-busy />;
  if (confirmed.error || version.error || !latest || !version.data)
    return <p role="alert" className="py-10 text-center text-sm text-[#b3261e]">{apiError(confirmed.error ?? version.error, "확정한 내용을 불러오지 못했어요.")}</p>;

  const reopenDoc = () =>
    reopen.mutate(undefined, {
      onSuccess: () => toast.success("다시 고칠 수 있어요. 고친 뒤 확정하면 수정 후 확정으로 남아요."),
      onError: (e) => toast.error(apiError(e)),
    });

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3" data-rise>
        <p className="flex flex-wrap items-center gap-2 text-sm text-[#6c6a62]">
          <Pill tone={latest.revision > 1 ? "yellow" : "dark"}>{revisionLabel(latest.revision)}</Pill>
          {fmtDate(latest.confirmed_at)} · {latest.confirmed_by_name} · 요구사항 {rows.length}개
        </p>
        <div className="flex flex-wrap gap-2 print:hidden">
          <ExcelButton projectId={pid} docId={doc.id} versionId={latest.version_id} baseName={`${project.name}_${latest.title}_확정${latest.revision}`} rows={rows} readOnly={readOnly} />
          <Btn size="sm" onClick={() => window.print()}>PDF로 저장</Btn>
          {isAdmin ? (
            <Btn size="sm" variant="dark" disabled={reopen.isPending} onClick={reopenDoc}>확정 후 수정</Btn>
          ) : (
            !readOnly && <span className="inline-flex items-center text-xs text-[#6c6a62]">확정 후 수정은 관리자만 할 수 있어요</span>
          )}
        </div>
      </div>
      <RequirementTable items={rows} />
    </div>
  );
}
