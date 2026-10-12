export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" stroke="#D97757" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 6h18a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H12l-5 4v-4H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z" />
      <path d="M10 12.5h.01" />
      <path d="M18 12.5h.01" />
      <path d="M10.5 15.5c1.8 1.6 5.2 1.6 7 0" />
    </svg>
  );
}
