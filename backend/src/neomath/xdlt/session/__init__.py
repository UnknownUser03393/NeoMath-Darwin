"""Incremental compilation sessions and render patches."""

from __future__ import annotations

from neomath.xdlt.session.cache import (
    EnvironmentSnapshot,
    ExecutionCacheKey,
    SessionCache,
    SourceRangeIndex,
    VerificationCacheKey,
)
from neomath.xdlt.session.changes import (
    SourceChange,
    apply_changes,
    compute_source_change,
    validate_changes,
)
from neomath.xdlt.session.result import CompilationResult, IncrementalCompilationResult
from neomath.xdlt.session.session import CompilationSession

__all__ = [
    "CompilationResult",
    "CompilationSession",
    "EnvironmentSnapshot",
    "ExecutionCacheKey",
    "IncrementalCompilationResult",
    "SessionCache",
    "SourceChange",
    "SourceRangeIndex",
    "VerificationCacheKey",
    "apply_changes",
    "compute_source_change",
    "validate_changes",
]
