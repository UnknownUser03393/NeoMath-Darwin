import SwiftUI

struct CompletionEnvelope: Decodable {
    var items: [MathCompletion]?
    var error: String?
}
struct MathCompletion: Decodable, Identifiable {
    var id: String
    var label: String
    var risk: String
    var available: Bool
    var reason: String
    var preview: String
    var riskDescription: String {
        switch risk {
        case "safe": return "Equivalent transformation"
        case "calculus": return "Calculation result · not an equivalent derivation step"
        case "may_add_solutions": return "May add solutions · check the next step"
        case "may_lose_solutions": return "May lose solutions · check the next step"
        default: return "Requires domain and solution-set review"
        }
    }
    private enum CodingKeys: String, CodingKey { case id, label, risk, available, reason, preview }
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(String.self, forKey: .id); label = try values.decodeIfPresent(String.self, forKey: .label) ?? id
        risk = try values.decodeIfPresent(String.self, forKey: .risk) ?? "requires_review"
        available = try values.decodeIfPresent(Bool.self, forKey: .available) ?? false
        reason = try values.decodeIfPresent(String.self, forKey: .reason) ?? ""
        preview = try values.decodeIfPresent(String.self, forKey: .preview) ?? ""
    }
}
struct TransformPalette: View {
    var doc: Notebook
    var trace: TraceResult? = nil
    var selected: UUID
    var onApply: (String, String) async -> Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var busy = false
    @State private var explanation = ""
    @State private var operation = "factor"
    @State private var argument = "2"
    @Environment(\.dismiss) private var dismiss
    @State private var completions: CompletionEnvelope?
    private func apply(_ operation: String, argument: String) {
        busy = true
        Task { defer { busy = false }; if await onApply(operation, argument) { dismiss() } }
    }
    private func operationTitle(_ item: MathCompletion) -> String {
        ["solve": "Solve", "factor": "Factor", "expand": "Expand", "move_terms": "Move terms", "multiply": "Multiply both sides by 2", "divide": "Divide both sides by 2", "square_both_sides": "Square both sides", "verify": "Verify current step"][item.id] ?? item.label
    }
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    if let cell = doc.cells.first(where: { $0.id == selected }) {
                        Text("Selected equation").font(.system(size: 15, weight: .semibold)).foregroundStyle(DarwinTheme.secondary)
                        TypesetMath(source: cell.source)
                    }
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Structured transformation").font(.headline)
                        Picker("Operation", selection: $operation) { ForEach(["factor", "expand", "simplify", "differentiate", "integrate", "move_terms", "multiply", "divide", "square_both_sides", "solve", "verify"], id: \.self) { Text($0.replacingOccurrences(of: "_", with: " ")).tag($0) } }
                        if ["multiply", "divide"].contains(operation) { TextField("Expression", text: $argument).textInputAutocapitalization(.never).autocorrectionDisabled().padding(12).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 8)) }
                        DarwinButton(title: busy ? "Working…" : "Apply transformation", selected: true) { apply(operation, argument: ["multiply", "divide"].contains(operation) ? argument : "") }.disabled(busy || (["multiply", "divide"].contains(operation) && argument.isEmpty))
                    }
                    Text("Next step").font(.system(size: 17, weight: .semibold))
                    if let items = completions?.items {
                        ForEach(items) { item in
                            Button {
                                guard item.available else { return }; apply(item.id, argument: "")
                            } label: {
                                VStack(alignment: .leading, spacing: 12) {
                                    HStack { Text(operationTitle(item)).font(.system(size: 15, weight: .semibold)); Spacer(); Image(systemName: "arrow.down") }
                                    if !item.preview.isEmpty { ScrollView(.horizontal) { TypesetMath(source: item.preview, size: 23) } }
                                    Text(item.available ? item.riskDescription : "Unavailable for this equation")
                                        .font(.system(size: 13)).foregroundStyle(item.risk == "safe" ? DarwinTheme.secondary : DarwinTheme.caution)
                                }.padding(20).frame(maxWidth: .infinity, alignment: .leading).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 10))
                            }.buttonStyle(DarwinPressStyle()).disabled(busy || !item.available).opacity(item.available ? 1 : 0.6)
                        }
                        if items.isEmpty { Text("No transformations are available for this step.").foregroundStyle(DarwinTheme.secondary) }
                    }
                    if let error = completions?.error { Text(error).foregroundStyle(DarwinTheme.fault) }
                    DarwinButton(title: "Explain", icon: "text.bubble") {
                        busy = true
                        Task {
                            defer { busy = false }
                            do { let reply = try await BackendClient().explain(source: doc.cells.filter { $0.kind != "markdown" }.map(\.source).joined(separator: "\n"), trace: trace); explanation = (reply["text"] as? String ?? "") + " (" + (reply["source"] as? String ?? "") + ")" }
                            catch { explanation = error.localizedDescription }
                        }
                    }.disabled(busy)
                    if !explanation.isEmpty { Text(explanation).font(.system(size: 14)).textSelection(.enabled).padding(12).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 12)).transition(reduceMotion ? .identity : .move(edge: .bottom)) }
                    Text("Suggestions come from the selected mathematical backend. Applying one inserts a new step and checks the derivation.").font(.caption).foregroundStyle(DarwinTheme.secondary)
                }.padding(24)
            }.background(DarwinTheme.canvas).navigationTitle("Transform").navigationBarTitleDisplayMode(.inline)
                .toolbar { Button("Cancel") { dismiss() } }
        }.task {
            let maths = doc.cells.filter { $0.kind != "markdown" }
            guard let index = maths.firstIndex(where: { $0.id == selected }) else { return }
            let source = maths.prefix(index+1).map(\.source).joined(separator: "\n")
            if UserDefaults.standard.bool(forKey: "darwin.useBackend") {
                do { let result = try await BackendClient().call("getCompletions", ["engine": "auto", "source": source, "step": index]); let data = try JSONSerialization.data(withJSONObject: result); completions = CompletionEnvelope(items: try JSONDecoder().decode([MathCompletion].self, from: data)) }
                catch { completions = CompletionEnvelope(error: error.localizedDescription) }
                return
            }
            completions = try? JSONDecoder().decode(CompletionEnvelope.self, from: MathCoreBridge.completions(source, step: index))
        }.foregroundStyle(DarwinTheme.ink).tint(DarwinTheme.accent)
        .animation(reduceMotion ? nil : DarwinMotion.panel, value: operation)
        .animation(reduceMotion ? nil : DarwinMotion.page, value: explanation)
        .presentationDetents([.medium, .large])
    }
}
