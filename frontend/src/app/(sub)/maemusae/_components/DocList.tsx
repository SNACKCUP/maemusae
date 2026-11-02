"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";

import { DOC_KINDS, revisionLabel } from "../_lib/labels";
import type { ApiConfirmedDocument } from "../_lib/api";
import { Pill, card, fmtDate } from "./ui";

// 확정한 문서 기록 (확정할 때마다 한 줄). 검색, 최신/오래된순, 종류로 거를 수 있고 행을 누르면 그 확정 기록을 연다.
export function DocList({ projectId, docs }: { projectId: string; docs: ApiConfirmedDocument[] }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"new" | "old">("new");
  const [kind, setKind] = useState("all");

  const shown = useMemo(
    () =>
      docs
        .filter((d) => kind === "all" || d.kind_label === kind)
        .filter((d) => !q.trim() || `${d.title} ${d.confirmed_by_name}`.toLowerCase().includes(q.trim().toLowerCase()))
        .sort((a, b) => (sort === "new" ? b.confirmed_at.localeCompare(a.confirmed_at) : a.confirmed_at.localeCompare(b.confirmed_at))),
    [docs, q, sort, kind],
  );

  return (
    <section aria-labelledby="doclist" className="grid gap-4" data-rise>
      <h2 id="doclist" className="text-xl font-extrabold tracking-tight">확정한 문서</h2>
      <div className="flex flex-wrap gap-2">
        <Input aria-label="문서 검색" value={q} placeholder="문서 이름·확정인 검색" onChange={(e) => setQ(e.target.value)} className="h-10 w-64 rounded-full border-[1.5px] border-[#111] bg-white px-4" />
        <NativeSelect aria-label="정렬" value={sort} onChange={(e) => setSort(e.target.value as "new" | "old")} className="h-10 w-28 rounded-full border-[1.5px] border-[#111]">
          <option value="new">최신순</option><option value="old">오래된순</option>
        </NativeSelect>
        <NativeSelect aria-label="문서 종류" value={kind} onChange={(e) => setKind(e.target.value)} className="h-10 w-40 rounded-full border-[1.5px] border-[#111]">
          <option value="all">전체 종류</option>
          {DOC_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </NativeSelect>
      </div>
      <div className={`${card} overflow-x-auto p-0`}>
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead>
            <tr className="border-b-[1.5px] border-[#111] text-xs font-extrabold text-[#6c6a62]">
              {["문서", "종류", "구분", "요구사항", "확정일", "확정인"].map((h) => <th key={h} scope="col" className="px-5 py-3">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 ? (
              <tr><td colSpan={6} className="px-5 py-8 text-center text-[#6c6a62]">조건에 맞는 문서가 없어요.</td></tr>
            ) : (
              shown.map((d) => (
                <tr key={d.version_id} onClick={() => router.push(`/maemusae/projects/${projectId}/docs/${d.version_id}`)} className="cursor-pointer border-b border-[#111]/10 last:border-0 hover:bg-[#ebeae4]">
                  <td className="px-5 py-3 font-semibold"><Link href={`/maemusae/projects/${projectId}/docs/${d.version_id}`} className="hover:underline" onClick={(e) => e.stopPropagation()}>{d.title}</Link></td>
                  <td className="px-5 py-3">{d.kind_label}</td>
                  <td className="px-5 py-3"><Pill tone={d.revision > 1 ? "yellow" : "plain"}>{revisionLabel(d.revision)}</Pill></td>
                  <td className="px-5 py-3 tabular-nums text-[#55534c]">{d.item_count}개</td>
                  <td className="px-5 py-3 text-[#55534c]">{fmtDate(d.confirmed_at)}</td>
                  <td className="px-5 py-3 text-[#55534c]">{d.confirmed_by_name}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
