#include "neomath/semantics/engine.hpp"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <sstream>
#include <type_traits>

#include "neomath/algebra/polynomial.hpp"

namespace neomath {
namespace {

struct Evaluation {
    bool defined{false};
    std::optional<Rational> value;
};

struct PredicateEvaluation {
    bool defined{false};
    std::optional<Rational> leftValue;
    std::optional<Rational> rightValue;
    std::optional<bool> predicateResult;
    std::optional<Rational> residual;
};

std::string trim(const std::string& text) {
    auto first = text.begin();
    while (first != text.end() && std::isspace(static_cast<unsigned char>(*first)) != 0) {
        ++first;
    }
    auto last = text.end();
    while (last != first && std::isspace(static_cast<unsigned char>(*(last - 1))) != 0) {
        --last;
    }
    return {first, last};
}

/// Map machine reason codes to non-empty student-facing Chinese copy.
/// The structured code remains on MathState::reason / API fields.
std::string userFacingReason(const std::string& reason) {
    if (reason == "INTEGER_OVERFLOW") {
        return "精确有理数运算超出 64 位整数范围（INTEGER_OVERFLOW）。请改用更小的中间量，"
               "或把推导拆成多步。";
    }
    if (reason == "DIVISION_BY_ZERO") {
        return "出现了除以零（DIVISION_BY_ZERO），该步在当前定义下无意义。";
    }
    if (reason == "ANALYSIS_TIME_LIMIT") {
        return "分析超时（ANALYSIS_TIME_LIMIT）。请缩短推导或降低表达式复杂度。";
    }
    if (reason == "POLYNOMIAL_DEGREE_LIMIT") {
        return "多项式次数超出当前限制（POLYNOMIAL_DEGREE_LIMIT）。";
    }
    if (reason.empty()) {
        return "当前步骤暂时无法验证。";
    }
    return reason;
}

Evaluation evaluateExpression(const Expression& expression, const Rational& x) {
    try {
        return std::visit(
            [&x](const auto& node) -> Evaluation {
                using T = std::decay_t<decltype(node)>;
                if constexpr (std::is_same_v<T, IntegerExpr>) {
                    return {true, Rational{node.value}};
                } else if constexpr (std::is_same_v<T, RationalExpr>) {
                    return {true, node.value};
                } else if constexpr (std::is_same_v<T, SymbolExpr>) {
                    return node.name == "x" ? Evaluation{true, x} : Evaluation{};
                } else if constexpr (std::is_same_v<T, std::shared_ptr<const UnaryExpr>>) {
                    const auto operand = evaluateExpression(node->operand, x);
                    if (!operand.defined || !operand.value.has_value()) {
                        return {};
                    }
                    return {true, -(*operand.value)};
                } else if constexpr (std::is_same_v<T, std::shared_ptr<const SquareRootExpr>>) {
                    const auto operand = evaluateExpression(node->operand, x);
                    if (!operand.defined || !operand.value.has_value()) {
                        return {};
                    }
                    Rational root;
                    if (!exactSquareRoot(*operand.value, root)) {
                        return {};
                    }
                    return {true, root};
                } else {
                    const auto left = evaluateExpression(node->left, x);
                    const auto right = evaluateExpression(node->right, x);
                    if (!left.defined || !right.defined || !left.value.has_value() ||
                        !right.value.has_value()) {
                        return {};
                    }
                    switch (node->op) {
                        case BinaryOperator::Add:
                            return {true, *left.value + *right.value};
                        case BinaryOperator::Subtract:
                            return {true, *left.value - *right.value};
                        case BinaryOperator::Multiply:
                            return {true, *left.value * *right.value};
                        case BinaryOperator::Divide:
                            if (right.value->isZero()) {
                                return {};
                            }
                            return {true, *left.value / *right.value};
                        case BinaryOperator::Power: {
                            if (!right.value->isInteger() || right.value->numerator() < 0 ||
                                right.value->numerator() > 16) {
                                return {};
                            }
                            return {true, pow(*left.value, static_cast<std::uint32_t>(
                                                               right.value->numerator()))};
                        }
                    }
                    return {};
                }
            },
            expression);
    } catch (const MathError&) {
        return {};
    }
}

std::pair<bool, std::optional<bool>> evaluateEquality(const EqualityPredicate& equality,
                                                      const Rational& x) {
    const auto left = evaluateExpression(equality.left, x);
    const auto right = evaluateExpression(equality.right, x);
    const bool defined = left.defined && right.defined;
    if (!defined || !left.value.has_value() || !right.value.has_value()) {
        return {false, std::nullopt};
    }
    return {true, *left.value == *right.value};
}

std::pair<bool, std::optional<bool>> evaluatePredicate(const Predicate& predicate,
                                                       const Rational& x) {
    bool anyDefined = false;
    for (const auto& alternative : predicate.alternatives) {
        const auto [defined, result] = evaluateEquality(alternative, x);
        anyDefined = anyDefined || defined;
        if (defined && result.value_or(false)) {
            return {true, true};
        }
    }
    if (!anyDefined) {
        return {false, std::nullopt};
    }
    return {true, false};
}

PredicateEvaluation evaluatePredicateDetailed(const Predicate& predicate, const Rational& x) {
    PredicateEvaluation fallback;
    for (const auto& equality : predicate.alternatives) {
        const auto left = evaluateExpression(equality.left, x);
        const auto right = evaluateExpression(equality.right, x);
        if (!left.defined || !right.defined || !left.value.has_value() ||
            !right.value.has_value()) {
            continue;
        }
        PredicateEvaluation current{true, left.value, right.value, *left.value == *right.value,
                                    *left.value - *right.value};
        if (current.predicateResult.value_or(false)) {
            return current;
        }
        if (!fallback.defined) {
            fallback = std::move(current);
        }
    }
    return fallback;
}

void addDenominatorExclusions(const RationalFunction& function, std::set<Rational>& exclusions) {
    for (const auto& root : rationalRoots(function.denominator)) {
        exclusions.insert(root);
    }
}

DomainSet domainForExpression(const Expression& expression) {
    DomainSet domain;
    const auto function = toRationalFunction(expression);
    if (function.value.has_value()) {
        addDenominatorExclusions(*function.value, domain.excluded);
        if (!domain.excluded.empty()) {
            domain.kind = DomainKind::RealExcludingFinite;
        }
        return domain;
    }

    const auto* squareRoot = std::get_if<std::shared_ptr<const SquareRootExpr>>(&expression);
    if (squareRoot == nullptr) {
        domain.kind = DomainKind::Unverified;
        return domain;
    }
    const auto operand = toRationalFunction((*squareRoot)->operand);
    if (!operand.value.has_value() || operand.value->denominator.degree() > 0 ||
        operand.value->numerator.degree() > 1) {
        domain.kind = DomainKind::Unverified;
        return domain;
    }
    const auto slope = operand.value->numerator.coefficient(1);
    const auto intercept = operand.value->numerator.coefficient(0);
    if (slope.isZero()) {
        domain.kind = intercept < Rational{0} ? DomainKind::Empty : DomainKind::AllReal;
        return domain;
    }
    const auto boundary = -intercept / slope;
    domain.kind = DomainKind::Interval;
    if (slope > Rational{0}) {
        domain.lower = boundary;
    } else {
        domain.upper = boundary;
    }
    return domain;
}

DomainSet intersectDomains(const DomainSet& left, const DomainSet& right) {
    if (left.kind == DomainKind::Empty || right.kind == DomainKind::Empty) {
        return {DomainKind::Empty};
    }
    if (left.kind == DomainKind::Unverified || right.kind == DomainKind::Unverified) {
        return {DomainKind::Unverified};
    }
    if (left.kind == DomainKind::Interval) {
        return left;
    }
    if (right.kind == DomainKind::Interval) {
        return right;
    }
    DomainSet result;
    result.excluded = left.excluded;
    result.excluded.insert(right.excluded.begin(), right.excluded.end());
    result.kind = result.excluded.empty() ? DomainKind::AllReal : DomainKind::RealExcludingFinite;
    return result;
}

struct EqualityAnalysis {
    DomainSet domain;
    SolutionSet solutions;
    std::vector<SolutionVerification> verifications;
    VerificationStatus status{VerificationStatus::Unverified};
    std::string reason;
};

bool domainContains(const DomainSet& domain, const Rational& value);

EqualityAnalysis analyzeSquareRootEquality(const EqualityPredicate& equality,
                                           const std::shared_ptr<const SquareRootExpr>& squareRoot,
                                           const Expression& other, const bool rootOnLeft) {
    EqualityAnalysis analysis;
    analysis.domain =
        intersectDomains(domainForExpression(equality.left), domainForExpression(equality.right));

    const auto operand = toRationalFunction(squareRoot->operand, 2);
    const auto otherFunction = toRationalFunction(other, 2);
    if (!operand.value.has_value() || !otherFunction.value.has_value() ||
        operand.value->denominator.degree() > 0 || otherFunction.value->denominator.degree() > 0 ||
        operand.value->numerator.degree() > 1 || otherFunction.value->numerator.degree() > 1) {
        analysis.reason = "square_root_form_not_supported";
        return analysis;
    }

    const auto equation =
        operand.value->numerator - otherFunction.value->numerator * otherFunction.value->numerator;
    if (equation.degree() > 2) {
        analysis.reason = "squared_equation_degree_limit";
        return analysis;
    }
    const auto candidates = rationalRoots(equation);
    analysis.solutions.kind = SolutionKind::Finite;
    for (const auto& candidate : candidates) {
        const auto [defined, result] = evaluateEquality(equality, candidate);
        const auto inDomain = domainContains(analysis.domain, candidate);
        const auto accepted = inDomain && defined && result.value_or(false);
        analysis.verifications.push_back(
            {candidate, inDomain, result, VerificationStatus::Verified,
             accepted ? std::optional<std::string>{"accepted"}
                      : std::optional<std::string>{!inDomain  ? "outside_domain"
                                                   : !defined ? "undefined_in_original_predicate"
                                                              : "rejected_by_original_predicate"}});
        if (accepted) {
            analysis.solutions.values.insert(candidate);
        }
    }
    if (analysis.solutions.values.empty()) {
        analysis.solutions.kind = SolutionKind::Empty;
    }
    analysis.status = VerificationStatus::Verified;
    analysis.reason =
        rootOnLeft ? "verified_square_root_equation" : "verified_square_root_equation_swapped";
    return analysis;
}

EqualityAnalysis analyzeEquality(const EqualityPredicate& equality) {
    if (const auto* root = std::get_if<std::shared_ptr<const SquareRootExpr>>(&equality.left)) {
        return analyzeSquareRootEquality(equality, *root, equality.right, true);
    }
    if (const auto* root = std::get_if<std::shared_ptr<const SquareRootExpr>>(&equality.right)) {
        return analyzeSquareRootEquality(equality, *root, equality.left, false);
    }

    EqualityAnalysis analysis;
    analysis.domain =
        intersectDomains(domainForExpression(equality.left), domainForExpression(equality.right));
    const auto left = toRationalFunction(equality.left, 4);
    const auto right = toRationalFunction(equality.right, 4);
    if (!left.value.has_value() || !right.value.has_value()) {
        analysis.reason = !left.value.has_value() ? left.reason : right.reason;
        return analysis;
    }

    const auto equation = left.value->denominator == right.value->denominator
                              ? left.value->numerator - right.value->numerator
                              : left.value->numerator * right.value->denominator -
                                    right.value->numerator * left.value->denominator;
    std::set<Rational> exclusions;
    addDenominatorExclusions(*left.value, exclusions);
    addDenominatorExclusions(*right.value, exclusions);

    if (equation.isZero()) {
        analysis.solutions.excluded = exclusions;
        analysis.solutions.kind =
            exclusions.empty() ? SolutionKind::AllReal : SolutionKind::AllRealExcludingFinite;
        analysis.status = VerificationStatus::Verified;
        analysis.reason = exclusions.empty() ? "identity" : "identity_with_domain_exclusions";
        return analysis;
    }
    if (equation.degree() == 0) {
        analysis.solutions.kind = SolutionKind::Empty;
        analysis.status = VerificationStatus::Verified;
        analysis.reason = "contradiction";
        return analysis;
    }
    if (equation.degree() > 2) {
        analysis.reason = "solver_supports_degree_at_most_two";
        return analysis;
    }
    if (equation.degree() == 2) {
        const auto a = equation.coefficient(2);
        const auto b = equation.coefficient(1);
        const auto c = equation.coefficient(0);
        const auto discriminant = b * b - Rational{4} * a * c;
        if (discriminant < Rational{0}) {
            analysis.solutions.kind = SolutionKind::Empty;
            analysis.status = VerificationStatus::Verified;
            analysis.reason = "negative_discriminant";
            return analysis;
        }
        Rational root;
        if (!exactSquareRoot(discriminant, root)) {
            analysis.reason = "irrational_roots_not_representable_in_v1";
            return analysis;
        }
    }
    analysis.solutions.kind = SolutionKind::Finite;
    for (const auto& candidate : rationalRoots(equation)) {
        const auto inDomain =
            !exclusions.contains(candidate) && domainContains(analysis.domain, candidate);
        if (exclusions.contains(candidate)) {
            analysis.verifications.push_back({candidate, false, std::nullopt,
                                              VerificationStatus::Verified, "excluded_by_domain"});
            continue;
        }
        const auto [defined, result] = evaluateEquality(equality, candidate);
        const auto accepted = inDomain && defined && result.value_or(false);
        analysis.verifications.push_back(
            {candidate, inDomain, result, VerificationStatus::Verified,
             accepted ? std::optional<std::string>{"accepted"}
                      : std::optional<std::string>{!inDomain  ? "outside_domain"
                                                   : !defined ? "undefined_in_original_predicate"
                                                              : "rejected_by_original_predicate"}});
        if (accepted) {
            analysis.solutions.values.insert(candidate);
        }
    }
    if (analysis.solutions.values.empty()) {
        analysis.solutions.kind = SolutionKind::Empty;
    }
    analysis.status = VerificationStatus::Verified;
    analysis.reason = "exact_rational_solver";
    return analysis;
}

bool solutionContains(const SolutionSet& set, const Rational& value) {
    switch (set.kind) {
        case SolutionKind::Finite:
            return set.values.contains(value);
        case SolutionKind::Empty:
            return false;
        case SolutionKind::AllReal:
            return true;
        case SolutionKind::AllRealExcludingFinite:
            return !set.excluded.contains(value);
        case SolutionKind::Unverified:
            return false;
    }
    return false;
}

bool equalSolutions(const SolutionSet& left, const SolutionSet& right) {
    return left.kind == right.kind && left.values == right.values &&
           left.excluded == right.excluded;
}

bool subsetOf(const SolutionSet& left, const SolutionSet& right) {
    if (left.kind == SolutionKind::Empty) {
        return true;
    }
    if (right.kind == SolutionKind::AllReal) {
        return true;
    }
    if (left.kind == SolutionKind::Finite) {
        return std::all_of(left.values.begin(), left.values.end(), [&right](const Rational& value) {
            return solutionContains(right, value);
        });
    }
    if (left.kind == SolutionKind::AllRealExcludingFinite &&
        right.kind == SolutionKind::AllRealExcludingFinite) {
        return std::includes(left.excluded.begin(), left.excluded.end(), right.excluded.begin(),
                             right.excluded.end());
    }
    return left.kind == right.kind;
}

bool domainContains(const DomainSet& domain, const Rational& value) {
    switch (domain.kind) {
        case DomainKind::AllReal:
            return true;
        case DomainKind::Empty:
            return false;
        case DomainKind::RealExcludingFinite:
            return !domain.excluded.contains(value);
        case DomainKind::Interval:
            if (domain.lower.has_value() &&
                (value < *domain.lower || (!domain.lowerInclusive && value == *domain.lower))) {
                return false;
            }
            if (domain.upper.has_value() &&
                (value > *domain.upper || (!domain.upperInclusive && value == *domain.upper))) {
                return false;
            }
            return true;
        case DomainKind::Union:
            return false;
        case DomainKind::Unverified:
            return false;
    }
    return false;
}

bool equalDomains(const DomainSet& left, const DomainSet& right) {
    return left.kind == right.kind && left.excluded == right.excluded &&
           left.lower == right.lower && left.upper == right.upper &&
           left.lowerInclusive == right.lowerInclusive &&
           left.upperInclusive == right.upperInclusive;
}

ProbeEvaluation makeProbe(const Predicate& previous, const Predicate& current,
                          const Rational& value, const std::string& reason) {
    const auto previousEvaluation = evaluatePredicateDetailed(previous, value);
    const auto currentEvaluation = evaluatePredicateDetailed(current, value);
    return {value,
            previousEvaluation.defined,
            currentEvaluation.defined,
            previousEvaluation.predicateResult,
            currentEvaluation.predicateResult,
            previousEvaluation.leftValue,
            previousEvaluation.rightValue,
            currentEvaluation.leftValue,
            currentEvaluation.rightValue,
            previousEvaluation.residual,
            currentEvaluation.residual,
            reason};
}

StepRelation compareStates(const MathState& previous, const Predicate& previousPredicate,
                           const MathState& current, const Predicate& currentPredicate) {
    StepRelation relation;
    if (previous.verificationStatus != VerificationStatus::Verified ||
        current.verificationStatus != VerificationStatus::Verified) {
        relation.reason = "one_or_both_steps_unverified";
        return relation;
    }

    if (previous.solutionSet.kind == SolutionKind::Finite) {
        for (const auto& value : previous.solutionSet.values) {
            if (!solutionContains(current.solutionSet, value)) {
                relation.lostSolutions.push_back(value);
            }
        }
    }
    if (current.solutionSet.kind == SolutionKind::Finite) {
        for (const auto& value : current.solutionSet.values) {
            if (!solutionContains(previous.solutionSet, value)) {
                relation.gainedSolutions.push_back(value);
            }
        }
    }
    const bool previousSubsetCurrent = subsetOf(previous.solutionSet, current.solutionSet);
    const bool currentSubsetPrevious = subsetOf(current.solutionSet, previous.solutionSet);
    if (previousSubsetCurrent && currentSubsetPrevious &&
        equalSolutions(previous.solutionSet, current.solutionSet)) {
        relation.relation = equalDomains(previous.domain, current.domain)
                                ? RelationKind::Equivalent
                                : RelationKind::ConditionEquivalent;
    } else if (currentSubsetPrevious) {
        relation.relation = RelationKind::ForwardImplication;
    } else if (previousSubsetCurrent) {
        relation.relation = RelationKind::ReverseImplication;
    } else {
        relation.relation = RelationKind::Unrelated;
    }

    relation.domainExpanded = false;
    relation.domainShrunk = false;
    for (const auto& value : previous.domain.excluded) {
        if (domainContains(current.domain, value)) {
            relation.domainExpanded = true;
            if (!relation.probe.has_value()) {
                relation.probe =
                    makeProbe(previousPredicate, currentPredicate, value, "domain_expansion");
            }
        }
    }
    for (const auto& value : current.domain.excluded) {
        if (domainContains(previous.domain, value)) {
            relation.domainShrunk = true;
            if (!relation.probe.has_value()) {
                relation.probe =
                    makeProbe(previousPredicate, currentPredicate, value, "domain_shrink");
            }
        }
    }
    if (!relation.lostSolutions.empty()) {
        relation.probe = makeProbe(previousPredicate, currentPredicate,
                                   relation.lostSolutions.front(), "lost_solution");
    } else if (!relation.gainedSolutions.empty()) {
        relation.probe = makeProbe(previousPredicate, currentPredicate,
                                   relation.gainedSolutions.front(), "gained_solution");
    } else if (!relation.probe.has_value() &&
               !equalSolutions(previous.solutionSet, current.solutionSet)) {
        if (previous.solutionSet.kind == SolutionKind::AllRealExcludingFinite &&
            current.solutionSet.kind == SolutionKind::AllReal) {
            const auto value = *previous.solutionSet.excluded.begin();
            relation.probe =
                makeProbe(previousPredicate, currentPredicate, value, "gained_solution");
        } else if (previous.solutionSet.kind == SolutionKind::AllReal &&
                   current.solutionSet.kind == SolutionKind::AllRealExcludingFinite) {
            const auto value = *current.solutionSet.excluded.begin();
            relation.probe = makeProbe(previousPredicate, currentPredicate, value, "lost_solution");
        }
    }

    if (relation.relation == RelationKind::Equivalent) {
        relation.reason = "solution_set_and_domain_preserved";
    } else if (relation.domainExpanded) {
        relation.reason = "domain_expanded";
    } else if (!relation.lostSolutions.empty()) {
        relation.reason = "solutions_lost";
    } else if (!relation.gainedSolutions.empty()) {
        relation.reason = "solutions_gained";
    } else {
        relation.reason = "semantic_relation_changed";
    }
    if (!relation.lostSolutions.empty() && !relation.gainedSolutions.empty()) {
        relation.type = StepRelationType::SolutionChanged;
    } else if (!relation.lostSolutions.empty()) {
        relation.type = StepRelationType::SolutionLoss;
    } else if (!relation.gainedSolutions.empty()) {
        relation.type = StepRelationType::SolutionGain;
    } else if (relation.domainExpanded) {
        relation.type = StepRelationType::DomainExpanded;
    } else if (relation.domainShrunk) {
        relation.type = StepRelationType::DomainRestricted;
    } else {
        switch (relation.relation) {
            case RelationKind::Equivalent:
                relation.type = StepRelationType::Equivalent;
                break;
            case RelationKind::ConditionEquivalent:
                relation.type = StepRelationType::ConditionalEquivalence;
                break;
            case RelationKind::ForwardImplication:
            case RelationKind::ReverseImplication:
                relation.type = StepRelationType::ImplicationOnly;
                break;
            case RelationKind::Unrelated:
                relation.type = StepRelationType::NonEquivalent;
                break;
            case RelationKind::Unverified:
                relation.type = StepRelationType::Unverified;
                break;
        }
    }
    return relation;
}

std::string solutionSource(const SolutionSet& solution) {
    if (solution.kind == SolutionKind::Empty) {
        return "0 = 1";
    }
    if (solution.kind != SolutionKind::Finite || solution.values.empty()) {
        return "";
    }
    std::ostringstream output;
    bool first = true;
    for (const auto& value : solution.values) {
        if (!first) {
            output << " or ";
        }
        output << "x = " << value.toString();
        first = false;
    }
    return output.str();
}

std::optional<Polynomial> equationPolynomial(const EqualityPredicate& equality) {
    const auto left = toRationalFunction(equality.left, 4);
    const auto right = toRationalFunction(equality.right, 4);
    if (!left.value.has_value() || !right.value.has_value() ||
        left.value->denominator.degree() > 0 || right.value->denominator.degree() > 0) {
        return std::nullopt;
    }
    return left.value->numerator * right.value->denominator -
           right.value->numerator * left.value->denominator;
}

std::optional<std::string> polynomialPreview(const EqualityPredicate& equality) {
    const auto polynomial = equationPolynomial(equality);
    if (!polynomial.has_value()) {
        return std::nullopt;
    }
    return polynomial->toString() + " = 0";
}

std::string linearFactor(const Rational& root) {
    if (root.isZero()) {
        return "x";
    }
    if (root < Rational{0}) {
        return "(x + " + (-root).toString() + ")";
    }
    return "(x - " + root.toString() + ")";
}

std::optional<std::string> factorPreview(const EqualityPredicate& equality) {
    const auto polynomial = equationPolynomial(equality);
    if (!polynomial.has_value() || polynomial->degree() != 2) {
        return std::nullopt;
    }
    const auto roots = rationalRoots(*polynomial);
    if (roots.empty()) {
        return std::nullopt;
    }
    std::string factors;
    if (polynomial->coefficient(2) != Rational{1}) {
        factors += polynomial->coefficient(2).toString() + "*";
    }
    factors += linearFactor(roots.back());
    if (roots.size() == 1) {
        factors += "^2";
    } else {
        factors += linearFactor(roots.front());
    }
    return factors + " = 0";
}

std::optional<std::string> argumentExpression(const std::optional<std::string>& argument) {
    if (!argument.has_value() || trim(*argument).empty()) {
        return std::nullopt;
    }
    const auto parsed = parsePredicate(trim(*argument) + " = 0");
    if (!parsed.predicate.has_value() || parsed.predicate->alternatives.size() != 1) {
        return std::nullopt;
    }
    return printExpression(parsed.predicate->alternatives.front().left);
}

std::optional<std::string> binaryTransformationPreview(const Predicate& predicate,
                                                       const std::string& operation,
                                                       const std::optional<std::string>& argument) {
    if (predicate.alternatives.size() != 1) {
        return std::nullopt;
    }
    const auto operand = argumentExpression(argument);
    if (!operand.has_value()) {
        return std::nullopt;
    }
    const auto& equality = predicate.alternatives.front();
    return "(" + printExpression(equality.left) + ") " + operation + " (" + *operand + ") = (" +
           printExpression(equality.right) + ") " + operation + " (" + *operand + ")";
}

std::optional<std::string> squareTransformationPreview(const Predicate& predicate) {
    if (predicate.alternatives.size() != 1) {
        return std::nullopt;
    }
    const auto& equality = predicate.alternatives.front();
    const auto squareSide = [](const Expression& expression) {
        if (const auto* root = std::get_if<std::shared_ptr<const SquareRootExpr>>(&expression)) {
            return printExpression((*root)->operand);
        }
        return "(" + printExpression(expression) + ")^2";
    };
    return squareSide(equality.left) + " = " + squareSide(equality.right);
}

bool certificateCondition(const TransformationKind kind, const MathState& before,
                          const MathState& after) {
    switch (kind) {
        case TransformationKind::Factor:
        case TransformationKind::Expand:
        case TransformationKind::MoveTerms:
        case TransformationKind::Verify:
            return equalSolutions(before.solutionSet, after.solutionSet) &&
                   equalDomains(before.domain, after.domain);
        case TransformationKind::Solve:
            return equalSolutions(before.solutionSet, after.solutionSet);
        case TransformationKind::Multiply:
        case TransformationKind::SquareBothSides:
            return subsetOf(before.solutionSet, after.solutionSet);
        case TransformationKind::Divide:
            return subsetOf(after.solutionSet, before.solutionSet);
        case TransformationKind::Unsupported:
            return false;
    }
    return false;
}

bool provablyNonzeroConstant(const std::optional<std::string>& argument) {
    const auto operand = argumentExpression(argument);
    if (!operand.has_value()) {
        return false;
    }
    const auto parsed = parsePredicate(*operand + " = 0");
    if (!parsed.predicate.has_value()) {
        return false;
    }
    const auto converted = toRationalFunction(parsed.predicate->alternatives.front().left);
    return converted.value.has_value() && converted.value->numerator.degree() == 0 &&
           converted.value->denominator.degree() == 0 &&
           !converted.value->numerator.coefficient(0).isZero();
}

}  // namespace

Document parseDocument(const std::string& source, const ExecutionLimits& limits) {
    Document document;
    document.source = source;
    document.limits = limits;
    std::istringstream lines(source);
    std::string line;
    while (std::getline(lines, line)) {
        auto content = trim(line);
        if (content.empty() || content.starts_with("#")) {
            continue;
        }
        if (document.steps.size() >= limits.maxDocumentSteps) {
            DocumentStep step;
            step.source = content;
            step.error = ParseError{"DOCUMENT_STEP_LIMIT",
                                    "document step limit exceeded",
                                    0,
                                    content.size(),
                                    {},
                                    std::nullopt,
                                    std::nullopt};
            document.steps.push_back(std::move(step));
            break;
        }
        DocumentStep step;
        if (content.starts_with("::expr ")) {
            content = trim(content.substr(7));
        } else if (content.starts_with("^")) {
            step.source = content;
            step.kind = "command";
            document.steps.push_back(std::move(step));
            continue;
        }
        step.source = content;
        const auto parsed = parsePredicate(content, limits);
        step.predicate = parsed.predicate;
        step.error = parsed.error;
        document.steps.push_back(std::move(step));
    }
    return document;
}

MathState analyzePredicate(const Predicate& predicate, const std::string& source) {
    MathState state;
    state.source = source;
    state.canonical = printPredicate(predicate);
    if (predicate.alternatives.empty()) {
        state.reason = "empty_predicate";
        return state;
    }
    bool first = true;
    for (const auto& equality : predicate.alternatives) {
        const auto equalityAnalysis = analyzeEquality(equality);
        state.solutionVerifications.insert(state.solutionVerifications.end(),
                                           equalityAnalysis.verifications.begin(),
                                           equalityAnalysis.verifications.end());
        if (equalityAnalysis.status != VerificationStatus::Verified) {
            state.reason = equalityAnalysis.reason;
            state.verificationStatus = equalityAnalysis.status;
            return state;
        }
        if (first) {
            state.domain = equalityAnalysis.domain;
            state.solutionSet = equalityAnalysis.solutions;
            first = false;
            continue;
        }
        if (state.solutionSet.kind == SolutionKind::Finite ||
            state.solutionSet.kind == SolutionKind::Empty) {
            state.solutionSet.kind = SolutionKind::Finite;
            state.solutionSet.values.insert(equalityAnalysis.solutions.values.begin(),
                                            equalityAnalysis.solutions.values.end());
            if (state.solutionSet.values.empty()) {
                state.solutionSet.kind = SolutionKind::Empty;
            }
        } else if (equalityAnalysis.solutions.kind == SolutionKind::AllReal) {
            state.solutionSet.kind = SolutionKind::AllReal;
            state.solutionSet.excluded.clear();
        } else {
            state.reason = "disjunction_with_infinite_solution_set_not_supported";
            return state;
        }
    }
    for (const auto& excluded : state.domain.excluded) {
        state.assumptions.push_back(
            {"DOMAIN_EXCLUSION", "x != " + excluded.toString(), "原式在该值处没有定义"});
    }
    state.verificationStatus = VerificationStatus::Verified;
    state.reason = predicate.alternatives.size() > 1 ? "verified_disjunction" : "verified";
    return state;
}

ExecutionTrace replayTrace(const Document& document, const ExecutionTrace& cachedTrace,
                           const std::size_t reusableStates) {
    const auto started = std::chrono::steady_clock::now();
    const auto ensureWithinTimeLimit = [&document, &started] {
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started);
        if (elapsed > document.limits.maxAnalysisTime) {
            throw MathError("ANALYSIS_TIME_LIMIT", "analysis exceeded the configured time limit");
        }
    };
    ExecutionTrace trace;
    std::vector<const Predicate*> predicates;
    for (const auto& step : document.steps) {
        if (step.kind != "expression") {
            continue;
        }
        predicates.push_back(step.predicate.has_value() ? &*step.predicate : nullptr);
    }

    auto reusable = std::min({reusableStates, predicates.size(), cachedTrace.states.size(),
                              cachedTrace.diagnostics.size()});
    if (reusable > 1) {
        reusable = std::min(reusable, cachedTrace.relations.size() + 1);
    }
    trace.states.insert(trace.states.end(), cachedTrace.states.begin(),
                        cachedTrace.states.begin() + reusable);
    trace.diagnostics.insert(trace.diagnostics.end(), cachedTrace.diagnostics.begin(),
                             cachedTrace.diagnostics.begin() + reusable);
    const auto reusableRelations =
        reusable == 0 ? std::size_t{0} : std::min(reusable - 1, cachedTrace.relations.size());
    trace.relations.insert(trace.relations.end(), cachedTrace.relations.begin(),
                           cachedTrace.relations.begin() + reusableRelations);

    bool rootFaultSeen = false;
    if (cachedTrace.breakpointStep.has_value() && *cachedTrace.breakpointStep < reusable) {
        rootFaultSeen = true;
        trace.breakpointStep = cachedTrace.breakpointStep;
        trace.activeProbe = cachedTrace.activeProbe;
    }

    std::size_t expressionIndex = 0;
    for (const auto& step : document.steps) {
        if (step.kind != "expression") {
            continue;
        }
        if (expressionIndex++ < reusable) {
            continue;
        }
        if (!step.predicate.has_value()) {
            MathState state;
            state.source = step.source;
            state.reason = step.error.has_value() ? step.error->code : "parse_error";
            trace.states.push_back(std::move(state));
            continue;
        }
        trace.states.push_back(analyzePredicate(*step.predicate, step.source));
        ensureWithinTimeLimit();
    }

    for (std::size_t index = reusable; index < trace.states.size(); ++index) {
        StepDiagnostic diagnostic;
        if (index == 0) {
            if (trace.states[index].verificationStatus == VerificationStatus::Verified) {
                diagnostic = {DiagnosticStatus::Valid, "起点", "已建立精确数学状态"};
            } else {
                diagnostic = {DiagnosticStatus::Unverified, "暂时无法验证",
                              userFacingReason(trace.states[index].reason)};
            }
        } else if (predicates[index - 1] == nullptr || predicates[index] == nullptr) {
            StepRelation relation;
            relation.reason = "parse_error";
            trace.relations.push_back(std::move(relation));
            diagnostic = {DiagnosticStatus::Unverified, "暂时无法验证", "步骤无法解析"};
        } else {
            auto relation = compareStates(trace.states[index - 1], *predicates[index - 1],
                                          trace.states[index], *predicates[index]);
            const bool faulty = relation.relation != RelationKind::Equivalent &&
                                relation.relation != RelationKind::ConditionEquivalent;
            if (faulty && !rootFaultSeen) {
                rootFaultSeen = true;
                trace.breakpointStep = index;
                diagnostic = {DiagnosticStatus::RootFault, "根本问题",
                              userFacingReason(relation.reason)};
                if (relation.probe.has_value()) {
                    trace.activeProbe = relation.probe;
                }
            } else if (rootFaultSeen && faulty) {
                diagnostic = {DiagnosticStatus::IndependentFault, "新的独立问题",
                              userFacingReason(relation.reason)};
            } else if (rootFaultSeen) {
                diagnostic = {DiagnosticStatus::Tainted, "受前一步影响",
                              "当前步骤基于已经改变的数学状态"};
            } else {
                diagnostic = {DiagnosticStatus::Valid, "等价步骤",
                              userFacingReason(relation.reason)};
            }
            trace.relations.push_back(std::move(relation));
            ensureWithinTimeLimit();
        }
        trace.diagnostics.push_back(std::move(diagnostic));
    }
    trace.durationMs =
        std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started)
            .count();
    return trace;
}

ExecutionTrace runTrace(const Document& document) {
    return replayTrace(document, ExecutionTrace{}, 0);
}

std::vector<ProbeStepEvaluation> evaluateProbe(const Document& document, const Rational& value) {
    std::vector<ProbeStepEvaluation> evaluations;
    std::size_t expressionStep = 0;
    for (const auto& step : document.steps) {
        if (step.kind != "expression") {
            continue;
        }
        ProbeStepEvaluation result;
        result.step = expressionStep++;
        result.value = value;
        if (!step.predicate.has_value()) {
            result.reason = step.error.has_value() ? std::optional<std::string>{step.error->code}
                                                   : std::optional<std::string>{"parse_error"};
            evaluations.push_back(std::move(result));
            continue;
        }
        const auto evaluation = evaluatePredicateDetailed(*step.predicate, value);
        result.defined = evaluation.defined;
        result.leftValue = evaluation.leftValue;
        result.rightValue = evaluation.rightValue;
        result.predicateResult = evaluation.predicateResult;
        result.residual = evaluation.residual;
        if (!evaluation.defined) {
            result.reason = "undefined_at_probe";
        }
        evaluations.push_back(std::move(result));
    }
    return evaluations;
}

std::vector<Completion> getCompletions(const Document& document, const std::size_t step) {
    if (step >= document.steps.size() || !document.steps[step].predicate.has_value()) {
        return {};
    }
    const auto& predicate = *document.steps[step].predicate;
    const auto state = analyzePredicate(predicate, document.steps[step].source);
    std::vector<Completion> completions;
    const auto solve = solutionSource(state.solutionSet);
    completions.push_back({"solve", "求解", "safe", !solve.empty(),
                           solve.empty() ? "solution_form_not_available" : "verified_solution_set",
                           solve});
    const auto factor = predicate.alternatives.size() == 1
                            ? factorPreview(predicate.alternatives.front())
                            : std::nullopt;
    completions.push_back(
        {"factor", "因式分解", "safe", factor.has_value(),
         factor.has_value() ? "difference_of_squares" : "not_a_supported_difference_of_squares",
         factor.value_or("")});
    completions.push_back({"expand", "展开并整理", "safe",
                           predicate.alternatives.size() == 1 &&
                               polynomialPreview(predicate.alternatives.front()).has_value(),
                           "canonical_polynomial_form",
                           predicate.alternatives.size() == 1
                               ? polynomialPreview(predicate.alternatives.front()).value_or("")
                               : ""});
    completions.push_back({"move_terms", "移到等号左边", "safe",
                           predicate.alternatives.size() == 1 &&
                               polynomialPreview(predicate.alternatives.front()).has_value(),
                           "move_all_terms_left",
                           predicate.alternatives.size() == 1
                               ? polynomialPreview(predicate.alternatives.front()).value_or("")
                               : ""});
    completions.push_back(
        {"multiply", "两边乘以 2", "safe", predicate.alternatives.size() == 1,
         "nonzero_constant_multiplier",
         binaryTransformationPreview(predicate, "*", std::string{"2"}).value_or("")});
    completions.push_back(
        {"divide", "两边除以 2", "safe", predicate.alternatives.size() == 1,
         "nonzero_constant_divisor",
         binaryTransformationPreview(predicate, "/", std::string{"2"}).value_or("")});
    completions.push_back({"square_both_sides", "两边平方", "may_add_solutions",
                           predicate.alternatives.size() == 1, "source_implies_squared_equation",
                           squareTransformationPreview(predicate).value_or("")});
    completions.push_back({"verify", "验证当前步骤", "safe",
                           state.verificationStatus == VerificationStatus::Verified, state.reason,
                           printPredicate(predicate)});
    return completions;
}

TransformationResult executeTransformation(const Document& document, const std::size_t step,
                                           const std::string& intent,
                                           const std::optional<std::string>& argument) {
    TransformationResult result;
    if (step >= document.steps.size() || !document.steps[step].predicate.has_value()) {
        result.reason = "invalid_step";
        return result;
    }
    const auto& predicate = *document.steps[step].predicate;
    const auto before = analyzePredicate(predicate, document.steps[step].source);
    if (before.verificationStatus != VerificationStatus::Verified) {
        result.reason = "source_step_unverified";
        return result;
    }
    std::string transformed;
    std::string rule;
    TransformationKind kind{TransformationKind::Unsupported};
    VerificationMethod method{VerificationMethod::Unverified};
    auto effectiveArgument = argument;
    if (intent == "factor" && predicate.alternatives.size() == 1) {
        transformed = factorPreview(predicate.alternatives.front()).value_or("");
        rule = "difference_of_squares";
        kind = TransformationKind::Factor;
        method = VerificationMethod::ExactExpansion;
    } else if (intent == "expand" && predicate.alternatives.size() == 1) {
        transformed = polynomialPreview(predicate.alternatives.front()).value_or("");
        rule = "polynomial_normalization";
        kind = TransformationKind::Expand;
        method = VerificationMethod::PolynomialNormalization;
    } else if ((intent == "move_terms" || intent == "move_terms_left" || intent == "move") &&
               predicate.alternatives.size() == 1) {
        transformed = polynomialPreview(predicate.alternatives.front()).value_or("");
        rule = "move_all_terms_left";
        kind = TransformationKind::MoveTerms;
        method = VerificationMethod::PolynomialNormalization;
    } else if (intent == "multiply" || intent == "multiply_by") {
        if (!effectiveArgument.has_value()) {
            effectiveArgument = "2";
        }
        transformed = binaryTransformationPreview(predicate, "*", effectiveArgument).value_or("");
        rule = "multiply_both_sides";
        kind = TransformationKind::Multiply;
        method = VerificationMethod::SolutionSetComparison;
    } else if (intent == "divide" || intent == "divide_by") {
        if (!effectiveArgument.has_value()) {
            effectiveArgument = "2";
        }
        transformed = binaryTransformationPreview(predicate, "/", effectiveArgument).value_or("");
        rule = "divide_both_sides";
        kind = TransformationKind::Divide;
        method = VerificationMethod::DomainAnalysis;
    } else if (intent == "square" || intent == "square_both_sides") {
        transformed = squareTransformationPreview(predicate).value_or("");
        rule = "square_both_sides";
        kind = TransformationKind::SquareBothSides;
        method = VerificationMethod::SolutionSetComparison;
    } else if (intent == "solve") {
        transformed = solutionSource(before.solutionSet);
        rule = "exact_solution_set";
        kind = TransformationKind::Solve;
        method = VerificationMethod::ExactSubstitution;
    } else if (intent == "verify") {
        transformed = printPredicate(predicate);
        rule = "verify_current_predicate";
        kind = TransformationKind::Verify;
        method = VerificationMethod::ExactSubstitution;
    } else {
        result.reason = "unsupported_transformation";
        return result;
    }
    if (transformed.empty()) {
        result.reason = "transformation_not_available";
        return result;
    }
    const auto parsed = parseDocument(transformed);
    if (parsed.steps.empty() || !parsed.steps.front().predicate.has_value()) {
        result.reason = "generated_transformation_failed_to_parse";
        return result;
    }
    const auto after = analyzePredicate(*parsed.steps.front().predicate, transformed);
    const auto relation = compareStates(before, predicate, after, *parsed.steps.front().predicate);
    bool verified = certificateCondition(kind, before, after);
    if (kind == TransformationKind::Factor || kind == TransformationKind::Expand ||
        kind == TransformationKind::MoveTerms) {
        const auto sourcePolynomial = equationPolynomial(predicate.alternatives.front());
        const auto targetPolynomial =
            equationPolynomial(parsed.steps.front().predicate->alternatives.front());
        verified = verified && sourcePolynomial.has_value() && targetPolynomial.has_value() &&
                   *sourcePolynomial == *targetPolynomial;
    }
    if (!verified) {
        result.reason = "certificate_verification_failed";
        return result;
    }
    std::vector<Assumption> assumptions;
    if ((kind == TransformationKind::Multiply || kind == TransformationKind::Divide) &&
        !provablyNonzeroConstant(effectiveArgument)) {
        assumptions.push_back({"NONZERO", argumentExpression(effectiveArgument).value_or("unknown"),
                               "该式必须不等于 0，才能把此操作当作等价变换"});
    }
    result.applied = true;
    result.source = transformed;
    result.reason = assumptions.empty() ? "verified" : "verified_with_condition";
    result.certificate.kind = kind;
    result.certificate.rule = rule;
    result.certificate.source = printPredicate(predicate);
    result.certificate.target = printPredicate(*parsed.steps.front().predicate);
    result.certificate.requiredAssumptions = std::move(assumptions);
    result.certificate.claimedRelation = relation.relation;
    result.certificate.verificationMethod = method;
    result.certificate.status = VerificationStatus::Verified;
    result.certificate.beforeCanonical = before.canonical;
    result.certificate.afterCanonical = after.canonical;
    if (equalSolutions(before.solutionSet, after.solutionSet)) {
        result.certificate.solutionInvariant = "exact_solution_set_preserved";
    } else if (kind == TransformationKind::SquareBothSides ||
               kind == TransformationKind::Multiply) {
        result.certificate.solutionInvariant = "source_implies_target";
    } else {
        result.certificate.solutionInvariant = "target_implies_source_under_condition";
    }
    return result;
}

std::map<std::string, std::string> capabilities() {
    return {{"core", "C++20"},
            {"exactArithmetic", "int64_checked_rational"},
            {"maxIntegerBits", "63"},
            {"maxDocumentSteps", "200"},
            {"maxAstNodesPerStep", "10000"},
            {"maxAstDepth", "64"},
            {"maxAnalysisTimeMs", "500"},
            {"variables", "x"},
            {"domain", "real"},
            {"maxSolverDegree", "2"},
            {"trace", "root_fault_taint_probe"},
            {"transformations",
             "factor,expand,move_terms,divide,multiply,square_both_sides,solve,verify"},
            {"offline", "true"},
            {"apiVersion", "1"}};
}

}  // namespace neomath
