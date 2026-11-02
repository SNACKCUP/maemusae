// 매무새 백엔드(/api/mms) 호출. 킷의 api 클라이언트를 써서 로그인 토큰·자동 갱신이 그대로 붙는다.
// 응답 모양은 백엔드 스키마(snake_case)를 그대로 쓴다. 화면 부품은 이 파일을 직접 부르지 않고 queries.ts의 훅을 쓴다.

import { api } from "@/meerkit";

import type { ProjectRole } from "./types";

export interface ApiProject {
  id: number;
  name: string;
  start_date: string; // YYYY-MM-DD
  end_date: string;
  member_count: number;
  /** 이 프로젝트에서 내 역할. 멤버가 아닌 서비스 관리자(MASTER)가 보기만 할 때는 null */
  my_role: ProjectRole | null;
  created_at: string;
}

export interface ApiProjectPage {
  items: ApiProject[];
  total: number;
  page: number;
  size: number;
}

export interface ApiMember {
  id: number;
  /** 로그인 아이디 */
  user_id: string;
  name: string;
  role: ProjectRole;
  joined_at: string;
}

export interface ApiInvitation {
  id: number;
  email: string;
  role: ProjectRole;
  invited_by_name: string;
  expires_at: string;
  created_at: string;
}

export interface ApiInvitationInfo {
  project_name: string;
  invited_by_name: string;
  role: ProjectRole;
  email: string;
  expires_at: string;
  /** 초대 이메일로 이미 가입했는지. false면 가입, true면 로그인으로 보낸다 */
  account_exists: boolean;
}

export type ApiDocStatus = "EMPTY" | "ANALYZING" | "READY" | "CONFIRMING" | "CONFIRMED" | "FAILED";

export interface ApiDocument {
  id: number;
  kind: string;
  kind_label: string;
  status: ApiDocStatus;
  current_revision: number;
  source_count: number;
  /** 이번 분석 이후 마지막으로 버전 추가·저장한 시각. 다시 분석하면 null */
  saved_at: string | null;
  /** 마지막 버전 번호 (화면 "마지막 버전 v2"). 없으면 null */
  last_version_no: number | null;
  /** saved_at 뒤에 후보·입력을 또 고쳤는지 */
  changed_since_save: boolean;
  /** 직접 추가한 후보 수 (다시 분석하면 사라짐) */
  manual_count: number;
  confirmed_at: string | null;
  confirmed_by_name: string | null;
  /** 확정 창 경고: 체크된 후보 중 AI 질문에 아직 답이 없는 수 */
  open_question_count: number;
  /** 확정 창 경고: 체크된 후보 중 "AI 값 확인" 표시가 남은 수 */
  defaulted_count: number;
  updated_at: string;
}

export interface ApiSource {
  id: number;
  source_type: "FILE" | "TEXT";
  filename: string | null;
  content_type: string | null;
  size_bytes: number | null;
  page_count: number;
  uploaded_by_name: string;
  uploaded_by_me: boolean;
  created_at: string;
}

export interface ApiSourcePage {
  id: number;
  seq: number;
  page_no: number | null;
  location_label: string;
  text: string;
}

export interface ApiCode {
  code: string;
  label: string;
  sort_order: number;
}

export interface ApiCodeGroup {
  group_code: string;
  name: string;
  codes: ApiCode[];
}

export interface ApiRequirement {
  id: number;
  code: string; // REQ-012
  name: string;
  /** 공통코드 MMS_REQ_KIND */
  kind: string;
  /** 공통코드 MMS_PRIORITY */
  priority: string;
  /** 대·중·소분류 (업무 영역). 공통코드가 아니라 문서마다 AI가 채우고 사람이 고치는 글. 없으면 null */
  category_major: string | null;
  category_middle: string | null;
  category_minor: string | null;
  /** 체크. 해제하면 확정에서 빠진다 */
  is_included: boolean;
  /** 직접 추가한 후보 (이것만 지울 수 있다) */
  is_manual: boolean;
  /** AI 질문이 있고 아직 아무도 답을 남기지 않음 */
  needs_answer: boolean;
  /** 근거가 있고 모두 문서에서 확인됨 */
  verified_all: boolean;
  /** AI 값이 목록에 없어 기본값을 넣음 (확인 필요) */
  kind_defaulted: boolean;
  priority_defaulted: boolean;
  /** 고칠 때 그대로 보낸다. 다르면 409 REQUIREMENT_CHANGED */
  version: number;
}

export interface ApiRequirementPage {
  items: ApiRequirement[];
  next_cursor: number | null;
}

export interface ApiEvidence {
  id: number;
  source_file_id: number;
  /** 올린 파일 이름. 직접 쓴 글은 "직접 입력" */
  filename: string;
  location_label: string; // 3쪽
  /** 문장이 다음 쪽으로 넘어가면 끝 쪽 (화면 3~4쪽) */
  end_location_label: string | null;
  source_page_id: number;
  quote: string;
  /** false면 "위치 확인 필요" */
  verified: boolean;
}

export type NoteField = "DESCRIPTION" | "ANSWER";

export interface ApiNote {
  id: number;
  requirement_id: number;
  requirement_code: string;
  requirement_name: string;
  field: NoteField;
  text: string;
  author_name: string;
  /** 내가 남긴 입력 (지우기 버튼) */
  mine: boolean;
  /** 다시 분류에 반영됨 */
  applied: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiRequirementDetail extends ApiRequirement {
  description: string;
  ai_question: string | null;
  ai_answer: string | null;
  sources: ApiEvidence[];
  notes: ApiNote[];
  created_at: string;
  updated_at: string;
}

export interface RequirementFilter {
  kind?: string;
  priority?: string;
  included?: boolean;
  needs_check?: boolean;
  category_major?: string;
  q?: string;
}

/** 분류 칸은 빈 글자("")를 보내면 지운다 */
export type RequirementChanges = Partial<
  Pick<ApiRequirementDetail, "name" | "description" | "kind" | "priority" | "is_included"> & { category_major: string; category_middle: string; category_minor: string }
>;

export type CategoryField = "category_major" | "category_middle" | "category_minor";

/** 이 문서에서 쓴 분류 (필터·자동완성용). count = 그 분류의 후보 수 */
export interface ApiCategoryPath {
  major: string;
  middle: string | null;
  minor: string | null;
  count: number;
}

export interface ApiAnalysisRun {
  run_id: number;
  run_type: "ANALYZE" | "REFINE";
  status: "RUNNING" | "SUCCEEDED" | "FAILED";
  done_steps: number;
  total_steps: number;
  /** 실패 이유 (예: LLM_TIMEOUT, ANALYSIS_INTERRUPTED) */
  error_code: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface ApiVersionSaved {
  id: number;
  version_no: number;
  saved_at: string;
  /** 버전 저장이 이번 분석의 마지막 버전을 덮어썼으면 true */
  overwritten: boolean;
}

export interface ApiVersionListItem {
  id: number;
  kind: "SAVED" | "CONFIRMED";
  version_no: number | null;
  revision: number | null;
  item_count: number;
  created_by_name: string;
  created_at: string;
  updated_by_name: string | null;
  updated_at: string;
}

export interface ApiVersionItem {
  code: string;
  name: string;
  kind: string;
  priority: string;
  /** 분류가 생기기 전(M4-2 전)에 남긴 버전에는 없다 */
  category_major?: string | null;
  category_middle?: string | null;
  category_minor?: string | null;
  description: string;
  ai_question: string | null;
  ai_answer: string | null;
  is_included: boolean;
  is_manual: boolean;
  kind_defaulted: boolean;
  priority_defaulted: boolean;
  sources: Omit<ApiEvidence, "id" | "source_file_id" | "source_page_id">[];
  notes: { field: NoteField; text: string; author_name: string; updated_at: string }[];
}

export interface ApiVersionDetail extends ApiVersionListItem {
  items: ApiVersionItem[];
}

export interface ApiConfirmResult {
  version_id: number;
  /** 1 = 확정, 2부터 = 수정 후 확정 */
  revision: number;
  item_count: number;
  confirmed_at: string;
}

/** 프로젝트 상세 "확정한 문서" 표 한 줄 (확정할 때마다 한 줄, 최신순) */
export interface ApiConfirmedDocument {
  version_id: number;
  document_id: number;
  title: string;
  /** 공통코드 MMS_DOC_KIND */
  kind: string;
  kind_label: string;
  revision: number;
  item_count: number;
  confirmed_by_name: string;
  confirmed_at: string;
}

const P = "/mms/projects";
const D = (id: string, docId: number) => `${P}/${id}/documents/${docId}`;
const data = <T,>(r: { data: T }) => r.data;

/** Content-Disposition의 filename*=UTF-8''… (한글 이름). 없으면 null */
function filenameOf(header: unknown): string | null {
  const m = typeof header === "string" ? /filename\*=UTF-8''([^;]+)/i.exec(header) : null;
  if (!m) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch {
    return null;
  }
}

export const mmsApi = {
  // 프로젝트·멤버
  listProjects: (q?: string) => api.get<ApiProjectPage>(P, { params: { q: q || undefined, size: 100 } }).then(data),
  getProject: (id: string) => api.get<ApiProject>(`${P}/${id}`).then(data),
  createProject: (body: { name: string; start_date: string; end_date: string }) => api.post<ApiProject>(P, body).then(data),
  listMembers: (id: string) => api.get<ApiMember[]>(`${P}/${id}/members`).then(data),
  changeRole: (id: string, memberId: number, role: ProjectRole) => api.patch<ApiMember>(`${P}/${id}/members/${memberId}`, { role }).then(data),
  removeMember: (id: string, memberId: number) => api.delete(`${P}/${id}/members/${memberId}`),

  // 초대 (관리자)
  listInvitations: (id: string) => api.get<ApiInvitation[]>(`${P}/${id}/invitations`).then(data),
  invite: (id: string, email: string, role: ProjectRole = "MEMBER") => api.post<ApiInvitation>(`${P}/${id}/invitations`, { email, role }).then(data),
  revokeInvitation: (id: string, invitationId: number) => api.delete(`${P}/${id}/invitations/${invitationId}`),

  // 초대 링크 (토큰은 로그에 남지 않게 주소가 아니라 본문으로 보낸다)
  lookupInvitation: (token: string) => api.post<ApiInvitationInfo>("/mms/invitations/lookup", { token }).then(data),
  invitationSignupProof: (token: string) => api.post<{ email: string; email_verification_token: string }>("/mms/invitations/signup-proof", { token }).then(data),
  acceptInvitation: (token: string) => api.post<{ project_id: number; role: ProjectRole }>("/mms/invitations/accept", { token }).then(data),

  // 문서·올린 파일
  listDocuments: (id: string) => api.get<ApiDocument[]>(`${P}/${id}/documents`).then(data),
  listSources: (id: string, docId: number) => api.get<ApiSource[]>(`${P}/${id}/documents/${docId}/sources`).then(data),
  uploadSource: (id: string, docId: number, input: { file: File } | { text: string }) => {
    const form = new FormData();
    if ("file" in input) form.append("file", input.file);
    else form.append("text", input.text);
    return api.post<ApiSource>(`${P}/${id}/documents/${docId}/sources`, form).then(data);
  },
  deleteSource: (id: string, docId: number, sourceId: number) => api.delete(`${P}/${id}/documents/${docId}/sources/${sourceId}`),
  listSourcePages: (id: string, docId: number, sourceId: number) => api.get<ApiSourcePage[]>(`${P}/${id}/documents/${docId}/sources/${sourceId}/pages`).then(data),
  // 원본은 공개 주소가 없어서 로그인 토큰을 붙여 받아야 한다 (a 태그로 바로 열면 401)
  downloadSource: (id: string, docId: number, sourceId: number) =>
    api.get<Blob>(`${P}/${id}/documents/${docId}/sources/${sourceId}/file`, { responseType: "blob" }).then(data),

  // 요구사항 후보 (목록은 가벼운 칸만, 설명·근거·입력은 상세)
  listRequirements: (id: string, docId: number, filter: RequirementFilter, cursor?: number) =>
    api
      .get<ApiRequirementPage>(`${D(id, docId)}/requirements`, {
        params: { ...filter, needs_check: filter.needs_check || undefined, q: filter.q?.trim() || undefined, cursor, limit: 200 },
      })
      .then(data),
  getRequirement: (id: string, docId: number, reqId: number) => api.get<ApiRequirementDetail>(`${D(id, docId)}/requirements/${reqId}`).then(data),
  updateRequirement: (id: string, docId: number, reqId: number, body: RequirementChanges & { version: number }) =>
    api.patch<ApiRequirement>(`${D(id, docId)}/requirements/${reqId}`, body).then(data),
  /** 하나라도 실패하면 아무것도 안 바뀐다 (최대 500개) */
  updateRequirements: (id: string, docId: number, items: (RequirementChanges & { id: number; version: number })[]) =>
    api.patch<ApiRequirement[]>(`${D(id, docId)}/requirements`, { items }).then(data),
  createRequirement: (id: string, docId: number, body: { name: string; description?: string; kind: string; priority: string; category_major?: string; category_middle?: string; category_minor?: string }) =>
    api.post<ApiRequirement>(`${D(id, docId)}/requirements`, body).then(data),
  deleteRequirement: (id: string, docId: number, reqId: number) => api.delete(`${D(id, docId)}/requirements/${reqId}`),
  listCategories: (id: string, docId: number) => api.get<ApiCategoryPath[]>(`${D(id, docId)}/categories`).then(data),

  // 입력한 내용 (사람마다 칸마다 한 건)
  writeNote: (id: string, docId: number, reqId: number, field: NoteField, text: string) =>
    api.put<ApiNote>(`${D(id, docId)}/requirements/${reqId}/notes/${field}`, { text }).then(data),
  deleteNote: (id: string, docId: number, reqId: number, field: NoteField) => api.delete(`${D(id, docId)}/requirements/${reqId}/notes/${field}`),
  listNotes: (id: string, docId: number) => api.get<ApiNote[]>(`${D(id, docId)}/notes`, { params: { limit: 500 } }).then(data),

  // AI 분석·다시 분류 (202로 바로 돌아오고, 진행률은 getAnalysis)
  analyze: (id: string, docId: number, body: { prompt?: string; restart?: boolean }) =>
    api.post<{ run_id: number }>(`${D(id, docId)}/analyze`, body).then(data),
  refine: (id: string, docId: number, body: { prompt?: string }) => api.post<{ run_id: number }>(`${D(id, docId)}/refine`, body).then(data),
  /** 분석한 적이 없으면 null */
  getAnalysis: (id: string, docId: number) => api.get<ApiAnalysisRun | null>(`${D(id, docId)}/analysis`).then(data),

  // 버전 (버전 추가 = 무조건 새 버전, 버전 저장 = 이번 분석 이후 마지막 버전을 덮어씀)
  addVersion: (id: string, docId: number) => api.post<ApiVersionSaved>(`${D(id, docId)}/versions`).then(data),
  saveVersion: (id: string, docId: number) => api.put<ApiVersionSaved>(`${D(id, docId)}/versions/latest`).then(data),
  listVersions: (id: string, docId: number) => api.get<ApiVersionListItem[]>(`${D(id, docId)}/versions`).then(data),
  getVersion: (id: string, docId: number, versionId: number) => api.get<ApiVersionDetail>(`${D(id, docId)}/versions/${versionId}`).then(data),

  // 확정 (관리자). 확정 내용은 getVersion으로 읽는다
  confirm: (id: string, docId: number) => api.post<ApiConfirmResult>(`${D(id, docId)}/confirm`).then(data),
  reopen: (id: string, docId: number) => api.post(`${D(id, docId)}/reopen`),
  listConfirmed: (id: string) => api.get<ApiConfirmedDocument[]>(`${P}/${id}/confirmed`).then(data),
  // 확정 기록 Excel. 로그인 토큰이 필요해서 a 태그 대신 blob으로 받는다 (멤버만, MASTER 403)
  downloadExcel: (id: string, docId: number, versionId: number) =>
    api.get<Blob>(`${D(id, docId)}/versions/${versionId}/excel`, { responseType: "blob" }).then((r) => ({ blob: r.data, filename: filenameOf(r.headers["content-disposition"]) })),

  // 공통코드 (구분 드롭다운 등)
  codeGroup: (groupCode: string) => api.get<ApiCodeGroup>(`/codes/${groupCode}`).then(data),
};

/** 서버 오류 응답 {detail, code}에서 화면에 보여 줄 문구를 꺼낸다 */
export function apiError(error: unknown, fallback = "요청에 실패했어요. 잠시 후 다시 시도해 주세요."): string {
  const res = (error as { response?: { data?: { detail?: unknown } } })?.response;
  if (!res) return error ? "서버에 연결할 수 없어요." : fallback;
  return typeof res.data?.detail === "string" ? res.data.detail : fallback;
}

/** 서버 오류 코드 (예: INVITATION_INVALID). 없으면 null */
export function apiErrorCode(error: unknown): string | null {
  const code = (error as { response?: { data?: { code?: unknown } } })?.response?.data?.code;
  return typeof code === "string" ? code : null;
}

/** 오류 HTTP 상태 (예: 404). 응답이 없으면 null */
export function apiStatus(error: unknown): number | null {
  return (error as { response?: { status?: number } })?.response?.status ?? null;
}
