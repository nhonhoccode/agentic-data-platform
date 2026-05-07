import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, Square, Paperclip, Loader2 } from "lucide-react";
import { uploadFile } from "@/lib/api";

interface ComposerProps {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export function Composer({ busy, onSend, onStop }: ComposerProps) {
  const [text, setText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadInfo, setUploadInfo] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (!text.trim() || busy) return;
    onSend(text);
    setText("");
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadInfo(null);
    const result = await uploadFile(file);
    setUploading(false);
    if (result.ok) {
      setUploadInfo(`✓ Đã nạp ${result.rows_loaded} dòng vào ${result.table}`);
    } else {
      setUploadInfo(`✗ ${result.detail}`);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="border-t bg-background p-4">
      {uploadInfo && (
        <div className="mb-2 rounded-md bg-muted px-3 py-1.5 text-xs text-muted-foreground">{uploadInfo}</div>
      )}
      <div className="flex items-end gap-2">
        <input ref={fileInputRef} type="file" accept=".csv,.txt,.pdf" className="hidden" onChange={handleUpload} />
        <Button variant="outline" size="icon" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
          {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}
        </Button>

        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Hỏi về KPI, doanh thu, danh mục, schema..."
          className="min-h-[44px] flex-1 resize-none"
          rows={1}
        />

        {busy ? (
          <Button variant="destructive" size="icon" onClick={onStop}>
            <Square className="h-4 w-4" />
          </Button>
        ) : (
          <Button size="icon" onClick={handleSend} disabled={!text.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
