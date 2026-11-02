"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { AiPromptInput, useAuth } from "@/meerkit";

import { apiError, apiErrorCode, type ApiDocument, type ApiRequirement, type NoteField, type RequirementChanges, type RequirementFilter } from "../_lib/api";
import { readLastViewed, writeLastViewed } from "../_lib/lastViewed";
import {
  useAnalyze,
  useBulkUpdateRequirements,
  useCategories,
  useConfirm,
  useCreateRequirement,
  useDeleteRequirement,
  useNotes,
  usePriorities,
  useRefine,
  useReloadDoc,
  useReqKinds,
  useRequirement,
  useRequirementList,
  useSaveVersion,
  useSources,
  useUpdateRequirement,
  useUploadSource,
  useWriteNote,
} from "../_lib/queries";
import { CandidateList } from "./CandidateList";
import { ConfirmDialog, RestartDialog } from "./dialogs";
import { FIELD_LABEL, RequirementDetail } from "./RequirementDetail";
import { Btn, Pill, card, fmtTime } from "./ui";
import { VersionsDialog } from "./VersionsDialog";

const NO_FILTER = { kind: "all", priority: "all", major: "all", checked: "all", needsCheck: false, q: "" };

/** 다시 분석 확인 창 문구. 이번 분석 이후 버전을 남겼는지, 그 뒤에 또 고쳤는지로 고른다 */
function restartWarning(doc: ApiDocument) {
  const last = doc.last_version_no ? `v${doc.last_version_no}` : "마지막 버전";
  if (!doc.saved_at) return "다시 분석하면 지금 후보와 직접 입력한 내용이 모두 지워져요. 지금 결과를 남기려면 창을 닫고 먼저 버전 추가를 눌러 주세요.";
  if (doc.changed_since_save) return `마지막 버전(${last}, ${fmtTime(doc.saved_at)}) 이후 고친 내용은 지워져요. 남기려면 먼저 버전 저장(덮어쓰기)이나 버전 추가를 눌러 주세요.`;
  return `지금 결과는 ${last}로 남아 있어서 버전 기록에서 다시 볼 수 있어요.`;
}

// 후보 목록 + 상세 편집 + 입력한 내용 리스트 + 다시 분류. 확정 전까지 팀이 함께 쓰는 작업대.
export function Workspace({ projectId, doc, isAdmin, readOnly }: { projectId: string; doc: ApiDocument; isAdmin: boolean; readOnly: boolean }) {
  const docId = doc.id;
  const { user } = useAuth();
  const kinds = useReqKinds();
  const { data: sources = [] } = useSources(projectId, docId);
  const priorities = usePriorities();

  // 필터는 서버로 보낸다. 검색어는 0.3초 쉬었다가 보낸다
  const [filter, setFilter] = useState(NO_FILTER);
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(filter.q), 300);
    return () => clearTimeout(t);
  }, [filter.q]);
  const serverFilter = useMemo<RequirementFilter>(
    () => ({
      kind: filter.kind === "all" ? undefined : filter.kind,
      priority: filter.priority === "all" ? undefined : filter.priority,
      category_major: filter.major === "all" ? undefined : filter.major,
      included: filter.checked === "all" ? undefined : filter.checked === "on",
      needs_check: filter.needsCheck,
      q,
    }),
    [filter.kind, filter.priority, filter.major, filter.checked, filter.needsCheck, q],
  );
  const filtering = JSON.stringify(filter) !== JSON.stringify(NO_FILTER);
  const list = useRequirementList(projectId, docId, serverFilter);
  const items = list.items;

  // 마지막으로 보던 후보 (사람별로 브라우저에). 없거나 지워졌으면 첫 후보
  const [picked, setSelectedId] = useState<number | null>(() => readLastViewed(user?.id, docId));
  const [centerId, setCenterId] = useState<number | null>(picked);
  const pickedFailed = useRequirement(projectId, docId, picked).isError;
  const selectedId = picked === null || pickedFailed ? (items[0]?.id ?? null) : picked;
  const detailQuery = useRequirement(projectId, docId, selectedId);
  const detail = detailQuery.data;
  const [tick, setTick] = useState(0);

  const select = (id: number, center = false) => {
    setSelectedId(id);
    writeLastViewed(user?.id, docId, id);
    if (center) {
      // 걸러진 목록에 가려져 있으면 필터를 풀어 보이게 한다
      if (!items.some((c) => c.id === id)) setFilter(NO_FILTER);
      setCenterId(id);
    }
  };

  const update = useUpdateRequirement(projectId, docId);
  const bulk = useBulkUpdateRequirements(projectId, docId);
  const create = useCreateRequirement(projectId, docId);
  const remove = useDeleteRequirement(projectId, docId);
  const writeNote = useWriteNote(projectId, docId);
  const reload = useReloadDoc(projectId, docId);
  const saveVersion = useSaveVersion(projectId, docId);
  const analyze = useAnalyze(projectId, docId);
  const refine = useRefine(projectId, docId);
  const upload = useUploadSource(projectId, docId);
  const confirm = useConfirm(projectId, docId);
  const categories = useCategories(projectId, docId).data ?? [];
  const majors = [...new Set(categories.map((c) => c.major))];

  // 다른 사람이 먼저 고쳤으면(version 불일치) 최신 내용으로 다시 불러오고 상세 칸도 새로 그린다
  const onWriteError = (e: unknown) => {
    if (apiErrorCode(e) === "REQUIREMENT_CHANGED") {
      toast.warning("다른 사람이 먼저 고쳤어요. 최신 내용으로 다시 불러올게요.");
      reload();
      setTick((t) => t + 1);
    } else toast.error(apiError(e));
  };
  const save = (row: Pick<ApiRequirement, "id" | "version">, changes: RequirementChanges) =>
    update.mutate({ reqId: row.id, version: row.version, changes }, { onError: onWriteError });
  const note = (field: NoteField, text: string | null) =>
    selectedId && writeNote.mutate({ reqId: selectedId, field, text }, { onError: (e) => toast.error(apiError(e)) });

  // 보이는 후보를 한꺼번에 체크·해제 (500개씩, 하나라도 실패하면 그 묶음은 안 바뀜)
  const toggleAll = async (included: boolean) => {
    const targets = items.filter((r) => r.is_included !== included).map((r) => ({ id: r.id, version: r.version, is_included: included }));
    try {
      for (let i = 0; i < targets.length; i += 500) await bulk.mutateAsync(targets.slice(i, i + 500));
    } catch (e) {
      onWriteError(e);
    }
  };

  const addCandidate = () =>
    create.mutate(
      { name: "새 요구사항", kind: kinds.codes[0]?.code ?? "FUNCTIONAL", priority: priorities.codes.find((p) => p.code === "MEDIUM")?.code ?? priorities.codes[0]?.code ?? "MEDIUM" },
      { onSuccess: (row) => select(row.id, true), onError: (e) => toast.error(apiError(e)) },
    );

  const [askRestart, setAskRestart] = useState(false);
  const [askSave, setAskSave] = useState(false);
  const [askConfirm, setAskConfirm] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);

  const keepVersion = (overwrite: boolean) =>
    saveVersion.mutate(overwrite, {
      onSuccess: (v) => toast.success(!overwrite ? `v${v.version_no} 버전을 추가했어요.` : v.overwritten ? `v${v.version_no}에 덮어 저장했어요.` : `v${v.version_no} 버전으로 저장했어요.`),
      onError: (e) => toast.error(apiError(e)),
    });

  // 확정: 서버가 체크된 후보를 지금 모습 그대로 확정 기록에 남기고 문서를 확정됨으로 바꾼다 (화면은 확정 문서로 넘어감)
  const submitConfirm = () =>
    confirm.mutate(undefined, {
      onSuccess: (r) => toast.success(`${r.revision > 1 ? "수정 후 확정" : "확정"}했어요. 요구사항 ${r.item_count}개가 담겼어요.`),
      onError: (e) => toast.error(apiError(e, "확정하지 못했어요.")),
    });
  // 막지는 않고 확정 창에서 미리 알린다 (체크된 후보 기준)
  const warnings = [
    doc.open_question_count > 0 && `AI 질문에 답이 없는 후보 ${doc.open_question_count}개`,
    doc.defaulted_count > 0 && `AI 값 확인이 남은 후보 ${doc.defaulted_count}개`,
  ].filter(Boolean);

  // 다시 분류: 붙인 파일을 먼저 올린 뒤, 반영 안 된 입력과 새 파일을 기존 후보에 반영한다
  const submitRefine = async (msg: string, files: File[]) => {
    for (const file of files) {
      try {
        await upload.mutateAsync({ file });
      } catch (e) {
        toast.error(`${file.name}: ${apiError(e, "올리지 못했어요.")}`);
      }
    }
    refine.mutate({ prompt: msg.trim() || undefined }, { onError: (e) => toast.error(apiError(e)) });
  };

  // 입력한 내용 목록 (작성자 필터와 검색은 받아 온 목록 안에서)
  const notes = useNotes(projectId, docId).data ?? [];
  const [noteSort, setNoteSort] = useState<"new" | "old">("new");
  const [noteAuthor, setNoteAuthor] = useState("all");
  const [noteQuery, setNoteQuery] = useState("");
  const authors = [...new Set(notes.map((n) => n.author_name))];
  const shownNotes = notes
    .filter((n) => noteAuthor === "all" || n.author_name === noteAuthor)
    .filter((n) => {
      const nq = noteQuery.trim().toLowerCase();
      return !nq || `${n.requirement_code} ${n.requirement_name}`.toLowerCase().includes(nq);
    })
    .sort((a, b) => (noteSort === "new" ? b.updated_at.localeCompare(a.updated_at) : a.updated_at.localeCompare(b.updated_at)));

  const loadMore = useCallback(() => void list.fetchNextPage(), [list]);
  const shownCount = `${items.length}${list.hasNextPage ? "+" : ""}`;
  const busy = saveVersion.isPending || confirm.isPending;

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3" data-rise>
        <p className="text-sm text-[#6c6a62]">
          작업 중
          {doc.last_version_no != null && <> · 마지막 버전 v{doc.last_version_no}{doc.saved_at && ` (${fmtTime(doc.saved_at)})`}</>}
          {doc.saved_at && doc.changed_since_save && <span className="ml-1 text-[#c2410c]">· 버전 이후 고친 내용 있음</span>}
        </p>
        <div className="flex flex-wrap gap-2">
          <Btn size="sm" onClick={() => setVersionsOpen(true)}>버전 기록</Btn>
          {!readOnly && (
            <>
              <Btn size="sm" disabled={busy} onClick={() => keepVersion(false)}>버전 추가</Btn>
              <Btn size="sm" disabled={busy} onClick={() => setAskSave(true)}>버전 저장</Btn>
              <Btn size="sm" disabled={analyze.isPending} onClick={() => setAskRestart(true)}>다시 분석</Btn>
            </>
          )}
          {isAdmin ? (
            <Btn size="sm" variant="primary" disabled={busy} onClick={() => setAskConfirm(true)}>{confirm.isPending ? "확정 중…" : "요구사항 확정"}</Btn>
          ) : (
            <span className="inline-flex items-center text-xs text-[#6c6a62]" title="확정은 프로젝트 관리자만 할 수 있어요">확정은 관리자만 할 수 있어요</span>
          )}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]" data-rise>
        <section aria-label="요구사항 후보" className={`${card} flex h-[600px] flex-col gap-3 p-4`}>
          <div className="flex items-center justify-between px-2">
            <h2 className="font-extrabold">후보 {shownCount}</h2>
            {!readOnly && <Btn size="sm" disabled={create.isPending} onClick={addCandidate}>+ 직접 추가</Btn>}
          </div>
          <div className="grid gap-2 px-1">
            <div className="flex flex-wrap gap-2">
              <NativeSelect aria-label="구분" value={filter.kind} onChange={(e) => setFilter({ ...filter, kind: e.target.value })} className="h-9 w-28 rounded-full border-[1.5px] border-[#111] text-sm">
                <option value="all">전체 구분</option>
                {kinds.codes.map((k) => <option key={k.code} value={k.code}>{k.label}</option>)}
              </NativeSelect>
              <NativeSelect aria-label="우선순위" value={filter.priority} onChange={(e) => setFilter({ ...filter, priority: e.target.value })} className="h-9 w-32 rounded-full border-[1.5px] border-[#111] text-sm">
                <option value="all">전체 우선순위</option>
                {priorities.codes.map((p) => <option key={p.code} value={p.code}>{p.label}</option>)}
              </NativeSelect>
              {majors.length > 0 && (
                <NativeSelect aria-label="대분류" value={filter.major} onChange={(e) => setFilter({ ...filter, major: e.target.value })} className="h-9 w-36 rounded-full border-[1.5px] border-[#111] text-sm">
                  <option value="all">전체 대분류</option>
                  {majors.map((m) => <option key={m} value={m}>{m}</option>)}
                </NativeSelect>
              )}
              <NativeSelect aria-label="체크 여부" value={filter.checked} onChange={(e) => setFilter({ ...filter, checked: e.target.value })} className="h-9 w-32 rounded-full border-[1.5px] border-[#111] text-sm">
                <option value="all">체크 전체</option><option value="on">체크됨</option><option value="off">체크 안 됨</option>
              </NativeSelect>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Input aria-label="후보 검색" value={filter.q} placeholder="번호(REQ-012)·이름 검색" onChange={(e) => setFilter({ ...filter, q: e.target.value })} className="h-9 min-w-0 flex-1 rounded-full border-[1.5px] border-[#111] bg-white px-4 text-sm" />
              <label className="flex shrink-0 cursor-pointer items-center gap-2 text-sm">
                <Checkbox checked={filter.needsCheck} onCheckedChange={(v) => setFilter({ ...filter, needsCheck: v === true })} />확인 필요만
              </label>
              {filtering && <button type="button" className="shrink-0 text-xs underline underline-offset-4" onClick={() => setFilter(NO_FILTER)}>초기화</button>}
            </div>
            {!readOnly && items.length > 0 && (
              <div className="flex gap-3 text-xs">
                <button type="button" disabled={bulk.isPending} className="underline underline-offset-4 disabled:opacity-50" onClick={() => toggleAll(true)}>보이는 후보 모두 체크</button>
                <button type="button" disabled={bulk.isPending} className="underline underline-offset-4 disabled:opacity-50" onClick={() => toggleAll(false)}>모두 해제</button>
              </div>
            )}
          </div>
          {list.isLoading ? (
            <p className="py-8 text-center text-sm text-[#6c6a62]">후보를 불러오는 중…</p>
          ) : (
            <CandidateList
              items={items}
              selectedId={selectedId}
              centerId={centerId}
              readOnly={readOnly}
              hasMore={!!list.hasNextPage}
              loadingMore={list.isFetchingNextPage}
              onLoadMore={loadMore}
              onSelect={(id) => select(id)}
              onToggle={(row, included) => save(row, { is_included: included })}
            />
          )}
        </section>

        <section aria-label="요구사항 상세" className={`${card} grid content-start gap-4`}>
          {!detail ? (
            <p className="py-10 text-center text-sm text-[#6c6a62]">{selectedId && detailQuery.isLoading ? "불러오는 중…" : "왼쪽에서 요구사항을 고르면 자세히 볼 수 있어요."}</p>
          ) : (
            <RequirementDetail
              key={`${detail.id}:${tick}`}
              detail={detail}
              categories={categories}
              readOnly={readOnly}
              onSave={(changes) => save(detail, changes)}
              onNote={note}
              onDelete={() => remove.mutate(detail.id, { onSuccess: () => setSelectedId(null), onError: (e) => toast.error(apiError(e)) })}
            />
          )}
        </section>
      </div>

      <section aria-label="입력한 내용 리스트" className={`${card} grid gap-3`} data-rise>
        <h2 className="font-extrabold">입력한 내용 <span className="text-sm font-normal text-[#6c6a62]">· 누르면 해당 요구사항으로 이동해요</span></h2>
        {notes.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <NativeSelect aria-label="정렬" value={noteSort} onChange={(e) => setNoteSort(e.target.value as "new" | "old")} className="h-9 w-28 rounded-full border-[1.5px] border-[#111] text-sm">
              <option value="new">최신순</option><option value="old">오래된순</option>
            </NativeSelect>
            <NativeSelect aria-label="작성자" value={noteAuthor} onChange={(e) => setNoteAuthor(e.target.value)} className="h-9 w-32 rounded-full border-[1.5px] border-[#111] text-sm">
              <option value="all">전체 멤버</option>
              {authors.map((a) => <option key={a} value={a}>{a}</option>)}
            </NativeSelect>
            <Input aria-label="입력한 내용 검색" value={noteQuery} placeholder="후보 번호·이름 검색" onChange={(e) => setNoteQuery(e.target.value)} className="h-9 w-56 rounded-full border-[1.5px] border-[#111] bg-white px-4 text-sm" />
          </div>
        )}
        {notes.length === 0 ? (
          <p className="text-sm text-[#6c6a62]">상세 칸에 내용을 적고 벗어나면 여기에 쌓여요.</p>
        ) : shownNotes.length === 0 ? (
          <p className="text-sm text-[#6c6a62]">조건에 맞는 내용이 없어요.</p>
        ) : (
          <ul className="grid max-h-48 gap-1.5 overflow-y-auto">
            {shownNotes.map((n) => (
              <li key={n.id} className="flex items-center gap-1">
                <button type="button" onClick={() => select(n.requirement_id, true)} className="flex min-w-0 flex-1 items-baseline gap-3 rounded-xl px-3 py-2 text-left text-sm hover:bg-[#ebeae4]">
                  <span className="shrink-0 text-xs text-[#6c6a62]">{n.requirement_code}</span>
                  <Pill tone={n.field === "ANSWER" ? "orange" : "plain"} className="shrink-0">{FIELD_LABEL[n.field]}</Pill>
                  <span className="flex-1 truncate">{n.text}</span>
                  {n.applied && <Pill className="shrink-0">반영됨</Pill>}
                  <span className="shrink-0 text-xs text-[#6c6a62]">{n.author_name} · {fmtTime(n.updated_at)}</span>
                </button>
                {n.mine && !readOnly && (
                  <button type="button" aria-label={`${n.requirement_code} 내 입력 지우기`} className="shrink-0 px-2 text-xs underline underline-offset-4" onClick={() => writeNote.mutate({ reqId: n.requirement_id, field: n.field, text: null }, { onError: (e) => toast.error(apiError(e)) })}>지우기</button>
                )}
              </li>
            ))}
          </ul>
        )}
        {!readOnly && (
          <AiPromptInput
            placeholder="고객에게 새로 받은 내용이나 AI의 질문에 대한 답을 적고, 필요하면 파일도 붙여요"
            accept=".pdf,.docx,.xlsx,.txt,.md,.pptx"
            requireText={false}
            submitLabel={refine.isPending || upload.isPending ? "보내는 중…" : "다시 분류"}
            disabled={refine.isPending || upload.isPending}
            onSubmit={submitRefine}
          />
        )}
      </section>

      <RestartDialog
        open={askRestart}
        onOpenChange={setAskRestart}
        warning={<>{restartWarning(doc)} 후보는 REQ-001부터 다시 매겨져요.</>}
        sources={sources}
        onConfirm={(prompt) => analyze.mutate({ restart: true, prompt: prompt || undefined }, { onError: (e) => toast.error(apiError(e)) })}
      />
      {/* 버전 저장 = 이번 분석 뒤 남긴 마지막 버전 덮어쓰기. 덮어쓸 버전이 없으면(saved_at 없음) 버전 추가로 안내한다 */}
      {doc.saved_at && doc.last_version_no ? (
        <ConfirmDialog
          open={askSave}
          onOpenChange={setAskSave}
          title={`v${doc.last_version_no} 버전을 덮어쓸까요?`}
          body={<>v{doc.last_version_no} 버전을 지금 내용으로 바꿔요. 새 버전은 만들지 않아요. 새 버전으로 남기려면 버전 추가를 눌러 주세요.</>}
          confirmLabel="바꾸기"
          onConfirm={() => keepVersion(true)}
        />
      ) : (
        <ConfirmDialog
          open={askSave}
          onOpenChange={setAskSave}
          title="먼저 버전 추가를 해 주세요"
          body={<>버전 저장은 새 버전을 만들지 않고 마지막 버전을 지금 내용으로 바꿔요. {doc.last_version_no ? "다시 분석한 뒤로 남긴 버전이 없어서" : "아직 남긴 버전이 없어서"} 바꿀 버전이 없어요.</>}
          confirmLabel="버전 추가하기"
          cancelLabel="닫기"
          onConfirm={() => keepVersion(false)}
        />
      )}
      <ConfirmDialog
        open={askConfirm}
        onOpenChange={setAskConfirm}
        title="요구사항을 확정할까요?"
        body={
          <>
            {warnings.length > 0 && <span className="mb-2 block font-semibold text-[#c2410c]">{warnings.join(", ")}가 남아 있어요. 그래도 확정할 수 있어요.</span>}
            체크한 후보로 요구사항정의서를 만들어요. 확정한 뒤에도 관리자는 다시 열어 고칠 수 있어요.
          </>
        }
        confirmLabel={warnings.length > 0 ? "그래도 확정" : "확정"}
        onConfirm={submitConfirm}
      />
      <VersionsDialog open={versionsOpen} onOpenChange={setVersionsOpen} projectId={projectId} docId={docId} />
    </div>
  );
}

export const ANALYZING_LABELS = ["문서를 읽는 중", "요구사항을 가려내는 중", "모호한 부분을 찾는 중", "후보를 정리하는 중"];
export const REFINING_LABELS = ["입력한 내용을 읽는 중", "후보에 반영하는 중", "새 문서와 맞춰 보는 중"];
