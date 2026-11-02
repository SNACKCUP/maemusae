"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";

import { Checkbox } from "@/components/ui/checkbox";

import type { ApiRequirement } from "../_lib/api";
import { usePriorities, useReqKinds } from "../_lib/queries";
import { Btn, Pill } from "./ui";

/**
 * 요구사항 후보 목록. 받은 후보를 모두 그리고, 더 있으면 맨 아래 "더 보기"로 다음 묶음(200개)을 받는다.
 * 받는 동안은 버튼 자리에 불러오는 중 표시를 둔다.
 * centerId가 바뀌면 그 후보를 목록 가운데로 가져온다 (다시 들어왔을 때, 입력한 내용에서 눌렀을 때).
 *
 * [예비 가상 스크롤] 처음에는 @tanstack/react-virtual 로 보이는 줄만 그렸지만, 줄 위치 계산에 인라인 style 이
 * 필요해서 "더 보기"로 바꿨다 (SoYoung, 10/30). 후보가 수천 개로 늘어 느려지면 아래 주석을 참고해 되돌린다.
 *   import { useVirtualizer } from "@tanstack/react-virtual";
 *   const v = useVirtualizer({ count: items.length, getScrollElement: () => boxRef.current, estimateSize: () => 82, overscan: 8, gap: 8 });
 *   <ul className="relative w-full" style={{ height: v.getTotalSize() }}> … <li ref={v.measureElement} data-index={row.index}
 *     className="absolute left-0 top-0 …" style={{ transform: `translateY(${row.start}px)` }}>
 *   끝 근처에서 onLoadMore(), centerId 는 v.scrollToIndex(index, { align: "center" })
 */
export function CandidateList({
  items,
  selectedId,
  centerId,
  readOnly,
  hasMore,
  loadingMore,
  onLoadMore,
  onSelect,
  onToggle,
}: {
  items: ApiRequirement[];
  selectedId: number | null;
  centerId: number | null;
  readOnly: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  onSelect: (id: number) => void;
  onToggle: (row: ApiRequirement, included: boolean) => void;
}) {
  const kinds = useReqKinds();
  const priorities = usePriorities();
  const listRef = useRef<HTMLUListElement>(null);

  // 가운데로 올 후보가 바뀌거나, 그 후보가 다음 묶음에 있다가 받아졌을 때
  const centerIndex = centerId == null ? -1 : items.findIndex((r) => r.id === centerId);
  useEffect(() => {
    if (centerIndex < 0) return;
    listRef.current?.querySelector(`[data-id="${centerId}"]`)?.scrollIntoView({ block: "center" });
  }, [centerIndex, centerId]);

  if (items.length === 0) return <p className="py-8 text-center text-sm text-[#6c6a62]">조건에 맞는 후보가 없어요.</p>;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto pr-1">
      <ul ref={listRef} className="grid gap-2">
        {items.map((c) => {
          const on = c.id === selectedId;
          return (
            <li
              key={c.id}
              data-id={c.id}
              className={`flex w-full items-start gap-3 rounded-2xl border-[1.5px] p-3 ${on ? "border-[#111] bg-[#f2f69a]" : "border-[#111]/20 bg-white"}`}
            >
              <Checkbox checked={c.is_included} disabled={readOnly} aria-label={`${c.name} 포함`} onCheckedChange={(val) => onToggle(c, val === true)} className="mt-1" />
              <button type="button" onClick={() => onSelect(c.id)} className="grid flex-1 gap-1 text-left" aria-current={on}>
                <span className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                  <span className="text-xs text-[#6c6a62]">{c.code}</span>
                  {c.name}
                </span>
                {c.category_major && <span className="truncate text-xs text-[#6c6a62]">{[c.category_major, c.category_middle, c.category_minor].filter(Boolean).join(" > ")}</span>}
                <span className="flex flex-wrap gap-1.5">
                  <Pill>{kinds.label(c.kind)}</Pill>
                  <Pill>{priorities.label(c.priority)}</Pill>
                  {c.needs_answer && <Pill tone="orange">확인 필요</Pill>}
                  {(c.kind_defaulted || c.priority_defaulted) && <Pill tone="orange">AI 값 확인</Pill>}
                  {c.is_manual && <Pill>직접 추가</Pill>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {hasMore && (
        <div className="flex justify-center py-3">
          {loadingMore ? (
            <p role="status" className="flex items-center gap-2 text-xs text-[#6c6a62]">
              <Loader2 className="size-4 animate-spin" aria-hidden />
              더 불러오는 중…
            </p>
          ) : (
            <Btn size="sm" onClick={onLoadMore}>더 보기</Btn>
          )}
        </div>
      )}
    </div>
  );
}
