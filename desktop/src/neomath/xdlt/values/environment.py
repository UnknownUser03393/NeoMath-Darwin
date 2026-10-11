"""Value environment: ``symbolId -> SemanticValue``.

Resolution priority is fixed:

    runtime override > document value > symbolic fallback

Overrides never mutate the ``.hw`` source; they only shadow the effective value,
which feeds semantic hashes and execution inputs.
"""

from __future__ import annotations

from typing import Any

from neomath.xdlt.values.nodes import SemanticValue, SymbolicValue


class ValueEnvironment:
    def __init__(self) -> None:
        self._values: dict[str, SemanticValue] = {}
        self._overrides: dict[str, SemanticValue] = {}
        self._names: dict[str, str] = {}
        self._meta: dict[str, dict[str, Any]] = {}

    def declare(self, name: str, symbol_id: str, value: SemanticValue | None = None) -> None:
        if value is None:
            value = SymbolicValue(name, None, [])
        self._values[symbol_id] = value
        self._names[name] = symbol_id
        self._meta[symbol_id] = {
            "name": name,
            "type": _meta_type(value),
            "properties": _meta_properties(value),
        }

    def override(self, name: str, value: SemanticValue) -> None:
        symbol_id = self._names.get(name)
        if symbol_id is not None:
            self._overrides[symbol_id] = value

    def has_value(self, symbol_id: str) -> bool:
        return symbol_id in self._overrides or symbol_id in self._values

    def resolve(self, symbol_id: str) -> SemanticValue:
        if symbol_id in self._overrides:
            return self._overrides[symbol_id]
        if symbol_id in self._values:
            return self._values[symbol_id]
        meta = self._meta.get(symbol_id, {})
        return SymbolicValue(
            str(meta.get("name", symbol_id)),
            meta.get("type"),
            list(meta.get("properties", [])),
        )

    def resolve_name(self, name: str) -> SemanticValue:
        symbol_id = self._names.get(name)
        if symbol_id is None:
            return SymbolicValue(name)
        return self.resolve(symbol_id)

    def effective(self) -> dict[str, SemanticValue]:
        symbol_ids = list(dict.fromkeys(list(self._values) + list(self._overrides)))
        return {symbol_id: self.resolve(symbol_id) for symbol_id in symbol_ids}

    def to_dict(self) -> dict[str, Any]:
        return {
            symbol_id: value.to_dict() for symbol_id, value in self.effective().items()
        }

    def values_hash(self) -> str:
        from neomath.xdlt.graph.hash import stable_hash

        return stable_hash({"values": self.to_dict()})


def _meta_type(value: SemanticValue) -> str | None:
    if isinstance(value, SymbolicValue):
        return value.type_expr
    return None


def _meta_properties(value: SemanticValue) -> list[str]:
    if isinstance(value, SymbolicValue):
        return list(value.properties)
    return []
