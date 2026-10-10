#include "converters.hpp"

#include <pybind11/stl.h>

#include <type_traits>

namespace neomath::bindings {
namespace {

const char* verificationName(const VerificationStatus status) {
    switch (status) {
        case VerificationStatus::Verified:
            return "verified";
        case VerificationStatus::Unverified:
            return "unverified";
        case VerificationStatus::Unsupported:
            return "unsupported";
    }
    return "unverified";
}

const char* diagnosticName(const DiagnosticStatus status) {
    switch (status) {
        case DiagnosticStatus::Valid:
            return "valid";
        case DiagnosticStatus::RootFault:
            return "root_fault";
        case DiagnosticStatus::Tainted:
            return "tainted";
        case DiagnosticStatus::IndependentFault:
            return "independent_fault";
        case DiagnosticStatus::Unverified:
            return "unverified";
        case DiagnosticStatus::Unsupported:
            return "unsupported";
    }
    return "unverified";
}

const char* relationName(const RelationKind relation) {
    switch (relation) {
        case RelationKind::Equivalent:
            return "equivalent";
        case RelationKind::ConditionEquivalent:
            return "condition_equivalent";
        case RelationKind::ForwardImplication:
            return "forward_implication";
        case RelationKind::ReverseImplication:
            return "reverse_implication";
        case RelationKind::Unrelated:
            return "unrelated";
        case RelationKind::Unverified:
            return "unverified";
    }
    return "unverified";
}

const char* stepRelationTypeName(const StepRelationType relation) {
    switch (relation) {
        case StepRelationType::Equivalent:
            return "equivalent";
        case StepRelationType::SolutionLoss:
            return "solution_loss";
        case StepRelationType::SolutionGain:
            return "solution_gain";
        case StepRelationType::SolutionChanged:
            return "solution_changed";
        case StepRelationType::DomainRestricted:
            return "domain_restricted";
        case StepRelationType::DomainExpanded:
            return "domain_expanded";
        case StepRelationType::ConditionalEquivalence:
            return "conditional_equivalence";
        case StepRelationType::ImplicationOnly:
            return "implication_only";
        case StepRelationType::NonEquivalent:
            return "non_equivalent";
        case StepRelationType::Unverified:
            return "unverified";
    }
    return "unverified";
}

const char* solutionName(const SolutionKind kind) {
    switch (kind) {
        case SolutionKind::Finite:
            return "finite";
        case SolutionKind::Empty:
            return "empty";
        case SolutionKind::AllReal:
            return "all_real";
        case SolutionKind::AllRealExcludingFinite:
            return "all_real_excluding_finite";
        case SolutionKind::Unverified:
            return "unverified";
    }
    return "unverified";
}

const char* domainName(const DomainKind kind) {
    switch (kind) {
        case DomainKind::AllReal:
            return "all_real";
        case DomainKind::Empty:
            return "empty";
        case DomainKind::RealExcludingFinite:
            return "real_excluding_finite";
        case DomainKind::Interval:
            return "interval";
        case DomainKind::Union:
            return "union";
        case DomainKind::Unverified:
            return "unverified";
    }
    return "unverified";
}

py::list rationalList(const auto& values) {
    py::list result;
    for (const auto& value : values) {
        result.append(value.toString());
    }
    return result;
}

py::dict expressionToPython(const Expression& expression) {
    return std::visit(
        [](const auto& node) -> py::dict {
            using T = std::decay_t<decltype(node)>;
            py::dict result;
            if constexpr (std::is_same_v<T, IntegerExpr>) {
                result["type"] = "integer";
                result["value"] = node.value;
                result["start"] = node.span.start;
                result["end"] = node.span.end;
            } else if constexpr (std::is_same_v<T, RationalExpr>) {
                result["type"] = "rational";
                result["value"] = node.value.toString();
                result["start"] = node.span.start;
                result["end"] = node.span.end;
            } else if constexpr (std::is_same_v<T, SymbolExpr>) {
                result["type"] = "symbol";
                result["name"] = node.name;
                result["start"] = node.span.start;
                result["end"] = node.span.end;
            } else if constexpr (std::is_same_v<T, std::shared_ptr<const UnaryExpr>>) {
                result["type"] = "negate";
                result["operand"] = expressionToPython(node->operand);
                result["start"] = node->span.start;
                result["end"] = node->span.end;
            } else if constexpr (std::is_same_v<T, std::shared_ptr<const SquareRootExpr>>) {
                result["type"] = "sqrt";
                result["operand"] = expressionToPython(node->operand);
                result["start"] = node->span.start;
                result["end"] = node->span.end;
            } else {
                const char* operation = "add";
                switch (node->op) {
                    case BinaryOperator::Add:
                        operation = "add";
                        break;
                    case BinaryOperator::Subtract:
                        operation = "subtract";
                        break;
                    case BinaryOperator::Multiply:
                        operation = "multiply";
                        break;
                    case BinaryOperator::Divide:
                        operation = "divide";
                        break;
                    case BinaryOperator::Power:
                        operation = "power";
                        break;
                }
                result["type"] = operation;
                result["left"] = expressionToPython(node->left);
                result["right"] = expressionToPython(node->right);
                result["start"] = node->span.start;
                result["end"] = node->span.end;
            }
            return result;
        },
        expression);
}

py::dict parseErrorToPython(const ParseError& error) {
    py::dict result;
    result["type"] = "parse_error";
    result["code"] = error.code;
    result["message"] = error.message;
    result["start"] = error.start;
    result["end"] = error.end;
    result["expected"] = error.expected;
    result["actual"] = error.actual.has_value() ? py::cast(*error.actual) : py::none();
    result["suggestion"] = error.suggestion.has_value() ? py::cast(*error.suggestion) : py::none();
    return result;
}

py::dict predicateToPython(const Predicate& predicate) {
    py::dict result;
    result["type"] = predicate.alternatives.size() > 1 ? "disjunction" : "equality";
    py::list alternatives;
    for (const auto& equality : predicate.alternatives) {
        py::dict item;
        item["type"] = "equality";
        item["left"] = expressionToPython(equality.left);
        item["right"] = expressionToPython(equality.right);
        item["start"] = equality.span.start;
        item["end"] = equality.span.end;
        alternatives.append(std::move(item));
    }
    result["alternatives"] = std::move(alternatives);
    result["canonical"] = printPredicate(predicate);
    return result;
}

py::dict domainToPython(const DomainSet& domain) {
    py::dict result;
    result["kind"] = domainName(domain.kind);
    result["excluded"] = rationalList(domain.excluded);
    result["lower"] = domain.lower.has_value() ? py::cast(domain.lower->toString()) : py::none();
    result["upper"] = domain.upper.has_value() ? py::cast(domain.upper->toString()) : py::none();
    result["lowerInclusive"] = domain.lowerInclusive;
    result["upperInclusive"] = domain.upperInclusive;
    return result;
}

py::dict solutionToPython(const SolutionSet& solution) {
    py::dict result;
    result["kind"] = solutionName(solution.kind);
    result["values"] = rationalList(solution.values);
    result["excluded"] = rationalList(solution.excluded);
    return result;
}

py::dict probeToPython(const ProbeEvaluation& probe) {
    py::dict result;
    result["value"] = probe.value.toString();
    result["previousDefined"] = probe.previousDefined;
    result["currentDefined"] = probe.currentDefined;
    result["previousPredicateResult"] = probe.previousPredicateResult.has_value()
                                            ? py::cast(*probe.previousPredicateResult)
                                            : py::none();
    result["currentPredicateResult"] = probe.currentPredicateResult.has_value()
                                           ? py::cast(*probe.currentPredicateResult)
                                           : py::none();
    result["previousLeftValue"] = probe.previousLeftValue.has_value()
                                      ? py::cast(probe.previousLeftValue->toString())
                                      : py::none();
    result["previousRightValue"] = probe.previousRightValue.has_value()
                                       ? py::cast(probe.previousRightValue->toString())
                                       : py::none();
    result["currentLeftValue"] = probe.currentLeftValue.has_value()
                                     ? py::cast(probe.currentLeftValue->toString())
                                     : py::none();
    result["currentRightValue"] = probe.currentRightValue.has_value()
                                      ? py::cast(probe.currentRightValue->toString())
                                      : py::none();
    result["previousResidual"] = probe.previousResidual.has_value()
                                     ? py::cast(probe.previousResidual->toString())
                                     : py::none();
    result["currentResidual"] = probe.currentResidual.has_value()
                                    ? py::cast(probe.currentResidual->toString())
                                    : py::none();
    result["reason"] = probe.reason;
    return result;
}

py::dict assumptionToPython(const Assumption& assumption) {
    py::dict result;
    result["code"] = assumption.code;
    result["expression"] = assumption.expression;
    result["description"] = assumption.description;
    return result;
}

const char* transformationKindName(const TransformationKind kind) {
    switch (kind) {
        case TransformationKind::Factor:
            return "factor";
        case TransformationKind::Expand:
            return "expand";
        case TransformationKind::MoveTerms:
            return "move_terms";
        case TransformationKind::Divide:
            return "divide";
        case TransformationKind::Multiply:
            return "multiply";
        case TransformationKind::SquareBothSides:
            return "square_both_sides";
        case TransformationKind::Solve:
            return "solve";
        case TransformationKind::Verify:
            return "verify";
        case TransformationKind::Unsupported:
            return "unsupported";
    }
    return "unsupported";
}

const char* verificationMethodName(const VerificationMethod method) {
    switch (method) {
        case VerificationMethod::PolynomialNormalization:
            return "polynomial_normalization";
        case VerificationMethod::ExactExpansion:
            return "exact_expansion";
        case VerificationMethod::ExactSubstitution:
            return "exact_substitution";
        case VerificationMethod::SolutionSetComparison:
            return "solution_set_comparison";
        case VerificationMethod::DomainAnalysis:
            return "domain_analysis";
        case VerificationMethod::Unverified:
            return "unverified";
    }
    return "unverified";
}

}  // namespace

py::dict documentToPython(const Document& document) {
    py::dict result;
    result["formatVersion"] = 1;
    result["source"] = document.source;
    py::list steps;
    for (const auto& step : document.steps) {
        py::dict item;
        item["source"] = step.source;
        item["kind"] = step.kind;
        if (step.predicate.has_value()) {
            item["ast"] = predicateToPython(*step.predicate);
        } else {
            item["ast"] = py::none();
        }
        if (step.error.has_value()) {
            item["error"] = parseErrorToPython(*step.error);
        } else {
            item["error"] = py::none();
        }
        steps.append(std::move(item));
    }
    result["steps"] = std::move(steps);
    return result;
}

py::dict stateToPython(const MathState& state) {
    py::dict result;
    py::dict verification;
    verification["status"] = state.verificationStatus == VerificationStatus::Verified ? "verified" : "unknown";
    verification["target"] = "solution_completeness";
    verification["method"] = "exact_core_analysis";
    verification["limitations"] = py::make_tuple("single_variable_real_rational_representation", "not_an_independent_proof_checker");
    result["verification"] = std::move(verification);
    result["source"] = state.source;
    result["canonical"] = state.canonical;
    result["domain"] = domainToPython(state.domain);
    result["solutionSet"] = solutionToPython(state.solutionSet);
    py::list assumptions;
    for (const auto& assumption : state.assumptions) {
        assumptions.append(assumptionToPython(assumption));
    }
    result["assumptions"] = std::move(assumptions);
    py::list verifications;
    for (const auto& verification : state.solutionVerifications) {
        py::dict item;
        item["candidate"] = verification.candidate.toString();
        item["inDomain"] = verification.inDomain;
        item["predicateResult"] = verification.predicateResult.has_value()
                                      ? py::cast(*verification.predicateResult)
                                      : py::none();
        item["status"] = verificationName(verification.status);
        item["reason"] =
            verification.reason.has_value() ? py::cast(*verification.reason) : py::none();
        verifications.append(std::move(item));
    }
    result["solutionVerifications"] = std::move(verifications);
    result["verificationStatus"] = verificationName(state.verificationStatus);
    result["trustLevel"] =
        state.verificationStatus == VerificationStatus::Verified ? "exact_core" : "unverified";
    result["reason"] = state.reason;
    return result;
}

py::dict traceToPython(const ExecutionTrace& trace) {
    py::dict result;
    py::list states;
    for (const auto& state : trace.states) {
        states.append(stateToPython(state));
    }
    result["states"] = std::move(states);
    py::list relations;
    for (const auto& relation : trace.relations) {
        py::dict item;
        item["type"] = stepRelationTypeName(relation.type);
        item["relation"] = relationName(relation.relation);
        item["lostSolutions"] = rationalList(relation.lostSolutions);
        item["gainedSolutions"] = rationalList(relation.gainedSolutions);
        item["domainExpanded"] = relation.domainExpanded;
        item["domainShrunk"] = relation.domainShrunk;
        py::list assumptions;
        for (const auto& assumption : relation.requiredAssumptions) {
            assumptions.append(assumptionToPython(assumption));
        }
        item["requiredAssumptions"] = std::move(assumptions);
        if (relation.probe.has_value()) {
            item["probe"] = probeToPython(*relation.probe);
        } else {
            item["probe"] = py::none();
        }
        item["reason"] = relation.reason;
        relations.append(std::move(item));
    }
    result["relations"] = std::move(relations);
    py::list diagnostics;
    for (const auto& diagnostic : trace.diagnostics) {
        py::dict item;
        item["status"] = diagnosticName(diagnostic.status);
        item["title"] = diagnostic.title;
        item["message"] = diagnostic.message;
        diagnostics.append(std::move(item));
    }
    result["diagnostics"] = std::move(diagnostics);
    if (trace.activeProbe.has_value()) {
        result["activeProbe"] = probeToPython(*trace.activeProbe);
    } else {
        result["activeProbe"] = py::none();
    }
    result["breakpointStep"] =
        trace.breakpointStep.has_value() ? py::cast(*trace.breakpointStep) : py::none();
    return result;
}

py::list probeTraceToPython(const std::vector<ProbeStepEvaluation>& evaluations) {
    py::list result;
    for (const auto& evaluation : evaluations) {
        py::dict item;
        item["step"] = evaluation.step;
        item["value"] = evaluation.value.toString();
        item["defined"] = evaluation.reason != std::optional<std::string>{"undefined_at_probe"} &&
            !evaluation.defined ? py::object(py::none()) : py::object(py::bool_(evaluation.defined));
        item["verificationStatus"] = !evaluation.predicateResult.has_value() ? "unknown" :
            *evaluation.predicateResult ? "verified" : "refuted";
        item["verificationTarget"] = "predicate_at_assignment";
        item["leftValue"] = evaluation.leftValue.has_value()
                                ? py::cast(evaluation.leftValue->toString())
                                : py::none();
        item["rightValue"] = evaluation.rightValue.has_value()
                                 ? py::cast(evaluation.rightValue->toString())
                                 : py::none();
        item["predicateResult"] = evaluation.predicateResult.has_value()
                                      ? py::cast(*evaluation.predicateResult)
                                      : py::none();
        item["residual"] = evaluation.residual.has_value()
                               ? py::cast(evaluation.residual->toString())
                               : py::none();
        item["reason"] = evaluation.reason.has_value() ? py::cast(*evaluation.reason) : py::none();
        result.append(std::move(item));
    }
    return result;
}

py::list completionsToPython(const std::vector<Completion>& completions) {
    py::list result;
    for (const auto& completion : completions) {
        py::dict item;
        item["id"] = completion.id;
        item["label"] = completion.label;
        item["risk"] = completion.risk;
        item["available"] = completion.available;
        item["reason"] = completion.reason;
        item["preview"] = completion.preview;
        result.append(std::move(item));
    }
    return result;
}

py::dict transformationToPython(const TransformationResult& transformation) {
    py::dict result;
    result["applied"] = transformation.applied;
    result["source"] = transformation.source;
    result["reason"] = transformation.reason;
    py::dict certificate;
    certificate["kind"] = transformationKindName(transformation.certificate.kind);
    certificate["rule"] = transformation.certificate.rule;
    certificate["source"] = transformation.certificate.source;
    certificate["target"] = transformation.certificate.target;
    py::list assumptions;
    for (const auto& assumption : transformation.certificate.requiredAssumptions) {
        assumptions.append(assumptionToPython(assumption));
    }
    certificate["requiredAssumptions"] = std::move(assumptions);
    certificate["claimedRelation"] = relationName(transformation.certificate.claimedRelation);
    certificate["verificationMethod"] =
        verificationMethodName(transformation.certificate.verificationMethod);
    certificate["status"] = verificationName(transformation.certificate.status);
    certificate["beforeCanonical"] = transformation.certificate.beforeCanonical;
    certificate["afterCanonical"] = transformation.certificate.afterCanonical;
    certificate["solutionInvariant"] = transformation.certificate.solutionInvariant;
    result["certificate"] = std::move(certificate);
    return result;
}

py::dict capabilitiesToPython(const std::map<std::string, std::string>& values) {
    py::dict result;
    for (const auto& [key, value] : values) {
        result[py::str(key)] = value;
    }
    return result;
}

}  // namespace neomath::bindings
