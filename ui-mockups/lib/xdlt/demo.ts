/**
 * Demo XDLT document for the incremental editor. Uses only syntax the current
 * backend parser actually supports (extracted from the test corpus).
 */
export const DEMO_XDLT = `# 热传导示例

#context {
    alpha: Real & Positive = 0.01
    L: Real & Positive = 1
    T: Real & Positive = 300
    x: Real
}

温度场 $u(x,t)$ 满足热传导方程，其中扩散率 $\\alpha = 0.01$，杆长 $L = 1$。

$$ #eq:heat(numbered=true)
\\frac{\\partial u}{\\partial t}
=
\\alpha \\frac{\\partial^2 u}{\\partial x^2}
$$

见 #eq:heat 的解。把初温记为 $T$，参考 #thm:solution。

#thm:solution("Heat equation solution") {
    解具有形式：

    $$ #eq:solution(numbered=true)
    u(x,t)
    =
    \\sin\\left(\\frac{\\pi x}{L}\\right)
    e^{-\\alpha (\\frac{\\pi}{L})^2 t}
    $$
}

#proof(#thm:solution) {
    使用分离变量法求解。
}

#assert:valid(using=sympy) {
    claim alpha + 0 == alpha
}

#assert:unknown(using=sympy) {
    claim f(x) == 1
}

#exec:data(
    python,
    inputs=[alpha, L]
) {
from xdlt_runtime import output

output.text("alpha = " + str(alpha))
output.json({
    "alpha": alpha,
    "L": L
})
output.table([["alpha", alpha], ["L", L]])
output.image(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAGAAAAAgCAYAAADtwH1UAAAB10lEQVR42u3R7UoTAACGUX9LhJRUVFQgYSElISKhpLVSMyuzYok00WrEiiEDFbMyFJKMObX51dSWSGVkH2qSkSEiQ4aIrZJlMivMwkoMw0iUx4vo73tu4QQFh2xjxeqdrFwbTciGOFZtNhAadpA14WmsizCyPtLExqhzbIq5wJZYG2HxhWw1XCM8qYzth+xEHHWy47iLSGMLuzLbiDI9ITqnmxhzL7stA8RZveyxvSEh38++SxPsvzpFYslPkq/PkVK+wGH7Isfs85ysmCXDMY3JMUlOZQBzlR9LlQ9r9RC2ag8Ft/oocvZQ7OyktKadstr73Ky9S2WdC2ddDfX1DhobbuBuKKX19mXaXPm0u3J51mjhedNZeppM9Dafor85Hc+dVLzuRIbdCYy0xONr3cvbewbePzjA6MNk/I9S+PA4lY9PjzDekUagK52J7hN8fmHky8sMJl9l8vX1ab71ZfG9P5vpgTP88Jj5NXieGa+F2aGL/B62MjeSyx+fjfl3efwdLeCfv5CFsSIWx6+wFCiGTyUEKUABClCAAhSgAAUoQAEKUIACFKAABShAAQpQgAIUoAAFKEABClCAAhSgAAUoQAEKUIACFKAABShAAQpQgAIU8P8By2h0PfLi6/PBAAAAAElFTkSuQmCC",
    ),
    name="plot.png",
)
}

#fig:heat-plot(
    source=#exec:data[3]
) {
    温度场示意图。
}

Opaque 占位符 $\\unknown{foo}$ 会走 fallback。
`;

/** Starter content for a freshly created XDLT document (minimal, valid). */
export const BLANK_XDLT = `# 未命名文档

在这里写下你的数学文档。

`;

