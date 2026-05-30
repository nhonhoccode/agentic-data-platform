import {
  Sparkles,
  Database,
  Search,
  BarChart3,
  Zap,
  Bot,
  ArrowRight,
  Github,
  CheckCircle2,
  Loader2,
  ChevronRight,
  MessageSquareText,
  Network,
  ShieldCheck,
} from "lucide-react";

interface LandingProps {
  onEnter: () => void;
}

const SOURCE_URL = "https://github.com/nhonhoccode/agentic-data-platform";

const TECH_BADGES = [
  "LangGraph",
  "FastAPI",
  "Postgres",
  "Qdrant",
  "Tavily",
  "Claude Haiku 4.5",
  "Plotly",
  "Next.js",
];

export function Landing({ onEnter }: LandingProps) {
  return (
    <div className="min-h-screen bg-white">
      <Header onEnter={onEnter} />
      <Hero onEnter={onEnter} />
      <Stats />
      <Pipeline />
      <Features />
      <TechStack />
      <Footer />
    </div>
  );
}

function Header({ onEnter }: { onEnter: () => void }) {
  return (
    <header className="sticky top-0 z-50 border-b-2 border-black bg-white/90 backdrop-blur supports-[backdrop-filter]:bg-white/70">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border-2 border-black bg-pink-400 neo-shadow-sm">
            <Sparkles className="h-5 w-5 text-black" strokeWidth={3} />
          </div>
          <span className="text-sm font-black uppercase tracking-tight">
            Olist · Agentic Data Platform
          </span>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={SOURCE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-white px-3 py-1.5 text-xs font-bold uppercase neo-shadow-sm neo-press"
          >
            <Github className="h-4 w-4" strokeWidth={3} />
            Source
          </a>
          <button
            onClick={onEnter}
            className="inline-flex items-center gap-1.5 rounded-md border-2 border-black bg-pink-400 px-4 py-1.5 text-xs font-bold uppercase neo-shadow-sm neo-press"
          >
            Đăng nhập
            <ArrowRight className="h-4 w-4" strokeWidth={3} />
          </button>
        </div>
      </div>
    </header>
  );
}

function Hero({ onEnter }: { onEnter: () => void }) {
  return (
    <section className="relative overflow-hidden border-b-2 border-black bg-gradient-to-b from-yellow-50 via-white to-white px-6 pb-24 pt-16 md:pt-20">
      <DecorativeGrid />
      <div className="relative mx-auto grid max-w-6xl items-center gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-12 xl:gap-16">
        <div className="flex flex-col items-start gap-6">
          <span className="inline-flex items-center gap-1.5 rounded-full border-2 border-black bg-lime-300 px-3 py-1 text-[11px] font-bold uppercase tracking-tight neo-shadow-sm">
            <Zap className="h-3 w-3" strokeWidth={3} />
            v2 · multi-agent loop + Tavily web search
          </span>
          <h1 className="text-4xl font-black uppercase leading-[1.05] tracking-tight md:text-5xl xl:text-6xl">
            Phân tích Olist
            <br />
            bằng câu hỏi
            <br />
            <span className="mt-2 inline-block bg-pink-300 px-3 pb-2 pt-1.5 border-2 border-black neo-shadow">
              tiếng Việt.
            </span>
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-zinc-700">
            LangGraph multi-agent tự chọn SQL · KPI · schema · biểu đồ · web
            search cho từng câu hỏi. Mỗi bước render live trong timeline để bạn
            thấy chính xác agent đang chạy tool gì, tại sao chọn câu SQL đó, dữ
            liệu lấy ở đâu.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={onEnter}
              className="group inline-flex items-center gap-2 rounded-md border-2 border-black bg-pink-400 px-6 py-3 text-sm font-black uppercase neo-shadow neo-press"
            >
              Bắt đầu chat
              <ArrowRight
                className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
                strokeWidth={3}
              />
            </button>
            <a
              href={SOURCE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-md border-2 border-black bg-white px-6 py-3 text-sm font-bold uppercase neo-shadow-sm neo-press"
            >
              <Github className="h-4 w-4" strokeWidth={3} />
              Xem source
            </a>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-2 text-xs font-medium text-zinc-600">
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-lime-600" strokeWidth={3} />
              99,441 đơn hàng
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-lime-600" strokeWidth={3} />
              40k+ vectors RAG
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-lime-600" strokeWidth={3} />
              SSE streaming
            </span>
          </div>
        </div>

        <div className="mx-auto w-full max-w-[440px] lg:mx-0 lg:ml-auto">
          <DemoMockup />
        </div>
      </div>
    </section>
  );
}

function DecorativeGrid() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 opacity-[0.04]"
      style={{
        backgroundImage:
          "linear-gradient(to right, #000 1px, transparent 1px), linear-gradient(to bottom, #000 1px, transparent 1px)",
        backgroundSize: "32px 32px",
      }}
    />
  );
}

function DemoMockup() {
  return (
    <div className="relative">
      <div
        aria-hidden
        className="absolute inset-0 -translate-x-2 translate-y-3 rounded-md border-2 border-black bg-pink-200"
      />
      <div className="relative overflow-hidden rounded-md border-2 border-black bg-white neo-shadow-lg">
        <div className="flex items-center gap-1.5 border-b-2 border-black bg-yellow-300 px-3 py-2">
          <span className="h-2.5 w-2.5 rounded-full border border-black bg-red-400" />
          <span className="h-2.5 w-2.5 rounded-full border border-black bg-yellow-400" />
          <span className="h-2.5 w-2.5 rounded-full border border-black bg-lime-400" />
          <span className="ml-2 text-[10px] font-bold uppercase tracking-tight">
            chat · olist agent
          </span>
        </div>
        <div className="flex flex-col gap-3 p-4">
          <div className="flex justify-end">
            <div className="max-w-[80%] rounded-md border-2 border-black bg-yellow-200 px-3 py-2 text-xs font-bold neo-shadow-sm">
              Tỷ lệ giao trễ theo tháng?
            </div>
          </div>

          <div className="flex flex-col gap-1 rounded-md border-2 border-black bg-white p-2.5 text-[11px] neo-shadow-sm">
            <div className="text-[9px] font-black uppercase tracking-tight">
              SQL agent
            </div>
            <TimelineRow
              icon={<CheckCircle2 className="h-3 w-3 text-lime-600" strokeWidth={3} />}
              label="Tra cứu schema (6 bảng)"
              elapsed="0.12s"
            />
            <TimelineRow
              icon={<CheckCircle2 className="h-3 w-3 text-lime-600" strokeWidth={3} />}
              label="Đã sinh SQL"
              elapsed="1.4s"
              detail="SELECT order_month, late_delivery_rate FROM serving…"
            />
            <TimelineRow
              icon={<CheckCircle2 className="h-3 w-3 text-lime-600" strokeWidth={3} />}
              label="Chạy SQL xong (23 dòng)"
              elapsed="0.04s"
            />
            <div className="mt-1 text-[9px] font-black uppercase tracking-tight">
              Viz agent
            </div>
            <TimelineRow
              icon={
                <Loader2
                  className="h-3 w-3 animate-spin text-pink-500"
                  strokeWidth={3}
                />
              }
              label="Vẽ line (23 điểm)…"
              elapsed="0.3s"
              active
            />
          </div>

          <SparkPreview />
        </div>
      </div>
    </div>
  );
}

function TimelineRow({
  icon,
  label,
  detail,
  elapsed,
  active,
}: {
  icon: React.ReactNode;
  label: string;
  detail?: string;
  elapsed?: string;
  active?: boolean;
}) {
  return (
    <div className={active ? "rounded-sm bg-pink-100 px-1 py-0.5" : ""}>
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="font-semibold">{label}</span>
        {elapsed && (
          <span className="ml-auto font-mono text-[9px] tabular-nums text-zinc-400">
            {elapsed}
          </span>
        )}
      </div>
      {detail && (
        <div className="ml-4 truncate font-mono text-[9px] italic text-zinc-500">
          {detail}
        </div>
      )}
    </div>
  );
}

function SparkPreview() {
  // A miniature sparkline so the mock card "feels" like a real chat reply.
  // 2016-09 (100%) and 2016-10 (0.75%) had sample-size-1/3 — dropping them so
  // the y-axis isn't dominated by an outlier and the trend is visible.
  const points = [
    2.93, 2.96, 4.56, 6.56, 2.99, 3.03, 2.79, 2.91, 4.39, 4.18, 12.4, 7.46,
    5.7, 14.13, 18.96, 4.5, 6.56, 1.16, 3.38, 6.19,
  ];
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const W = 280;
  const H = 64;
  const pad = 6;
  const step = W / (points.length - 1);
  const y = (p: number) => H - pad - ((p - min) / range) * (H - pad * 2);
  const pathPts = points.map((p, i) => `${i * step},${y(p)}`).join(" ");
  return (
    <div className="rounded-md border-2 border-black bg-white p-2 neo-shadow-sm">
      <div className="mb-1 flex items-center justify-between text-[9px] font-black uppercase tracking-tight">
        <span>late_delivery_rate theo order_month</span>
        <span className="font-mono text-zinc-400">{max.toFixed(1)}% peak</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none">
        <polyline
          points={pathPts}
          fill="none"
          stroke="#000"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {points.map((p, i) => (
          <circle
            key={i}
            cx={i * step}
            cy={y(p)}
            r="2"
            fill="#facc15"
            stroke="#000"
            strokeWidth="1"
          />
        ))}
      </svg>
    </div>
  );
}

function Stats() {
  const items = [
    { value: "99,441", label: "đơn hàng Olist", color: "bg-yellow-200" },
    { value: "23", label: "tool agent đang chạy", color: "bg-cyan-200" },
    { value: "<2s", label: "median trả lời", color: "bg-lime-200" },
    { value: "40k+", label: "vector schema/glossary", color: "bg-pink-200" },
  ];
  return (
    <section className="border-b-2 border-black bg-black px-6 py-14 text-white">
      <div className="mx-auto grid max-w-6xl gap-4 sm:grid-cols-2 md:grid-cols-4">
        {items.map((s) => (
          <div
            key={s.label}
            className={`flex flex-col gap-2 rounded-md border-2 border-black px-5 py-5 ${s.color} text-black neo-shadow`}
          >
            <div className="text-4xl font-black leading-none tracking-tight">
              {s.value}
            </div>
            <div className="text-[11px] font-bold uppercase leading-snug tracking-tight">
              {s.label}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Pipeline() {
  const steps = [
    {
      n: "01",
      title: "Classify intent",
      body: "Router phân loại câu hỏi (SQL / KPI / schema / web search / chitchat) trong dưới 50ms.",
      color: "bg-yellow-200",
    },
    {
      n: "02",
      title: "Multi-agent loop",
      body: "Manager-loop điều phối SQL · Viz · Analytic · Retrieval · Web search, có self-correction tối đa 3 lần.",
      color: "bg-cyan-200",
    },
    {
      n: "03",
      title: "Synthesize + stream",
      body: "Claude Haiku tổng hợp, stream từng token qua SSE. Kết quả kèm citation + biểu đồ tự render.",
      color: "bg-pink-200",
    },
  ];
  return (
    <section className="border-b-2 border-black bg-white px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-10 flex flex-col items-start gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full border-2 border-black bg-pink-300 px-3 py-1 text-[10px] font-bold uppercase neo-shadow-sm">
            <Network className="h-3 w-3" strokeWidth={3} />
            Pipeline
          </span>
          <h2 className="text-4xl font-black uppercase tracking-tight">
            3 bước từ câu hỏi → câu trả lời
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {steps.map((s, i) => (
            <div key={s.n} className="relative">
              <div className="rounded-md border-2 border-black bg-white p-5 neo-shadow">
                <div
                  className={`mb-3 inline-block rounded-md border-2 border-black px-2 py-0.5 text-[10px] font-black uppercase ${s.color} neo-shadow-sm`}
                >
                  Step {s.n}
                </div>
                <h3 className="text-lg font-black uppercase tracking-tight">
                  {s.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-700">
                  {s.body}
                </p>
              </div>
              {i < steps.length - 1 && (
                <ChevronRight
                  aria-hidden
                  className="absolute -right-3 top-1/2 hidden h-6 w-6 -translate-y-1/2 text-black md:block"
                  strokeWidth={3}
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Features() {
  const items = [
    {
      icon: <Database className="h-5 w-5" strokeWidth={3} />,
      color: "bg-cyan-300",
      title: "Hỏi SQL tự nhiên",
      body: "Agent sinh SQL từ câu hỏi tiếng Việt, chạy trên schema marts/serving với AST guardrail chỉ-đọc, self-correction tối đa 3 lần khi lỗi.",
    },
    {
      icon: <BarChart3 className="h-5 w-5" strokeWidth={3} />,
      color: "bg-lime-300",
      title: "Biểu đồ tự động",
      body: "Viz agent đọc kết quả query, tự chọn bar/line, validate spec qua self-correction loop và render Plotly inline ngay trong chat.",
    },
    {
      icon: <Search className="h-5 w-5" strokeWidth={3} />,
      color: "bg-pink-300",
      title: "Web search fallback",
      body: "Khi dataset không có dữ liệu (tin tức, giá hiện tại, sự kiện 2024+), agent tự gọi Tavily. Kết quả có citation kèm link nguồn.",
    },
    {
      icon: <MessageSquareText className="h-5 w-5" strokeWidth={3} />,
      color: "bg-yellow-300",
      title: "Timeline live",
      body: "Mỗi tool call hiện 1 dòng riêng (spinner → check), kèm SQL preview, row count, thời gian chạy. Theo dõi agent realtime như Claude Cowork.",
    },
    {
      icon: <ShieldCheck className="h-5 w-5" strokeWidth={3} />,
      color: "bg-orange-300",
      title: "Guardrail",
      body: "SQL chạy với role read-only, AST validation chặn DDL/DML, statement timeout 120s, row limit 500-5000 tùy rule.",
    },
    {
      icon: <Bot className="h-5 w-5" strokeWidth={3} />,
      color: "bg-violet-300",
      title: "Self-host LLM",
      body: "Hỗ trợ Gemini · DeepSeek · OpenRouter · Anthropic · 9router · vLLM Qwen — đổi provider chỉ bằng 1 biến env, không cần redeploy.",
    },
  ];
  return (
    <section className="border-b-2 border-black bg-yellow-50 px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-10 flex flex-col items-start gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full border-2 border-black bg-cyan-300 px-3 py-1 text-[10px] font-bold uppercase neo-shadow-sm">
            <Sparkles className="h-3 w-3" strokeWidth={3} />
            Features
          </span>
          <h2 className="text-4xl font-black uppercase tracking-tight">
            6 tính năng cốt lõi
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {items.map((f) => (
            <div
              key={f.title}
              className="group flex flex-col gap-3 rounded-md border-2 border-black bg-white p-5 neo-shadow transition-transform hover:-translate-y-0.5"
            >
              <div
                className={`inline-flex h-10 w-10 items-center justify-center rounded-md border-2 border-black ${f.color} neo-shadow-sm`}
              >
                {f.icon}
              </div>
              <h3 className="text-base font-black uppercase tracking-tight">
                {f.title}
              </h3>
              <p className="text-sm leading-relaxed text-zinc-700">{f.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function TechStack() {
  return (
    <section className="border-b-2 border-black bg-white px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex flex-col items-start gap-2">
          <span className="text-[10px] font-black uppercase tracking-tight text-zinc-500">
            Built with
          </span>
          <h2 className="text-2xl font-black uppercase tracking-tight">
            Tech stack
          </h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {TECH_BADGES.map((t) => (
            <span
              key={t}
              className="rounded-md border-2 border-black bg-white px-3 py-1.5 text-xs font-bold neo-shadow-sm"
            >
              {t}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t-2 border-black bg-black px-6 py-6 text-white">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-3 md:flex-row md:items-center">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-tight">
          <Sparkles className="h-4 w-4 text-pink-400" strokeWidth={3} />
          Olist Agentic Data Platform
        </div>
        <a
          href={SOURCE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-tight text-white hover:text-pink-300"
        >
          <Github className="h-3.5 w-3.5" strokeWidth={3} />
          github.com/nhonhoccode/agentic-data-platform
        </a>
      </div>
    </footer>
  );
}
