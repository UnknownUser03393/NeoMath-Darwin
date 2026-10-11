import Foundation

struct BackendClient {
    static var base: String { UserDefaults.standard.string(forKey: "darwin.backendURL") ?? "http://127.0.0.1:8765/api" }
    func envelope(_ method: String, _ payload: [String: Any] = [:]) async throws -> [String: Any] {
        var payload = payload
        if ["parseDocument", "analyzeDocument", "runTrace", "replay", "getCompletions", "executeTransformation", "evaluateProbe"].contains(method) {
            payload["engine"] = "auto"
            if payload["document"] == nil, let source = payload.removeValue(forKey: "source") as? String { payload["document"] = ["source": source] }
        }
        guard let url = URL(string: Self.base.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/" + method), ["http", "https"].contains(url.scheme ?? "") else { throw BackendError("Invalid backend URL") }
        var request = URLRequest(url: url, timeoutInterval: 15)
        request.httpMethod = method == "health" ? "GET" : "POST"; request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if method != "health" { request.httpBody = try JSONSerialization.data(withJSONObject: payload) }
        let data: Data
        let response: URLResponse
        do { (data, response) = try await URLSession.shared.data(for: request) }
        catch {
            let details = String(describing: error as NSError)
            if details.contains("Local network prohibited") {
                throw BackendError("Allow NeoMath in Settings → Privacy & Security → Local Network, then reconnect. Server: \(Self.base)")
            }
            throw BackendError("\(error.localizedDescription) Server: \(Self.base)", code: String((error as NSError).code))
        }
        guard let result = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { throw BackendError("Invalid NeoMath response") }
        guard (response as? HTTPURLResponse)?.statusCode == 200, result["ok"] as? Bool == true else {
            let error = result["error"] as? [String: Any] ?? [:]
            throw BackendError(error["message"] as? String ?? "NeoMath request failed", code: error["code"] as? String)
        }
        return result
    }
    func explain(source: String, trace: TraceResult?) async throws -> [String: Any] {
        var payload: [String: Any] = ["source": source, "document": ["source": source]]
        if let raw = trace?.backendTrace { payload["trace"] = ["ok": true, "result": try JSONSerialization.jsonObject(with: JSONEncoder().encode(raw))] }
        return try await envelope("requestAiExplanation", payload)
    }
    func call(_ method: String, _ payload: [String: Any] = [:]) async throws -> Any { try await envelope(method, payload)["result"] ?? NSNull() }
}
struct BackendError: LocalizedError { var message: String; var code: String?; init(_ message: String, code: String? = nil) { self.message = message; self.code = code }; var errorDescription: String? { code.map { $0 + ": " + message } ?? message } }
