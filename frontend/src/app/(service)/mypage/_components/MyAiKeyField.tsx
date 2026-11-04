"use client";

import { ApiKeyInput } from "@/meerkit";

import { apiError } from "../../_lib/api";
import { useDeleteMyAiKey, useMyAiKey, useSaveMyAiKey } from "../../_lib/queries";
import { Btn } from "../../_components/ui";

// 내 AI 키. 키는 서버에 암호화해 저장하고, 화면에는 끝 4자리만 보여 준다.
// 개인 키 사용이 켜져 있으면(in_use) 분석·다시 분류를 누른 사람의 키로 돌고, 꺼져 있으면 서비스 키로 돈다.
export function MyAiKeyField() {
  const { data, isLoading, isError } = useMyAiKey();
  const save = useSaveMyAiKey();
  const remove = useDeleteMyAiKey();

  if (isLoading) return <div className="h-11" aria-busy />;
  if (isError || !data) return <p className="text-sm text-[#6c6a62]">AI 키 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</p>;
  if (!data.storage_ready) return <p className="text-sm text-[#6c6a62]">AI 키 저장 기능을 준비하고 있어요.</p>;

  const hint = data.key_hint ? `…${data.key_hint}` : undefined;
  return (
    <div className="grid gap-3">
      {/* 저장한 끝자리가 바뀌면 입력 칸을 새로 그린다 (킷 부품은 처음 값만 읽음) */}
      <ApiKeyInput
        key={data.key_hint ?? "none"}
        initial={{ keyHint: hint }}
        onSave={async ({ apiKey }) => {
          if (!apiKey) return; // 새 키를 넣지 않으면 저장한 키를 그대로 씀
          try {
            await save.mutateAsync(apiKey);
          } catch (e) {
            throw new Error(apiError(e, "키를 저장하지 못했어요. 잠시 후 다시 시도해 주세요."));
          }
        }}
      />
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[#6c6a62]">
        <p>
          {data.in_use
            ? "요구사항 분석·다시 분류는 누른 사람의 키로 돌아요. 키가 없으면 분석을 시작할 수 없어요."
            : "지금은 서비스 키로 분석해요. 저장한 키는 개인 키 사용이 켜지면 쓰여요."}
        </p>
        {data.key_hint && (
          <Btn size="sm" variant="ghost" className="ml-auto" disabled={remove.isPending} onClick={() => remove.mutate()}>
            {remove.isPending ? "지우는 중…" : "키 지우기"}
          </Btn>
        )}
      </div>
      {remove.isError && <p role="alert" className="text-xs text-[#b3261e]">{apiError(remove.error, "키를 지우지 못했어요.")}</p>}
    </div>
  );
}
