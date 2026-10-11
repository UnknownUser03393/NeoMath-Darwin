"use client";

import { useRef } from "react";
import { useNotebook } from "@/lib/notebook/commands";
import type { MarkdownCell } from "@/lib/notebook/types";

export function MarkdownCellView({
  cell,
  isEditing,
}: {
  cell: MarkdownCell;
  isEditing: boolean;
}) {
  const { dispatch } = useNotebook();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [heading, ...body] = cell.source.split("\n");
  const title = heading.replace(/^#\s*/, "");

  const resize = (element: HTMLTextAreaElement) => {
    element.style.height = "0";
    element.style.height = `${Math.max(96, element.scrollHeight)}px`;
  };

  if (isEditing) {
    return (
      <div className="markdown-edit">
        <div className="markdown-prompt">Md</div>
        <textarea
          ref={textareaRef}
          id={`editor-${cell.id}`}
          value={cell.source}
          rows={4}
          onFocus={(event) => resize(event.currentTarget)}
          onInput={(event) => resize(event.currentTarget)}
          onChange={(event) =>
            dispatch({
              type: "cell/updateSource",
              cellId: cell.id,
              source: event.target.value,
            })
          }
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              dispatch({ type: "cell/edit", cellId: null });
              document.getElementById(`cell-${cell.id}`)?.focus();
            }
          }}
          aria-label="Markdown 输入"
        />
      </div>
    );
  }

  return (
    <div
      className="markdown-rendered"
      onDoubleClick={() => {
        dispatch({ type: "cell/edit", cellId: cell.id });
        window.setTimeout(() => textareaRef.current?.focus(), 0);
      }}
    >
      <div className="markdown-kicker">NOTEBOOK LESSON · 方程与等价变换</div>
      <h1>{title}</h1>
      <p>{body.join(" ")}</p>
    </div>
  );
}
