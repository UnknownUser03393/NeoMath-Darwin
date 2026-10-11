#pragma once

#include <chrono>
#include <cstddef>
#include <memory>
#include <optional>
#include <string>
#include <variant>
#include <vector>

#include "neomath/exact/rational.hpp"

namespace neomath {

struct SourceSpan {
    std::size_t start{};
    std::size_t end{};
};

struct IntegerExpr {
    std::int64_t value{};
    SourceSpan span{};
};
struct RationalExpr {
    Rational value{};
    SourceSpan span{};
};
struct SymbolExpr {
    std::string name;
    SourceSpan span{};
};
struct UnaryExpr;
struct BinaryExpr;
struct SquareRootExpr;

using Expression =
    std::variant<IntegerExpr, RationalExpr, SymbolExpr, std::shared_ptr<const UnaryExpr>,
                 std::shared_ptr<const BinaryExpr>, std::shared_ptr<const SquareRootExpr>>;

enum class UnaryOperator { Negate };
enum class BinaryOperator { Add, Subtract, Multiply, Divide, Power };

struct UnaryExpr {
    UnaryOperator op{UnaryOperator::Negate};
    Expression operand;
    SourceSpan span{};
};
struct BinaryExpr {
    BinaryOperator op{BinaryOperator::Add};
    Expression left;
    Expression right;
    SourceSpan span{};
};
struct SquareRootExpr {
    Expression operand;
    SourceSpan span{};
};

struct EqualityPredicate {
    Expression left;
    Expression right;
    SourceSpan span{};
};

struct Predicate {
    std::vector<EqualityPredicate> alternatives;
    SourceSpan span{};
};

struct ParseError {
    std::string code;
    std::string message;
    std::size_t start{};
    std::size_t end{};
    std::vector<std::string> expected;
    std::optional<std::string> actual;
    std::optional<std::string> suggestion;
};

struct ParseResult {
    std::optional<Predicate> predicate;
    std::optional<ParseError> error;
};

struct ExecutionLimits {
    std::size_t maxDocumentSteps{200};
    std::size_t maxAstNodesPerStep{10'000};
    std::size_t maxAstDepth{64};
    std::size_t maxPolynomialDegree{4};
    // V1 uses checked int64 rationals; the limit is explicit rather than silently rounding.
    std::size_t maxIntegerBits{63};
    std::chrono::milliseconds maxAnalysisTime{500};
};

[[nodiscard]] ParseResult parsePredicate(const std::string& source,
                                         const ExecutionLimits& limits = {});
[[nodiscard]] std::string printExpression(const Expression& expression);
[[nodiscard]] std::string printPredicate(const Predicate& predicate);
[[nodiscard]] std::size_t countNodes(const Expression& expression);

}  // namespace neomath
