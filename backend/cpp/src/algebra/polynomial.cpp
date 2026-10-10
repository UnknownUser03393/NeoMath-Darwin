#include "neomath/algebra/polynomial.hpp"

#include <algorithm>
#include <sstream>
#include <type_traits>

namespace neomath {
namespace {

void ensureDegree(const Polynomial& polynomial, const int maxDegree) {
    if (polynomial.degree() > maxDegree) {
        throw MathError("POLYNOMIAL_DEGREE_LIMIT", "polynomial degree limit exceeded");
    }
}

RationalFunction addFunctions(const RationalFunction& lhs, const RationalFunction& rhs) {
    return {lhs.numerator * rhs.denominator + rhs.numerator * lhs.denominator,
            lhs.denominator * rhs.denominator};
}

RationalFunction subtractFunctions(const RationalFunction& lhs, const RationalFunction& rhs) {
    return {lhs.numerator * rhs.denominator - rhs.numerator * lhs.denominator,
            lhs.denominator * rhs.denominator};
}

RationalFunction multiplyFunctions(const RationalFunction& lhs, const RationalFunction& rhs) {
    return {lhs.numerator * rhs.numerator, lhs.denominator * rhs.denominator};
}

PolynomialConversion convert(const Expression& expression, const int maxDegree) {
    try {
        return std::visit(
            [maxDegree](const auto& node) -> PolynomialConversion {
                using T = std::decay_t<decltype(node)>;
                if constexpr (std::is_same_v<T, IntegerExpr>) {
                    return {
                        RationalFunction{Polynomial{Rational{node.value}}, Polynomial{Rational{1}}},
                        ""};
                } else if constexpr (std::is_same_v<T, RationalExpr>) {
                    return {RationalFunction{Polynomial{node.value}, Polynomial{Rational{1}}}, ""};
                } else if constexpr (std::is_same_v<T, SymbolExpr>) {
                    return {RationalFunction{Polynomial::variable(), Polynomial{Rational{1}}}, ""};
                } else if constexpr (std::is_same_v<T, std::shared_ptr<const SquareRootExpr>>) {
                    return {std::nullopt, "square_root_requires_special_solver"};
                } else if constexpr (std::is_same_v<T, std::shared_ptr<const UnaryExpr>>) {
                    auto operand = convert(node->operand, maxDegree);
                    if (!operand.value.has_value()) {
                        return operand;
                    }
                    operand.value->numerator = Polynomial{Rational{-1}} * operand.value->numerator;
                    return operand;
                } else {
                    auto left = convert(node->left, maxDegree);
                    auto right = convert(node->right, maxDegree);
                    if (!left.value.has_value()) {
                        return left;
                    }
                    if (!right.value.has_value()) {
                        return right;
                    }
                    RationalFunction result;
                    switch (node->op) {
                        case BinaryOperator::Add:
                            result = addFunctions(*left.value, *right.value);
                            break;
                        case BinaryOperator::Subtract:
                            result = subtractFunctions(*left.value, *right.value);
                            break;
                        case BinaryOperator::Multiply:
                            result = multiplyFunctions(*left.value, *right.value);
                            break;
                        case BinaryOperator::Divide:
                            if (right.value->numerator.isZero()) {
                                return {std::nullopt, "division_by_zero_expression"};
                            }
                            result = {left.value->numerator * right.value->denominator,
                                      left.value->denominator * right.value->numerator};
                            break;
                        case BinaryOperator::Power: {
                            const auto* exponent = std::get_if<IntegerExpr>(&node->right);
                            if (exponent == nullptr || exponent->value < 0 ||
                                exponent->value > maxDegree) {
                                return {std::nullopt, "power_must_be_a_small_nonnegative_integer"};
                            }
                            const auto convertedBase = convert(node->left, maxDegree);
                            if (!convertedBase.value.has_value()) {
                                return convertedBase;
                            }
                            result = {pow(convertedBase.value->numerator,
                                          static_cast<std::uint32_t>(exponent->value), maxDegree),
                                      pow(convertedBase.value->denominator,
                                          static_cast<std::uint32_t>(exponent->value), maxDegree)};
                            break;
                        }
                    }
                    ensureDegree(result.numerator, maxDegree);
                    ensureDegree(result.denominator, maxDegree);
                    return {std::move(result), ""};
                }
            },
            expression);
    } catch (const MathError& error) {
        return {std::nullopt, error.code()};
    }
}

}  // namespace

Polynomial::Polynomial() = default;

Polynomial::Polynomial(Rational constant) {
    if (!constant.isZero()) {
        terms_.emplace(0, constant);
    }
}

Polynomial::Polynomial(std::map<int, Rational> terms) : terms_(std::move(terms)) { normalize(); }

Polynomial Polynomial::variable() { return Polynomial({{1, Rational{1}}}); }

int Polynomial::degree() const noexcept { return terms_.empty() ? -1 : terms_.rbegin()->first; }

bool Polynomial::isZero() const noexcept { return terms_.empty(); }

Rational Polynomial::coefficient(const int exponent) const {
    const auto found = terms_.find(exponent);
    return found == terms_.end() ? Rational{0} : found->second;
}

Rational Polynomial::evaluate(const Rational& x) const {
    Rational result{0};
    for (auto iterator = terms_.rbegin(); iterator != terms_.rend(); ++iterator) {
        result = result + iterator->second * pow(x, static_cast<std::uint32_t>(iterator->first));
    }
    return result;
}

std::string Polynomial::toString() const {
    if (terms_.empty()) {
        return "0";
    }
    std::ostringstream output;
    bool first = true;
    for (auto iterator = terms_.rbegin(); iterator != terms_.rend(); ++iterator) {
        const auto exponent = iterator->first;
        const auto coefficient = iterator->second;
        if (!first) {
            output << (coefficient.numerator() < 0 ? " - " : " + ");
        } else if (coefficient.numerator() < 0) {
            output << "-";
        }
        const auto absolute = coefficient.numerator() < 0 ? -coefficient : coefficient;
        if (exponent == 0 || absolute != Rational{1}) {
            output << absolute.toString();
            if (exponent > 0) {
                output << "*";
            }
        }
        if (exponent > 0) {
            output << "x";
            if (exponent > 1) {
                output << "^" << exponent;
            }
        }
        first = false;
    }
    return output.str();
}

const std::map<int, Rational>& Polynomial::terms() const noexcept { return terms_; }

void Polynomial::normalize() {
    for (auto iterator = terms_.begin(); iterator != terms_.end();) {
        if (iterator->second.isZero()) {
            iterator = terms_.erase(iterator);
        } else {
            ++iterator;
        }
    }
}

Polynomial operator+(const Polynomial& lhs, const Polynomial& rhs) {
    auto terms = lhs.terms_;
    for (const auto& [exponent, coefficient] : rhs.terms_) {
        terms[exponent] = terms[exponent] + coefficient;
    }
    return Polynomial(std::move(terms));
}

Polynomial operator-(const Polynomial& lhs, const Polynomial& rhs) {
    auto terms = lhs.terms_;
    for (const auto& [exponent, coefficient] : rhs.terms_) {
        terms[exponent] = terms[exponent] - coefficient;
    }
    return Polynomial(std::move(terms));
}

Polynomial operator*(const Polynomial& lhs, const Polynomial& rhs) {
    std::map<int, Rational> terms;
    for (const auto& [leftExponent, leftCoefficient] : lhs.terms_) {
        for (const auto& [rightExponent, rightCoefficient] : rhs.terms_) {
            const auto exponent = leftExponent + rightExponent;
            terms[exponent] = terms[exponent] + leftCoefficient * rightCoefficient;
        }
    }
    return Polynomial(std::move(terms));
}

Polynomial pow(const Polynomial& base, std::uint32_t exponent, const int maxDegree) {
    Polynomial result{Rational{1}};
    Polynomial factor = base;
    while (exponent > 0) {
        if ((exponent & 1U) != 0U) {
            result = result * factor;
            ensureDegree(result, maxDegree);
        }
        exponent >>= 1U;
        if (exponent > 0) {
            factor = factor * factor;
            ensureDegree(factor, maxDegree);
        }
    }
    return result;
}

PolynomialConversion toRationalFunction(const Expression& expression, const int maxDegree) {
    return convert(expression, maxDegree);
}

std::vector<Rational> rationalRoots(const Polynomial& polynomial) {
    if (polynomial.degree() < 1 || polynomial.degree() > 2) {
        return {};
    }
    const auto a = polynomial.coefficient(2);
    const auto b = polynomial.coefficient(1);
    const auto c = polynomial.coefficient(0);
    if (a.isZero()) {
        if (b.isZero()) {
            return {};
        }
        return {-c / b};
    }
    const auto discriminant = b * b - Rational{4} * a * c;
    Rational squareRoot;
    if (!exactSquareRoot(discriminant, squareRoot)) {
        return {};
    }
    const auto denominator = Rational{2} * a;
    std::vector<Rational> roots{(-b - squareRoot) / denominator};
    const auto second = (-b + squareRoot) / denominator;
    if (second != roots.front()) {
        roots.push_back(second);
    }
    std::sort(roots.begin(), roots.end());
    return roots;
}

}  // namespace neomath
