import type { Metadata } from "next";

import { Btn } from "./_components/ui";

export const metadata: Metadata = { title: "페이지를 찾을 수 없어요", robots: { index: false, follow: false } };

export default function NotFound() {
  return (
    <section className="mx-auto grid max-w-xl justify-items-center gap-5 py-10 text-center">
      <p className="text-[120px] font-extrabold leading-none tracking-[-0.06em] sm:text-[160px]">4<span className="text-[#ff5a14]">0</span>4</p>
      <h1 className="text-2xl font-extrabold tracking-tight">찾으시는 페이지가 없어요</h1>
      <p className="text-sm leading-relaxed text-[#6c6a62]">주소가 바뀌었거나 없어진 페이지일 수 있어요.<br />프로젝트 목록에서 다시 시작해 보세요.</p>
      <div className="mt-2 flex gap-3">
        <Btn href="/maemusae" variant="outline">처음으로</Btn>
        <Btn href="/maemusae/projects" variant="primary">프로젝트 목록</Btn>
      </div>
    </section>
  );
}
