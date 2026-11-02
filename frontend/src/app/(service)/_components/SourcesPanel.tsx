"use client";

import { useState } from "react";
import { toast } from "sonner";

import { apiError, type ApiSource } from "../_lib/api";
import { downloadSource, useDeleteSource, useSources } from "../_lib/queries";
import { ConfirmDialog } from "./dialogs";
import { Btn, card, fmtTime } from "./ui";

const size = (n: number | null) => (n == null ? "" : n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))}KB` : `${(n / 1024 / 1024).toFixed(1)}MB`);

/** 요구사항정의서에 올린 고객 문서 목록. 원본은 서버가 권한을 확인한 뒤 내려 준다 */
export function SourcesPanel({ projectId, docId, canManageAll, readOnly }: { projectId: string; docId: number | undefined; canManageAll: boolean; readOnly: boolean }) {
  const { data: sources = [] } = useSources(projectId, docId);
  const remove = useDeleteSource(projectId, docId);
  const [removing, setRemoving] = useState<ApiSource | null>(null);
  if (!docId || sources.length === 0) return null;

  const title = (s: ApiSource) => s.filename ?? "직접 입력한 내용";
  return (
    <section aria-labelledby="sources" className={`${card} grid gap-3`} data-rise>
      <h2 id="sources" className="text-lg font-extrabold tracking-tight">올린 문서 {sources.length}개</h2>
      <ul className="grid divide-y divide-[#111]/15">
        {sources.map((s) => (
          <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <span className="min-w-0">
              <span className="block truncate font-semibold">{title(s)}</span>
              <span className="text-xs text-[#6c6a62]">
                {s.uploaded_by_name} · {fmtTime(s.created_at)} · {s.page_count}쪽{s.size_bytes != null && ` · ${size(s.size_bytes)}`}
              </span>
            </span>
            <span className="flex gap-2">
              {s.source_type === "FILE" && (
                <Btn size="sm" onClick={() => downloadSource(projectId, docId, s.id, s.filename ?? "원본").catch((e) => toast.error(apiError(e, "원본을 받지 못했어요.")))}>원본 받기</Btn>
              )}
              {!readOnly && (s.uploaded_by_me || canManageAll) && <Btn size="sm" variant="ghost" onClick={() => setRemoving(s)}>삭제</Btn>}
            </span>
          </li>
        ))}
      </ul>
      <ConfirmDialog
        open={!!removing}
        onOpenChange={(v) => !v && setRemoving(null)}
        title="올린 문서를 지울까요?"
        body={removing ? `${title(removing)} — 원본 파일과 뽑아 둔 글이 함께 지워져요.` : ""}
        confirmLabel="삭제"
        danger
        onConfirm={() => {
          if (removing) remove.mutate(removing.id, { onSuccess: () => toast.success("지웠어요."), onError: (e) => toast.error(apiError(e)) });
          setRemoving(null);
        }}
      />
    </section>
  );
}
