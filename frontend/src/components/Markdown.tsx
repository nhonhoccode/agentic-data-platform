import { lazy, Suspense } from "react";

const MarkdownInner = lazy(() => import("./MarkdownInner"));

interface MarkdownProps {
  content: string;
}

export function Markdown({ content }: MarkdownProps) {
  return (
    <Suspense fallback={<span className="text-sm">{content}</span>}>
      <MarkdownInner content={content} />
    </Suspense>
  );
}
