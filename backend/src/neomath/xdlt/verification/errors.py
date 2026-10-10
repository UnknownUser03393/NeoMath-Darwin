"""Typed errors surfaced by the verification pipeline."""


class VerificationError(Exception):
    """Base class for all verification-time errors."""


class CannotDecideError(VerificationError):
    """The backend cannot prove or disprove a statement (not a failure)."""


class UnresolvedReferenceError(VerificationError):
    """A semantic reference in SEL has no target in the entity registry."""


class InvalidReferenceTypeError(VerificationError):
    """A SEL operation needs a math value but the reference targets another kind."""


class UnsupportedOperationError(VerificationError):
    """A SEL/math construct is outside the current backend's supported subset."""


class UnsupportedRequirementError(VerificationError):
    """A ``require`` statement cannot be translated into verifier assumptions."""
