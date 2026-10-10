from __future__ import annotations

from typing import Any


def explain_diagnostic(trace: dict[str, Any]) -> str:
    result = trace.get("result", trace)
    probe = result.get("activeProbe")
    diagnostics = result.get("diagnostics", [])
    root = next((item for item in diagnostics if item.get("status") == "root_fault"), None)
    if root is None:
        return "当前已验证步骤保持相同的解集与定义域。你可以继续推导，或使用补全查看安全操作。"
    if probe:
        value = probe.get("value")
        reason = probe.get("reason")
        if reason == "lost_solution":
            return f"在这里试入 x = {value}：它在上一步成立，在这一步不再成立，所以发生了丢根。"
        if reason == "gained_solution":
            return f"在这里试入 x = {value}：它在上一步不成立，却在这一步成立，所以出现了增根。"
        if reason == "domain_expansion":
            return f"在这里试入 x = {value}：上一步没有定义，这一步却成立，说明定义域被扩大了。"
    return f"问题从这里开始：{root.get('message', '相邻步骤的数学语义发生了变化')}。"
