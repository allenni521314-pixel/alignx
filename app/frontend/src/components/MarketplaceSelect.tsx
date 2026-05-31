import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const MARKETPLACE_OPTIONS = [
  { value: "US", label: "美国站", flag: "🇺🇸", domain: "www.amazon.com", currency: "$" },
  { value: "JP", label: "日本站", flag: "🇯🇵", domain: "www.amazon.co.jp", currency: "¥" },
  { value: "DE", label: "德国站", flag: "🇩🇪", domain: "www.amazon.de", currency: "€" },
  { value: "UK", label: "英国站", flag: "🇬🇧", domain: "www.amazon.co.uk", currency: "£" },
  { value: "CA", label: "加拿大站", flag: "🇨🇦", domain: "www.amazon.ca", currency: "C$" },
] as const;

export const MARKETPLACE_BY_VALUE = MARKETPLACE_OPTIONS.reduce(
  (map, item) => ({ ...map, [item.value]: item }),
  {} as Record<string, (typeof MARKETPLACE_OPTIONS)[number]>
);

export function MarketplaceSelect({
  value,
  onChange,
  className = "",
  triggerClassName = "",
}: {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  triggerClassName?: string;
}) {
  return (
    <div className={className}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className={`bg-gray-50 border-gray-200 text-gray-900 ${triggerClassName}`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-white border-gray-200">
          {MARKETPLACE_OPTIONS.map((marketplace) => (
            <SelectItem key={marketplace.value} value={marketplace.value} className="text-gray-900 hover:bg-brand-50">
              <span className="mr-2">{marketplace.flag}</span>
              {marketplace.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
