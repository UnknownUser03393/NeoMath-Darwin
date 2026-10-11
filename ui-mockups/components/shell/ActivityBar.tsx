"use client";

import {
  Bug,
  Braces,
  HelpCircle,
  Settings,
  type LucideIcon,
} from "lucide-react";
import type { SidePanelMode } from "@/lib/shell/sidePanelMode";

interface ActivityBarProps {
  sidebarOpen: boolean;
  activeMode: SidePanelMode;
  onSelectMode: (mode: SidePanelMode) => void;
}

const topItems: Array<{ mode: SidePanelMode; label: string; Icon: LucideIcon }> =
  [
    { mode: "notebook", label: "工作区", Icon: Bug },
    { mode: "variables", label: "变量", Icon: Braces },
    { mode: "help", label: "帮助", Icon: HelpCircle },
  ];

export function ActivityBar({
  sidebarOpen,
  activeMode,
  onSelectMode,
}: ActivityBarProps) {
  const isActive = (mode: SidePanelMode) =>
    sidebarOpen && activeMode === mode;

  return (
    <aside className="activity-bar" aria-label="活动栏">
      <div className="activity-mark" aria-label="NeoMath">
        N
      </div>
      {topItems.map(({ mode, label, Icon }) => (
        <button
          key={mode}
          className={`activity-button ${isActive(mode) ? "active" : ""}`}
          onClick={() => onSelectMode(mode)}
          aria-label={label}
          aria-pressed={isActive(mode)}
          title={label}
          data-activity={mode}
        >
          <Icon size={17} strokeWidth={1.6} />
        </button>
      ))}
      <div className="activity-spacer" />
      <button
        className={`activity-button ${isActive("settings") ? "active" : ""}`}
        onClick={() => onSelectMode("settings")}
        aria-label="设置"
        aria-pressed={isActive("settings")}
        title="设置"
        data-activity="settings"
      >
        <Settings size={17} strokeWidth={1.6} />
      </button>
    </aside>
  );
}
