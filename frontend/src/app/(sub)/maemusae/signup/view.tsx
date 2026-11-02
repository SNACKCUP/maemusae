"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { AuthPanel } from "@/meerkit";

import { card } from "../_components/ui";

export default function SignupPage() {
  const router = useRouter();
  return (
    <div className="mx-auto grid w-full max-w-md gap-6" data-rise>
      <div>
        <p className="mb-3 text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">매무새</p>
        <h1 className="text-[34px] leading-[1.1] tracking-[-0.03em]"><span className="font-extrabold">회원가입</span></h1>
        <p className="mt-2 text-sm text-[#6c6a62]">정보를 입력해 계정을 만드세요.</p>
      </div>
      <div className={card}>
        <AuthPanel mode="signup" onSuccess={() => router.push("/maemusae/projects")} />
      </div>
      <p className="text-center text-sm text-[#6c6a62]">이미 계정이 있으신가요? <Link href="/maemusae/login" className="font-semibold text-[#111] underline underline-offset-4">로그인</Link></p>
    </div>
  );
}
