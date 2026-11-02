"use client";

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
  const [removing, setRemoving] = useState<Removing | null>(null);

  const row = "grid items-center gap-3 px-6 py-4 sm:grid-cols-[minmax(0,1.1fr)_minmax(0,1.6fr)_7rem_6rem]";

  return (
    <div className="grid gap-8">
      <PageHead eyebrow={projectName} title="멤버 권한 관리">
        <Btn variant="primary" onClick={() => setInviting(true)}>+ 멤버 초대</Btn>
      </PageHead>
      <p className="-mt-4 text-sm text-[#6c6a62]" data-rise>
        관리자는 요구사항을 확정하고 멤버를 관리해요. 일반 멤버는 확정 외의 모든 작업을 할 수 있어요. <Link href={`/maemusae/projects/${id}`} className="underline">프로젝트로 돌아가기</Link>
      </p>

      <ul className={`${card} grid gap-0 divide-y divide-[#111]/15 p-0`} data-rise>
        {members.map((m) => (
          <li key={`m-${m.id}`} className={row}>
            <span className="flex items-center gap-3">
              <UserAvatar user={{ name: m.name, nickname: null, avatar_url: null }} size="sm" />
              <span className="font-semibold">{m.name}</span>
            </span>
            <span className="text-sm text-[#6c6a62]">{m.user_id}</span>
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
            <Btn size="sm" variant="ghost" className="justify-self-end" onClick={() => setRemoving({ kind: "member", item: m })}>내보내기</Btn>
          </li>
        ))}
        {invitations.map((inv) => (
          <li key={`i-${inv.id}`} className={row}>
            <span className="flex items-center gap-3">
              <UserAvatar user={{ name: inv.email, nickname: null, avatar_url: null }} size="sm" />
              <span className="font-semibold">{inv.email.split("@")[0]}</span>
            </span>
            <span className="text-sm text-[#6c6a62]">
              {inv.email}
              <span className="mt-1 block"><Pill tone="yellow">초대 대기 · {fmtDate(inv.expires_at)}까지</Pill></span>
            </span>
            <span className="text-sm text-[#6c6a62]">{ROLE_LABEL[inv.role]}</span>
            <Btn size="sm" variant="ghost" className="justify-self-end" onClick={() => setRemoving({ kind: "invite", item: inv })}>초대 취소</Btn>
          </li>
        ))}
      </ul>

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
        open={!!removing}
        onOpenChange={(v) => !v && setRemoving(null)}
        title={removing?.kind === "invite" ? "초대를 취소할까요?" : "멤버를 내보낼까요?"}
        body={removing ? (removing.kind === "invite" ? removing.item.email : `${removing.item.name}(${removing.item.user_id})`) : ""}
        confirmLabel={removing?.kind === "invite" ? "초대 취소" : "내보내기"}
        danger
        onConfirm={() => {
          if (!removing) return;
          const done = { onSuccess: () => toast.success("처리했어요."), onError: (err: unknown) => toast.error(apiError(err)) };
          if (removing.kind === "invite") revoke.mutate(removing.item.id, done);
          else removeMember.mutate(removing.item.id, done);
          setRemoving(null);
        }}
      />
    </div>
  );
}
