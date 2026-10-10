#pragma once

#include <compare>
#include <cstdint>
#include <stdexcept>
#include <string>

namespace neomath {

class MathError final : public std::runtime_error {
   public:
    MathError(std::string code, const std::string& message);
    [[nodiscard]] const std::string& code() const noexcept;

   private:
    std::string code_;
};

/// Exact reduced rational with a strictly positive denominator.
class Rational final {
   public:
    Rational(std::int64_t numerator = 0, std::int64_t denominator = 1);

    [[nodiscard]] std::int64_t numerator() const noexcept;
    [[nodiscard]] std::int64_t denominator() const noexcept;
    [[nodiscard]] bool isInteger() const noexcept;
    [[nodiscard]] bool isZero() const noexcept;
    [[nodiscard]] std::string toString() const;

    friend Rational operator+(const Rational& lhs, const Rational& rhs);
    friend Rational operator-(const Rational& lhs, const Rational& rhs);
    friend Rational operator*(const Rational& lhs, const Rational& rhs);
    friend Rational operator/(const Rational& lhs, const Rational& rhs);
    friend Rational operator-(const Rational& value);
    friend bool operator==(const Rational&, const Rational&) = default;
    friend std::strong_ordering operator<=>(const Rational& lhs, const Rational& rhs);

   private:
    std::int64_t numerator_;
    std::int64_t denominator_;
};

[[nodiscard]] Rational pow(const Rational& base, std::uint32_t exponent);
[[nodiscard]] bool exactSquareRoot(const Rational& value, Rational& result);

}  // namespace neomath
