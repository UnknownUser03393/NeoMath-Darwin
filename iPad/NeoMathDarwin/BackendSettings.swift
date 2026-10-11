import SwiftUI

struct BackendSettings: View {
    @AppStorage("darwin.backendURL") private var url = "http://127.0.0.1:8765/api"
    @AppStorage("darwin.useBackend") private var useBackend = false
    @State private var model = ""
    @State private var workspace = ""
    @State private var configured = false
    @State private var status = ""
    @State private var busy = false
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Toggle("Use backend for derivation checks", isOn: $useBackend)
            TextField("API URL", text: $url).textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL).padding(.horizontal, 12).frame(minHeight: 44).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 10))
            DarwinButton(title: "Connect / refresh", selected: true) { Task { await refresh() } }.disabled(busy)
            if !workspace.isEmpty { LabeledContent("Workspace", value: workspace) }
            Text(configured ? "AI configured" : "AI uses the original local explanation fallback").font(.caption)
            TextField("Qwen model", text: $model).textInputAutocapitalization(.never).autocorrectionDisabled().padding(.horizontal, 12).frame(minHeight: 44).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 10))
            DarwinButton(title: "Save backend settings", selected: true) { Task { busy = true; defer { busy = false }; do { _ = try await BackendClient().call("saveSettings", ["qwen_model": model, "openai_model": model]); await refresh(); status = "Saved" } catch { status = error.localizedDescription } } }.disabled(busy || model.isEmpty)
            if !status.isEmpty { Text(status).font(.caption).textSelection(.enabled) }
        }.task { await refresh() }
    }
    private func refresh() async {
        busy = true; defer { busy = false }
        do { let settings = try await BackendClient().call("getSettings") as? [String: Any] ?? [:]; model = settings["qwenModel"] as? String ?? settings["openaiModel"] as? String ?? ""; workspace = settings["dataDir"] as? String ?? ""; configured = settings["qwenConfigured"] as? Bool ?? settings["openaiConfigured"] as? Bool ?? false; status = "Connected" }
        catch { status = error.localizedDescription }
    }
}
