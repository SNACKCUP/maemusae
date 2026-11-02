"use client";

import { ChevronDown, FolderKanban, LogOut, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";

import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { UserAvatar, isAdminUser, meerkitConfig, type User } from "@/meerkit";

import { Pill } from "./ui";

const item = "cursor-pointer gap-2.5 rounded-xl px-3 py-2.5 text-sm font-semibold text-[#111] focus:bg-[#f2f69a] focus:text-[#111] [&_svg]:size-4 [&_svg]:text-[#111]";

// 로그인한 사람의 프로필 버튼과 메뉴. 킷의 UserMenu와 하는 일은 같고, 매무새의 굵은 테두리·그림자 모양으로 그린다.
export function AccountMenu({ user, onLogout }: { user: User; onLogout: () => void }) {
  const name = user.nickname?.trim() || user.name;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="계정 메뉴"
          className="group flex items-center gap-2 rounded-full border-2 border-[#111] bg-white py-1 pl-1 pr-3 text-[13px] font-semibold shadow-[3px_3px_0_#111] outline-none transition-[transform,box-shadow] duration-150 hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[5px_5px_0_#111] focus-visible:ring-2 focus-visible:ring-[#ff5a14] focus-visible:ring-offset-2 data-[state=open]:bg-[#f2f69a]"
        >
          <UserAvatar user={user} size="md" className="border-2 border-[#111]" />
          <span className="max-w-[8rem] truncate">{name}</span>
          <ChevronDown className="size-3.5 transition-transform duration-200 group-data-[state=open]:rotate-180" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={10} className="w-72 rounded-[22px] border-2 border-[#111] bg-white p-2 text-[#111] shadow-[5px_5px_0_#111]">
        <div className="flex items-center gap-3 rounded-2xl bg-[#f6f6f3] p-3">
          <UserAvatar user={user} size="lg" className="border-2 border-[#111]" />
          <div className="min-w-0">
            <p className="truncate text-sm font-extrabold">{name}</p>
            <p className="truncate text-xs text-[#6c6a62]">{user.email}</p>
            {user.roles.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {user.roles.map((r) => <Pill key={r.id} tone="yellow" className="px-2 py-0.5 text-[10px]">{r.name}</Pill>)}
              </div>
            )}
          </div>
        </div>
        <DropdownMenuSeparator className="my-2 bg-[#111]/15" />
        <DropdownMenuItem asChild className={item}>
          <Link href={meerkitConfig.routes.me}><UserRound aria-hidden /> 내 정보</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild className={item}>
          <Link href="/projects"><FolderKanban aria-hidden /> 내 프로젝트</Link>
        </DropdownMenuItem>
        {isAdminUser(user) && (
          <DropdownMenuItem asChild className={item}>
            <Link href={meerkitConfig.routes.adminMembers}><ShieldCheck aria-hidden /> 멤버 관리</Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator className="my-2 bg-[#111]/15" />
        <DropdownMenuItem onSelect={onLogout} className={`${item} focus:bg-[#ffd2b8]`}>
          <LogOut aria-hidden /> 로그아웃
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
