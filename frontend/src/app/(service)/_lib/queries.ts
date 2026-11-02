"use client";

// 매무새 서버 데이터 훅 (TanStack Query). 화면 부품은 이 훅만 쓰고, 서버 호출은 api.ts에 둔다.

import { useInfiniteQuery, useMutation, useQueries, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { useAuth } from "@/meerkit";

import { mmsApi, type ApiRequirement, type ApiRequirementDetail, type ApiRequirementPage, type NoteField, type RequirementChanges, type RequirementFilter } from "./api";
import type { ProjectRole } from "./types";

const keys = {
  projects: ["mms", "projects"] as const,
  project: (id: string) => ["mms", "projects", id] as const,
  members: (id: string) => ["mms", "projects", id, "members"] as const,
  invitations: (id: string) => ["mms", "projects", id, "invitations"] as const,
  documents: (id: string) => ["mms", "projects", id, "documents"] as const,
  sources: (id: string, docId: number) => ["mms", "projects", id, "documents", docId, "sources"] as const,
  pages: (id: string, docId: number, sourceId: number) => ["mms", "projects", id, "documents", docId, "sources", sourceId] as const,
  code: (group: string) => ["mms", "codes", group] as const,
  // 한 문서의 후보·입력·분석·버전은 모두 doc(id, docId) 아래에 두어 한꺼번에 다시 불러올 수 있게 한다
  doc: (id: string, docId: number) => ["mms", "projects", id, "doc", docId] as const,
  requirements: (id: string, docId: number) => ["mms", "projects", id, "doc", docId, "requirements"] as const,
  requirement: (id: string, docId: number, reqId: number) => ["mms", "projects", id, "doc", docId, "requirement", reqId] as const,
  notes: (id: string, docId: number) => ["mms", "projects", id, "doc", docId, "notes"] as const,
  analysis: (id: string, docId: number) => ["mms", "projects", id, "doc", docId, "analysis"] as const,
  versions: (id: string, docId: number) => ["mms", "projects", id, "doc", docId, "versions"] as const,
  version: (id: string, docId: number, versionId: number) => ["mms", "projects", id, "doc", docId, "versions", versionId] as const,
  categories: (id: string, docId: number) => ["mms", "projects", id, "doc", docId, "categories"] as const,
  confirmed: (id: string) => ["mms", "projects", id, "confirmed"] as const,
};

/** 로그인이 끝난 뒤에만 부른다 (세션 복원 전에 부르면 401) */
function useReady() {
  const { isAuthenticated, isLoading } = useAuth();
  return isAuthenticated && !isLoading;
}

// ---- 프로젝트·멤버 ----

export function useProjects() {
  return useQuery({ queryKey: keys.projects, queryFn: () => mmsApi.listProjects(), enabled: useReady() });
}

export function useProject(id: string) {
  return useQuery({ queryKey: keys.project(id), queryFn: () => mmsApi.getProject(id), enabled: useReady(), retry: false });
}

export function useMembers(id: string) {
  return useQuery({ queryKey: keys.members(id), queryFn: () => mmsApi.listMembers(id), enabled: useReady() });
}

/** 프로젝트를 만들고, 적어 둔 이메일에 초대장을 보낸다. 초대에 실패한 이메일은 돌려준다 */
export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { name: string; startDate: string; endDate: string; inviteEmails: string[] }) => {
      const project = await mmsApi.createProject({ name: input.name, start_date: input.startDate, end_date: input.endDate });
      const results = await Promise.allSettled(input.inviteEmails.map((email) => mmsApi.invite(String(project.id), email)));
      const failed = input.inviteEmails.filter((_, i) => results[i].status === "rejected");
      return { project, invited: input.inviteEmails.length - failed.length, failed };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
  });
}

export function useChangeRole(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, role }: { memberId: number; role: ProjectRole }) => mmsApi.changeRole(id, memberId, role),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.project(id) }),
  });
}

export function useRemoveMember(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (memberId: number) => mmsApi.removeMember(id, memberId),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.project(id) }),
  });
}

// ---- 초대 ----

/** 대기 중인 초대. 관리자만 볼 수 있어서 enabled로 막는다 */
export function useInvitations(id: string, enabled: boolean) {
  return useQuery({ queryKey: keys.invitations(id), queryFn: () => mmsApi.listInvitations(id), enabled: useReady() && enabled });
}

export function useInvite(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (email: string) => mmsApi.invite(id, email),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.invitations(id) }),
  });
}

export function useRevokeInvitation(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: number) => mmsApi.revokeInvitation(id, invitationId),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.invitations(id) }),
  });
}

/** 초대 링크 내용. 로그인하지 않아도 볼 수 있다 */
export function useInvitationInfo(token: string | null) {
  return useQuery({ queryKey: ["mms", "invitation", token], queryFn: () => mmsApi.lookupInvitation(token!), enabled: !!token, retry: false });
}

/** 초대 링크로 처음 가입할 때 쓸 가입 증표 (인증번호 대신). 아직 가입하지 않은 사람에게만 받는다 */
export function useInvitationSignupProof(token: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["mms", "invitation", token, "signup-proof"],
    queryFn: () => mmsApi.invitationSignupProof(token!),
    enabled: !!token && enabled,
    retry: false,
    staleTime: Infinity,
  });
}

export function useAcceptInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => mmsApi.acceptInvitation(token),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
  });
}

// ---- 문서·올린 파일 ----

export function useDocuments(id: string) {
  return useQuery({ queryKey: keys.documents(id), queryFn: () => mmsApi.listDocuments(id), enabled: useReady() });
}

/** 요구사항정의서 문서 (프로젝트를 만들면 서버가 1행 만든다) */
export function useRequirementsDoc(id: string) {
  const q = useDocuments(id);
  return { ...q, data: q.data?.find((d) => d.kind === "REQUIREMENTS") };
}

/** 프로젝트 목록 카드용: 프로젝트마다 요구사항정의서 상태 (id → 서버 상태) */
export function useRequirementsDocStatuses(ids: string[]) {
  const ready = useReady();
  return useQueries({
    queries: ids.map((id) => ({ queryKey: keys.documents(id), queryFn: () => mmsApi.listDocuments(id), enabled: ready })),
    combine: (results) => Object.fromEntries(ids.map((id, i) => [id, results[i].data?.find((d) => d.kind === "REQUIREMENTS")?.status])),
  });
}

export function useSources(id: string, docId: number | undefined) {
  return useQuery({ queryKey: keys.sources(id, docId ?? 0), queryFn: () => mmsApi.listSources(id, docId!), enabled: useReady() && !!docId });
}

export function useUploadSource(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { file: File } | { text: string }) => mmsApi.uploadSource(id, docId!, input),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.sources(id, docId ?? 0) });
      qc.invalidateQueries({ queryKey: keys.documents(id) });
    },
  });
}

export function useDeleteSource(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: number) => mmsApi.deleteSource(id, docId!, sourceId),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.sources(id, docId ?? 0) });
      qc.invalidateQueries({ queryKey: keys.documents(id) });
    },
  });
}

export function useSourcePages(id: string, docId: number | undefined, sourceId: number | null) {
  return useQuery({
    queryKey: keys.pages(id, docId ?? 0, sourceId ?? 0),
    queryFn: () => mmsApi.listSourcePages(id, docId!, sourceId!),
    enabled: useReady() && !!docId && !!sourceId,
  });
}

/** 원본 파일을 받아 브라우저 저장으로 넘긴다 */
export async function downloadSource(id: string, docId: number, sourceId: number, filename: string) {
  saveBlob(await mmsApi.downloadSource(id, docId, sourceId), filename);
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  // 저장이 시작된 뒤에 지운다
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---- 요구사항 후보 ----

/** 후보 목록. 서버가 200개씩 주고, 끝까지 내리면 fetchNextPage로 다음 묶음을 받는다 */
export function useRequirementList(id: string, docId: number | undefined, filter: RequirementFilter) {
  const q = useInfiniteQuery({
    queryKey: [...keys.requirements(id, docId ?? 0), filter],
    queryFn: ({ pageParam }) => mmsApi.listRequirements(id, docId!, filter, pageParam),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: useReady() && !!docId,
    placeholderData: (prev) => prev,
  });
  return { ...q, items: q.data?.pages.flatMap((p) => p.items) ?? [] };
}

export function useRequirement(id: string, docId: number | undefined, reqId: number | null) {
  return useQuery({
    queryKey: keys.requirement(id, docId ?? 0, reqId ?? 0),
    queryFn: () => mmsApi.getRequirement(id, docId!, reqId!),
    enabled: useReady() && !!docId && !!reqId,
    retry: false,
  });
}

type InfiniteList = { pages: ApiRequirementPage[]; pageParams: unknown[] };

/** 고친 후보를 다시 불러오지 않고 목록·상세 캐시에 바로 넣는다 (수백 개 목록을 매번 새로 받지 않게) */
function putRequirement(qc: QueryClient, id: string, docId: number, row: ApiRequirement) {
  qc.setQueriesData<InfiniteList>({ queryKey: keys.requirements(id, docId) }, (old) =>
    old && { ...old, pages: old.pages.map((p) => ({ ...p, items: p.items.map((r) => (r.id === row.id ? row : r)) })) },
  );
  qc.setQueryData<ApiRequirementDetail>(keys.requirement(id, docId, row.id), (old) => old && { ...old, ...row });
}

/** 문서 카드(버전 이후 고침 여부, 확정 경고 개수 등)도 바뀌므로 함께 다시 읽는다 */
const refreshDocCard = (qc: QueryClient, id: string) => qc.invalidateQueries({ queryKey: keys.documents(id) });

const CATEGORY_KEYS = ["category_major", "category_middle", "category_minor"] as const;
const touchesCategory = (changes: RequirementChanges) => CATEGORY_KEYS.some((k) => changes[k] !== undefined);

export function useUpdateRequirement(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ reqId, version, changes }: { reqId: number; version: number; changes: RequirementChanges }) =>
      mmsApi.updateRequirement(id, docId!, reqId, { ...changes, version }),
    onSuccess: (row, { changes }) => {
      putRequirement(qc, id, docId!, row);
      // 설명은 목록에 없으니 상세 캐시에만 넣는다. 필터에 걸린 목록은 칸이 바뀌면 빠질 수 있어서 다시 읽는다
      if (changes.description !== undefined) qc.setQueryData<ApiRequirementDetail>(keys.requirement(id, docId!, row.id), (old) => old && { ...old, description: changes.description! });
      if (changes.kind || changes.priority || changes.is_included !== undefined || changes.name || touchesCategory(changes))
        qc.invalidateQueries({ queryKey: keys.requirements(id, docId!), refetchType: "none" });
      if (touchesCategory(changes)) qc.invalidateQueries({ queryKey: keys.categories(id, docId!) });
      refreshDocCard(qc, id);
    },
  });
}

export function useBulkUpdateRequirements(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items: (RequirementChanges & { id: number; version: number })[]) => mmsApi.updateRequirements(id, docId!, items),
    onSuccess: (rows) => {
      for (const row of rows) putRequirement(qc, id, docId!, row);
      refreshDocCard(qc, id);
    },
  });
}

export function useCreateRequirement(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof mmsApi.createRequirement>[2]) => mmsApi.createRequirement(id, docId!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.requirements(id, docId!) });
      refreshDocCard(qc, id);
    },
  });
}

export function useDeleteRequirement(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reqId: number) => mmsApi.deleteRequirement(id, docId!, reqId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.requirements(id, docId!) });
      qc.invalidateQueries({ queryKey: keys.notes(id, docId!) });
      qc.invalidateQueries({ queryKey: keys.categories(id, docId!) });
      refreshDocCard(qc, id);
    },
  });
}

/** 이 문서에서 쓴 대·중·소분류 (대분류 필터, 분류 칸 자동완성) */
export function useCategories(id: string, docId: number | undefined) {
  return useQuery({ queryKey: keys.categories(id, docId ?? 0), queryFn: () => mmsApi.listCategories(id, docId!), enabled: useReady() && !!docId });
}

/** 409 REQUIREMENT_CHANGED 뒤처럼 이 문서의 후보·입력을 모두 새로 읽는다 */
export function useReloadDoc(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return () => {
    if (!docId) return;
    qc.invalidateQueries({ queryKey: keys.doc(id, docId) });
    refreshDocCard(qc, id);
  };
}

// ---- 입력한 내용 ----

export function useNotes(id: string, docId: number | undefined) {
  return useQuery({ queryKey: keys.notes(id, docId ?? 0), queryFn: () => mmsApi.listNotes(id, docId!), enabled: useReady() && !!docId });
}

/** 내 입력 남기기(text) 또는 지우기(text = null). 확인 필요 표시가 바뀔 수 있어 후보도 다시 읽는다 */
export function useWriteNote(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ reqId, field, text }: { reqId: number; field: NoteField; text: string | null }) => {
      if (text !== null) return mmsApi.writeNote(id, docId!, reqId, field, text);
      await mmsApi.deleteNote(id, docId!, reqId, field);
      return null;
    },
    onSuccess: (_, { reqId }) => {
      qc.invalidateQueries({ queryKey: keys.requirement(id, docId!, reqId) });
      qc.invalidateQueries({ queryKey: keys.notes(id, docId!) });
      qc.invalidateQueries({ queryKey: keys.requirements(id, docId!) });
      refreshDocCard(qc, id);
    },
  });
}

// ---- AI 분석·다시 분류 ----

/** 마지막 분석 진행률. 도는 동안(RUNNING)만 2초마다 다시 읽는다 */
export function useAnalysis(id: string, docId: number | undefined) {
  return useQuery({
    queryKey: keys.analysis(id, docId ?? 0),
    queryFn: () => mmsApi.getAnalysis(id, docId!),
    enabled: useReady() && !!docId,
    refetchInterval: (q) => (q.state.data?.status === "RUNNING" ? 2000 : false),
  });
}

/** 분석이 끝나면 부른다: 후보·입력·문서 카드·올린 파일(분석 표시)을 새로 읽는다 */
export function useAfterAnalysis(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return () => {
    if (!docId) return;
    for (const k of [keys.requirements, keys.notes, keys.categories]) qc.invalidateQueries({ queryKey: k(id, docId) });
    qc.invalidateQueries({ queryKey: [...keys.doc(id, docId), "requirement"] });
    qc.invalidateQueries({ queryKey: keys.sources(id, docId) });
    refreshDocCard(qc, id);
  };
}

/** 분석 시작. restart=true면 후보·직접 추가·입력을 모두 지우고 REQ-001부터 다시 분석한다 */
export function useAnalyze(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { prompt?: string; restart?: boolean }) => mmsApi.analyze(id, docId!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.analysis(id, docId!) });
      refreshDocCard(qc, id);
    },
  });
}

/** 다시 분류: 반영 안 된 입력과 새로 올린 파일을 기존 후보에 반영 (번호는 그대로) */
export function useRefine(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { prompt?: string }) => mmsApi.refine(id, docId!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.analysis(id, docId!) });
      refreshDocCard(qc, id);
    },
  });
}

// ---- 버전 ----

export function useVersions(id: string, docId: number | undefined, enabled = true) {
  return useQuery({ queryKey: keys.versions(id, docId ?? 0), queryFn: () => mmsApi.listVersions(id, docId!), enabled: useReady() && !!docId && enabled });
}

export function useVersion(id: string, docId: number | undefined, versionId: number | undefined) {
  return useQuery({
    queryKey: keys.version(id, docId ?? 0, versionId ?? 0),
    queryFn: () => mmsApi.getVersion(id, docId!, versionId!),
    enabled: useReady() && !!docId && !!versionId,
    retry: false,
  });
}

/** overwrite=false 버전 추가(무조건 새 버전), true 버전 저장(이번 분석 이후 마지막 버전을 덮어씀) */
export function useSaveVersion(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (overwrite: boolean) => (overwrite ? mmsApi.saveVersion(id, docId!) : mmsApi.addVersion(id, docId!)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.versions(id, docId!) });
      refreshDocCard(qc, id);
    },
  });
}

// ---- 확정 ----

// [예비 목 저장소] 서버 없이 확정을 흉내 낼 때 store.confirm에 넘길 후보를 모은다 (Workspace의 확정 버튼에서 불렀다).
// 다시 쓸 때 주석을 풀고 import type { ConfirmedItem } from "./types" 를 넣는다
// export async function loadConfirmItems(id: string, docId: number): Promise<ConfirmedItem[]> {
//   const rows: ApiRequirement[] = [];
//   let cursor: number | undefined;
//   do {
//     const page = await mmsApi.listRequirements(id, docId, { included: true }, cursor);
//     rows.push(...page.items);
//     cursor = page.next_cursor ?? undefined;
//   } while (cursor !== undefined);
//   const items: ConfirmedItem[] = [];
//   for (let i = 0; i < rows.length; i += 8) {
//     const details = await Promise.all(rows.slice(i, i + 8).map((r) => mmsApi.getRequirement(id, docId, r.id)));
//     for (const d of details)
//       items.push({ id: d.id, code: d.code, name: d.name, kind: d.kind, priority: d.priority, description: d.description, quote: d.sources.map((s) => s.quote).join("\n") });
//   }
//   return items;
// }

/** 확정 뒤에는 문서 상태·확정 목록·버전 기록이 모두 바뀐다 */
function refreshConfirm(qc: QueryClient, id: string, docId: number) {
  refreshDocCard(qc, id);
  qc.invalidateQueries({ queryKey: keys.confirmed(id) });
  qc.invalidateQueries({ queryKey: keys.versions(id, docId) });
  qc.invalidateQueries({ queryKey: keys.requirements(id, docId) }); // "AI 값 확인" 표시가 풀린다
}

export function useConfirm(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => mmsApi.confirm(id, docId!), onSettled: () => refreshConfirm(qc, id, docId!) });
}

/** 확정 후 수정: 문서만 다시 고칠 수 있게 열고, 확정 기록은 그대로 둔다 (다음 확정은 번호 + 1) */
export function useReopen(id: string, docId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => mmsApi.reopen(id, docId!), onSettled: () => refreshConfirm(qc, id, docId!) });
}

/** 확정한 문서 목록 (최신이 앞) */
export function useConfirmedDocs(id: string) {
  return useQuery({ queryKey: keys.confirmed(id), queryFn: () => mmsApi.listConfirmed(id), enabled: useReady() });
}

/** 확정 기록 Excel을 받아 브라우저 저장으로 넘긴다. 서버가 이름을 주지 않으면 fallbackName */
export async function downloadConfirmedExcel(id: string, docId: number, versionId: number, fallbackName: string) {
  const { blob, filename } = await mmsApi.downloadExcel(id, docId, versionId);
  saveBlob(blob, filename ?? fallbackName);
}

// ---- 공통코드 ----

function useCodes(group: string) {
  const q = useQuery({ queryKey: keys.code(group), queryFn: () => mmsApi.codeGroup(group), enabled: useReady(), staleTime: 5 * 60_000 });
  const codes = q.data?.codes ?? [];
  /** 저장된 값이 목록에 없으면(관리자가 끈 값) 코드 그대로 보여 준다 */
  const label = (code: string) => codes.find((c) => c.code === code)?.label ?? code;
  return { codes, label, isLoading: q.isLoading };
}

/** 요구사항 구분 (기능/비기능/제약사항). 관리자가 값을 늘릴 수 있어서 코드에 적지 않고 서버에서 받는다 */
export const useReqKinds = () => useCodes("MMS_REQ_KIND");

/** 우선순위 (높음/보통/낮음) */
export const usePriorities = () => useCodes("MMS_PRIORITY");
