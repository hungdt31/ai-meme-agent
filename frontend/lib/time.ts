/** "vừa xong", "5 phút", "3 giờ", "2 ngày", rồi ngày tháng. */
export function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "vừa xong";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} phút`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} giờ`;
  if (seconds < 7 * 86400) return `${Math.floor(seconds / 86400)} ngày`;
  return new Date(iso).toLocaleDateString("vi-VN", { day: "numeric", month: "short" });
}
