import SwiftUI

struct DarwinInspector: View {
    var doc: Notebook
    var trace: TraceResult?
    var selected: UUID?
    var relation: Bool
    var pinned: Bool
    var onPin: () -> Void
    var onClose: () -> Void
    var onEdit: () -> Void
    var onTransform: (UUID, String) -> Void
    var onGoFault: () -> Void
    @Namespace private var tabSelection
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var tab = "Overview"
    @State private var value = "0"
    @State private var probe: TraceResult?
    @State private var substitution = false
    @State private var explanationText = ""
    @State private var explanationSource = ""
    @State private var explaining = false
    @State private var explanationGeneration = 0
    @State private var probeGeneration = 0
    private var maths: [Cell] { doc.cells.filter { $0.kind != "markdown" } }
    private var index: Int? { maths.firstIndex { $0.id == selected } }
    private var result: StepResult? { index.flatMap { trace?.steps?.indices.contains($0) == true ? trace?.steps?[$0] : nil } }
    private var before: StepResult? { guard let i = index, i > 0, trace?.steps?.indices.contains(i-1) == true else { return nil }; return trace?.steps?[i-1] }
    private var heading: String { guard let i = index else { return "Inspect" }; return relation && i > 0 ? "Step \(i) → \(i+1)" : "Step \(i+1)" }
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(heading).font(.system(size: 17, weight: .semibold))
                Spacer()
                DarwinButton(title: "", icon: pinned ? "pin.fill" : "pin", selected: pinned) { onPin() }.accessibilityLabel("Pin inspector")
                DarwinButton(title: "", icon: "xmark") { onClose() }.accessibilityLabel("Close inspector")
            }.padding(.horizontal, 16).frame(minHeight: 56)
            Divider().overlay(DarwinTheme.separator)
            HStack(spacing: 4) {
                ForEach(["Overview", "Evidence", "Details"], id: \.self) { item in
                    Button { withAnimation(reduceMotion ? nil : DarwinMotion.panel) { tab = item } } label: {
                        Text(item).font(.system(size: 13, weight: .medium)).frame(maxWidth: .infinity).frame(height: 44)
                            .foregroundStyle(tab == item ? DarwinTheme.accent : DarwinTheme.secondary)
                            .background { if tab == item { RoundedRectangle(cornerRadius: 8).fill(DarwinTheme.elevated).matchedGeometryEffect(id: "tab", in: tabSelection) } }
                    }.buttonStyle(DarwinPressStyle())
                }
            }.padding(4).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 10)).padding(12)
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if let result, let index {
                        status(result, index: index)
                        if tab == "Overview" { overview(result, index: index) }
                        else if tab == "Evidence" { evidence(result, index: index) }
                        else { details(result) }
                    } else {
                        Image(systemName: "cursorarrow.click").font(.system(size: 26)).foregroundStyle(DarwinTheme.tertiary)
                        Text(selected == nil ? "Select a step or relation to inspect." : trace?.error ?? "Run Check to obtain the mathematical state.")
                            .font(.system(size: 15)).foregroundStyle(DarwinTheme.secondary)
                    }
                }.id(tab).transition(reduceMotion ? .identity : .asymmetric(insertion: .move(edge: .trailing), removal: .move(edge: .leading))).padding(20).frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .onChange(of: selected) { _, _ in probeGeneration += 1; explanationGeneration += 1; probe = nil; substitution = false; explanationText = ""; explanationSource = ""; explaining = false }
        .onChange(of: doc.cells) { _, _ in probeGeneration += 1; explanationGeneration += 1; probe = nil; substitution = false; explanationText = ""; explanationSource = ""; explaining = false }
    }
    private func status(_ r: StepResult, index: Int) -> some View {
        HStack(spacing: 10) {
            Image(systemName: r.status == "valid" ? "checkmark.circle" : r.status == "tainted" ? "arrow.turn.down.right" : "exclamationmark.circle")
            Text(title(r, index: index)).font(.system(size: 17, weight: .semibold))
        }.foregroundStyle(index == 0 ? DarwinTheme.secondary : DarwinTheme.tone(r.status))
    }
    private func title(_ r: StepResult, index: Int) -> String {
        if r.lost?.isEmpty == false { return "Lost solution" }
        if r.gained?.isEmpty == false { return "Extraneous solution" }
        switch r.status { case "valid": return index == 0 ? "Initial state" : "Equivalent"; case "tainted": return "Affected by upstream step"; case "root_fault": return "Domain or solution changed"; case "parse_error": return "Syntax error"; default: return "Unverified" }
    }
    private func overview(_ r: StepResult, index: Int) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            section("Equations") {
                if index > 0 {
                    compareBlock("Before · Step \(index)", source: maths[index-1].source)
                }
                compareBlock(index > 0 ? "After · Step \(index+1)" : "Equation", source: r.source)
            }
            section("Solution set") {
                HStack(alignment: .top, spacing: 16) {
                    if let before { setColumn("Before", value: before.solutions) }
                    setColumn(before == nil ? "Solutions" : "After", value: r.solutions)
                }
                if let lost = r.lost, !lost.isEmpty {
                    HStack { Text("Lost").font(.system(size: 13)).foregroundStyle(DarwinTheme.fault); TypesetMath(source: "{" + lost.joined(separator: ", ") + "}", size: 21) }
                }
            }
            if let gained = r.gained, !gained.isEmpty {
                section("Gained solutions") { TypesetMath(source: "{" + gained.joined(separator: ", ") + "}", size: 21) }
            }
            section("Domain") { HStack(alignment: .top, spacing: 16) { if let before { setColumn("Before", value: before.domain) }; setColumn(before == nil ? "Domain" : "After", value: r.domain) }; if r.domainExpanded == true { Text("Domain expanded").font(.caption).foregroundStyle(DarwinTheme.caution) }; if r.domainShrunk == true { Text("Domain shrunk").font(.caption).foregroundStyle(DarwinTheme.caution) } }
            if let witness = r.witness {
                section("Witness") { witnessBlock(r, value: witness) }
            }
            section("Why this step matters") {
                Text(explanation(r)).font(.system(size: 15)).foregroundStyle(DarwinTheme.secondary)
            }
            HStack {
                DarwinButton(title: "Edit source", selected: true) { onEdit() }
                if r.status == "tainted" { DarwinButton(title: "First fault") { onGoFault() } }
            }
            if let id = selected {
                DarwinButton(title: "Transform", icon: "arrow.triangle.branch") { onTransform(id, "") }
                DarwinButton(title: explaining ? "Explaining…" : "Explain", icon: "text.bubble") {
                    let source = maths.prefix(index + 1).map(\.source).joined(separator: "\n")
                    explanationGeneration += 1; let token = explanationGeneration; explaining = true
                    Task {
                        defer { if token == explanationGeneration { explaining = false } }
                        do { let reply = try await BackendClient().explain(source: source, trace: trace); guard token == explanationGeneration else { return }; explanationText = reply["text"] as? String ?? ""; explanationSource = reply["source"] as? String ?? "" }
                        catch { guard token == explanationGeneration else { return }; explanationText = error.localizedDescription; explanationSource = "Connection error" }
                    }
                }.disabled(explaining)
                if !explanationText.isEmpty { section("Explanation · " + explanationSource) { Text(explanationText).font(.system(size: 15)).textSelection(.enabled) } }
            }
        }
    }
    private func evidence(_ r: StepResult, index: Int) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            section("Automatic witness") {
                if let witness = r.witness { witnessBlock(r, value: witness) }
                else { Text("No counterexample returned. This alone does not prove equivalence.").font(.system(size: 15)).foregroundStyle(DarwinTheme.secondary) }
            }
            section("Manual probe") {
                Text(r.variable ?? "x").font(.system(size: 13)).foregroundStyle(DarwinTheme.secondary)
                TextField("Exact rational, e.g. 1/2", text: $value).textInputAutocapitalization(.never).autocorrectionDisabled()
                    .padding(12).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 10))
                DarwinButton(title: "Evaluate", selected: true) { runProbe(index) }
                Text("Single-point evaluation; not a proof of equivalence or completeness.").font(.system(size: 12)).foregroundStyle(DarwinTheme.secondary)
                if let probe { probeRows(probe) }
            }
        }
    }
    private func details(_ r: StepResult) -> some View {
        section("Mathematical state") {
            LabeledContent("Engine", value: r.engine ?? "C++ MathCore")
            LabeledContent("Status", value: r.status)
            if let trust = r.trust { LabeledContent("Trust", value: trust) }
            if let verification = r.verification {
                LabeledContent("Verification", value: verification.status)
                LabeledContent("Target", value: verification.target)
                LabeledContent("Method", value: verification.method)
                ForEach(verification.limitations, id: \.self) { Text($0).font(.caption) }
            }
            if let hits = trace?.cacheHits { LabeledContent("Reused states", value: String(hits)) }
            Text("Domain").font(.caption).foregroundStyle(DarwinTheme.secondary)
            TypesetMath(source: r.domain, size: 21)
            if let ms = trace?.durationMs { LabeledContent("Duration", value: String(format: "%.2f ms", ms)) }
            Text(r.reason).font(.system(size: 13)).foregroundStyle(DarwinTheme.secondary)
            Text(r.engine == nil || r.engine == "C++20" ? "Exact rational arithmetic. Unsupported expressions remain unverified." : "Verification and limitations are reported by the selected mathematical engine.").font(.system(size: 13)).foregroundStyle(DarwinTheme.secondary)
            if pinned { Text("Pinned to \(heading)").font(.caption).foregroundStyle(DarwinTheme.accent) }
        }
    }
    private func explanation(_ r: StepResult) -> String {
        if r.lost?.isEmpty == false { return "This step removes a solution of the previous equation. Substitute the witness to see where the two equations disagree." }
        if r.gained?.isEmpty == false { return "This step adds a solution that does not satisfy the previous equation. Check the witness in both equations." }
        if r.status == "tainted" { return "An earlier step changed the solution set. Review the first fault before continuing this derivation." }
        if r.status == "valid" { return "\(r.engine ?? "MathCore") established the mathematical state. The reported verification method and limitations apply." }
        return r.message.isEmpty ? r.reason : r.message
    }
    private func section<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.system(size: 15, weight: .semibold)).foregroundStyle(DarwinTheme.secondary).padding(.horizontal, 4)
            VStack(alignment: .leading, spacing: 12, content: content).frame(maxWidth: .infinity, alignment: .leading)
                .padding(12).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 14))
        }
    }
    private func compareBlock(_ label: String, source: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label).font(.system(size: 12)).foregroundStyle(DarwinTheme.tertiary)
            ScrollView(.horizontal) { TypesetMath(source: source, size: 21) }
        }.padding(.vertical, 8).frame(maxWidth: .infinity, alignment: .leading)
    }
    private func setColumn(_ label: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 8) { Text(label).font(.system(size: 12)).foregroundStyle(DarwinTheme.tertiary); TypesetMath(source: value, size: 21) }.frame(maxWidth: .infinity, alignment: .leading)
    }
    private func witnessBlock(_ r: StepResult, value: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Counterexample").font(.system(size: 12)).foregroundStyle(DarwinTheme.tertiary)
            TypesetMath(source: "x = " + value, size: 28)
            HStack(spacing: 32) { verdict("Before", value: r.before ?? "Unknown"); verdict("After", value: r.after ?? "Unknown") }
            DarwinButton(title: substitution ? "Hide substitution" : "Substitute", selected: true) {
                substitution.toggle(); if substitution, let index { runProbe(index, value: value) }
            }
            if substitution, let left = r.previousLeft, let right = r.previousRight { LabeledContent("Before · left / right", value: left + " / " + right) }
            if substitution, let left = r.left, let right = r.right { LabeledContent("After · left / right", value: left + " / " + right) }
            if substitution, let probe { probeRows(probe) }
        }
    }
    private func verdict(_ label: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 6) { Text(label).font(.system(size: 12)).foregroundStyle(DarwinTheme.tertiary); Text(value).font(.system(size: 15, weight: .semibold)).foregroundStyle(value == "True" ? DarwinTheme.verified : value == "False" ? DarwinTheme.fault : DarwinTheme.secondary) }
    }
    private func probeRows(_ probe: TraceResult) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            if let error = probe.error { Text(error).foregroundStyle(DarwinTheme.fault) }
            ForEach(Array((probe.steps ?? []).enumerated()), id: \.offset) { i, e in
                VStack(alignment: .leading, spacing: 6) {
                HStack { Text("Step \(i+1)").font(.system(size: 13)); Spacer(); Text(e.after ?? "Unknown").font(.system(size: 13, weight: .semibold)).foregroundStyle(e.after == "True" ? DarwinTheme.verified : DarwinTheme.fault) }
                if let left = e.left, let right = e.right { Text("Left \(left) · Right \(right)").font(.caption).foregroundStyle(DarwinTheme.secondary) }
                }.padding(12).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 10))
            }
        }
    }
    private func runProbe(_ index: Int, value: String? = nil) {
        let source = maths.prefix(index + 1).map(\.source).joined(separator: "\n")
        if UserDefaults.standard.bool(forKey: "darwin.useBackend") {
            probeGeneration += 1; let token = probeGeneration
            let value = value ?? self.value
            Task {
                do {
                    let reply = try await BackendClient().call("evaluateProbe", ["engine": "auto", "source": source, "probe": ["value": value]]) as? [String: Any] ?? [:]
                    let evaluations = reply["steps"] as? [[String: Any]] ?? []
                    if token == probeGeneration {
                        probe = TraceResult(steps: evaluations.map { e in StepResult(source: "", solutions: "", domain: "", status: "probe", title: "Substitution", message: "", reason: e["reason"] as? String ?? "", after: BackendTrace.predicate(e["predicateResult"], defined: e["defined"]), left: e["leftValue"] as? String, right: e["rightValue"] as? String) })
                    }
                } catch { if token == probeGeneration { probe = TraceResult(error: error.localizedDescription) } }
            }
        } else { probe = try? JSONDecoder().decode(TraceResult.self, from: MathCoreBridge.probe(source, value: value ?? self.value)) }
    }
}
