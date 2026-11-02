"use client";

import type { ReactNode } from "react";

import { useAuth } from "@/meerkit";

import { apiStatus, type ApiProject } from "../_lib/api";
import { useProject } from "../_lib/queries";
import type { ProjectRole } from "../_lib/types";
import { Btn, card } from "./ui";

interface GuardContext {
  project: ApiProject;
  /** 이 프로젝트에서 내 역할. 서비스 관리자(MASTER)가 멤버가 아닌데 보기만 할 때는 null */
  role: ProjectRole | null;
  isAdmin: boolean;
  /** 멤버가 아니라 보기만 하는 중 (MASTER 고객 지원). 바꾸는 버튼을 숨긴다 */
  readOnly: boolean;
}

function Blocked({ title, body, login }: { title: string; body: string; login?: boolean }) {
  return (
    <div className={`${card} mx-auto max-w-lg text-center`} role="alert">
      <h2 className="text-2xl font-extrabold tracking-tight">{title}</h2>
      <p className="mx-auto mt-2 text-sm text-[#6c6a62]">{body}</p>
      {login ? <Btn href="/maemusae/login" variant="dark" className="mt-6">로그인</Btn> : <Btn href="/maemusae/projects" variant="dark" className="mt-6">프로젝트 목록으로</Btn>}
    </div>
  );
}

/**
 * 프로젝트 안의 화면을 지키는 가드. Meerkit의 RequireAuth/RequireRole이 "로그인했는가, 전역 역할이 있는가"를 본다면,
 * 이 가드는 "이 프로젝트의 멤버인가, 프로젝트 관리자인가"를 본다. 역할은 서버 응답(my_role)을 쓰고, 서버도 같은 검사를 한다.
 */
export function ProjectGuard({ projectId, need = "member", children }: { projectId: string; need?: "member" | "admin"; children: (ctx: GuardContext) => ReactNode }) {
  const auth = useAuth();
  const { data: project, error, isLoading } = useProject(projectId);
  if (auth.isLoading || (auth.isAuthenticated && isLoading)) return <div className="h-[40vh]" aria-busy />;
  if (!auth.isAuthenticated) return <Blocked title="로그인이 필요해요" body="프로젝트는 로그인한 멤버만 볼 수 있어요." login />;
  if (error || !project) {
    const status = apiStatus(error);
    if (status === 403) return <Blocked title="이 프로젝트의 멤버가 아니에요" body="프로젝트 관리자에게 초대를 요청해 주세요." />;
    if (status === 404 || status === 422) return <Blocked title="프로젝트를 찾을 수 없어요" body="주소가 잘못되었거나 삭제된 프로젝트예요." />;
    return <Blocked title="프로젝트를 불러오지 못했어요" body="잠시 후 다시 시도해 주세요." />;
  }
  const role = project.my_role;
  if (need === "admin" && role !== "ADMIN") return <Blocked title="프로젝트 관리자만 볼 수 있어요" body="멤버 권한은 관리자만 바꿀 수 있어요." />;
  return <>{children({ project, role, isAdmin: role === "ADMIN", readOnly: role === null })}</>;
}
