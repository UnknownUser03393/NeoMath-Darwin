import Foundation

enum BackendTrace {
    static func set(_ raw: Any?) -> String {
        guard let s = raw as? [String: Any] else { return "—" }
        if s["kind"] as? String == "unverified" { return "Unknown" + ((s["display"] as? String).map { " · " + $0 } ?? "") }
        if let display = s["display"] as? String { return display }
        switch s["kind"] as? String {
        case "finite": return "{" + (s["values"] as? [String] ?? []).joined(separator: ", ") + "}"
        case "empty": return "∅"
        case "all_real": return "ℝ"
        case "expression": return "Unknown"
        case "interval":
            let lower = s["lower"] as? String ?? "−∞", upper = s["upper"] as? String ?? "∞"
            return (s["lowerInclusive"] as? Bool == true && !lower.contains("∞") ? "[" : "(") + lower + ", " + upper + (s["upperInclusive"] as? Bool == true && !upper.contains("∞") ? "]" : ")")
        case "all_real_except_finite", "all_real_excluding_finite", "real_excluding_finite": let excluded = s["excluded"] as? [String] ?? []; return "ℝ ∖ {" + excluded.joined(separator: ", ") + "}"
        default: return "Unknown"
        }
    }
    static func decode(_ envelope: [String: Any], expectedSteps: Int? = nil, method: String? = nil) throws -> TraceResult {
        guard envelope["ok"] as? Bool == true, let raw = envelope["result"] as? [String: Any], let states = raw["states"] as? [[String: Any]], let diagnostics = raw["diagnostics"] as? [[String: Any]], diagnostics.count == states.count, expectedSteps == nil || expectedSteps == states.count else { throw BackendError("Incomplete mathematical response; verification unavailable") }
        let relations = raw["relations"] as? [[String: Any]] ?? []
        let steps = states.enumerated().map { i, state in
            let diagnostic = diagnostics.indices.contains(i) ? diagnostics[i] : [:]
            let relation = i > 0 && relations.indices.contains(i-1) ? relations[i-1] : [:]
            let probe = relation["probe"] as? [String: Any] ?? [:]
            let proof = verification(state["verification"])
            var status = diagnostic["status"] as? String ?? "unverified"
            if status == "valid" && (proof?.status != "verified" || state["trustLevel"] as? String == "unverified" || (i > 0 && relation["relation"] as? String != "equivalent")) { status = "unverified" }
            let downgraded = status != diagnostic["status"] as? String
            let unavailable = "Verification remains unknown for this mathematical state; no verified equivalence is reported."
            return StepResult(source: state["source"] as? String ?? "", solutions: set(state["solutionSet"]), domain: set(state["domain"]), status: status, title: downgraded ? "Unverified" : diagnostic["title"] as? String ?? "", message: downgraded ? unavailable : diagnostic["message"] as? String ?? "", reason: downgraded ? unavailable : relation["reason"] as? String ?? state["reason"] as? String ?? "", lost: relation["lostSolutions"] as? [String], gained: relation["gainedSolutions"] as? [String], relation: relation["relation"] as? String, witness: probe["value"] as? String, before: predicate(probe["previousPredicateResult"], defined: probe["previousDefined"]), after: predicate(probe["currentPredicateResult"], defined: probe["currentDefined"]), engine: state["engine"] as? String ?? raw["engine"] as? String ?? "Unknown", trust: state["trustLevel"] as? String, verification: proof, variable: state["variable"] as? String, left: probe["currentLeftValue"] as? String, right: probe["currentRightValue"] as? String, previousLeft: probe["previousLeftValue"] as? String, previousRight: probe["previousRightValue"] as? String, domainExpanded: relation["domainExpanded"] as? Bool, domainShrunk: relation["domainShrunk"] as? Bool)
        }
        let metrics = envelope["metrics"] as? [String: Any] ?? [:]
        let original = (try? JSONSerialization.data(withJSONObject: raw)).flatMap { try? JSONDecoder().decode([String: JSONValue].self, from: $0) }
        return TraceResult(backendTrace: original, method: method, steps: steps, durationMs: (metrics["durationMs"] as? NSNumber)?.doubleValue, cacheHits: (metrics["cacheHits"] as? NSNumber)?.intValue, engine: raw["engine"] as? String ?? "Unknown")
    }
    static func verification(_ raw: Any?) -> Verification? { guard let raw, let data = try? JSONSerialization.data(withJSONObject: raw) else { return nil }; return try? JSONDecoder().decode(Verification.self, from: data) }
    static func predicate(_ raw: Any?, defined: Any?) -> String? { if defined as? Bool == false { return "Undefined" }; return (raw as? Bool).map { $0 ? "True" : "False" } }
}
