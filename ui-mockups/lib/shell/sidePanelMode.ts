/**
 * Workspace side-panel modes driven by the activity bar.
 * Pure helpers so mode identity and toggle behavior are unit-testable.
 *
 * Product rule: only modes with real content exist. No search skeleton.
 */

export type SidePanelMode = "notebook" | "variables" | "help" | "settings";

export type SidePanelState = {
  open: boolean;
  mode: SidePanelMode;
};

export const SIDE_PANEL_META: Record<
  SidePanelMode,
  {
    /** Activity-bar / short label (Chinese for feature modes). */
    label: string;
    /** Uppercase chrome heading shown in the panel. */
    heading: string;
    /** aria-label on the side panel surface. */
    ariaLabel: string;
  }
> = {
  notebook: {
    label: "工作区",
    heading: "工作区",
    ariaLabel: "工作区面板",
  },
  variables: {
    label: "变量",
    heading: "变量",
    ariaLabel: "变量面板",
  },
  help: {
    label: "帮助",
    heading: "帮助",
    ariaLabel: "帮助面板",
  },
  settings: {
    label: "设置",
    heading: "设置",
    ariaLabel: "设置面板",
  },
};

/** Modes other than the notebook file browser. */
export const FEATURE_PANEL_MODES: SidePanelMode[] = [
  "variables",
  "help",
  "settings",
];

/**
 * VS Code–style activity click: same mode while open → close;
 * otherwise open (or switch to) the clicked mode.
 */
export function resolvePanelToggle(
  current: SidePanelState,
  clicked: SidePanelMode,
): SidePanelState {
  if (current.open && current.mode === clicked) {
    return { open: false, mode: current.mode };
  }
  return { open: true, mode: clicked };
}

/** Generic open/close without changing mode (mobile menu, close button). */
export function resolvePanelVisibility(
  current: SidePanelState,
  open: boolean,
): SidePanelState {
  return { ...current, open };
}
