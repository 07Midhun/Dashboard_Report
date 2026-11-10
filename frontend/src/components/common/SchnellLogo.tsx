export function SchnellLogo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 select-none">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#18A6A0] to-[#0D7780] shadow-sm ring-1 ring-white/20">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          className="h-5 w-5 text-white"
          stroke="currentColor"
          strokeWidth="2.1"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" />
        </svg>
      </div>
      {!compact && (
        <div className="leading-tight">
          <div className="text-base font-extrabold tracking-wider text-white">SCHNELL</div>
          <div className="text-[10px] font-medium uppercase tracking-widest text-teal-100/80">
            Electrical Asset Reports
          </div>
        </div>
      )}
    </div>
  );
}

