#include <cctype>
#include <algorithm>
#include <limits>
#include <sstream>
#include <set>

#include "neomath/syntax/ast.hpp"

namespace neomath {
namespace {

enum class TokenType {
    Integer,
    Decimal,
    Symbol,
    Plus,
    Minus,
    PlusMinus,
    MinusPlus,
    Star,
    Slash,
    Caret,
    Equal,
    LeftParen,
    RightParen,
    Or,
    Sqrt,
    End,
    Invalid
};

struct Token {
    TokenType type{TokenType::Invalid};
    std::string text;
    SourceSpan span;
};

std::vector<Token> lex(const std::string& source, std::optional<ParseError>& error) {
    std::vector<Token> tokens;
    std::size_t position = 0;
    std::set<std::string> variables;
    while (position < source.size()) {
        const auto byte = static_cast<unsigned char>(source[position]);
        if (std::isspace(byte) != 0) {
            ++position;
            continue;
        }
        const auto start = position;
        if (std::isdigit(byte) != 0 || (source[position] == '.' && position + 1 < source.size() && std::isdigit(static_cast<unsigned char>(source[position + 1])))) {
            while (position < source.size() &&
                   std::isdigit(static_cast<unsigned char>(source[position])) != 0) {
                ++position;
            }
            bool decimal = false;
            if (position < source.size() && source[position] == '.') {
                decimal = true;
                ++position;
                while (position < source.size() && std::isdigit(static_cast<unsigned char>(source[position]))) ++position;
                if (position < source.size() && source[position] == '.') {
                    error = ParseError{"INVALID_DECIMAL", "小数只能包含一个小数点。", start, position + 1, {}, source.substr(start, position + 1 - start), std::nullopt};
                    return {};
                }
            }
            tokens.push_back(
                {decimal ? TokenType::Decimal : TokenType::Integer, source.substr(start, position - start), {start, position}});
            continue;
        }
        if (std::isalpha(byte) != 0 || source[position] == '_') {
            while (position < source.size()) {
                const auto current = static_cast<unsigned char>(source[position]);
                if (std::isalnum(current) == 0 && source[position] != '_') {
                    break;
                }
                ++position;
            }
            const auto word = source.substr(start, position - start);
            TokenType type = TokenType::Invalid;
            if (word == "or") {
                type = TokenType::Or;
            } else if (word == "sqrt") {
                type = TokenType::Sqrt;
            } else if (word.size() > 1 && position < source.size() && source[position] == '(') {
                error = ParseError{"UNKNOWN_IDENTIFIER",
                                   "当前 Core 不支持此函数；目前仅支持 sqrt。",
                                   start,
                                   position,
                                   {"x", "sqrt", "or"},
                                   word,
                                   std::nullopt};
                return {};
            } else {
                type = TokenType::Symbol;
                variables.insert(word);
                if (variables.size() > 1) {
                    error = ParseError{"MULTIPLE_VARIABLES", "当前 Core 仅支持单变量方程，不能混用多个变量。", start, position, {}, word, std::nullopt};
                    return {};
                }
            }
            tokens.push_back({type, word, {start, position}});
            continue;
        }
        TokenType type = TokenType::Invalid;
        std::size_t width = 1;
        if (byte >= 0x80) {
            // Keep complete UTF-8 characters in errors, never a truncated leading byte.
            width = byte < 0xe0 ? 2 : byte < 0xf0 ? 3 : 4;
            width = std::min(width, source.size() - position);
            const auto character = source.substr(position, width);
            if (character == "±") type = TokenType::PlusMinus;
            else if (character == "∓") type = TokenType::MinusPlus;
            else if (character == "−" || character == "–") type = TokenType::Minus;
            else if (character == "×" || character == "·" || character == "⋅") type = TokenType::Star;
            else if (character == "÷") type = TokenType::Slash;
            else if (character == "√") type = TokenType::Sqrt;
        }
        if (type == TokenType::Invalid) {
        switch (source[position]) {
            case '+':
                type = TokenType::Plus;
                break;
            case '-':
                type = TokenType::Minus;
                break;
            case '*':
                type = TokenType::Star;
                break;
            case '/':
                type = TokenType::Slash;
                break;
            case '^':
                type = TokenType::Caret;
                break;
            case '=':
                type = TokenType::Equal;
                break;
            case '(':
                type = TokenType::LeftParen;
                break;
            case ')':
                type = TokenType::RightParen;
                break;
            default:
                error = ParseError{"INVALID_CHARACTER",
                                   "当前 Core 不支持此符号；目前支持单变量等式、四则运算、平方根和 ±。",
                                   start,
                                   start + width,
                                   {},
                                   source.substr(start, width),
                                   std::nullopt};
                return {};
        }
        }
        position += width;
        tokens.push_back({type, source.substr(start, width), {start, position}});
    }
    tokens.push_back({TokenType::End, "", {source.size(), source.size()}});
    return tokens;
}

SourceSpan expressionSpan(const Expression& expression) {
    return std::visit(
        [](const auto& node) -> SourceSpan {
            if constexpr (requires { node->span; }) {
                return node->span;
            } else {
                return node.span;
            }
        },
        expression);
}

class Parser final {
   public:
    Parser(std::vector<Token> tokens, const ExecutionLimits& limits)
        : tokens_(std::move(tokens)), limits_(limits) {}

    ParseResult parse() {
        try {
            Predicate predicate;
            do {
                const auto start = position_;
                negativeBranch_ = false;
                hasChoice_ = false;
                predicate.alternatives.push_back(parseEquality());
                if (hasChoice_) {
                    const auto end = position_;
                    position_ = start;
                    negativeBranch_ = true;
                    predicate.alternatives.push_back(parseEquality());
                    position_ = end;
                }
            } while (match(TokenType::Or));
            if (!check(TokenType::End)) {
                fail("UNEXPECTED_TOKEN", "unexpected token after equation", {"or", "end of line"});
            }
            predicate.span = {predicate.alternatives.front().span.start,
                              predicate.alternatives.back().span.end};
            for (const auto& equality : predicate.alternatives) {
                const auto nodes = countNodes(equality.left) + countNodes(equality.right);
                if (nodes > limits_.maxAstNodesPerStep) {
                    fail("COMPLEXITY_LIMIT", "expression node limit exceeded", {});
                }
            }
            return {std::move(predicate), std::nullopt};
        } catch (const ParseFailure& failure) {
            return {std::nullopt, failure.error};
        } catch (const MathError& error) {
            const auto& token = peek();
            return {std::nullopt, ParseError{error.code(),
                                             error.what(),
                                             token.span.start,
                                             token.span.end,
                                             {},
                                             token.text,
                                             std::nullopt}};
        }
    }

   private:
    struct ParseFailure {
        ParseError error;
    };

    class DepthGuard final {
       public:
        explicit DepthGuard(Parser& parser) : parser_(parser) {
            ++parser_.depth_;
            if (parser_.depth_ > parser_.limits_.maxAstDepth) {
                parser_.fail("DEPTH_LIMIT", "expression nesting limit exceeded", {});
            }
        }
        ~DepthGuard() { --parser_.depth_; }

       private:
        Parser& parser_;
    };

    EqualityPredicate parseEquality() {
        const auto left = parseAdditive();
        if (!match(TokenType::Equal)) {
            fail("EXPECTED_EQUALITY", "each derivation step must contain '='", {"="});
        }
        const auto right = parseAdditive();
        return {left, right, {expressionSpan(left).start, expressionSpan(right).end}};
    }

    Expression parseAdditive() {
        DepthGuard guard(*this);
        Expression expression = parseMultiplicative();
        while (check(TokenType::Plus) || check(TokenType::Minus) || check(TokenType::PlusMinus) || check(TokenType::MinusPlus)) {
            auto op = advance().type;
            if (op == TokenType::PlusMinus || op == TokenType::MinusPlus) {
                hasChoice_ = true;
                op = (negativeBranch_ != (op == TokenType::MinusPlus)) ? TokenType::Minus : TokenType::Plus;
            }
            auto right = parseMultiplicative();
            const auto span =
                SourceSpan{expressionSpan(expression).start, expressionSpan(right).end};
            expression = std::make_shared<const BinaryExpr>(
                BinaryExpr{op == TokenType::Plus ? BinaryOperator::Add : BinaryOperator::Subtract,
                           std::move(expression), std::move(right), span});
        }
        return expression;
    }

    bool beginsImplicitFactor() const {
        return check(TokenType::Integer) || check(TokenType::Decimal) || check(TokenType::Symbol) ||
               check(TokenType::LeftParen) || check(TokenType::Sqrt);
    }

    Expression parseMultiplicative() {
        DepthGuard guard(*this);
        Expression expression = parseUnary();
        while (check(TokenType::Star) || check(TokenType::Slash) || beginsImplicitFactor()) {
            BinaryOperator op = BinaryOperator::Multiply;
            if (check(TokenType::Star) || check(TokenType::Slash)) {
                op = advance().type == TokenType::Slash ? BinaryOperator::Divide
                                                        : BinaryOperator::Multiply;
            }
            auto right = parseUnary();
            const auto span =
                SourceSpan{expressionSpan(expression).start, expressionSpan(right).end};
            expression = std::make_shared<const BinaryExpr>(
                BinaryExpr{op, std::move(expression), std::move(right), span});
        }
        return expression;
    }

    Expression parseUnary() {
        DepthGuard guard(*this);
        if (check(TokenType::PlusMinus) || check(TokenType::MinusPlus)) {
            const auto token = advance();
            hasChoice_ = true;
            auto operand = parseUnary();
            if (negativeBranch_ != (token.type == TokenType::MinusPlus)) {
                const auto end = expressionSpan(operand).end;
                return std::make_shared<const UnaryExpr>(UnaryExpr{UnaryOperator::Negate, std::move(operand), {token.span.start, end}});
            }
            return operand;
        }
        if (match(TokenType::Minus)) {
            const auto start = previous().span.start;
            auto operand = parseUnary();
            const auto end = expressionSpan(operand).end;
            return std::make_shared<const UnaryExpr>(
                UnaryExpr{UnaryOperator::Negate, std::move(operand), {start, end}});
        }
        if (match(TokenType::Plus)) {
            return parseUnary();
        }
        return parsePower();
    }

    Expression parsePower() {
        DepthGuard guard(*this);
        Expression expression = parsePrimary();
        if (match(TokenType::Caret)) {
            auto exponent = parseUnary();
            const auto span =
                SourceSpan{expressionSpan(expression).start, expressionSpan(exponent).end};
            expression = std::make_shared<const BinaryExpr>(BinaryExpr{
                BinaryOperator::Power, std::move(expression), std::move(exponent), span});
        }
        return expression;
    }

    Expression parsePrimary() {
        DepthGuard guard(*this);
        if (match(TokenType::Decimal)) {
            const auto token = previous();
            const auto dot = token.text.find('.');
            Rational value{0};
            Rational scale{1};
            for (std::size_t i = 0; i < token.text.size(); ++i) {
                if (i == dot) continue;
                value = value * Rational{10} + Rational{token.text[i] - '0'};
                if (i > dot) scale = scale * Rational{10};
            }
            value = value / scale;
            if (value.isInteger()) return IntegerExpr{value.numerator(), token.span};
            return RationalExpr{value, token.span};
        }
        if (match(TokenType::Integer)) {
            const auto& token = previous();
            try {
                std::size_t consumed = 0;
                const auto value = std::stoll(token.text, &consumed);
                if (consumed != token.text.size()) {
                    fail("INVALID_INTEGER", "invalid integer literal", {"integer"});
                }
                return IntegerExpr{value, token.span};
            } catch (const std::out_of_range&) {
                fail("INTEGER_LIMIT", "integer literal exceeds the exact 64-bit core limit",
                     {"64-bit integer"});
            } catch (const std::invalid_argument&) {
                fail("INVALID_INTEGER", "invalid integer literal", {"integer"});
            }
        }
        if (match(TokenType::Symbol)) {
            return SymbolExpr{previous().text, previous().span};
        }
        if (match(TokenType::Sqrt)) {
            const auto start = previous().span.start;
            if (previous().text == "√" && !check(TokenType::LeftParen)) {
                auto operand = parseUnary();
                const auto end = expressionSpan(operand).end;
                return std::make_shared<const SquareRootExpr>(SquareRootExpr{std::move(operand), {start, end}});
            }
            consume(TokenType::LeftParen, "EXPECTED_LEFT_PAREN", "sqrt must be followed by '('",
                    {"("});
            auto operand = parseAdditive();
            const auto close = consume(TokenType::RightParen, "EXPECTED_RIGHT_PAREN",
                                       "sqrt is missing ')'", {")"});
            return std::make_shared<const SquareRootExpr>(
                SquareRootExpr{std::move(operand), {start, close.span.end}});
        }
        if (match(TokenType::LeftParen)) {
            auto expression = parseAdditive();
            consume(TokenType::RightParen, "EXPECTED_RIGHT_PAREN", "group is missing ')'", {")"});
            return expression;
        }
        fail("EXPECTED_EXPRESSION", "expected a number, x, sqrt, or parenthesized expression",
             {"integer", "x", "sqrt", "("});
    }

    const Token& consume(const TokenType type, const std::string& code, const std::string& message,
                         std::vector<std::string> expected) {
        if (check(type)) {
            return advance();
        }
        fail(code, message, std::move(expected));
    }

    [[noreturn]] void fail(const std::string& code, const std::string& message,
                           std::vector<std::string> expected) const {
        const auto& token = peek();
        throw ParseFailure{ParseError{
            code, message, token.span.start, token.span.end, std::move(expected),
            token.type == TokenType::End ? std::nullopt : std::optional<std::string>{token.text},
            std::nullopt}};
    }

    bool match(const TokenType type) {
        if (!check(type)) {
            return false;
        }
        advance();
        return true;
    }
    bool check(const TokenType type) const { return peek().type == type; }
    const Token& advance() {
        if (!check(TokenType::End)) {
            ++position_;
        }
        return previous();
    }
    const Token& peek() const { return tokens_[position_]; }
    const Token& previous() const { return tokens_[position_ - 1]; }

    std::vector<Token> tokens_;
    const ExecutionLimits& limits_;
    std::size_t position_{};
    std::size_t depth_{};
    bool negativeBranch_{};
    bool hasChoice_{};
};

int precedence(const BinaryOperator op) {
    switch (op) {
        case BinaryOperator::Add:
        case BinaryOperator::Subtract:
            return 1;
        case BinaryOperator::Multiply:
        case BinaryOperator::Divide:
            return 2;
        case BinaryOperator::Power:
            return 3;
    }
    return 0;
}

std::string printWithPrecedence(const Expression& expression, const int parentPrecedence) {
    return std::visit(
        [parentPrecedence](const auto& node) -> std::string {
            using T = std::decay_t<decltype(node)>;
            if constexpr (std::is_same_v<T, IntegerExpr>) {
                return std::to_string(node.value);
            } else if constexpr (std::is_same_v<T, RationalExpr>) {
                const auto text = node.value.toString();
                return !node.value.isInteger() && parentPrecedence > 2 ? "(" + text + ")" : text;
            } else if constexpr (std::is_same_v<T, SymbolExpr>) {
                return node.name;
            } else if constexpr (std::is_same_v<T, std::shared_ptr<const UnaryExpr>>) {
                const auto text = "-" + printWithPrecedence(node->operand, 4);
                return parentPrecedence > 4 ? "(" + text + ")" : text;
            } else if constexpr (std::is_same_v<T, std::shared_ptr<const SquareRootExpr>>) {
                return "sqrt(" + printWithPrecedence(node->operand, 0) + ")";
            } else {
                const auto current = precedence(node->op);
                std::string symbol;
                switch (node->op) {
                    case BinaryOperator::Add:
                        symbol = " + ";
                        break;
                    case BinaryOperator::Subtract:
                        symbol = " - ";
                        break;
                    case BinaryOperator::Multiply:
                        symbol = " * ";
                        break;
                    case BinaryOperator::Divide:
                        symbol = " / ";
                        break;
                    case BinaryOperator::Power:
                        symbol = "^";
                        break;
                }
                const auto text =
                    printWithPrecedence(node->left, current) + symbol +
                    printWithPrecedence(node->right,
                                        current + (node->op == BinaryOperator::Power ? -1 : 1));
                return current < parentPrecedence ? "(" + text + ")" : text;
            }
        },
        expression);
}

}  // namespace

ParseResult parsePredicate(const std::string& source, const ExecutionLimits& limits) {
    std::optional<ParseError> lexError;
    auto tokens = lex(source, lexError);
    if (lexError.has_value()) {
        return {std::nullopt, std::move(lexError)};
    }
    return Parser(std::move(tokens), limits).parse();
}

std::string printExpression(const Expression& expression) {
    return printWithPrecedence(expression, 0);
}

std::string printPredicate(const Predicate& predicate) {
    std::ostringstream output;
    for (std::size_t index = 0; index < predicate.alternatives.size(); ++index) {
        if (index > 0) {
            output << " or ";
        }
        output << printExpression(predicate.alternatives[index].left) << " = "
               << printExpression(predicate.alternatives[index].right);
    }
    return output.str();
}

std::size_t countNodes(const Expression& expression) {
    return std::visit(
        [](const auto& node) -> std::size_t {
            using T = std::decay_t<decltype(node)>;
            if constexpr (std::is_same_v<T, std::shared_ptr<const UnaryExpr>> ||
                          std::is_same_v<T, std::shared_ptr<const SquareRootExpr>>) {
                return 1 + countNodes(node->operand);
            } else if constexpr (std::is_same_v<T, std::shared_ptr<const BinaryExpr>>) {
                return 1 + countNodes(node->left) + countNodes(node->right);
            } else {
                return 1;
            }
        },
        expression);
}

}  // namespace neomath
