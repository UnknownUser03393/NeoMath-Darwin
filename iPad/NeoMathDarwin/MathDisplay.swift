import Foundation

// Port of origin/main src/math-format.ts: presentation parsing, never a solver.
enum MathDisplay {
    static func latex(_ source: String) -> String {
        var raw = source.trimmingCharacters(in: .whitespacesAndNewlines)
        if raw.hasPrefix("$$"), raw.hasSuffix("$$"), raw.count >= 4 { raw = String(raw.dropFirst(2).dropLast(2)) }
        else if raw.hasPrefix("$"), raw.hasSuffix("$"), raw.count >= 2 { raw = String(raw.dropFirst().dropLast()) }
        if raw.range(of: #"\\[a-zA-Z]+"#, options: .regularExpression) != nil { return raw }
        for (from, to) in [("−", "-"), ("–", "-"), ("×", "*"), ("·", "*"), ("⋅", "*"), ("÷", "/"), ("√", "sqrt")] { raw = raw.replacingOccurrences(of: from, with: to) }
        if raw.hasPrefix("ℝ"), let brace = raw.firstIndex(of: "{"), raw.contains("∖") || raw.contains("\\") { return "\\mathbb{R} \\setminus " + latex(String(raw[brace...])) }
        if raw.hasPrefix("{"), raw.hasSuffix("}") { return "\\left\\{" + raw.dropFirst().dropLast().components(separatedBy: ",").map(latex).joined(separator: ",\\,") + "\\right\\}" }
        if raw.range(of: #"^[\[(][^,]+,[^,]+[\])]$"#, options: .regularExpression) != nil { let inner = String(raw.dropFirst().dropLast()).components(separatedBy: ","); return "\\left" + String(raw.first!) + latex(inner[0]) + ",\\," + latex(inner[1]) + "\\right" + String(raw.last!) }
        if raw.contains("ℝ") || raw.contains("∅") || raw.contains("∞") { return raw.replacingOccurrences(of: "ℝ", with: "\\mathbb{R}").replacingOccurrences(of: "∅", with: "\\emptyset").replacingOccurrences(of: "∞", with: "\\infty") }
        return (try? Parser(raw).parse()) ?? raw
    }
    private final class Parser {
        struct Expression { var tex: String; var inner: String? }
        enum Invalid: Error { case notation }
        var tokens: [String]; var index = 0; var valid: Bool
        init(_ source: String) {
            let regex = try! NSRegularExpression(pattern: #"[a-zA-Z_][a-zA-Z_0-9]*|(?:\d+(?:\.\d*)?|\.\d+)|>=|<=|!=|[+\-±∓*/^()=<>≥≤≠]"#)
            let ns = source as NSString
            tokens = regex.matches(in: source, range: NSRange(location: 0, length: ns.length)).map { ns.substring(with: $0.range) }
            valid = tokens.joined() == source.replacingOccurrences(of: #"\s"#, with: "", options: .regularExpression)
        }
        var peek: String { tokens.indices.contains(index) ? tokens[index] : "" }
        func take() throws -> String { guard tokens.indices.contains(index) else { throw Invalid.notation }; defer { index += 1 }; return tokens[index] }
        func expect(_ token: String) throws { guard try take() == token else { throw Invalid.notation } }
        func atom() throws -> Expression {
            let token = try take()
            if token == "(" { let inner = try expression().tex; try expect(")"); return Expression(tex: "\\left(" + inner + "\\right)", inner: inner) }
            if token == "sqrt" { let body = try atom(); return Expression(tex: "\\sqrt{" + (body.inner ?? body.tex) + "}") }
            if ["sin", "cos", "tan", "asin", "acos", "atan", "exp", "log", "ln", "abs"].contains(token) {
                try expect("("); let body = try expression().tex; try expect(")")
                if token == "abs" { return Expression(tex: "\\left|" + body + "\\right|") }
                return Expression(tex: "\\" + (["asin": "arcsin", "acos": "arccos", "atan": "arctan"][token] ?? token) + "\\left(" + body + "\\right)")
            }
            if token == "pi" { return Expression(tex: "\\pi") }
            guard token.range(of: #"^(?:\d+(?:\.\d*)?|\.\d+|[a-zA-Z_][a-zA-Z_0-9]*)$"#, options: .regularExpression) != nil else { throw Invalid.notation }
            return Expression(tex: token.replacingOccurrences(of: "_", with: "\\_"))
        }
        func power() throws -> Expression { let base = try atom(); guard peek == "^" else { return base }; _ = try take(); let exponent = try unary(); return Expression(tex: base.tex + "^{" + (exponent.inner ?? exponent.tex) + "}") }
        func unary() throws -> Expression { if ["-", "+", "±", "∓"].contains(peek) { let sign = try take(); return Expression(tex: (sign == "±" ? "\\pm " : sign == "∓" ? "\\mp " : sign) + (try unary().tex)) }; return try power() }
        func product() throws -> Expression {
            var left = try unary()
            while ["*", "/", "(", "sqrt"].contains(peek) || (peek.range(of: #"^[a-zA-Z_0-9.]"#, options: .regularExpression) != nil && peek != "or") {
                let operation = ["*", "/"].contains(peek) ? try take() : "implicit", right = try unary()
                left = Expression(tex: operation == "/" ? "\\frac{" + (left.inner ?? left.tex) + "}{" + (right.inner ?? right.tex) + "}" : left.tex + (operation == "*" ? " \\cdot " : "\\,") + right.tex)
            }
            return left
        }
        func expression() throws -> Expression { var left = try product(); while ["+", "-", "±", "∓"].contains(peek) { let operation = try take(); left = Expression(tex: left.tex + " " + (operation == "±" ? "\\pm" : operation == "∓" ? "\\mp" : operation) + " " + (try product().tex)) }; return left }
        func relation() throws -> String { var tex = try expression().tex; let operators = ["=": "=", "<": "<", ">": ">", ">=": "\\ge", "<=": "\\le", "!=": "\\ne", "≥": "\\ge", "≤": "\\le", "≠": "\\ne"]; while let op = operators[peek] { _ = try take(); tex += " " + op + " " + (try expression().tex) }; return tex }
        func parse() throws -> String { guard valid else { throw Invalid.notation }; var tex = try relation(); while peek == "or" { _ = try take(); tex += " \\quad\\text{or}\\quad " + (try relation()) }; guard index == tokens.count else { throw Invalid.notation }; return tex }
    }
}
