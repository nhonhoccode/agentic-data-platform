import { Lightbulb, BarChart3, Database, BookOpen, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Suggestion {
  text: string;
  icon: React.ElementType;
  category: "kpi" | "sql" | "schema" | "definition" | "trend";
}

const SUGGESTIONS_GROUPS: Record<string, Suggestion[]> = {
  initial: [
    { text: "Cho tôi xem KPI tháng", icon: TrendingUp, category: "kpi" },
    { text: "Doanh thu theo danh mục", icon: BarChart3, category: "sql" },
    { text: "Tỷ lệ giao trễ theo tháng", icon: TrendingUp, category: "trend" },
    { text: "GMV nghĩa là gì?", icon: BookOpen, category: "definition" },
    { text: "Top 10 sản phẩm bán chạy", icon: BarChart3, category: "sql" },
    { text: "Schema bảng orders có gì?", icon: Database, category: "schema" },
  ],
  kpi: [
    { text: "Cho xem trend GMV 6 tháng gần nhất", icon: TrendingUp, category: "trend" },
    { text: "Tháng nào có doanh thu cao nhất?", icon: BarChart3, category: "kpi" },
    { text: "AOV trung bình quý 4/2018", icon: TrendingUp, category: "kpi" },
    { text: "Tỷ lệ giao thành công có tăng không?", icon: TrendingUp, category: "trend" },
  ],
  sql: [
    { text: "100 đơn hàng gần nhất", icon: Database, category: "sql" },
    { text: "Top 5 thành phố có nhiều khách hàng nhất", icon: BarChart3, category: "sql" },
    { text: "Phương thức thanh toán phổ biến nhất", icon: BarChart3, category: "sql" },
    { text: "AOV theo từng danh mục", icon: BarChart3, category: "sql" },
  ],
  trend: [
    { text: "So sánh doanh thu 2017 vs 2018", icon: TrendingUp, category: "trend" },
    { text: "Mùa nào bán chạy nhất?", icon: TrendingUp, category: "trend" },
    { text: "Doanh thu các category trong 12 tháng", icon: BarChart3, category: "trend" },
  ],
  definition: [
    { text: "AOV nghĩa là gì?", icon: BookOpen, category: "definition" },
    { text: "Delivery delay days được tính như thế nào?", icon: BookOpen, category: "definition" },
    { text: "Delivered order rate là gì?", icon: BookOpen, category: "definition" },
  ],
  schema: [
    { text: "Bảng nào có cột customer_id?", icon: Database, category: "schema" },
    { text: "Có những bảng marts nào?", icon: Database, category: "schema" },
    { text: "Cấu trúc bảng fct_orders ra sao?", icon: Database, category: "schema" },
  ],
};

interface SuggestedQuestionsProps {
  onPick: (text: string) => void;
  variant?: "initial" | "compact";
  intent?: string | null;
}

const CATEGORY_BY_INTENT: Record<string, string> = {
  kpi_summary: "kpi",
  sql_query: "sql",
  business_definition: "definition",
  schema_search: "schema",
};

export function SuggestedQuestions({ onPick, variant = "initial", intent }: SuggestedQuestionsProps) {
  const group = intent ? CATEGORY_BY_INTENT[intent] || "initial" : "initial";
  const items = SUGGESTIONS_GROUPS[group] ?? SUGGESTIONS_GROUPS.initial;

  if (variant === "compact") {
    return (
      <div className="flex flex-wrap gap-1.5">
        {items.slice(0, 4).map((s) => (
          <button
            key={s.text}
            onClick={() => onPick(s.text)}
            className="flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 text-xs text-primary hover:bg-primary/10 transition-colors"
          >
            <s.icon className="h-3 w-3" />
            <span>{s.text}</span>
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Lightbulb className="h-3.5 w-3.5" />
        <span>Gợi ý câu hỏi</span>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((s) => (
          <button
            key={s.text}
            onClick={() => onPick(s.text)}
            className={cn(
              "group flex items-start gap-2 rounded-xl border bg-card p-3 text-left text-sm transition-all",
              "hover:border-primary/40 hover:bg-primary/5 hover:shadow-sm",
            )}
          >
            <s.icon className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
            <span className="text-foreground/80 group-hover:text-foreground">{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
