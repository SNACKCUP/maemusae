"use client";

import Link from "next/link";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

import { apiError } from "../_lib/api";
import { useVersions } from "../_lib/queries";
import { Btn, Pill, fmtDate, fmtTime } from "./ui";

/** 버전 기록: 버전 추가·버전 저장으로 남긴 것만 쌓인다. 누르면 그 버전을 읽기 전용으로 연다 */
export function VersionsDialog({ open, onOpenChange, projectId, docId }: { open: boolean; onOpenChange: (v: boolean) => void; projectId: string; docId: number }) {
  const { data: versions = [], isLoading, error } = useVersions(projectId, docId, open);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg rounded-[28px] border-[1.5px] border-[#111]">
        <DialogHeader>
          <DialogTitle className="text-2xl font-extrabold tracking-tight">버전 기록</DialogTitle>
          <DialogDescription>버전 추가·버전 저장을 누른 순간의 후보, 근거, 입력이 그대로 남아요. 다시 분석해도 지워지지 않아요.</DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <p className="py-6 text-center text-sm text-[#6c6a62]">불러오는 중…</p>
        ) : error ? (
          <p role="alert" className="py-6 text-center text-sm text-[#b3261e]">{apiError(error, "버전 기록을 불러오지 못했어요.")}</p>
        ) : versions.length === 0 ? (
          <p className="py-6 text-center text-sm text-[#6c6a62]">아직 남긴 버전이 없어요. 위의 버전 추가를 누르면 지금 모습이 v1로 남아요.</p>
        ) : (
          <ul className="grid max-h-80 divide-y divide-[#111]/15 overflow-y-auto">
            {versions.map((v) => (
              <li key={v.id}>
                <Link href={`/maemusae/projects/${projectId}/requirements/versions/${v.id}`} className="flex items-center justify-between gap-3 rounded-xl px-2 py-3 hover:bg-[#ebeae4]">
                  <span className="flex items-center gap-2">
                    <Pill tone={v.kind === "CONFIRMED" ? "dark" : "yellow"}>{v.kind === "CONFIRMED" ? `확정 ${v.revision}` : `v${v.version_no}`}</Pill>
                    <span className="text-sm font-semibold">후보 {v.item_count}개</span>
                  </span>
                  <span className="text-right text-xs text-[#6c6a62]">
                    {v.updated_by_name ?? v.created_by_name} · {fmtDate(v.updated_at)} {fmtTime(v.updated_at)}
                    {v.updated_by_name && <span className="block">덮어 저장됨</span>}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <div className="flex justify-end">
          <Btn onClick={() => onOpenChange(false)}>닫기</Btn>
        </div>
      </DialogContent>
    </Dialog>
  );
}
