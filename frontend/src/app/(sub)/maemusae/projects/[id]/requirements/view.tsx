"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AiPromptInput, ThinkingIndicator } from "@/meerkit";

import { ProjectGuard } from "../../../_components/ProjectGuard";
import { SourcesPanel } from "../../../_components/SourcesPanel";
import { Viewer } from "../../../_components/Viewer";
import { ANALYZING_LABELS, REFINING_LABELS, Workspace } from "../../../_components/Workspace";
import { Btn, PageHead, Pill, card } from "../../../_components/ui";
import { apiError, type ApiAnalysisRun } from "../../../_lib/api";
import { DOC_STATUS, docStatus } from "../../../_lib/labels";
import { useAfterAnalysis, useAnalysis, useAnalyze, useRequirementsDoc, useUploadSource } from "../../../_lib/queries";

// 분석 실패 이유 (서버 error_code). 그 밖의 코드는 기본 문구
const FAIL_TEXT: Record<string, string> = {
  LLM_TIMEOUT: "AI 응답이 너무 늦어 멈췄어요.",
  LLM_PROVIDER_ERROR: "AI 서비스에 연결하지 못했어요.",
  LLM_RATE_LIMITED: "AI 요청이 몰려 멈췄어요.",
  LLM_BAD_OUTPUT: "AI 답을 읽지 못했어요.",
  ANALYSIS_INTERRUPTED: "서버가 다시 시작되어 분석이 멈췄어요.",
};
// 다시 시도해도 같은 결과인 설정 문제 (서버 운영자가 고쳐야 함). "잠시 후 다시 시도" 를 붙이지 않는다
const SETUP_FAIL_TEXT: Record<string, string> = {
  LLM_NOT_CONFIGURED: "AI 키가 설정되지 않아 분석할 수 없어요. 관리자에게 문의해 주세요.",
  LLM_AUTH_FAILED: "AI 키가 올바르지 않아 분석할 수 없어요. 관리자에게 문의해 주세요.",
  LLM_QUOTA_EXCEEDED: "AI 사용 한도를 모두 써서 분석할 수 없어요. 관리자에게 문의해 주세요.",
};
const failText = (code: string | null) =>
  (code && SETUP_FAIL_TEXT[code]) || `${(code && FAIL_TEXT[code]) || "분석하지 못했어요."} 잠시 후 다시 시도해 주세요.`;

export default function RequirementsPage() {
  const { id } = useParams<{ id: string }>();
  const { data: serverDoc } = useRequirementsDoc(id);
  const docId = serverDoc?.id;
  const { data: run } = useAnalysis(id, docId);
  const afterAnalysis = useAfterAnalysis(id, docId);
  const analyze = useAnalyze(id, docId);
  const upload = useUploadSource(id, docId);
  const [uploading, setUploading] = useState(false);
  const hasSources = (serverDoc?.source_count ?? 0) > 0;

  const running = run?.status === "RUNNING" || serverDoc?.status === "ANALYZING";
  const status = running ? "analyzing" : docStatus(serverDoc?.status);
  const st = DOC_STATUS[status];

  // 분석이 끝나면 후보·입력·문서를 새로 읽고, 실패했으면 이유를 알린다.
  // 진행 중이던 분석이 끝났을 때와, 작은 문서라 처음 읽었을 때 이미 끝나 있던 새 분석 둘 다 잡는다 (처음 들어올 때 본 지난 분석은 빼고)
  // (undefined = 아직 못 읽음, null = 분석한 적 없음)
  const prevRun = useRef<ApiAnalysisRun | null | undefined>(undefined);
  useEffect(() => {
    const prev = prevRun.current;
    prevRun.current = run;
    if (prev === undefined || !run || run.status === "RUNNING") return;
    if (prev && prev.run_id === run.run_id && prev.status !== "RUNNING") return;
    afterAnalysis();
    if (run.status === "FAILED") toast.error(failText(run.error_code));
    else toast.success(run.run_type === "REFINE" ? "다시 분류를 마쳤어요. 바뀐 후보를 확인해 주세요." : "분석을 마쳤어요.");
  }, [run, afterAnalysis]);

  // 붙인 파일을 서버에 올리고(원본 보관 + 글 뽑기), 올린 문서가 하나라도 있으면 분석을 시작한다
  const submit = async (msg: string, files: File[]) => {
    setUploading(true);
    let ok = 0;
    for (const file of files) {
      try {
        await upload.mutateAsync({ file });
        ok += 1;
      } catch (e) {
        toast.error(`${file.name}: ${apiError(e, "올리지 못했어요.")}`);
      }
    }
    setUploading(false);
    if (ok > 0 || hasSources) analyze.mutate({ prompt: msg.trim() || undefined }, { onError: (e) => toast.error(apiError(e)) });
  };

  return (
    <ProjectGuard projectId={id}>
      {({ project, isAdmin, readOnly }) => (
        <div className="grid gap-8">
          <PageHead eyebrow={project.name} title="요구사항정의서">
            <Pill tone={st.tone}>{st.label}</Pill>
            <Link href={`/maemusae/projects/${id}`} className="text-sm underline print:hidden">프로젝트로</Link>
          </PageHead>

          {status === "empty" && (
            <section className={`${card} mx-auto grid w-full max-w-2xl gap-4`} data-rise>
              <h2 className="text-xl font-extrabold tracking-tight">고객 문서를 올리고 요청을 적어 주세요</h2>
              <p className="text-sm text-[#6c6a62]">문서를 한 개 이상 붙이고 보내면 AI가 요구사항 후보를 가려내요. 글은 비워 두어도 괜찮아요. 파일 하나는 10MB까지예요.</p>
              {serverDoc?.status === "FAILED" && run?.status === "FAILED" && <p role="alert" className="text-sm font-medium text-[#b3261e]">지난 분석이 실패했어요. {failText(run.error_code)}</p>}
              {readOnly ? (
                <p className="text-sm text-[#6c6a62]">분석은 프로젝트 멤버만 시작할 수 있어요.</p>
              ) : (
                <AiPromptInput
                  placeholder="예: 쇼핑몰 리뉴얼 요청서예요. 결제와 회원 관련 요구사항 위주로 뽑아 주세요"
                  accept=".pdf,.docx,.xlsx,.txt,.md,.pptx"
                  minFiles={hasSources ? 0 : 1}
                  requireText={false}
                  submitLabel={uploading ? "올리는 중…" : "분류 시작"}
                  disabled={uploading || analyze.isPending || !serverDoc}
                  onSubmit={submit}
                />
              )}
              {!readOnly && hasSources && (
                // 입력창은 글이나 새 파일이 있어야 보내기가 켜진다. 이미 올린 문서만으로 시작하는 길을 따로 둔다
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#f6f6f3] px-4 py-3">
                  <p className="text-sm text-[#6c6a62]">올린 문서 {serverDoc?.source_count}개로 요청 글 없이 바로 시작할 수 있어요.</p>
                  <Btn size="sm" variant="primary" disabled={uploading || analyze.isPending} onClick={() => submit("", [])}>
                    {analyze.isPending ? "시작하는 중…" : "올린 문서로 분석 시작"}
                  </Btn>
                </div>
              )}
            </section>
          )}

          {status === "analyzing" && (
            <section className={`${card} mx-auto grid w-full max-w-2xl justify-items-center gap-4 py-16`} role="status" data-rise>
              <ThinkingIndicator size="lg" labels={run?.run_type === "REFINE" ? REFINING_LABELS : ANALYZING_LABELS} />
              {run && run.total_steps > 1 && (
                <p className="text-sm font-semibold tabular-nums">{Math.min(run.done_steps + 1, run.total_steps)}/{run.total_steps} {run.run_type === "REFINE" ? "다시 분류 중" : "분석 중"}</p>
              )}
              <p className="text-sm text-[#6c6a62]">다른 화면에 다녀와도 서버에서 계속 진행돼요.</p>
            </section>
          )}

          <div className="print:hidden">
            <SourcesPanel projectId={id} docId={docId} canManageAll={isAdmin} readOnly={readOnly} />
          </div>

          {status === "ready" && serverDoc && <Workspace projectId={id} doc={serverDoc} isAdmin={isAdmin} readOnly={readOnly} />}
          {status === "confirmed" && serverDoc && <Viewer project={project} doc={serverDoc} isAdmin={isAdmin} readOnly={readOnly} />}
        </div>
      )}
    </ProjectGuard>
  );
}
