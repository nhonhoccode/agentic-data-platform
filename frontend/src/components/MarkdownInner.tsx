import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

interface MarkdownInnerProps {
  content: string;
}

export default function MarkdownInner({ content }: MarkdownInnerProps) {
  return (
    <div className="markdown-body text-sm">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code(props) {
            const { className, children, ...rest } = props;
            const match = /language-(\w+)/.exec(className || "");
            const codeText = String(children).replace(/\n$/, "");
            const inline = !codeText.includes("\n");
            if (inline) {
              return (
                <code className="rounded bg-muted px-1 py-0.5" {...rest}>
                  {children}
                </code>
              );
            }
            return (
              <SyntaxHighlighter
                style={oneDark as Record<string, React.CSSProperties>}
                language={match?.[1] ?? "text"}
                PreTag="div"
                customStyle={{ margin: 0, borderRadius: 8, fontSize: 12.5 }}
              >
                {codeText}
              </SyntaxHighlighter>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
