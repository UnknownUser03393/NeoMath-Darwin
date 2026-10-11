# Recording Scenes — 场景清单

录制画布 recording.html 中的场景、步骤和时长。

## 场景列表

| Scene | Steps | Total Hold (ms) | 旁白段落 |
|-------|-------|-----------------|----------|
| hook | 2 | 5000 | Scene 01 |
| problem | 4 | 9600 | Scene 02 |
| workflow | 4 | 6700 | Scene 03 |
| trust-model | 3 | 7300 | Scene 07 |
| engineering | 2 | 5000 | Scene 08 |
| ai-collaboration | 2 | 4500 | Scene 09 (前半) |
| reflection | 2 | 6000 | Scene 10 (前半) |
| end | 1 | 3500 | Scene 10 (后半) |

## 详细步骤

### hook
| Step | Hold (ms) | 内容 |
|------|-----------|------|
| 0 | 2500 | NeoMath 标题 + 副标题 + 标语 |
| 1 | 2500 | "答案错了，究竟是从哪一步开始错的？" |

### problem
| Step | Hold (ms) | 内容 |
|------|-----------|------|
| 0 | 2200 | x(x−1)=0 → 除以 x → x−1=0 |
| 1 | 2200 | 解集对比 {0,1} → {1} |
| 2 | 2200 | LOST ROOT 标记 |
| 3 | 3000 | Witness x=0 验证：原式 ✓ 新式 ✕ |

### workflow
| Step | Hold (ms) | 内容 |
|------|-----------|------|
| 0 | 1800 | Write + Complete |
| 1 | 1200 | + Run |
| 2 | 1200 | + Break (高亮) |
| 3 | 2500 | + Explain + Fix + Replay |

### trust-model
| Step | Hold (ms) | 内容 |
|------|-----------|------|
| 0 | 2000 | "AI ≠ Math Truth" 标题 |
| 1 | 1800 | AI 框 + 箭头 |
| 2 | 3500 | Validation Boundary + C++ MathCore + 结论 |

### engineering
| Step | Hold (ms) | 内容 |
|------|-----------|------|
| 0 | 1500 | "工程验证" 标题 |
| 1 | 3500 | 四个指标卡片 |

### ai-collaboration
| Step | Hold (ms) | 内容 |
|------|-----------|------|
| 0 | 2000 | Human + AI + Tests + Iteration |
| 1 | 2500 | 协作循环流程图 |

### reflection
| Step | Hold (ms) | 内容 |
|------|-----------|------|
| 0 | 3000 | AI 可以生成代码，但… |
| 1 | 3000 | 不能证明 → Unverified |

### end
| Step | Hold (ms) | 内容 |
|------|-----------|------|
| 0 | 3500 | NeoMath 标题 + 副标题 + 署名 |

## data-demo-id 索引

recording.html 中所有可供 Playwright 定位的元素：

```
hook-title
hook-subtitle
hook-tagline
hook-question
problem-original-equation
problem-transformed-equation
problem-set-diff
problem-lost-root
problem-verification
workflow-title
workflow-pipeline
workflow-write
workflow-complete
workflow-run
workflow-break
workflow-explain
workflow-fix
workflow-replay
trust-headline
trust-ai-box
trust-validation-boundary
trust-core-box
trust-verdict
engineering-title
engineering-metrics
engineering-tests
engineering-differential
engineering-latency
engineering-replay
collab-title
collab-actors
collab-flow
reflection-quote
reflection-unverified
end-title
end-subtitle
end-tagline
end-credit
```
