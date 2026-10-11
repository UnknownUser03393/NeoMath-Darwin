"use client";

import { useState, type FormEvent } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

export type FileNameKind = "notebook" | "xdlt";
export type FileNameMode = "new" | "rename";

const KIND_SUFFIX: Record<FileNameKind, string> = {
  notebook: ".nm",
  xdlt: ".xdlt",
};

const KIND_LABEL: Record<FileNameKind, string> = {
  notebook: "推导",
  xdlt: "XDLT 文档",
};

interface FileNameDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: FileNameMode;
  kind: FileNameKind;
  /** Pre-filled base name (without suffix) for rename. */
  defaultValue?: string;
  /** Original file name being renamed — excluded from the duplicate check. */
  renameFrom?: string;
  /** File names (with suffix) already present in the workspace. */
  existing: string[];
  onSubmit: (name: string) => void;
}

/**
 * shadcn Dialog for naming a new or renamed workspace file. Replaces the
 * browser window.prompt: inline validation (blank / duplicate / illegal
 * characters), Enter to confirm, Escape to cancel.
 */
export function FileNameDialog({
  open,
  onOpenChange,
  mode,
  kind,
  defaultValue = "",
  renameFrom,
  existing,
  onSubmit,
}: FileNameDialogProps) {
  const suffix = KIND_SUFFIX[kind];
  const label = KIND_LABEL[kind];
  const isRename = mode === "rename";
  const [value, setValue] = useState(defaultValue);
  const [error, setError] = useState<string | null>(null);

  // Reset the field whenever the dialog reopens (derived-state update during
  // render, not an effect, so a fresh rename always starts from its file).
  const [lastOpen, setLastOpen] = useState(open);
  if (open !== lastOpen) {
    setLastOpen(open);
    if (open) {
      setValue(defaultValue);
      setError(null);
    }
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const clean = value.trim();
    if (!clean) {
      setError("文件名不能为空。");
      return;
    }
    if (/[\\/]/.test(clean) || clean === "." || clean === "..") {
      setError("文件名不能包含 / 或 \\，也不能是 . 或 ..。");
      return;
    }
    const base = clean.replace(/\.(nm|xdlt)$/, "");
    const fileName = `${base}${suffix}`;
    if (!(isRename && fileName === renameFrom) && existing.includes(fileName)) {
      setError(`「${fileName}」已存在。`);
      return;
    }
    onSubmit(base);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onOpenAutoFocus={(event) => event.preventDefault()}>
        <DialogHeader>
          <DialogTitle>{isRename ? `重命名${label}` : `新建${label}`}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Input
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
                if (error) setError(null);
              }}
              placeholder={`文件名${suffix}`}
              autoFocus
              spellCheck={false}
              aria-invalid={error !== null}
            />
            {error && (
              <p className="text-xs text-destructive" role="alert">
                {error}
              </p>
            )}
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="inline-flex h-8 items-center rounded-sm border border-border px-3 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              取消
            </button>
            <button
              type="submit"
              className="inline-flex h-8 items-center rounded-sm bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary-hover"
            >
              {isRename ? "重命名" : "创建"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
