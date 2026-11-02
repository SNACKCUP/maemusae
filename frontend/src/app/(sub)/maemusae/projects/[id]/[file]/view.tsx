"use client";

import { useParams } from "next/navigation";

import { ProjectGuard } from "../../../_components/ProjectGuard";
import { Btn, card } from "../../../_components/ui";

const TITLES: Record<string, string> = { spec: "기능정의서", report: "중간보고서", export: "내보내기" };

// 아직 만들지 않은 파일들의 자리. 요구사항정의서가 확정되면 이어서 붙는다.
export default function ComingSoonPage() {
  const { id, file } = useParams<{ id: string; file: string }>();
  const title = TITLES[file] ?? "이 문서";
  return (
    <ProjectGuard projectId={id}>
      {() => (
        <div className={`${card} mx-auto grid max-w-lg justify-items-center gap-3 py-14 text-center`} data-rise>
          <h1 className="text-3xl font-extrabold tracking-tight">{title}</h1>
          <p className="text-sm text-[#6c6a62]">준비 중이에요.</p>
          <Btn href={`/maemusae/projects/${id}`} variant="dark" className="mt-3">프로젝트로 돌아가기</Btn>
        </div>
      )}
    </ProjectGuard>
  );
}
