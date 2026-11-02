"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { AuthPanel } from "@/meerkit";

import { card } from "../_components/ui";

export default function LoginPage() {
  const router = useRouter();
  return (
    <div className="mx-auto grid w-full max-w-md gap-6" data-rise>
      <div>
        <p className="mb-3 text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">매무새</p>
        <h1 className="text-[34px] leading-[1.1] tracking-[-0.03em]"><span className="font-extrabold">로그인</span></h1>
        <p className="mt-2 text-sm text-[#6c6a62]">아이디와 비밀번호를 입력하세요.</p>
      </div>
      <div className={card}>
        <AuthPanel mode="login" onSuccess={() => router.push("/maemusae/projects")} />
      </div>
      <p className="text-center text-sm text-[#6c6a62]">계정이 없으신가요? <Link href="/maemusae/signup" className="font-semibold text-[#111] underline underline-offset-4">회원가입</Link></p>
    </div>
  );
}
