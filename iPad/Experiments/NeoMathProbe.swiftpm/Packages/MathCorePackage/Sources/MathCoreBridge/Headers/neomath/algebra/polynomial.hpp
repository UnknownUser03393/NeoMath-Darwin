#pragma once

#include <map>
#include <optional>
#include <string>
#include <vector>

#include "neomath/syntax/ast.hpp"

namespace neomath {

/// Sparse exact polynomial in x; zero coefficients are never stored.
class Polynomial final {
   public:
    Polynomial();
    explicit Polynomial(Rational constant);
    static Polynomial variable();

    [[nodiscard]] int degree() const noexcept;
    [[nodiscard]] bool isZero() const noexcept;
    [[nodiscard]] Rational coefficient(int exponent) const;
    [[nodiscard]] Rational evaluate(const Rational& x) const;
    [[nodiscard]] std::string toString() const;
    [[nodiscard]] const std::map<int, Rational>& terms() const noexcept;

    friend Polynomial operator+(const Polynomial& lhs, const Polynomial& rhs);
    friend Polynomial operator-(const Polynomial& lhs, const Polynomial& rhs);
    friend Polynomial operator*(const Polynomial& lhs, const Polynomial& rhs);
    friend bool operator==(const Polynomial&, const Polynomial&) = default;

   private:
    explicit Polynomial(std::map<int, Rational> terms);
    void normalize();
    std::map<int, Rational> terms_;
};

[[nodiscard]] Polynomial pow(const Polynomial& base, std::uint32_t exponent, int maxDegree = 4);

struct RationalFunction {
    Polynomial numerator;
    Polynomial denominator{Rational{1}};
};

struct PolynomialConversion {
    std::optional<RationalFunction> value;
    std::string reason;
};

[[nodiscard]] PolynomialConversion toRationalFunction(const Expression& expression,
                                                      int maxDegree = 4);
[[nodiscard]] std::vector<Rational> rationalRoots(const Polynomial& polynomial);

}  // namespace neomath
