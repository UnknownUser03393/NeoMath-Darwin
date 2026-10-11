# 可信边界

| 能力 | 权威来源 | 可否被 AI 改写 |
|---|---|---|
| 解析、定义域、解集 | C++ MathCore | 否 |
| Root Fault / Tainted | C++ MathCore | 否 |
| Probe 值与代回结果 | C++ MathCore | 否 |
| Transformation Certificate | C++ MathCore | 否 |
| 学生语言解释 | 本地模板或 AI | 是，仅措辞 |
| 自然语言到 Intent | AI + Python allowlist | 候选，须经 C++ 执行与证书验证 |

AI 失败、离线或 Schema 不合法时不会影响核心运行。任何 AI 候选都不能直接修改
MathState。

