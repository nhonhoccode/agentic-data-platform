import { Globe, ExternalLink, AlertTriangle, Compass, KeyRound } from "lucide-react";
import type { WebSearchPayload } from "@/lib/api";

interface WebSearchResultsProps {
  webSearch: WebSearchPayload;
  onRetryWithForceSearch?: (query: string) => void;
  onTurnOnToggle?: (query: string) => void;
  /** True if the current user has the `web_search` feature granted. */
  webSearchAllowed?: boolean;
}

export function WebSearchResults({
  webSearch,
  onRetryWithForceSearch,
  onTurnOnToggle,
  webSearchAllowed = true,
}: WebSearchResultsProps) {
  if (webSearch.error) {
    const err = webSearch.error;
    const reason = webSearch.reason ?? "";

    // 1) Out-of-domain — offer "Vẫn tra cứu Internet" CTA that re-runs the
    // same query with force_web_search=true. Hidden when the user doesn't
    // have permission (replaced with "contact admin" hint).
    if (err === "out_of_domain") {
      return (
        <div className="flex flex-col gap-2 rounded-md border-2 border-black bg-yellow-100 p-3 text-xs text-black neo-shadow-sm">
          <div className="flex items-start gap-2">
            <Compass className="h-4 w-4 flex-shrink-0" strokeWidth={3} />
            <div>
              <div className="font-bold uppercase">Câu hỏi ngoài phạm vi Olist</div>
              <div className="mt-0.5">
                Trợ lý mặc định chỉ tra cứu trong domain e-commerce / data.
                {webSearchAllowed
                  ? " Nếu anh muốn vẫn search trên Internet cho câu này, bấm bên dưới."
                  : " Liên hệ admin để được cấp quyền dùng web search."}
              </div>
            </div>
          </div>
          {webSearchAllowed && onRetryWithForceSearch && (
            <button
              onClick={() => onRetryWithForceSearch(webSearch.query)}
              className="inline-flex w-fit items-center gap-1.5 rounded-md border-2 border-black bg-pink-400 px-3 py-1.5 text-[11px] font-black uppercase neo-shadow-sm neo-press"
            >
              <Globe className="h-3.5 w-3.5" strokeWidth={3} />
              Vẫn tra cứu Internet
            </button>
          )}
        </div>
      );
    }

    // 2) Toggle off (user or admin) — show the toggle CTA.
    if (err === "disabled" || err === "blocked") {
      const isToggleOffUser = (reason || "").toLowerCase().includes("toggle_off_user") || reason === "toggle_off_user";
      const isTavilyMissing = (reason || "").toUpperCase().includes("TAVILY_API_KEY");
      // If toggle is off because permission missing, surface the admin-approval
      // hint instead of suggesting the user toggle it on.
      const isPermissionDenied = isToggleOffUser && !webSearchAllowed;
      return (
        <div className="flex flex-col gap-2 rounded-md border-2 border-black bg-yellow-100 p-3 text-xs text-black neo-shadow-sm">
          <div className="flex items-start gap-2">
            {isTavilyMissing ? (
              <KeyRound className="h-4 w-4 flex-shrink-0" strokeWidth={3} />
            ) : (
              <Globe className="h-4 w-4 flex-shrink-0" strokeWidth={3} />
            )}
            <div>
              <div className="font-bold uppercase">
                {isTavilyMissing
                  ? "Web search chưa có API key"
                  : isPermissionDenied
                    ? "Tính năng cần admin phê duyệt"
                    : isToggleOffUser
                      ? "Web search đang tắt"
                      : "Web search bị quản trị viên tắt"}
              </div>
              <div className="mt-0.5">
                {isTavilyMissing ? (
                  <>
                    Điền <code>TAVILY_API_KEY</code> vào <code>.env</code> rồi recreate
                    api để dùng.
                  </>
                ) : isPermissionDenied ? (
                  <>Tài khoản của anh ở tier <b>basic</b> — chưa được cấp quyền web search. Hãy liên hệ admin để được nâng tier.</>
                ) : isToggleOffUser ? (
                  <>Bật công tắc Web search ở góc khung soạn tin để cho phép tra Internet.</>
                ) : (
                  <>
                    Admin đã tắt <code>WEB_SEARCH_ENABLED</code>. Liên hệ admin để
                    bật lại.
                  </>
                )}
              </div>
            </div>
          </div>
          {isToggleOffUser && !isPermissionDenied && onTurnOnToggle && (
            <button
              onClick={() => onTurnOnToggle(webSearch.query)}
              className="inline-flex w-fit items-center gap-1.5 rounded-md border-2 border-black bg-lime-300 px-3 py-1.5 text-[11px] font-black uppercase neo-shadow-sm neo-press"
            >
              <Globe className="h-3.5 w-3.5" strokeWidth={3} />
              Bật & hỏi lại
            </button>
          )}
        </div>
      );
    }

    // 3) Other error (Tavily HTTP / parse) — generic.
    return (
      <div className="flex items-start gap-2 rounded-md border-2 border-black bg-orange-300 p-3 text-xs text-black neo-shadow-sm">
        <AlertTriangle className="h-4 w-4 flex-shrink-0" strokeWidth={3} />
        <div>
          <div className="font-bold uppercase">Web search lỗi</div>
          <div className="mt-0.5">{reason || err}</div>
        </div>
      </div>
    );
  }

  if (!webSearch.results || webSearch.results.length === 0) {
    return (
      <div className="rounded-md border-2 border-black bg-white p-3 text-xs neo-shadow-sm">
        <div className="flex items-center gap-2 font-bold uppercase">
          <Globe className="h-4 w-4" strokeWidth={3} />
          Web search
        </div>
        <div className="mt-1 text-zinc-600">Không có kết quả nào cho “{webSearch.query}”.</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border-2 border-black bg-white p-3 neo-shadow-sm">
      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-tight">
        <Globe className="h-4 w-4" strokeWidth={3} />
        Web search ({webSearch.count} kết quả)
      </div>

      {webSearch.answer && (
        <div className="rounded-sm border-2 border-black bg-yellow-100 p-2 text-xs">
          <div className="font-bold uppercase">Tóm tắt từ Tavily</div>
          <div className="mt-1 leading-relaxed">{webSearch.answer}</div>
        </div>
      )}

      <ul className="flex flex-col gap-2">
        {webSearch.results.map((r, i) => {
          let host = r.url;
          try {
            host = new URL(r.url).host;
          } catch {
            host = r.url;
          }
          return (
            <li
              key={`${r.url}-${i}`}
              className="rounded-sm border-2 border-black bg-white p-2 text-xs neo-shadow-sm"
            >
              <a
                href={r.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group block"
              >
                <div className="flex items-center gap-1.5 text-[11px] uppercase text-zinc-500">
                  <span className="truncate">{host}</span>
                  <ExternalLink className="h-3 w-3 flex-shrink-0" strokeWidth={3} />
                </div>
                <div className="mt-0.5 font-bold leading-tight group-hover:underline">
                  {r.title || r.url}
                </div>
                {r.snippet && (
                  <div className="mt-1 leading-snug text-zinc-700">{r.snippet}</div>
                )}
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
