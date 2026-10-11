"use client";

import {
  useEffect,
  useRef,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";

interface Props {
  id: string;
  value: string;
  placeholder?: string;
  /** Focus the editor when it becomes selected-and-editing (new cell). */
  autoFocus?: boolean;
  onChange: (value: string) => void;
  onRun: (advance: boolean) => void;
  onEscape: () => void;
  onFocus: () => void;
}

export function MathCellEditor({
  id,
  value,
  placeholder,
  autoFocus,
  onChange,
  onRun,
  onEscape,
  onFocus,
}: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const resize = () => {
    const element = ref.current;
    if (!element) return;
    element.style.height = "0";
    element.style.height = `${Math.max(38, element.scrollHeight)}px`;
  };

  useEffect(resize, [value]);

  useEffect(() => {
    if (autoFocus) {
      ref.current?.focus();
    }
  }, [autoFocus]);

  const change = (event: ChangeEvent<HTMLTextAreaElement>) => {
    onChange(event.target.value);
  };

  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && event.shiftKey) {
      event.preventDefault();
      onRun(true);
    } else if (
      event.key === "Enter" &&
      (event.ctrlKey || event.metaKey)
    ) {
      event.preventDefault();
      onRun(false);
    } else if (event.key === "Escape") {
      event.preventDefault();
      onEscape();
    }
  };

  return (
    <textarea
      ref={ref}
      id={`editor-${id}`}
      className="math-editor"
      value={value}
      placeholder={placeholder}
      rows={1}
      spellCheck={false}
      onChange={change}
      onInput={resize}
      onKeyDown={keyDown}
      onFocus={onFocus}
      aria-label="数学输入"
    />
  );
}
