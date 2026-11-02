import { notFound } from "next/navigation";

export const instant = false;

// /maemusae 아래의 없는 주소를 매무새 404 화면으로 보낸다
export default function CatchAll() {
  notFound();
}
