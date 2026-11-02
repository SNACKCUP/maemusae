// 마지막으로 보던 후보. 여러 멤버가 같은 문서를 봐도 서로 덮이지 않게 서버가 아니라 사람별로 브라우저에 둔다.
// 저장소를 못 쓰는 환경(사생활 보호 창 등)에서도 화면은 그대로 동작해야 해서 읽기·쓰기를 모두 감싼다.

const key = (userId: number, docId: number) => `mms:lastViewed:${userId}:${docId}`;

export function readLastViewed(userId: number | undefined, docId: number): number | null {
  if (!userId) return null;
  try {
    const v = Number(window.localStorage.getItem(key(userId, docId)));
    return Number.isInteger(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

export function writeLastViewed(userId: number | undefined, docId: number, requirementId: number) {
  if (!userId) return;
  try {
    window.localStorage.setItem(key(userId, docId), String(requirementId));
  } catch {
    // 저장하지 못해도 다음에 첫 후보부터 보여 주면 된다
  }
}
