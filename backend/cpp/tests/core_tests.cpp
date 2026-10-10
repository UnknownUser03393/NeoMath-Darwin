#define CATCH_CONFIG_MAIN
#include <limits>
#include <stdexcept>
#include <string>

#include "catch2/catch.hpp"
#include "neomath/algebra/polynomial.hpp"
#include "neomath/exact/rational.hpp"
#include "neomath/semantics/engine.hpp"

namespace {

using neomath::DiagnosticStatus;
using neomath::DomainKind;
using neomath::Rational;
using neomath::SolutionKind;

void require(const bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

neomath::ExecutionTrace trace(const std::string& source) {
    return neomath::runTrace(neomath::parseDocument(source));
}

void testRationalNormalization() {
    require(Rational(2, 4) == Rational(1, 2), "rational reduction");
    require(Rational(0, -7).toString() == "0", "canonical zero");
    require(Rational(1, -2).toString() == "-1/2", "positive denominator");
    require(Rational(1, 3) + Rational(1, 6) == Rational(1, 2), "exact addition");
    require(Rational(2, 3) * Rational(9, 4) == Rational(3, 2), "exact multiplication");
}

void testParserAndImplicitMultiplication() {
    const auto parsed = neomath::parsePredicate("x(x - 1) = 0");
    require(parsed.predicate.has_value(), "implicit multiplication parses");
    require(neomath::printPredicate(*parsed.predicate).find("*") != std::string::npos,
            "canonical form is explicit");
    const auto invalid = neomath::parsePredicate("sin(x) = 0");
    require(invalid.error.has_value(), "unsupported identifier is structured parse error");
}

void testPolynomial() {
    const auto x = neomath::Polynomial::variable();
    const auto product =
        (x - neomath::Polynomial(Rational{1})) * (x + neomath::Polynomial(Rational{2}));
    require(product.degree() == 2, "polynomial degree");
    require(product.evaluate(Rational{1}).isZero(), "polynomial exact evaluation");
}

void testLostRootDemo() {
    const auto result = trace("x(x - 1) = 0\nx - 1 = 0\nx = 1");
    require(result.states.size() == 3, "lost-root state count");
    require(result.states[0].solutionSet.values.size() == 2, "initial roots are 0 and 1");
    require(result.relations[0].lostSolutions == std::vector<Rational>{Rational{0}},
            "zero is reported as lost");
    require(result.activeProbe.has_value() && result.activeProbe->value == Rational{0},
            "lost root probe is x=0");
    require(result.diagnostics[1].status == DiagnosticStatus::RootFault, "root fault location");
    require(result.diagnostics[2].status == DiagnosticStatus::Tainted, "taint propagation");
}

void testExtraneousRootDemo() {
    const auto result = trace(
        "sqrt(x) = x - 2\n"
        "x = (x - 2)^2\n"
        "x^2 - 5x + 4 = 0\n"
        "x = 1 or x = 4");
    require(result.states[0].solutionSet.values == std::set<Rational>{Rational{4}},
            "radical equation exact solution");
    require(result.relations[0].gainedSolutions == std::vector<Rational>{Rational{1}},
            "squaring reports extraneous root");
    require(result.activeProbe.has_value() && result.activeProbe->value == Rational{1},
            "extraneous root probe");
}

void testDomainExpansionDemo() {
    const auto result = trace("(x - 1) / (x - 1) = 1\n1 = 1");
    require(result.states[0].domain.kind == DomainKind::RealExcludingFinite,
            "division domain exclusion");
    require(result.states[0].solutionSet.kind == SolutionKind::AllRealExcludingFinite,
            "identity keeps domain exclusion");
    require(result.relations[0].domainExpanded, "domain expansion reported");
    require(result.activeProbe.has_value() && result.activeProbe->value == Rational{1},
            "domain probe");
    require(!result.activeProbe->previousDefined && result.activeProbe->currentDefined,
            "probe demonstrates undefined versus true");
}

void testTransformationCertificate() {
    const auto document = neomath::parseDocument("x^2 - 4 = 0");
    const auto transformed = neomath::executeTransformation(document, 0, "factor");
    require(transformed.applied, "factor transformation applied");
    require(transformed.source == "(x - 2)(x + 2) = 0", "difference of squares output");
    require(transformed.certificate.status == neomath::VerificationStatus::Verified,
            "verified certificate");
}

void testEdgeCases() {
    require(trace("x^2 + 1 = 0").states[0].solutionSet.kind == SolutionKind::Empty,
            "negative discriminant has no real roots");
    require(trace("1 / (x - 1) = 0").states[0].solutionSet.kind == SolutionKind::Empty,
            "rational numerator cannot be zero");
    require(trace("0x = 0").states[0].solutionSet.kind == SolutionKind::AllReal,
            "zero identity is all reals");
    require(trace("(x^2 - 4) / (x - 2) = 0").states[0].solutionSet.values ==
                std::set<Rational>{Rational{-2}},
            "denominator exclusion removes canceled root");
}

void testAllTransformationsAndIndependentFault() {
    const auto expanded =
        neomath::executeTransformation(neomath::parseDocument("(x - 1)(x + 1) = 0"), 0, "expand");
    require(expanded.applied, "expand transformation applied");
    require(expanded.certificate.verificationMethod ==
                neomath::VerificationMethod::PolynomialNormalization,
            "expand uses polynomial normalization certificate");

    const auto divided = neomath::executeTransformation(neomath::parseDocument("x(x - 1) = 0"), 0,
                                                        "divide", std::string{"x"});
    require(divided.applied, "conditional divide transformation applied");
    require(!divided.certificate.requiredAssumptions.empty(), "divide records x nonzero");

    const auto squared = neomath::executeTransformation(neomath::parseDocument("sqrt(x) = x - 2"),
                                                        0, "square_both_sides");
    require(squared.applied, "square transformation produces verified implication");
    require(squared.source == "x = (x - 2)^2", "sqrt square simplifies to radicand");

    const auto result = trace(
        "x(x - 1) = 0\n"
        "x - 1 = 0\n"
        "x = 1\n"
        "x = 2");
    require(result.diagnostics[3].status == DiagnosticStatus::IndependentFault,
            "new semantic divergence after root fault is independent");
}

void testIntegerLimitIsStructured() {
    const auto parsed = neomath::parsePredicate(std::string(200, '9') + "x = 1");
    require(parsed.error.has_value(), "oversized integer is a parse error");
    require(parsed.error->code == "INTEGER_LIMIT", "oversized integer has stable code");
}

void testIntegerOverflowIsStructured() {
    bool threw = false;
    try {
        const auto huge = Rational{std::numeric_limits<std::int64_t>::max() / 2 + 1};
        (void)(huge * Rational{3});
    } catch (const neomath::MathError& error) {
        threw = true;
        require(error.code() == "INTEGER_OVERFLOW", "overflow throws INTEGER_OVERFLOW code");
        require(std::string(error.what()).find("64-bit") != std::string::npos,
                "overflow message is non-empty and specific");
    }
    require(threw, "checked rational multiplication must throw on overflow");

    // Document path: intermediate product exceeds int64 during analysis.
    const auto result = trace("9223372036854775807 * 2 = x");
    require(result.states.size() == 1, "overflow document has one state");
    require(result.states[0].reason == "INTEGER_OVERFLOW",
            "MathState.reason keeps structured overflow code");
    require(!result.diagnostics.empty(), "overflow yields a diagnostic");
    require(result.diagnostics[0].message.find("INTEGER_OVERFLOW") != std::string::npos,
            "diagnostic message is user-facing and names the code");
    require(result.diagnostics[0].message.size() > std::string("INTEGER_OVERFLOW").size(),
            "user-facing message is more than the bare code");
}

void testIncrementalReplayMatchesFullTrace() {
    const auto before = trace("x = 1\nx + 1 = 2\nx = 1");
    const auto changed = neomath::parseDocument("x = 1\nx + 1 = 2\nx = 2");
    const auto replayed = neomath::replayTrace(changed, before, 2);
    const auto full = neomath::runTrace(changed);

    require(replayed.states.size() == full.states.size(), "replay state count");
    require(replayed.relations.size() == full.relations.size(), "replay relation count");
    require(replayed.diagnostics.size() == full.diagnostics.size(), "replay diagnostic count");
    require(replayed.states[2].solutionSet.values == full.states[2].solutionSet.values,
            "changed state is recomputed");
    require(replayed.relations[1].relation == full.relations[1].relation,
            "boundary relation is recomputed");
    require(replayed.diagnostics[2].status == full.diagnostics[2].status,
            "boundary diagnostic is recomputed");
    require(replayed.breakpointStep == full.breakpointStep, "breakpoint remains exact");

    const auto faultyPrefix = trace("x(x - 1) = 0\nx - 1 = 0\nx = 1");
    const auto changedAfterFault = neomath::parseDocument("x(x - 1) = 0\nx - 1 = 0\nx = 2");
    const auto faultReplay = neomath::replayTrace(changedAfterFault, faultyPrefix, 2);
    const auto faultFull = neomath::runTrace(changedAfterFault);
    require(faultReplay.diagnostics[2].status == faultFull.diagnostics[2].status,
            "cached root fault affects recomputed diagnostics");
    require(faultReplay.breakpointStep == faultFull.breakpointStep,
            "cached root fault keeps the original breakpoint");
    require(faultReplay.activeProbe.has_value() && faultFull.activeProbe.has_value() &&
                faultReplay.activeProbe->value == faultFull.activeProbe->value,
            "cached root fault keeps the original probe");
}

}  // namespace

TEST_CASE("Rational maintains exact canonical invariants", "[rational]") {
    testRationalNormalization();
}

TEST_CASE("Common notation has exact semantics and safe diagnostics", "[parser][solver]") {
    require(trace("x^2=1\nx=±1").relations[0].relation == neomath::RelationKind::Equivalent, "plus minus preserves both roots");
    require(trace("x=2±1").states[0].solutionSet.values == std::set<Rational>{Rational{1}, Rational{3}}, "binary plus minus");
    require(trace("x=±1∓1").states[0].solutionSet.values == std::set<Rational>{Rational{0}}, "paired signs stay correlated");
    require(trace("0.1x=0.3").states[0].solutionSet.values == std::set<Rational>{Rational{3}}, "decimal arithmetic is exact");
    require(trace(".5y=1\ny=2").relations[0].relation == neomath::RelationKind::Equivalent, "renamed variable and leading dot decimal");
    require(trace("y×(y−1)=0\ny=1").relations[0].lostSolutions == std::vector<Rational>{Rational{0}}, "unicode operators preserve witness semantics");
    require(trace("t=√4").states[0].solutionSet.values == std::set<Rational>{Rational{2}}, "unicode square root");
    const auto unsupported = neomath::parsePredicate("x=🙂");
    require(unsupported.error && unsupported.error->actual == std::optional<std::string>{"🙂"}, "unsupported unicode error preserves whole character");
    require(neomath::parsePredicate("x+y=1").error->code == "MULTIPLE_VARIABLES", "multiple symbols rejected");
    require(neomath::parseDocument("x=1\ny=1").steps[1].error->code == "MULTIPLE_VARIABLES", "variable cannot change across derivation");
    require(trace("x=1\nx^2=2").diagnostics[1].status == DiagnosticStatus::Unverified, "unsupported solver is not a mathematical fault");
    for (const auto intent : {"solve", "factor", "expand", "move_terms"}) {
        const auto result = neomath::executeTransformation(neomath::parseDocument("y^2-1=0"), 0, intent);
        require(result.applied && result.source.find('x') == std::string::npos, "transformation preserves variable name");
    }
    require(!neomath::executeTransformation(neomath::parseDocument("y=1"), 0, "multiply", std::string{"x"}).applied, "foreign variable in transform rejected");
    const auto roundtrip = neomath::parsePredicate(neomath::printPredicate(*neomath::parsePredicate("x=0.5^2").predicate));
    require(neomath::analyzePredicate(*roundtrip.predicate, "").solutionSet.values == std::set<Rational>{Rational{1,4}}, "decimal canonical power preserves precedence");
}

TEST_CASE("Lexer and parser support implicit multiplication", "[parser]") {
    testParserAndImplicitMultiplication();
}

TEST_CASE("Polynomial arithmetic is exact", "[polynomial]") { testPolynomial(); }

TEST_CASE("Lost-root demo finds root fault and taint", "[trace][demo]") { testLostRootDemo(); }

TEST_CASE("Squaring demo finds an extraneous root", "[trace][demo]") { testExtraneousRootDemo(); }

TEST_CASE("Domain expansion demo produces an undefined probe", "[trace][demo]") {
    testDomainExpansionDemo();
}

TEST_CASE("Difference of squares produces a verified certificate", "[transform]") {
    testTransformationCertificate();
}

TEST_CASE("Supported edge cases preserve exact domain semantics", "[solver]") { testEdgeCases(); }

TEST_CASE("All transformation families are certified", "[transform]") {
    testAllTransformationsAndIndependentFault();
}

TEST_CASE("Oversized integers do not escape the parser", "[parser][limits]") {
    testIntegerLimitIsStructured();
}

TEST_CASE("Integer overflow is structured with a user-facing message", "[rational][limits]") {
    testIntegerOverflowIsStructured();
}

TEST_CASE("Incremental replay is equivalent to full recomputation", "[trace][replay]") {
    testIncrementalReplayMatchesFullTrace();
}

TEST_CASE("Incomplete radical root coverage is unknown, never empty verified", "[verification][limits]") {
    const auto result = trace("sqrt(x)=x-1");
    require(result.states[0].verificationStatus == neomath::VerificationStatus::Unverified,
            "irrational radical root exceeds rational solver capability");
    require(result.states[0].solutionSet.kind == SolutionKind::Unverified,
            "unsupported root coverage is not an empty solution set");
}

TEST_CASE("Original nested denominator obligations survive rewriting", "[verification][domain]") {
    const auto nested = trace("1/(1/x)=x").states[0];
    require(nested.domain.excluded.contains(Rational{0}), "nested division preserves nonzero obligation");
    const auto irrational = trace("1/(x^2-2)=1/(x^2-2)").states[0];
    require(irrational.verificationStatus == neomath::VerificationStatus::Unverified,
            "irrational exclusions exceed rational domain representation");
}

TEST_CASE("Unsupported infinite disjunction is unknown in both orders", "[verification][disjunction]") {
    for (const auto& source : {"x=0 or x/x=1", "x/x=1 or x=0"}) {
        const auto result = trace(source).states[0];
        require(result.verificationStatus == neomath::VerificationStatus::Unverified,
                "unsupported union must not be trusted");
        require(result.solutionSet.kind == SolutionKind::Unverified,
                "partial branch set must not escape as a complete answer");
    }
}
