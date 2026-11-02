"use client";

import { ArrowLeft, Mail } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { NativeSelect } from "@/components/ui/native-select";
import { UserAvatar } from "@/meerkit";

import { ConfirmDialog, InviteDialog } from "../../../_components/dialogs";
import { ProjectGuard } from "../../../_components/ProjectGuard";
import { Btn, PageHead, Pill, card, fmtDate } from "../../../_components/ui";
import { apiError, type ApiInvitation, type ApiMember } from "../../../_lib/api";
import { ROLE_LABEL } from "../../../_lib/labels";
import { useChangeRole, useInvitations, useInvite, useMembers, useRemoveMember, useRevokeInvitation } from "../../../_lib/queries";
import type { ProjectRole } from "../../../_lib/types";

type Removing = { kind: "member"; item: ApiMember } | { kind: "invite"; item: ApiInvitation };

export default function MembersPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <ProjectGuard projectId={id} need="admin">
      {({ project }) => <MembersBody id={id} projectName={project.name} />}
    </ProjectGuard>
  );
}

function MembersBody({ id, projectName }: { id: string; projectName: string }) {
  const { data: members = [] } = useMembers(id);
  const { data: invitations = [] } = useInvitations(id, true);
  const invite = useInvite(id);
  const changeRole = useChangeRole(id);
  const removeMember = useRemoveMember(id);
  const revoke = useRevokeInvitation(id);
  const [inviting, setInviting] = useState(false);
  // 닫는 동안(사라지는 애니메이션)에도 제목과 내용이 그대로 보이도록, 대상은 지우지 않고 열림 여부만 따로 둔다
  const [removing, setRemoving] = useState<Removing | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const askRemove = (r: Removing) => {
    setRemoving(r);
    setConfirmOpen(true);
  };

  const sorted = [...members].sort((a, b) => (a.role === b.role ? a.name.localeCompare(b.name, "ko") : a.role === "ADMIN" ? -1 : 1));
  const item = `${card} flex flex-wrap items-center gap-x-5 gap-y-3 p-4`;

  return (
    <div className="grid gap-10">
      <PageHead eyebrow={projectName} title="멤버 권한 관리">
        <Btn variant="primary" onClick={() => setInviting(true)}>+ 멤버 초대</Btn>
      </PageHead>

      <div className="-mt-4 grid gap-3" data-rise>
        <p className="max-w-2xl text-sm leading-relaxed text-[#6c6a62]">관리자는 요구사항을 확정하고 멤버를 관리해요. 일반 멤버는 확정 외의 모든 작업을 할 수 있어요.</p>
        <Link href={`/projects/${id}`} className="inline-flex w-fit items-center gap-1.5 rounded-full border-2 border-[#111] bg-white px-3.5 py-1.5 text-[13px] font-semibold shadow-[3px_3px_0_#111] transition-[transform,box-shadow] duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)] hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[5px_5px_0_#111]">
          <ArrowLeft aria-hidden className="size-4" /> 프로젝트로 돌아가기
        </Link>
      </div>

      <section aria-labelledby="member-list" className="grid gap-4" data-rise>
        <h2 id="member-list" className="text-xl font-extrabold tracking-tight">멤버 {members.length}명</h2>
        <ul className="grid gap-4">
          {sorted.map((m) => (
            <li key={`m-${m.id}`} className={item}>
              <UserAvatar user={{ name: m.name, nickname: null, avatar_url: null }} size="lg" className="size-14 border-2 border-[#111] text-lg" />
              <div className="min-w-0 flex-1 basis-48">
                <p className="flex min-w-0 items-center gap-2">
                  <Pill tone={m.role === "ADMIN" ? "orange" : "plain"} className="shrink-0 px-2 py-0.5 text-[11px]">{ROLE_LABEL[m.role]}</Pill>
                  <span className="truncate text-base font-extrabold">{m.name}</span>
                </p>
                <p className="mt-1 truncate text-xs text-[#6c6a62]">@{m.user_id} · {fmtDate(m.joined_at)} 합류</p>
              </div>
              <NativeSelect
                aria-label={`${m.name} 권한`}
                value={m.role}
                disabled={changeRole.isPending}
                onChange={(e) => {
                  const role = e.target.value as ProjectRole;
                  changeRole.mutate(
                    { memberId: m.id, role },
                    { onSuccess: () => toast.success(`${m.name}님을 ${ROLE_LABEL[role]}(으)로 바꿨어요.`), onError: (err) => toast.error(apiError(err)) },
                  );
                }}
                className="w-28 rounded-full border-2 border-[#111]"
              >
                <option value="ADMIN">관리자</option>
                <option value="MEMBER">일반</option>
              </NativeSelect>
              <Btn size="sm" variant="ghost" onClick={() => askRemove({ kind: "member", item: m })}>내보내기</Btn>
            </li>
          ))}
        </ul>
      </section>

      {invitations.length > 0 && (
        <section aria-labelledby="invite-list" className="grid gap-4" data-rise>
          <h2 id="invite-list" className="text-xl font-extrabold tracking-tight">초대 대기 {invitations.length}건</h2>
          <ul className="grid gap-4">
            {invitations.map((inv) => (
              <li key={`i-${inv.id}`} className={`${item} border-dashed bg-[#fbfcdc] shadow-none`}>
                <span aria-hidden className="grid size-14 shrink-0 place-items-center rounded-full border-2 border-dashed border-[#111] bg-white"><Mail className="size-5" /></span>
                <div className="min-w-0 flex-1 basis-48">
                  <p className="flex min-w-0 items-center gap-2">
                    <Pill tone="plain" className="shrink-0 px-2 py-0.5 text-[11px]">{ROLE_LABEL[inv.role]}</Pill>
                    <span className="truncate text-base font-extrabold">{inv.email}</span>
                  </p>
                  <p className="mt-1"><Pill tone="yellow" className="px-2 py-0.5 text-[11px]">초대 대기 · {fmtDate(inv.expires_at)}까지</Pill></p>
                </div>
                <Btn size="sm" variant="ghost" onClick={() => askRemove({ kind: "invite", item: inv })}>초대 취소</Btn>
              </li>
            ))}
          </ul>
        </section>
      )}

      <InviteDialog
        open={inviting}
        onOpenChange={setInviting}
        onInvite={async (email) => {
          try {
            await invite.mutateAsync(email);
            toast.success("초대장을 보냈어요. 7일 안에 수락해야 해요.");
            return null;
          } catch (e) {
            return apiError(e, "초대장을 보내지 못했어요.");
          }
        }}
      />
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={removing?.kind === "invite" ? "초대를 취소할까요?" : "멤버를 내보낼까요?"}
        body={removing ? (removing.kind === "invite" ? removing.item.email : `${removing.item.name}(${removing.item.user_id})`) : ""}
        confirmLabel={removing?.kind === "invite" ? "초대 취소" : "내보내기"}
        danger
        onConfirm={() => {
          if (!removing) return;
          const done = { onSuccess: () => toast.success("처리했어요."), onError: (err: unknown) => toast.error(apiError(err)) };
          if (removing.kind === "invite") revoke.mutate(removing.item.id, done);
          else removeMember.mutate(removing.item.id, done);
          setConfirmOpen(false);
        }}
      />
    </div>
  );
}
