#include "neomath/exact/rational.hpp"

#include <algorithm>
#include <limits>
#include <numeric>

namespace neomath {
namespace {

std::int64_t checkedAdd(const std::int64_t a, const std::int64_t b) {
    constexpr auto max = std::numeric_limits<std::int64_t>::max();
    constexpr auto min = std::numeric_limits<std::int64_t>::min();
    if ((b > 0 && a > max - b) || (b < 0 && a < min - b)) {
        throw MathError("INTEGER_OVERFLOW", "exact integer addition exceeded 64-bit range");
    }
    return a + b;
}

std::int64_t checkedSubtract(const std::int64_t a, const std::int64_t b) {
    constexpr auto max = std::numeric_limits<std::int64_t>::max();
    constexpr auto min = std::numeric_limits<std::int64_t>::min();
    if ((b < 0 && a > max + b) || (b > 0 && a < min + b)) {
        throw MathError("INTEGER_OVERFLOW", "exact integer subtraction exceeded 64-bit range");
    }
    return a - b;
}

std::int64_t checkedMultiply(const std::int64_t a, const std::int64_t b) {
    if (a == 0 || b == 0) {
        return 0;
    }
    constexpr auto max = std::numeric_limits<std::int64_t>::max();
    constexpr auto min = std::numeric_limits<std::int64_t>::min();
    if (a == -1 && b == min || b == -1 && a == min) {
        throw MathError("INTEGER_OVERFLOW", "exact integer multiplication exceeded 64-bit range");
    }
    if (a > 0) {
        if ((b > 0 && a > max / b) || (b < 0 && b < min / a)) {
            throw MathError("INTEGER_OVERFLOW",
                            "exact integer multiplication exceeded 64-bit range");
        }
    } else {
        if ((b > 0 && a < min / b) || (b < 0 && a < max / b)) {
            throw MathError("INTEGER_OVERFLOW",
                            "exact integer multiplication exceeded 64-bit range");
        }
    }
    return a * b;
}

std::int64_t magnitude(const std::int64_t value) {
    if (value == std::numeric_limits<std::int64_t>::min()) {
        throw MathError("INTEGER_OVERFLOW", "minimum 64-bit integer cannot be normalized");
    }
    return value < 0 ? -value : value;
}

int comparePositiveFractions(std::uint64_t leftNumerator, std::uint64_t leftDenominator,
                             std::uint64_t rightNumerator, std::uint64_t rightDenominator) {
    int direction = 1;
    while (true) {
        const auto leftQuotient = leftNumerator / leftDenominator;
        const auto rightQuotient = rightNumerator / rightDenominator;
        if (leftQuotient != rightQuotient) {
            return direction * (leftQuotient < rightQuotient ? -1 : 1);
        }
        const auto leftRemainder = leftNumerator % leftDenominator;
        const auto rightRemainder = rightNumerator % rightDenominator;
        if (leftRemainder == 0 || rightRemainder == 0) {
            if (leftRemainder == rightRemainder) {
                return 0;
            }
            return direction * (leftRemainder == 0 ? -1 : 1);
        }
        leftNumerator = leftDenominator;
        leftDenominator = leftRemainder;
        rightNumerator = rightDenominator;
        rightDenominator = rightRemainder;
        direction = -direction;
    }
}

std::uint64_t integerSquareRoot(const std::uint64_t value) {
    std::uint64_t low = 0;
    std::uint64_t high = std::min<std::uint64_t>(value, 3'037'000'499ULL) + 1;
    while (low + 1 < high) {
        const auto middle = low + (high - low) / 2;
        if (middle <= value / middle) {
            low = middle;
        } else {
            high = middle;
        }
    }
    return low;
}

}  // namespace

MathError::MathError(std::string code, const std::string& message)
    : std::runtime_error(message), code_(std::move(code)) {}

const std::string& MathError::code() const noexcept { return code_; }

Rational::Rational(std::int64_t numerator, std::int64_t denominator) {
    if (denominator == 0) {
        throw MathError("DIVISION_BY_ZERO", "a rational denominator cannot be zero");
    }
    if (numerator == std::numeric_limits<std::int64_t>::min() ||
        denominator == std::numeric_limits<std::int64_t>::min()) {
        throw MathError("INTEGER_OVERFLOW", "minimum 64-bit integer cannot be normalized");
    }
    if (numerator == 0) {
        numerator_ = 0;
        denominator_ = 1;
        return;
    }
    if (denominator < 0) {
        numerator = -numerator;
        denominator = -denominator;
    }
    const auto divisor = std::gcd(magnitude(numerator), denominator);
    numerator_ = numerator / divisor;
    denominator_ = denominator / divisor;
}

std::int64_t Rational::numerator() const noexcept { return numerator_; }

std::int64_t Rational::denominator() const noexcept { return denominator_; }

bool Rational::isInteger() const noexcept { return denominator_ == 1; }

bool Rational::isZero() const noexcept { return numerator_ == 0; }

std::string Rational::toString() const {
    if (denominator_ == 1) {
        return std::to_string(numerator_);
    }
    return std::to_string(numerator_) + "/" + std::to_string(denominator_);
}

Rational operator+(const Rational& lhs, const Rational& rhs) {
    const auto divisor = std::gcd(lhs.denominator_, rhs.denominator_);
    const auto leftScale = rhs.denominator_ / divisor;
    const auto rightScale = lhs.denominator_ / divisor;
    const auto numerator = checkedAdd(checkedMultiply(lhs.numerator_, leftScale),
                                      checkedMultiply(rhs.numerator_, rightScale));
    return Rational(numerator, checkedMultiply(lhs.denominator_, leftScale));
}

Rational operator-(const Rational& lhs, const Rational& rhs) {
    const auto divisor = std::gcd(lhs.denominator_, rhs.denominator_);
    const auto leftScale = rhs.denominator_ / divisor;
    const auto rightScale = lhs.denominator_ / divisor;
    const auto numerator = checkedSubtract(checkedMultiply(lhs.numerator_, leftScale),
                                           checkedMultiply(rhs.numerator_, rightScale));
    return Rational(numerator, checkedMultiply(lhs.denominator_, leftScale));
}

Rational operator*(const Rational& lhs, const Rational& rhs) {
    const auto crossLeft = std::gcd(magnitude(lhs.numerator_), rhs.denominator_);
    const auto crossRight = std::gcd(magnitude(rhs.numerator_), lhs.denominator_);
    return Rational(checkedMultiply(lhs.numerator_ / crossLeft, rhs.numerator_ / crossRight),
                    checkedMultiply(lhs.denominator_ / crossRight, rhs.denominator_ / crossLeft));
}

Rational operator/(const Rational& lhs, const Rational& rhs) {
    if (rhs.numerator_ == 0) {
        throw MathError("DIVISION_BY_ZERO", "division by zero is undefined");
    }
    return lhs * Rational(rhs.denominator_, rhs.numerator_);
}

Rational operator-(const Rational& value) {
    if (value.numerator_ == std::numeric_limits<std::int64_t>::min()) {
        throw MathError("INTEGER_OVERFLOW", "exact negation exceeded 64-bit range");
    }
    return Rational(-value.numerator_, value.denominator_);
}

std::strong_ordering operator<=>(const Rational& lhs, const Rational& rhs) {
    if (lhs.numerator_ < 0 && rhs.numerator_ >= 0) {
        return std::strong_ordering::less;
    }
    if (lhs.numerator_ >= 0 && rhs.numerator_ < 0) {
        return std::strong_ordering::greater;
    }
    const bool negative = lhs.numerator_ < 0;
    const auto comparison =
        comparePositiveFractions(static_cast<std::uint64_t>(magnitude(lhs.numerator_)),
                                 static_cast<std::uint64_t>(lhs.denominator_),
                                 static_cast<std::uint64_t>(magnitude(rhs.numerator_)),
                                 static_cast<std::uint64_t>(rhs.denominator_));
    const auto signedComparison = negative ? -comparison : comparison;
    if (signedComparison < 0) {
        return std::strong_ordering::less;
    }
    if (signedComparison > 0) {
        return std::strong_ordering::greater;
    }
    return std::strong_ordering::equal;
}

Rational pow(const Rational& base, std::uint32_t exponent) {
    Rational result{1};
    Rational factor = base;
    while (exponent > 0) {
        if ((exponent & 1U) != 0U) {
            result = result * factor;
        }
        exponent >>= 1U;
        if (exponent > 0) {
            factor = factor * factor;
        }
    }
    return result;
}

bool exactSquareRoot(const Rational& value, Rational& result) {
    if (value.numerator() < 0) {
        return false;
    }
    const auto numerator = static_cast<std::uint64_t>(value.numerator());
    const auto denominator = static_cast<std::uint64_t>(value.denominator());
    const auto numeratorRoot = integerSquareRoot(numerator);
    const auto denominatorRoot = integerSquareRoot(denominator);
    if (numeratorRoot * numeratorRoot != numerator ||
        denominatorRoot * denominatorRoot != denominator) {
        return false;
    }
    result = Rational(static_cast<std::int64_t>(numeratorRoot),
                      static_cast<std::int64_t>(denominatorRoot));
    return true;
}

}  // namespace neomath
