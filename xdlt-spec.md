# xdlt `.hw` Language Specification Draft

Status: Draft 0.1
Scope: Human Writing (`.hw`) source language and its semantic integration points.

This document specifies the `.hw` language used by xdlt. It is a source format for human-authored mathematical documents, not a layout language and not a thin Markdown wrapper.

The terms MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are used in the normative sense.

---

## 1. Design Goals

`.hw` is the human-facing mathematical source language in an xdlt project.

It MUST prioritize:

- mathematical semantic structure over visual markup;
- stable references and IDs over positional references;
- compiler-readable blocks over ambiguous prose conventions;
- LaTeX-quality mathematical notation without exposing LaTeX document structure;
- executable computation without turning the document into a notebook cell list;
- structured theorem/proof/assertion/card semantics;
- multi-backend compilation to PDF, LaTeX, HTML, and future renderers.

It MUST NOT encode:

- page margins;
- fonts;
- headers/footers;
- page numbers;
- LaTeX document class or preamble;
- `\begin{document}` / `\end{document}`;
- `\section{...}` / `\maketitle`;
- backend-specific layout commands in normal content.

The `.hw` source is one input to the xdlt compiler. Complete project compilation uses:

```text
.xdlt + meta.yaml + layout.json + main.hw + code/* + cards/* + assets/*
```

The compiler pipeline SHOULD be:

```text
.hw source
  -> lexer
  -> parser
  -> AST
  -> semantic analysis
  -> xdlt IR
  -> backend renderers (PDF, LaTeX, HTML, ...)
```

LaTeX is an output backend, not the internal semantic model.

---

## 2. Lexical Structure

### 2.1 Encoding

`.hw` files MUST be UTF-8.

Line endings MAY be LF or CRLF. A compiler MUST normalize line endings to LF internally while preserving source spans for diagnostics.

### 2.2 Lines and Blocks

`.hw` is line-oriented at the block level. A block begins at the first non-empty line after a block boundary and ends according to the block's syntax.

Blank lines separate paragraph-like blocks. Blank lines inside fenced or braced blocks are part of the block.

### 2.3 Significant Characters

The following characters have structural meaning at the beginning of a line:

```text
#       heading
:::     mathematical / semantic environment fence
```     code fence
@       directive
[       block label / caption / result metadata in specific contexts
%       comment line
```

The following delimiters have inline meaning:

```text
$...$           inline math
@ref(...)       reference
@cite(...)      citation
@meta(...)      metadata reference
@var(...)       semantic variable reference
@card(...)      knowledge card reference
```

### 2.4 Whitespace

Indentation is not generally semantic except inside fenced blocks and continuation lines explicitly defined by a construct.

Parsers SHOULD preserve original whitespace in source spans but SHOULD NOT make semantic decisions based on indentation unless the construct requires it.

### 2.5 Identifiers

IDs and symbolic names use:

```text
[A-Za-z_][A-Za-z0-9_-]*
```

Qualified IDs use dot or slash separators:

```text
section.heat
fig.solution-plot
card:heat-eq-solution
code/simulation.py#plot_heat
```

IDs are case-sensitive.

### 2.6 String Literals

Directive arguments MAY use quoted strings:

```text
@label("heat equation")
```

Double-quoted strings support escapes:

```text
\"  quote
\\  backslash
\n  newline
\t  tab
```

Unquoted directive values end at whitespace, comma, or `)` depending on context.

---

## 3. Document Structure

A `.hw` document is a sequence of top-level blocks.

Top-level block kinds:

```text
HeadingBlock
ParagraphBlock
DisplayMathBlock
MathEnvironmentBlock
TheoremLikeBlock
ProofBlock
AssertionBlock
ExecutableBlock
ExecutionResultReference
FigureBlock
TableBlock
CardReferenceBlock
DirectiveBlock
RawBackendBlock
CommentBlock
```

A document MAY contain zero or more top-level headings. If no heading exists, the document title is taken from `meta.yaml`, not inferred from the first paragraph.

The parser MUST preserve:

- source range for every block;
- raw source text for lossless formatting;
- stable or explicit block ID when present;
- diagnostics for parse/semantic errors.

---

## 4. Heading Syntax

Headings use `#` markers at the start of a line:

```hw
# Chapter Title
## Section Title
### Subsection Title
```

Rules:

- 1 to 6 `#` characters are allowed.
- A space MUST follow the final `#`.
- Heading text is inline content and MAY contain inline math and references.
- A heading MAY have an explicit ID:

```hw
## Heat equation solution {#sec:heat-solution}
```

A heading MUST NOT be converted directly to `\section{}` in the AST. It is represented as:

```json
{
  "type": "heading",
  "level": 2,
  "id": "sec:heat-solution",
  "content": [...inline nodes...]
}
```

Backend renderers decide whether this becomes numbered sections, slides, cards, web headings, etc.

---

## 5. Paragraphs

A paragraph is one or more consecutive non-empty lines that do not start another block construct.

```hw
Let $u(x,t)$ be the temperature distribution on a rod.
The boundary condition is homogeneous.
```

Line breaks inside a paragraph are soft. Renderers MAY reflow them.

A paragraph MAY contain:

- text;
- inline math;
- references;
- citations;
- metadata references;
- inline card references;
- inline result references.

Paragraphs MUST NOT contain raw display-level LaTeX environments.

---

## 6. Inline Math

Inline math uses single-dollar delimiters:

```hw
Let $u(x,t)$ satisfy the heat equation.
```

Rules:

- Inline math begins with `$` and ends with the next unescaped `$` on the same logical line.
- `$` may be escaped as `\$` in text.
- Inline math MUST NOT span blank lines.
- Inline math content is parsed as math text and stored as a MathInline node.

AST shape:

```json
{
  "type": "math_inline",
  "source": "u(x,t)",
  "mathDialect": "latex-math",
  "parsedExpression": null,
  "symbols": ["u", "x", "t"],
  "diagnostics": []
}
```

The parser SHOULD preserve the raw math string. A semantic analyzer MAY additionally parse it to a CAS expression or symbolic IR.

### 6.1 Markdown Conflict Rule

Because `_`, `*`, `[`, `]`, and `\` are common in LaTeX math, Markdown emphasis/link parsing MUST NOT run inside math spans.

Example:

```hw
$a_n = \frac{1}{n^2}$
```

The `_` is part of math, not emphasis.

---

## 7. Display Math

Display math uses `$$` fences on their own lines:

```hw
$$ {#eq:heat}
\frac{\partial u}{\partial t}
=
\alpha \frac{\partial^2 u}{\partial x^2}
$$
```

Rules:

- Opening and closing `$$` MUST appear alone except for attributes on the opener.
- Display math MAY have attributes after the opening fence.
- `#id` assigns a stable formula ID.
- A `number` attribute requests formula numbering.

```hw
$$ {#eq:heat number}
...
$$
```

Formula numbering is semantic. Backends MAY render it as `(1)`, equation numbers, HTML anchors, or other target-native numbering.

AST shape:

```json
{
  "type": "math_display",
  "id": "eq:heat",
  "numbered": true,
  "source": "\\frac{...}",
  "mathDialect": "latex-math",
  "symbols": ["u", "t", "alpha", "x"],
  "parsedExpression": null
}
```

### 7.1 LaTeX Commands Allowed in Math

Inside inline and display math, xdlt SHOULD allow the common LaTeX math subset:

- symbols and Greek letters: `\alpha`, `\lambda`, `\pi`;
- fractions, roots, sums, integrals: `\frac`, `\sqrt`, `\sum`, `\int`;
- scripts: `_`, `^`;
- delimiters: `\left`, `\right`, `\big`, etc.;
- alignment spacing: `\,`, `\quad`, `\qquad`;
- text inside math: `\text{...}`.

It MUST NOT allow document-level commands inside math:

```text
\documentclass
\usepackage
\begin{document}
\section
\input
\include
\write18
```

Unsupported or dangerous commands MUST produce diagnostics.

---

## 8. Mathematical Environments

Mathematical semantic environments use `:::` fences, not raw LaTeX environments.

General syntax:

```hw
::: <environment-kind> {#id key=value flag}
content...
:::
```

Supported theorem-like kinds:

```text
definition
theorem
lemma
proposition
corollary
example
remark
proof
algorithm
identity
derivation
```

Example:

```hw
::: theorem {#thm:separation title="Separation of variables"}
If $u(x,t)=X(x)T(t)$ and $u$ satisfies @ref(eq:heat), then the separated equations are ...
:::

::: proof {of=#thm:separation}
Substitute $u=XT$ into @ref(eq:heat) and divide by $\alpha XT$.
:::
```

AST shape:

```json
{
  "type": "math_environment",
  "kind": "theorem",
  "id": "thm:separation",
  "title": "Separation of variables",
  "content": [...blocks...],
  "relations": {
    "proves": null,
    "of": null,
    "dependsOn": []
  }
}
```

Proof blocks SHOULD use `of=#id` when proving a theorem-like block.

Raw LaTeX environments such as `\begin{theorem}` MUST NOT appear in normal `.hw` content.

---

## 9. Assertions / Verification

Visual check marks such as `✅` are not semantic assertions. They MAY appear as text, but they MUST NOT be used as proof or verification metadata.

Semantic assertions use `@assert` blocks.

```hw
@assert {#assert:initial-condition}
  claim: substitute(@ref(eq:final-solution), t=0) == @ref(eq:initial)
  using: sympy
  requires:
    - L > 0
    - alpha > 0
@end
```

Short form:

```hw
@assert {#assert:b1}
  expression: b_1
  equals: 1
@end
```

Rules:

- Assertions MUST have stable IDs, either explicit or compiler-generated.
- Assertions MUST produce a verification state:

```text
unverified
valid
valid-with-conditions
warning
invalid
unknown
```

- `unknown` MUST NOT be rendered as `invalid`.
- Backend output SHOULD be stored outside `.hw` unless pinned by the author.

AST shape:

```json
{
  "type": "assertion",
  "id": "assert:initial-condition",
  "claim": "substitute(@ref(eq:final-solution), t=0) == @ref(eq:initial)",
  "backend": "sympy",
  "requires": ["L > 0", "alpha > 0"],
  "verificationStatus": "unverified",
  "diagnostics": []
}
```

---

## 10. References

References use `@ref(...)`.

```hw
Substitute the ansatz into @ref(eq:heat).
```

Targets MAY be:

```text
eq:heat
sec:solution
thm:separation
fig:heat-plot
table:errors
card:fourier-series
```

Optional display text:

```hw
@ref(eq:heat, text="the heat equation")
```

References resolve semantically against the project symbol table, not by scanning rendered labels.

Formula numbering and heading numbering are backend concerns. The source reference is always by stable ID.

Unresolved references MUST produce diagnostics and SHOULD be preserved in output visibly enough for authors to find them.

---

## 11. Citations

Citations use `@cite(...)`.

```hw
The Fourier series argument follows @cite(evans-pde, page=47).
```

Multiple citations:

```hw
@cite(evans-pde, strauss-pde)
```

The bibliography source is not stored in `.hw`. It SHOULD be declared in `meta.yaml` or `.xdlt` build configuration.

AST shape:

```json
{
  "type": "citation",
  "keys": ["evans-pde"],
  "locator": {"page": "47"}
}
```

Backends MAY render citations as numeric, author-year, footnotes, or hyperlinks depending on `layout.json` and bibliography settings.

---

## 12. Figures and Assets

Figures are semantic asset references, not raw `\includegraphics`.

```hw
@figure {#fig:heat-plot}
  src: assets/figures/heat-plot.png
  alt: Heat equation profiles over time
  caption: Temperature profile for several $t$ values.
@end
```

Rules:

- `src` MUST be a project-relative path or an asset ID.
- `caption` is inline content.
- `alt` SHOULD be present for accessibility.
- Backends decide sizing and placement via `layout.json` unless explicit semantic hints are provided.

Optional semantic hints:

```hw
  role: result-plot
  generated-by: @exec(plot-heat)
```

AST shape:

```json
{
  "type": "figure",
  "id": "fig:heat-plot",
  "src": "assets/figures/heat-plot.png",
  "caption": [...inline nodes...],
  "alt": "Heat equation profiles over time",
  "generatedBy": "exec:plot-heat"
}
```

---

## 13. Tables

Tables SHOULD be semantic, not merely Markdown pipe art.

Simple table syntax is allowed:

```hw
@table {#table:coefficients}
  caption: Fourier coefficients
  columns: [n, b_n]
  rows:
    - [1, 1]
    - [2, 0]
    - [3, 0]
@end
```

For human-friendly small tables, pipe syntax MAY be accepted:

```hw
| n | b_n |
|---|-----|
| 1 | 1   |
| 2 | 0   |
```

But pipe tables MUST be normalized into the same Table AST.

AST shape:

```json
{
  "type": "table",
  "id": "table:coefficients",
  "columns": [
    {"key": "n", "content": [...inline nodes...]},
    {"key": "b_n", "content": [...inline nodes...]}
  ],
  "rows": [[...cells...]],
  "caption": [...inline nodes...]
}
```

Cells MAY contain inline math and references. Display math inside table cells SHOULD be rejected unless the table is explicitly declared as `mode=block`.

---

## 14. Executable Blocks

`.hw` supports Jupyter-style executable computation without treating the document as a flat notebook.

There are two kinds of code fences:

1. ordinary code block;
2. executable block.

### 14.1 Ordinary Code Block

Ordinary code uses a standard fence and is not executed:

````hw
```python
print("example")
```
````

AST:

```json
{
  "type": "code_block",
  "language": "python",
  "executable": false,
  "source": "print(...)"
}
```

### 14.2 Executable Block

Executable blocks use an `exec` fence:

````hw
```exec python {#exec:plot-heat kernel=python3 file="code/simulation.py"}
plot_heat(alpha=0.01, L=1)
```
````

Rules:

- Executable blocks MUST have a stable ID.
- If no ID is supplied, the compiler MUST generate one and SHOULD persist it via a formatter rewrite.
- The first word after `exec` is the language.
- `kernel` identifies the execution backend.
- `file` MAY point to an external code resource.
- Inline code inside the fence MAY call functions from the external file.

AST:

```json
{
  "type": "executable_block",
  "id": "exec:plot-heat",
  "language": "python",
  "kernel": "python3",
  "file": "code/simulation.py",
  "source": "plot_heat(alpha=0.01, L=1)",
  "dependsOn": []
}
```

### 14.3 Stable ID Generation

Compiler-generated executable IDs SHOULD use a deterministic path-local strategy:

```text
exec:<slug>-<short-hash>
```

Where:

- `slug` comes from nearest heading or explicit name;
- `short-hash` is derived from initial source + source path;
- once generated, the ID is written back into source by the formatter.

After an ID exists, it MUST remain stable even if the block source changes.

---

## 15. Execution Results

Execution results MUST NOT be stored inline in normal `.hw` source by default.

Recommended sidecar layout:

```text
.xdlt-cache/
  results/
    exec:plot-heat.json
```

or project-visible output:

```text
outputs/
  exec-plot-heat.result.json
  figures/heat-plot.png
```

A result record SHOULD contain:

```json
{
  "execId": "exec:plot-heat",
  "runId": "run:2026-08-07T12:00:00Z",
  "kernel": "python3",
  "status": "ok",
  "startedAt": "...",
  "finishedAt": "...",
  "inputsHash": "sha256:...",
  "outputs": [
    {"type": "image", "mime": "image/png", "path": "outputs/figures/heat.png"},
    {"type": "latex", "content": "b_1=1"}
  ],
  "diagnostics": []
}
```

`.hw` references results semantically:

```hw
@result(exec:plot-heat)
```

With selection:

```hw
@result(exec:plot-heat, output=0)
```

Pinned inline results MAY be allowed for review or archival mode:

```hw
@result(exec:plot-heat, pinned=true)
```

Pinned results MUST include provenance and hash metadata. They SHOULD NOT become the default editing mode.

---

## 16. Knowledge Card References

`.card.json` content is a semantic resource. `.hw` SHOULD reference cards semantically rather than blindly expanding them.

Inline reference:

```hw
We use @card(heat-eq-solution) with $\alpha>0$ and $L>0$.
```

Block reference:

```hw
@use-card {#use:heat-general}
  card: heat-eq-solution
  mode: reference
  bind:
    alpha: alpha
    L: L
  require:
    - alpha > 0
    - L > 0
@end
```

Modes:

```text
reference   keep semantic link, render summary/content as needed
embed       insert a snapshot while retaining source card ID
expand      inline editable copy; breaks live update but keeps provenance
```

Default MUST be `reference`.

A card insertion MUST produce a dependency edge:

```json
{
  "type": "card_reference",
  "id": "use:heat-general",
  "cardId": "heat-eq-solution",
  "mode": "reference",
  "bindings": {"alpha": "alpha", "L": "L"},
  "requiredContext": ["alpha > 0", "L > 0"],
  "provenance": {"cardVersion": "..."}
}
```

The compiler MUST check card conditions against the active context. Missing conditions produce diagnostics.

---

## 17. Variables / Metadata References

Metadata references use `@meta(...)`.

```hw
Submitted by @meta(author) for @meta(course).
```

Variables use `@var(...)` when the author wants semantic variable identity instead of plain text:

```hw
Let @var(alpha) be positive.
```

Context declarations MAY be written with `@context`:

```hw
@context {#ctx:heat}
  reals x t L alpha
  positive L alpha
  integers n
@end
```

Variable declarations belong to the active scope and feed semantic analysis.

`@meta(title)` reads from `meta.yaml`. `.hw` MUST NOT duplicate document title/author as authoritative metadata, although headings may naturally repeat a title as content when desired.

---

## 18. Comments

Line comments start with `%` at the beginning of a line:

```hw
% This comment is ignored by renderers.
```

Block comments:

```hw
@comment
This entire block is ignored by renderers but preserved by formatters.
@end
```

Comments MUST remain in source spans for formatter round-tripping but MUST NOT appear in AST semantic content unless a tooling mode requests them.

Inside math, `%` is treated according to LaTeX math text rules only if the math parser supports it. Otherwise it SHOULD produce a diagnostic.

---

## 19. Escaping Rules

Escapes in normal text:

```text
\$      literal dollar
\@      literal at-sign
\#      literal hash at line start
\%      literal percent at line start
\\      literal backslash
```

Escapes inside math are LaTeX math escapes and MUST NOT be interpreted as `.hw` escapes except for closing delimiter detection.

Escapes inside code fences are raw code text.

Escapes inside directive strings follow string literal rules.

### 19.1 Markdown Conflict Avoidance

`.hw` MAY support a small Markdown-like inline subset, but it MUST NOT allow Markdown constructs to override math semantics.

Specifically:

- `_` is never emphasis inside math;
- `*` is never emphasis inside math;
- `[x]` inside math is math text, not a link;
- backslash inside math is LaTeX math syntax;
- display math fences take precedence over any paragraph parsing.

---

## 20. Error Handling

The parser MUST be loss-tolerant.

For malformed constructs, it SHOULD:

1. create an error node or degraded text node;
2. preserve original source;
3. attach diagnostics with source ranges;
4. continue parsing subsequent blocks.

Diagnostic shape:

```json
{
  "severity": "error",
  "code": "UNTERMINATED_DISPLAY_MATH",
  "message": "Display math block is missing a closing $$ fence",
  "sourceRange": {"start": 120, "end": 180},
  "fixes": [
    {"title": "Insert closing $$", "edit": {...}}
  ]
}
```

Semantic errors include:

```text
DUPLICATE_ID
UNRESOLVED_REFERENCE
UNKNOWN_CARD
CARD_CONDITION_UNSATISFIED
EXECUTABLE_ID_MISSING
KERNEL_UNAVAILABLE
UNSUPPORTED_LATEX_COMMAND
RAW_BACKEND_UNAVAILABLE
ASSERTION_FAILED
ASSERTION_UNKNOWN
```

`unknown` verification MUST be distinct from `invalid`.

---

## 21. AST / Semantic Model

A `.hw` parser produces a concrete AST with source preservation. Semantic analysis enriches it into xdlt IR.

Minimum AST node fields:

```json
{
  "id": "optional stable id",
  "type": "node kind",
  "source": "raw source substring",
  "sourceRange": {"start": 0, "end": 0},
  "children": [],
  "diagnostics": []
}
```

Math nodes SHOULD contain:

```json
{
  "type": "math_display",
  "mathDialect": "latex-math",
  "source": "...",
  "parsedExpression": null,
  "symbolReferences": [],
  "contextId": "ctx:...",
  "numbered": true
}
```

Derivation nodes SHOULD contain:

```json
{
  "type": "derivation_step",
  "id": "der:...",
  "from": "...",
  "to": "...",
  "rule": "simplify",
  "dependencies": ["eq:..."],
  "requiredConditions": [],
  "verificationStatus": "unverified"
}
```

Executable nodes SHOULD contain:

```json
{
  "type": "executable_block",
  "id": "exec:...",
  "language": "python",
  "kernel": "python3",
  "file": "code/simulation.py",
  "source": "...",
  "resultRef": "results/exec....json"
}
```

Semantic IR additionally resolves:

- references;
- citations;
- context scopes;
- card dependencies;
- execution dependencies;
- formula numbering;
- theorem/proof relationships;
- assertion verification states;
- backend compatibility diagnostics.

---

## 22. Extension Mechanism

Extensions MUST be explicit and namespaced.

Directive extension:

```hw
@plugin:name {#id key=value}
...
@end
```

Environment extension:

```hw
::: plugin:name {#id}
...
:::
```

Unknown extensions MUST produce diagnostics but SHOULD preserve content.

Extensions MUST declare:

```json
{
  "name": "plugin:name",
  "version": "1.0.0",
  "nodeTypes": [...],
  "backends": ["html", "latex"],
  "fallback": "paragraph | raw | error"
}
```

Extensions MUST NOT silently inject layout behavior into `.hw`. Layout-affecting extension config belongs in `.xdlt` or `layout.json`.

---

## 23. Backward Compatibility

`.hw` SHOULD include an optional version directive at the top:

```hw
@xdlt(version="0.1")
```

If absent, compilers MAY assume the earliest supported version and issue a warning.

Compatibility rules:

- New parsers MUST preserve unknown directives as UnknownDirective nodes.
- New parsers MUST preserve unknown environments as UnknownEnvironment nodes.
- Formatters MUST NOT delete unknown nodes.
- Deprecated syntax SHOULD remain parseable for at least one major version.
- Semantic behavior changes MUST be gated by the declared language version when possible.

Migration tools SHOULD be able to rewrite older `.hw` documents into the latest syntax while preserving IDs.

---

## 24. Raw LaTeX Escape Hatch

Raw LaTeX is allowed only through explicit backend-scoped escape blocks:

```hw
@raw latex {#raw:tikz-diagram}
\begin{tikzpicture}
...
\end{tikzpicture}
@end
```

Rules:

- Raw backend blocks MUST declare a backend.
- They MUST produce compatibility diagnostics for other backends.
- They MUST NOT affect document-level preamble directly.
- Required packages or capabilities MUST be declared as metadata on the raw block or in project build config.

Example:

```hw
@raw latex {#raw:tikz requires=["tikz"] fallback="image"}
...
@end
```

HTML export may render a fallback image or diagnostic. PDF via LaTeX may render it directly.

Raw LaTeX MUST NOT be the default way to express theorem/proof/figure/table/code constructs.

---

## 25. Complete Example Document

````hw
@xdlt(version="0.1")

# 偏微分方程作业 3 {#doc:pde-hw3}

@context {#ctx:global}
  reals x t L alpha
  positive L alpha
  integers n
@end

## 第一题：热传导方程求解 {#sec:heat}

设 $u(x,t)$ 满足：

$$ {#eq:heat number}
\frac{\partial u}{\partial t}
=
\alpha \frac{\partial^2 u}{\partial x^2}
$$

边界条件：

$$ {#eq:boundary number}
u(0,t) = u(L,t) = 0
$$

初始条件：

$$ {#eq:initial number}
u(x,0) = \sin\left(\frac{\pi x}{L}\right)
$$

::: definition {#def:separation title="Separation ansatz"}
A separated solution has the form

$$ {#eq:ansatz}
u(x,t) = X(x)T(t)
$$
:::

将 @ref(eq:ansatz) 代入 @ref(eq:heat)，得到：

$$ {#eq:separated number}
X'' + \lambda X = 0,
\qquad
T' + \alpha \lambda T = 0
$$

::: theorem {#thm:eigenvalues title="Eigenvalues under homogeneous boundary conditions"}
Under @ref(eq:boundary), the admissible eigenvalues are

$$ {#eq:eigenvalues number}
\lambda_n = \left(\frac{n\pi}{L}\right)^2,
\qquad n=1,2,3,\dots
$$
:::

::: proof {of=#thm:eigenvalues}
The boundary conditions force $X(0)=X(L)=0$.
The non-trivial sine modes therefore require $n\in\mathbb{Z}_{>0}$.
:::

@use-card {#use:fourier-series}
  card: fourier-series-sine-basis
  mode: reference
  bind:
    interval: [0, L]
  require:
    - L > 0
@end

因此通解写为：

$$ {#eq:series-solution number}
u(x,t)
=
\sum_{n=1}^{\infty}
b_n
\sin\left(\frac{n\pi x}{L}\right)
e^{-\alpha\left(\frac{n\pi}{L}\right)^2t}
$$

代入 @ref(eq:initial)：

$$ {#eq:coefficients number}
\sum b_n \sin\left(\frac{n\pi x}{L}\right)
=
\sin\left(\frac{\pi x}{L}\right)
$$

因此 $b_1=1$，其余系数均为 $0$。

最终解：

$$ {#eq:final-solution number}
u(x,t)
=
\sin\left(\frac{\pi x}{L}\right)
e^{-\alpha\left(\frac{\pi}{L}\right)^2t}
$$

@assert {#assert:initial-condition}
  claim: substitute(@ref(eq:final-solution), t=0) == @ref(eq:initial)
  using: sympy
  requires:
    - L > 0
    - alpha > 0
@end

```exec python {#exec:plot-heat kernel=python3 file="code/simulation.py"}
plot_heat(alpha=0.01, L=1)
```

@figure {#fig:heat-plot}
  src: @result(exec:plot-heat, output=0)
  alt: Heat equation profiles over time
  caption: Profiles of the solution at several values of $t$.
@end

@table {#table:coefficients}
  caption: Nonzero Fourier coefficients
  columns: [n, b_n]
  rows:
    - [1, 1]
    - [2, 0]
    - [3, 0]
@end

The computation output is shown in @ref(fig:heat-plot), and the coefficients are summarized in @ref(table:coefficients).
````

---

## 26. Known Design Decisions and Rejected Alternatives

### 26.1 `.hw` is not Markdown plus math

Markdown compatibility is intentionally limited. Full Markdown introduces conflicts with LaTeX math and makes block parsing too ambiguous for semantic mathematics.

### 26.2 `.card.json` is semantic reference first

Cards SHOULD NOT be blindly inlined by default. Inline expansion loses provenance, update tracking, and condition checking. The default mode is `reference`; `embed` and `expand` are explicit choices.

### 26.3 Execution results live outside source by default

Storing outputs inline bloats diffs and makes source review noisy. Results belong in cache/outputs sidecars with hashes and provenance. Pinned inline results are allowed only as an explicit archival mode.

### 26.4 Raw LaTeX is backend-scoped

Raw LaTeX is sometimes necessary, but it harms cross-backend portability. Therefore it must be explicit, backend-scoped, and diagnostically visible.

### 26.5 Formula numbers are semantic requests

A numbered equation is not a LaTeX `equation` environment in source. It is a math display node with `numbered=true`; renderers implement numbering.
