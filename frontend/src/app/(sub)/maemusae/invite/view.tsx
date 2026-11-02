"use client";

import { useRouter, useSearchParams } from "next/navigation";

import { AuthPanel, useAuth } from "@/meerkit";

import { Btn, card } from "../_components/ui";
import { apiError } from "../_lib/api";
import { ROLE_LABEL } from "../_lib/labels";
import { useAcceptInvitation, useInvitationInfo, useInvitationSignupProof } from "../_lib/queries";

// 초대 메일의 링크(/maemusae/invite?token=...)로 들어오는 화면.
// 가입하지 않은 사람은 초대 이메일로 바로 가입하고(인증번호 생략), 가입한 사람은 로그인한 뒤 수락하면 프로젝트 멤버가 된다.
export default function InvitePage() {
  const token = useSearchParams().get("token");
  const router = useRouter();
  const auth = useAuth();
  const info = useInvitationInfo(token);
  const needsSignup = !auth.isLoading && !auth.isAuthenticated && info.data?.account_exists === false;
  const proof = useInvitationSignupProof(token, needsSignup);
  const accept = useAcceptInvitation();

  if (!token || info.isError) {
    return (
      <div className={`${card} mx-auto max-w-lg text-center`} role="alert">
        <h1 className="text-2xl font-extrabold tracking-tight">초대 링크를 쓸 수 없어요</h1>
        <p className="mt-2 text-sm text-[#6c6a62]">{token ? apiError(info.error) : "초대 메일의 링크를 다시 눌러 주세요."}</p>
        <Btn href="/maemusae/projects" variant="dark" className="mt-6">프로젝트 목록으로</Btn>
      </div>
    );
  }
  if (info.isLoading || !info.data || auth.isLoading) return <div className="h-[40vh]" aria-busy />;
  const inv = info.data;

  const head = (
    <div className="grid justify-items-center gap-2 text-center">
      <p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">프로젝트 초대</p>
      <h1 className="text-3xl font-extrabold tracking-tight">{inv.project_name}</h1>
      <p className="text-sm text-[#6c6a62]">{inv.invited_by_name}님이 <b>{inv.email}</b> 주소로 {ROLE_LABEL[inv.role]} 멤버 초대를 보냈어요.</p>
    </div>
  );

  // 로그인했으면 수락만 남는다. 다른 이메일 계정이면 서버가 거절하고 그 이유를 보여 준다
  if (auth.isAuthenticated) {
    return (
      <div className={`${card} mx-auto grid max-w-lg justify-items-center gap-4`} data-rise>
        {head}
        <p className="text-sm text-[#6c6a62]">지금 <b>{auth.user?.name}</b>님으로 로그인되어 있어요.</p>
        {accept.isError && <p role="alert" className="text-center text-sm font-semibold text-[#c2410c]">{apiError(accept.error)}</p>}
        <Btn
          variant="primary"
          size="lg"
          disabled={accept.isPending}
          onClick={() => accept.mutate(token, { onSuccess: (r) => router.push(`/maemusae/projects/${r.project_id}`) })}
        >
          {accept.isPending ? "수락하는 중…" : "초대 수락"}
        </Btn>
      </div>
    );
  }

  return (
    <div className="mx-auto grid w-full max-w-md gap-6" data-rise>
      <div className={card}>{head}</div>
      <div className={card}>
        {inv.account_exists ? (
          <>
            <p className="mb-4 text-sm text-[#6c6a62]">{inv.email} 계정으로 로그인하면 초대를 수락할 수 있어요.</p>
            <AuthPanel mode="login" />
          </>
        ) : proof.data ? (
          <>
            <p className="mb-4 text-sm text-[#6c6a62]">가입하면 바로 초대를 수락할 수 있어요.</p>
            <AuthPanel mode="signup" presetEmail={{ email: proof.data.email, token: proof.data.email_verification_token }} />
          </>
        ) : proof.isError ? (
          <p role="alert" className="text-sm font-semibold text-[#c2410c]">{apiError(proof.error)}</p>
        ) : (
          <div className="h-40" aria-busy />
        )}
      </div>
    </div>
  );
}
