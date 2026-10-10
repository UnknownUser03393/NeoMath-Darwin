#pragma once

#include <chrono>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "neomath/syntax/ast.hpp"

namespace neomath {

enum class VerificationStatus { Verified, Unverified, Unsupported };
enum class DiagnosticStatus {
    Valid,
    RootFault,
    Tainted,
    IndependentFault,
    Unverified,
    Unsupported
};
enum class RelationKind {
    Equivalent,
    ConditionEquivalent,
    ForwardImplication,
    ReverseImplication,
    Unrelated,
    Unverified
};

enum class StepRelationType {
    Equivalent,
    SolutionLoss,
    SolutionGain,
    SolutionChanged,
    DomainRestricted,
    DomainExpanded,
    ConditionalEquivalence,
    ImplicationOnly,
    NonEquivalent,
    Unverified
};

enum class SolutionKind { Finite, Empty, AllReal, AllRealExcludingFinite, Unverified };

struct SolutionSet {
    SolutionKind kind{SolutionKind::Unverified};
    std::set<Rational> values;
    std::set<Rational> excluded;
};

enum class DomainKind { AllReal, Empty, RealExcludingFinite, Interval, Union, Unverified };

struct DomainSet {
    DomainKind kind{DomainKind::AllReal};
    std::set<Rational> excluded;
    std::optional<Rational> lower;
    std::optional<Rational> upper;
    bool lowerInclusive{true};
    bool upperInclusive{true};
};

struct Assumption {
    std::string code;
    std::string expression;
    std::string description;
};

struct SolutionVerification {
    Rational candidate;
    bool inDomain{false};
    std::optional<bool> predicateResult;
    VerificationStatus status{VerificationStatus::Unverified};
    std::optional<std::string> reason;
};

struct MathState {
    std::string source;
    std::string canonical;
    DomainSet domain;
    SolutionSet solutionSet;
    std::vector<Assumption> assumptions;
    std::vector<SolutionVerification> solutionVerifications;
    VerificationStatus verificationStatus{VerificationStatus::Unverified};
    std::string reason;
};

struct ProbeEvaluation {
    Rational value;
    bool previousDefined{false};
    bool currentDefined{false};
    std::optional<bool> previousPredicateResult;
    std::optional<bool> currentPredicateResult;
    std::optional<Rational> previousLeftValue;
    std::optional<Rational> previousRightValue;
    std::optional<Rational> currentLeftValue;
    std::optional<Rational> currentRightValue;
    std::optional<Rational> previousResidual;
    std::optional<Rational> currentResidual;
    std::string reason;
};

struct ProbeStepEvaluation {
    std::size_t step{};
    Rational value;
    bool defined{false};
    std::optional<Rational> leftValue;
    std::optional<Rational> rightValue;
    std::optional<bool> predicateResult;
    std::optional<Rational> residual;
    std::optional<std::string> reason;
};

struct StepRelation {
    StepRelationType type{StepRelationType::Unverified};
    RelationKind relation{RelationKind::Unverified};
    std::vector<Rational> lostSolutions;
    std::vector<Rational> gainedSolutions;
    bool domainExpanded{false};
    bool domainShrunk{false};
    std::vector<Assumption> requiredAssumptions;
    std::optional<ProbeEvaluation> probe;
    std::string reason;
};

struct StepDiagnostic {
    DiagnosticStatus status{DiagnosticStatus::Unverified};
    std::string title;
    std::string message;
};

struct ExecutionTrace {
    std::vector<MathState> states;
    std::vector<StepRelation> relations;
    std::vector<StepDiagnostic> diagnostics;
    std::optional<ProbeEvaluation> activeProbe;
    std::optional<std::size_t> breakpointStep;
    double durationMs{};
};

struct DocumentStep {
    std::string source;
    std::string kind{"expression"};
    std::optional<Predicate> predicate;
    std::optional<ParseError> error;
};

struct Document {
    std::string source;
    std::vector<DocumentStep> steps;
    ExecutionLimits limits;
};

struct Completion {
    std::string id;
    std::string label;
    std::string risk;
    bool available{false};
    std::string reason;
    std::string preview;
};

enum class TransformationKind {
    Factor,
    Expand,
    MoveTerms,
    Divide,
    Multiply,
    SquareBothSides,
    Solve,
    Verify,
    Unsupported
};

enum class VerificationMethod {
    PolynomialNormalization,
    ExactExpansion,
    ExactSubstitution,
    SolutionSetComparison,
    DomainAnalysis,
    Unverified
};

struct TransformationCertificate {
    TransformationKind kind{TransformationKind::Unsupported};
    std::string rule;
    std::string source;
    std::string target;
    std::vector<Assumption> requiredAssumptions;
    RelationKind claimedRelation{RelationKind::Unverified};
    VerificationMethod verificationMethod{VerificationMethod::Unverified};
    VerificationStatus status{VerificationStatus::Unverified};
    std::string beforeCanonical;
    std::string afterCanonical;
    std::string solutionInvariant;
};

struct TransformationResult {
    bool applied{false};
    std::string source;
    TransformationCertificate certificate;
    std::string reason;
};

[[nodiscard]] Document parseDocument(const std::string& source, const ExecutionLimits& limits = {});
[[nodiscard]] MathState analyzePredicate(const Predicate& predicate, const std::string& source);
[[nodiscard]] ExecutionTrace runTrace(const Document& document);
[[nodiscard]] ExecutionTrace replayTrace(const Document& document,
                                         const ExecutionTrace& cachedTrace,
                                         std::size_t reusableStates);
[[nodiscard]] std::vector<ProbeStepEvaluation> evaluateProbe(const Document& document,
                                                             const Rational& value);
[[nodiscard]] std::vector<Completion> getCompletions(const Document& document, std::size_t step);
[[nodiscard]] TransformationResult executeTransformation(
    const Document& document, std::size_t step, const std::string& intent,
    const std::optional<std::string>& argument = std::nullopt);
[[nodiscard]] std::map<std::string, std::string> capabilities();

}  // namespace neomath
