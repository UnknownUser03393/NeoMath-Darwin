"""Lower structured execution outputs into Render IR nodes.

The HTML backend never switches on output type; outputs are lowered here to
meaning nodes (code, math, table, image) first.
"""

from __future__ import annotations

import json

from neomath.xdlt.execution.result import (
    ImageOutput,
    JsonOutput,
    MathOutput,
    Output,
    TableOutput,
    TextOutput,
)
from neomath.xdlt.execution.values import json_default
from neomath.xdlt.math import lower_to_semantic, parse_math
from neomath.xdlt.render.nodes import (
    RenderCode,
    RenderImage,
    RenderInlineMath,
    RenderNode,
    RenderTable,
)


def lower_execution_output(output: Output) -> RenderNode:
    if isinstance(output, TextOutput):
        return RenderCode(output.text)
    if isinstance(output, JsonOutput):
        encoded = json.dumps(
            output.value, sort_keys=True, ensure_ascii=False, default=json_default
        )
        return RenderCode(encoded, language="json")
    if isinstance(output, MathOutput):
        try:
            math_ir = lower_to_semantic(parse_math(output.expression))
        except Exception:  # noqa: BLE001 - degrade to raw text
            math_ir = {"kind": "opaque", "command": "", "raw": output.expression}
        return RenderInlineMath(math_ir, raw=output.expression)
    if isinstance(output, TableOutput):
        return RenderTable(
            None, None, list(output.headers), [list(row) for row in output.rows]
        )
    if isinstance(output, ImageOutput):
        src = f"data:{output.mime};base64,{output.data_base64}"
        return RenderImage(src, mime=output.mime, alt=output.name or "")
    # Unknown output kinds degrade to plain code without crashing.
    return RenderCode(str(getattr(output, "to_dict", lambda: {})()))
