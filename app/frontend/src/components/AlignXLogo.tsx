import { cn } from "@/lib/utils";

interface AlignXLogoProps {
  className?: string;
  markClassName?: string;
  showWordmark?: boolean;
  wordmarkClassName?: string;
  variant?: "solid" | "light";
  tagline?: string;
}

export function AlignXLogo({
  className,
  markClassName,
  showWordmark = false,
  wordmarkClassName,
  variant = "solid",
  tagline: _tagline = "先验证 再投入",
}: AlignXLogoProps) {
  const logoSrc = variant === "light"
    ? "/brand/alignx-logo-wide-inverse.png"
    : "/brand/alignx-logo-wide.jpg";

  if (showWordmark) {
    return (
      <div className={cn("flex items-center", className)}>
        <img
          src={logoSrc}
          alt="准神 ALIGNX"
          className={cn("h-12 w-auto max-w-full object-contain", wordmarkClassName)}
        />
      </div>
    );
  }

  return (
    <div className={cn("flex items-center", className)}>
      <img
        src={logoSrc}
        alt="准神 ALIGNX"
        className={cn("h-9 w-auto max-w-full object-contain", markClassName)}
      />
    </div>
  );
}
