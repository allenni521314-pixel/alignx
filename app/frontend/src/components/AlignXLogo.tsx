import { cn } from "@/lib/utils";

interface AlignXLogoProps {
  className?: string;
  markClassName?: string;
  showWordmark?: boolean;
  wordmarkClassName?: string;
  variant?: "solid" | "light";
}

export function AlignXLogo({
  className,
  markClassName,
  showWordmark = false,
  wordmarkClassName,
  variant = "solid",
}: AlignXLogoProps) {
  const isLight = variant === "light";

  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div
        className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border",
          isLight
            ? "border-brand-200 bg-white text-brand-800"
            : "border-brand-700 bg-brand-800 text-white shadow-sm",
          markClassName
        )}
      >
        <svg
          viewBox="0 0 48 48"
          aria-hidden="true"
          className="h-[78%] w-[78%]"
          fill="none"
        >
          <circle cx="24" cy="24" r="18" stroke="currentColor" strokeWidth="3.2" />
          <path
            d="M7.4 23.8c6.2.6 9.8-4.2 16.7-3.4 7.5.9 10.5 5.2 16.5 4.1"
            stroke="currentColor"
            strokeWidth="3.1"
            strokeLinecap="round"
          />
          <path
            d="M7.7 30.4c6.9.9 11.1-4.9 18.5-4 6.2.8 9.4 4.3 14.1 3.7"
            stroke="currentColor"
            strokeWidth="3.1"
            strokeLinecap="round"
          />
          <path
            d="M8.9 17.2c5.5.4 9-2.8 15.2-2.2 7 .7 10.4 4.1 15.2 3.6"
            stroke="currentColor"
            strokeWidth="3.1"
            strokeLinecap="round"
          />
        </svg>
      </div>
      {showWordmark && (
        <div className="min-w-0">
          <div className={cn("truncate font-bold tracking-tight text-brand-900", wordmarkClassName)}>
            AlignX
          </div>
          <div className="mt-0.5 hidden text-[10px] font-semibold tracking-[0.28em] text-gold-600 sm:block">
            AI OPERATIONS
          </div>
        </div>
      )}
    </div>
  );
}
