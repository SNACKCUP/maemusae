"use client";

import { useRef } from "react";

import { cn } from "@/lib/utils";

import { useReveal } from "../_lib/motion";
import { Btn, Pill, card } from "../_components/ui";

const STEPS = [
  { id: "project", no: "01", title: "프로젝트 만들기", body: "프로젝트는 요구사항 정리를 담는 작업 공간이에요. 고객 한 곳, 또는 개발 건 하나에 프로젝트 하나를 만드는 걸 추천해요.", points: ["상단 메뉴의 “프로젝트”로 이동해 “+ 프로젝트 등록”을 눌러요.", "프로젝트 이름과 시작일·종료일을 적어요.", "함께할 팀원의 이메일을 미리 적어 두면 만들어지면서 초대장이 같이 가요. 나중에 추가해도 괜찮아요.", "등록하면 프로젝트 화면으로 바로 이동해요. 만든 사람이 관리자가 됩니다."], tip: "프로젝트 화면에는 요구사항정의서 · 기능정의서 · 중간보고서 세 문서와 멤버가 모여 있어요. 지금은 요구사항정의서부터 만들 수 있어요.", mock: "project" },
  { id: "upload", no: "02", title: "문서 올리고 정리 요청하기", body: "요구사항정의서를 열면 문서를 올리는 입력 칸이 있어요. 고객이 보낸 자료를 그대로 올려도 돼요.", points: ["프로젝트 화면에서 “요구사항정의서”의 “열기”를 눌러요.", "고객 요청서, 회의 메모처럼 정리할 문서를 올려요. 파일 없이 내용을 직접 적어도 돼요.", "어떤 방향으로 정리하면 좋을지 한 줄 적어요. (예: “결제와 주문 중심으로 정리해 줘”)", "정리를 요청하면 AI가 문서를 읽고 상태가 “AI 분석 중”으로 바뀌었다가, 끝나면 “확정 대기”가 돼요."], tip: "방향을 구체적으로 적을수록 후보가 원하는 쪽으로 모여요. 모호하면 나중에 다시 분류할 수 있어요.", mock: "upload" },
  { id: "review", no: "03", title: "후보 살펴보고 고치기", body: "분석이 끝나면 화면이 둘로 나뉘어요. 왼쪽은 후보 목록, 오른쪽은 고른 후보의 상세예요. 확정 전까지 얼마든지 고칠 수 있어요.", points: ["왼쪽 목록에서 후보를 눌러 오른쪽 상세를 봐요. 후보마다 코드(REQ-001)와 구분(기능/비기능), 우선순위가 붙어 있어요.", "상세에서 이름, 구분, 우선순위, 설명을 고쳐요. “문서에서 찾은 근거”는 AI가 어느 문장을 보고 만들었는지 알려 줘요.", "필요 없는 후보는 왼쪽 체크를 해제해요. 체크된 후보만 정의서에 들어가요.", "빠진 요구사항은 “+ 직접 추가”로 넣어요.", "목록이 길면 구분, 우선순위, 체크 여부로 거르거나 코드·이름으로 검색해요. “확인 필요만”을 켜면 질문이 남은 후보만 보여요."], tip: "“확인 필요”는 AI가 판단하기 어려워 남긴 질문이에요. 후보를 눌러 답을 적고 아래 “다시 분류”를 누르면 답이 반영돼요.", mock: "review" },
  { id: "notes", no: "04", title: "새로 받은 내용 더하기", body: "고객에게 추가 답변을 받았거나 회의에서 내용이 바뀌었나요? 화면 아래 입력 칸에 적어 두면 돼요.", points: ["아래 “입력한 내용” 칸에 새로 받은 내용이나 AI 질문에 대한 답을 적어요. 필요하면 파일도 붙여요.", "“다시 분류”를 누르면 입력한 내용이 후보에 반영돼요.", "입력한 내용 목록에서 항목을 누르면 관련된 요구사항으로 이동해요. 최신순·오래된순, 작성자별로 모아 볼 수도 있어요."], tip: "누가 어떤 내용을 적었는지 남으니, 나중에 “이 요구사항이 왜 바뀌었지?”를 추적하기 좋아요.", mock: "notes" },
  { id: "confirm", no: "05", title: "관리자가 확정하기", body: "후보를 다 다듬었다면 확정할 차례예요. 확정은 프로젝트 관리자만 할 수 있어요.", points: ["화면 위의 “선택한 N개 · 확인이 필요한 질문 N개”로 남은 일을 확인해요.", "관리자가 “요구사항 확정”을 누르고 확인 창에서 한 번 더 확인해요.", "확정되면 상태가 “확정됨”으로 바뀌고 요구사항정의서가 만들어져요. 확정한 사람과 날짜가 함께 기록돼요.", "작업 도중에는 “임시 저장”으로 저장해 두고 나중에 이어서 해도 돼요."], tip: "체크된 후보가 하나도 없으면 “요구사항 확정” 버튼이 눌리지 않아요. 일반 멤버에게는 “확정은 관리자만 할 수 있어요”라고 보여요.", mock: "confirm" },
  { id: "members", no: "06", title: "멤버 초대하고 권한 나누기", body: "프로젝트는 혼자보다 함께할 때 좋아요. 멤버를 초대하고 맡은 일을 나눠 보세요.", points: ["프로젝트 화면의 “멤버 권한 관리”로 들어가 “+ 멤버 초대”를 눌러요.", "초대할 사람의 이메일을 적어 보내요. 초대는 7일 안에 수락해야 하고, 수락 전에는 “초대 대기”로 보여요.", "멤버 옆 선택창에서 관리자와 일반 권한을 바꿀 수 있어요.", "잘못 초대했거나 더 함께하지 않는 멤버는 “초대 취소”, “내보내기”로 정리해요."], tip: "관리자는 요구사항 확정과 멤버 관리를, 일반 멤버는 확정을 뺀 모든 작업(문서 올리기, 후보 고치기, 입력한 내용 더하기)을 할 수 있어요.", mock: "members" },
  { id: "export", no: "07", title: "내보내고 공유하기", body: "확정한 정의서는 표로 정리되어 있어서 바로 내보낼 수 있어요.", points: ["프로젝트 화면에서 확정된 요구사항정의서를 열어요.", "위쪽의 “Excel 받기” 또는 “PDF로 저장”을 눌러요.", "정의서 위에는 종류, 확정일, 최종 확정인, 요구사항 개수가 정리돼 있어요.", "내용을 고치고 다시 확정하면 새 판(v2, v3…)이 쌓여요. “수정 이력”에서 이전 판을 볼 수 있어요."], tip: "고객과 공유할 때는 PDF가, 항목을 더 다듬을 때는 Excel이 편해요.", mock: "export" },
] as const;

function Mock({ kind }: { kind: (typeof STEPS)[number]["mock"] }) {
  const base = "grid content-center gap-3 self-center rounded-2xl border-2 border-[#111] bg-[#f6f6f3] p-5";
  if (kind === "project") return (
    <div className={base} aria-hidden>
      <span className="text-xs font-bold text-[#6c6a62]">프로젝트 이름</span>
      <span className="rounded-full border-2 border-[#111] bg-white px-4 py-2 text-sm">쇼핑몰 리뉴얼</span>
      <span className="w-fit rounded-full border-2 border-[#111] bg-[#ff5a14] px-4 py-1.5 text-xs font-bold text-white shadow-[2px_2px_0_#111]">+ 프로젝트 등록</span>
    </div>
  );
  if (kind === "upload") return (
    <div className={base} aria-hidden>
      <span className="grid h-20 place-items-center rounded-xl border-2 border-dashed border-[#111] bg-white text-xs font-semibold">쇼핑몰_요청서.docx</span>
      <span className="rounded-full border-2 border-[#111] bg-white px-4 py-2 text-xs text-[#6c6a62]">결제와 주문 중심으로 정리해 줘</span>
    </div>
  );
  if (kind === "review") return (
    <div className={base} aria-hidden>
      {[["REQ-001", "비회원도 장바구니에 담을 수 있다", false], ["REQ-002", "결제 응답은 3초 이내여야 한다", true]].map(([c, n, q]) => (
        <div key={String(c)} className={cn("flex flex-wrap items-center gap-2 rounded-xl border-2 border-[#111] bg-white px-3 py-2 text-xs", !q && "bg-[#f2f69a]")}>
          <span className="text-[#6c6a62]">{c}</span><span className="font-bold">{n}</span>{q && <Pill tone="orange" className="px-2 py-0 text-[10px]">확인 필요</Pill>}
        </div>
      ))}
    </div>
  );
  if (kind === "notes") return (
    <div className={base} aria-hidden>
      <span className="rounded-xl border-2 border-[#111] bg-white px-3 py-2 text-xs text-[#6c6a62]">고객에게 새로 받은 내용을 적어요</span>
      <span className="w-fit rounded-full border-2 border-[#111] bg-[#111] px-4 py-1.5 text-xs font-bold text-white">다시 분류</span>
    </div>
  );
  if (kind === "confirm") return (
    <div className={base} aria-hidden>
      <div className="flex items-center gap-2"><Pill tone="yellow">확정 대기</Pill><span className="text-xs text-[#6c6a62]">선택한 8개</span></div>
      <span className="w-fit rounded-full border-2 border-[#111] bg-[#ff5a14] px-4 py-1.5 text-xs font-bold text-white shadow-[2px_2px_0_#111]">요구사항 확정</span>
    </div>
  );
  if (kind === "members") return (
    <div className={base} aria-hidden>
      {[["김다나", "관리자"], ["이작성", "일반"]].map(([n, r]) => (
        <div key={n} className="flex items-center justify-between rounded-xl border-2 border-[#111] bg-white px-3 py-2 text-xs"><span className="font-bold">{n}</span><Pill>{r}</Pill></div>
      ))}
    </div>
  );
  return (
    <div className={base} aria-hidden>
      <div className="flex gap-2"><span className="rounded-full border-2 border-[#111] bg-white px-3 py-1 text-xs font-bold">Excel 받기</span><span className="rounded-full border-2 border-[#111] bg-white px-3 py-1 text-xs font-bold">PDF로 저장</span></div>
      <span className="text-xs text-[#6c6a62]">확정일 · 최종 확정인 · 요구사항 개수</span>
    </div>
  );
}


const STATUS = [
  { label: "시작 전", tone: "plain", body: "아직 문서를 올리지 않았어요." },
  { label: "AI 분석 중", tone: "yellow", body: "AI가 문서에서 후보를 가려내고 있어요." },
  { label: "확정 대기", tone: "yellow", body: "후보가 준비됐어요. 팀이 다듬고 관리자가 확정하면 돼요." },
  { label: "확정 중", tone: "yellow", body: "관리자가 확정하고 정의서를 만드는 중이에요." },
  { label: "확정됨", tone: "dark", body: "정의서가 만들어졌어요. 내보내거나 이력을 볼 수 있어요." },
] as const;

const CAN: [string, boolean, boolean][] = [
  ["프로젝트 보기 · 문서 올리기", true, true],
  ["후보 고치기 · 직접 추가 · 입력한 내용 더하기", true, true],
  ["임시 저장 · 수정 이력 보기", true, true],
  ["Excel · PDF 내보내기", true, true],
  ["요구사항 확정", true, false],
  ["멤버 초대 · 권한 변경 · 내보내기", true, false],
];

const TERMS = [
  ["후보", "AI가 문서에서 뽑은 요구사항 초안이에요. 확정 전까지는 후보예요."],
  ["근거", "후보가 나온 문서 속 원래 문장이에요."],
  ["확인 필요", "AI가 판단하기 어려워 남긴 질문이 있는 후보예요."],
  ["다시 분류", "새로 적은 내용이나 답을 후보에 반영하는 기능이에요."],
  ["확정", "관리자가 후보를 정의서로 굳히는 일이에요. 한 번 하면 기록이 남아요."],
  ["수정 이력", "확정한 판들의 기록이에요. 고치고 다시 확정하면 새 판이 생겨요."],
];

const TROUBLE = [
  ["“요구사항 확정” 버튼이 안 눌려요", "체크된 후보가 하나도 없거나, 관리자가 아닌 계정일 수 있어요. 후보를 하나 이상 체크하고, 멤버 권한 관리에서 내 권한을 확인해 보세요."],
  ["초대받은 사람이 합류하지 못해요", "초대는 7일 안에 수락해야 해요. 기간이 지났다면 초대를 취소하고 다시 보내 주세요."],
  ["후보가 기대와 달라요", "정리 방향을 더 구체적으로 적고, 새로 받은 내용을 입력한 뒤 “다시 분류”를 눌러 보세요."],
  ["데이터를 처음 상태로 되돌리고 싶어요", "지금은 화면 확인용 예시 데이터로 동작해요. 화면 맨 아래 “데이터 초기화”를 누르면 처음 상태가 돼요."],
];

// 사용 가이드: 왼쪽 목차(큰 화면)와 여섯 단계. 각 단계에 화면 모양을 흉내 낸 그림을 붙였다.
export default function GuideView() {
  const root = useRef<HTMLElement>(null);
  useReveal(root);

  return (
    <article ref={root} className="mx-auto grid w-full max-w-[1100px] gap-16">
      <header className="grid gap-6 pt-4 sm:pt-10">
        <div data-hero><Pill tone="yellow" className="-rotate-2 shadow-[2px_2px_0_#111]">✦ Guide</Pill></div>
        <h1 data-hero className="text-[44px] leading-[1.05] tracking-[-0.05em] sm:text-[84px]">
          <span className="block font-light">처음이어도</span>
          <span className="block font-extrabold">일곱 단계면 끝</span>
        </h1>
        <p data-hero className="max-w-lg text-base leading-relaxed text-[#55534c]">프로젝트를 만들고 요구사항정의서를 확정해 내보내기까지, 순서대로 따라오세요.</p>
      </header>

      <div className="grid items-start gap-10 lg:grid-cols-[200px_1fr]">
        <nav aria-label="가이드 목차" className="lg:sticky lg:top-8">
          <ol className="flex flex-wrap gap-2 lg:grid">
            {STEPS.map((s) => (
              <li key={s.id}><a href={`#${s.id}`} className="inline-flex items-center gap-2 rounded-full border-2 border-transparent px-3 py-1.5 text-[13px] font-semibold transition-colors hover:border-[#111] hover:bg-[#f2f69a]"><span className="text-[#ff5a14]">{s.no}</span>{s.title}</a></li>
            ))}
          </ol>
        </nav>

        <div className="grid gap-8">
          {STEPS.map((s) => (
            <section key={s.id} id={s.id} data-reveal className={cn(card, "grid scroll-mt-8 gap-6 sm:p-8 md:grid-cols-[1.25fr_0.75fr]")}>
              <div className="grid content-start gap-4">
                <span className="grid size-11 place-items-center rounded-full border-2 border-[#111] bg-[#ff5a14] font-extrabold text-white">{s.no}</span>
                <h2 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{s.title}</h2>
                <p className="text-sm leading-relaxed text-[#55534c]">{s.body}</p>
                <ol className="grid gap-2.5 text-sm">
                  {s.points.map((pt, n) => (
                    <li key={pt} className="flex gap-3"><span aria-hidden className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border-2 border-[#111] bg-white text-[10px] font-extrabold">{n + 1}</span><span className="leading-relaxed">{pt}</span></li>
                  ))}
                </ol>
                <p className="rounded-xl border-2 border-dashed border-[#111] bg-[#f2f69a] px-4 py-3 text-[13px] font-medium">💡 {s.tip}</p>
              </div>
              <Mock kind={s.mock} />
            </section>
          ))}
        </div>
      </div>

      <section aria-label="문서 상태" className="grid gap-6">
        <div data-reveal className="grid gap-2"><p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">Status</p><h2 className="text-3xl tracking-[-0.04em] sm:text-5xl"><span className="font-light">지금 어디까지</span> <span className="font-extrabold">왔는지 보기</span></h2></div>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {STATUS.map((st) => (
            <li key={st.label} data-reveal className={cn(card, "grid content-start gap-3 p-5")}><Pill tone={st.tone} className="w-fit">{st.label}</Pill><p className="text-[13px] leading-relaxed text-[#55534c]">{st.body}</p></li>
          ))}
        </ul>
      </section>

      <section aria-label="권한별 할 수 있는 일" className="grid gap-6">
        <div data-reveal className="grid gap-2"><p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">Roles</p><h2 className="text-3xl tracking-[-0.04em] sm:text-5xl"><span className="font-light">권한별로</span> <span className="font-extrabold">할 수 있는 일</span></h2></div>
        <div data-reveal className={cn(card, "overflow-x-auto p-0")}>
          <table className="w-full min-w-[460px] text-left text-sm">
            <thead><tr className="border-b-2 border-[#111] bg-[#f6f6f3]"><th scope="col" className="px-6 py-4 font-extrabold">할 수 있는 일</th><th scope="col" className="px-6 py-4 font-extrabold">관리자</th><th scope="col" className="px-6 py-4 font-extrabold">일반</th></tr></thead>
            <tbody>
              {CAN.map(([n, a, b]) => (
                <tr key={n} className="border-b border-[#111]/15 last:border-0"><th scope="row" className="px-6 py-4 font-semibold">{n}</th><td className="px-6 py-4">{a ? "✓" : "—"}</td><td className={cn("px-6 py-4", !b && "text-[#6c6a62]")}>{b ? "✓" : "—"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-label="용어 사전" className="grid gap-6">
        <div data-reveal className="grid gap-2"><p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">Glossary</p><h2 className="text-3xl tracking-[-0.04em] sm:text-5xl"><span className="font-light">낯선 말은</span> <span className="font-extrabold">여기서 확인</span></h2></div>
        <dl className="grid gap-3 sm:grid-cols-2">
          {TERMS.map(([t, d]) => (
            <div key={t} data-reveal className={cn(card, "grid gap-1.5 p-5")}><dt className="text-base font-extrabold">{t}</dt><dd className="text-[13px] leading-relaxed text-[#55534c]">{d}</dd></div>
          ))}
        </dl>
      </section>

      <section aria-label="자주 막히는 곳" className="mx-auto grid w-full max-w-3xl gap-6">
        <div data-reveal className="grid gap-2 text-center"><p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[#6c6a62]">Troubleshooting</p><h2 className="text-3xl tracking-[-0.04em] sm:text-5xl"><span className="font-light">막혔다면</span> <span className="font-extrabold">여기를 보세요</span></h2></div>
        <div className="grid gap-4">
          {TROUBLE.map(([q, a]) => (
            <details key={q} data-reveal className="group rounded-[20px] border-2 border-[#111] bg-white px-6 py-4 shadow-[4px_4px_0_#111] open:bg-[#f2f69a]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-bold [&::-webkit-details-marker]:hidden">{q}<span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full border-2 border-[#111] bg-white text-lg leading-none transition-transform group-open:rotate-45">+</span></summary>
              <p className="pt-3 text-sm leading-relaxed text-[#55534c]">{a}</p>
            </details>
          ))}
        </div>
      </section>

      <section data-reveal className="grid gap-5 rounded-[32px] border-2 border-[#111] bg-[#111] px-6 py-14 text-center text-white sm:py-16">
        <h2 className="text-3xl tracking-[-0.04em] sm:text-5xl"><span className="font-light">이제 직접</span> <span className="font-extrabold">해 볼까요?</span></h2>
        <div className="flex justify-center"><Btn href="/maemusae/projects" variant="primary" size="lg">프로젝트 만들러 가기 →</Btn></div>
      </section>
    </article>
  );
}
