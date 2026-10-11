"""Tokenizer for the LaTeX-math subset.

Each single letter becomes its own ``symbol`` token (as in TeX math); commands
become ``command`` tokens. ``\\mathrm{...}`` is flattened to a single ``symbol``
token and ``\\text{...}`` to a ``text`` token so the parser can treat them as
atoms. Spacing commands (``\\,``, ``\\quad``, ...) are skipped entirely.
"""

from __future__ import annotations


class Token:
    __slots__ = ("kind", "value", "start", "end")

    def __init__(self, kind: str, value: str, start: int, end: int) -> None:
        self.kind = kind
        self.value = value
        self.start = start
        self.end = end

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Token({self.kind!r}, {self.value!r}, {self.start}, {self.end})"


_ONE_CHAR_KINDS = {
    "{": "lbrace",
    "}": "rbrace",
    "(": "lparen",
    ")": "rparen",
    "[": "lbracket",
    "]": "rbracket",
    "|": "pipe",
    ",": "comma",
    ".": "dot",
}

_OPERATORS = {"+", "-", "*", "/", "^", "_", "=", "<", ">", "!"}

_SINGLE_CHAR_SPACING = {",", ";", ":", "!"}
_MULTI_CHAR_SPACING = {"quad", "qquad"}


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in " \t\n\r":
            i += 1
            continue
        if ch == "\\":
            i = _lex_command(source, i, tokens)
            continue
        if ch.isdigit():
            j = i
            while j < n and (source[j].isdigit() or source[j] == "."):
                j += 1
            tokens.append(Token("number", source[i:j], i, j))
            i = j
            continue
        if ch.isalpha():
            tokens.append(Token("symbol", ch, i, i + 1))
            i += 1
            continue
        if ch in _OPERATORS:
            two = source[i : i + 2]
            if two in ("<=", ">=", "!="):
                tokens.append(Token("op", two, i, i + 2))
                i += 2
                continue
            tokens.append(Token("op", ch, i, i + 1))
            i += 1
            continue
        kind = _ONE_CHAR_KINDS.get(ch)
        if kind is not None:
            tokens.append(Token(kind, ch, i, i + 1))
            i += 1
            continue
        tokens.append(Token("unknown", ch, i, i + 1))
        i += 1
    tokens.append(Token("eof", "", n, n))
    return tokens


def _lex_command(source: str, start: int, tokens: list[Token]) -> int:
    n = len(source)
    j = start + 1
    if j >= n:
        tokens.append(Token("unknown", "\\", start, start + 1))
        return j
    c = source[j]
    if c == " " or c in _SINGLE_CHAR_SPACING:
        return j + 1
    if c.isalpha():
        k = j
        while k < n and source[k].isalpha():
            k += 1
        name = source[j:k]
        if name in _MULTI_CHAR_SPACING:
            return k
        if name in ("text", "mathrm") and k < n and source[k] == "{":
            depth = 1
            m = k + 1
            content: list[str] = []
            while m < n and depth > 0:
                if source[m] == "{":
                    depth += 1
                elif source[m] == "}":
                    depth -= 1
                if depth > 0:
                    content.append(source[m])
                m += 1
            text = "".join(content)
            if name == "mathrm":
                tokens.append(Token("symbol", text or "d", start, m))
            else:
                tokens.append(Token("text", text, start, m))
            return m
        tokens.append(Token("command", name, start, k))
        return k
    # Backslash followed by a non-letter, e.g. \left\{.
    tokens.append(Token("command", c, start, j + 1))
    return j + 1
