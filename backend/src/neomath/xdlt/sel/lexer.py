"""Tokenizer for SEL.

Keywords (``and``/``or``/``not``/``true``/``false``/``null``) are recognized
separately from ordinary identifiers. Semantic references (``#eq:heat``) become
a single ``ref`` token; a lone ``=`` is preserved for named-argument binding
(comparison equality is ``==``).
"""

from __future__ import annotations

_KEYWORDS = {"and", "or", "not", "true", "false", "null"}

_OPERATORS = {"+", "-", "*", "/", "^", "=", "<", ">", "!"}


class SelToken:
    __slots__ = ("kind", "value", "start", "end")

    def __init__(self, kind: str, value: str, start: int, end: int) -> None:
        self.kind = kind
        self.value = value
        self.start = start
        self.end = end

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"SelToken({self.kind!r}, {self.value!r}, {self.start}, {self.end})"


def tokenize_sel(source: str) -> list[SelToken]:
    tokens: list[SelToken] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in " \t\n\r":
            i += 1
            continue
        if ch == '"':
            j = i + 1
            chars: list[str] = []
            while j < n and source[j] != '"':
                if source[j] == "\\" and j + 1 < n:
                    chars.append(source[j + 1])
                    j += 2
                else:
                    chars.append(source[j])
                    j += 1
            tokens.append(SelToken("string", "".join(chars), i, j + 1 if j < n else j))
            i = j + 1 if j < n else j
            continue
        if ch.isdigit():
            j = i
            while j < n and (source[j].isdigit() or source[j] == "."):
                j += 1
            tokens.append(SelToken("number", source[i:j], i, j))
            i = j
            continue
        if ch == "#":
            j = i + 1
            while j < n and (source[j].isalnum() or source[j] in "_."):
                j += 1
            name = source[i + 1 : j]
            if j < n and source[j] == ":":
                k = j + 1
                while k < n and (source[k].isalnum() or source[k] in "_-"):
                    k += 1
                name = source[i + 1 : k]
                j = k
            tokens.append(SelToken("ref", name, i, j))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            word = source[i:j]
            kind = "keyword" if word in _KEYWORDS else "identifier"
            tokens.append(SelToken(kind, word, i, j))
            i = j
            continue
        if ch in _OPERATORS:
            two = source[i : i + 2]
            if two in ("==", "!=", "<=", ">="):
                tokens.append(SelToken("op", two, i, i + 2))
                i += 2
                continue
            tokens.append(SelToken("op", ch, i, i + 1))
            i += 1
            continue
        if ch in "()[],":
            tokens.append(SelToken("punct", ch, i, i + 1))
            i += 1
            continue
        tokens.append(SelToken("unknown", ch, i, i + 1))
        i += 1
    tokens.append(SelToken("eof", "", n, n))
    return tokens
