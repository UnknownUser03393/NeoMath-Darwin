import SwiftUI
import WebKit

@MainActor final class WritingStore: ObservableObject {
    @Published var files: [String] = []
    @Published var name = ""
    @Published var fileNames: [String: String] = [:]
    var displayName: String { fileNames[name] ?? name }
    @Published var source = ""
    @Published var css = ""
    @Published var output: [String: Any] = [:]
    @Published var error: String?
    @Published var compiling = false
    @Published var previewCurrent = false
    @Published var saveStatus = "Saved"
    @Published var automatic = true
    @Published var verify = true
    @Published var execute = true
    @Published var selection: NSRange?
    private var revision = 0
    private var session: String?
    private var queue: Task<Void, Never>?
    private var debounce: Task<Void, Never>?
    private var saveTask: Task<Void, Never>?
    private var saveQueue: Task<Void, Never>?
    private var generation = 0
    private let api = BackendClient()
    func create(_ title: String) async {
        let base = title.trimmingCharacters(in: .whitespacesAndNewlines)
        var name = base; var suffix = 2
        while files.contains(name) { name = base + " " + String(suffix); suffix += 1 }
        guard !name.isEmpty else { return }
        do { _ = try await api.call("saveXdltDocument", ["name": name, "source": "# " + name + "\n\n"]); await refresh(); await open(name) }
        catch { self.error = error.localizedDescription }
    }
    func refresh() async {
        do {
            let result = try await api.call("listXdltDocuments")
            let list = (result as? [String: Any])?["files"] as? [[String: Any]] ?? result as? [[String: Any]] ?? []
            files = list.compactMap { $0["name"] as? String }
            fileNames = Dictionary(list.compactMap { file in guard let name = file["name"] as? String, let fileName = file["fileName"] as? String else { return nil }; return (name, fileName) }, uniquingKeysWith: { first, _ in first })
            css = (try await api.call("getXdltReferenceCss") as? [String: Any])?["css"] as? String ?? ""
        } catch { self.error = error.localizedDescription }
    }
    func open(_ name: String) async {
        await close()
        do {
            let value = try await api.call("loadXdltDocument", ["name": name]) as? [String: Any]
            self.name = name; source = value?["source"] as? String ?? ""; output = [:]; previewCurrent = false; saveStatus = "Saved"
            compile()
        } catch { self.error = error.localizedDescription }
    }
    func edited(_ value: String, composing: Bool) {
        source = value; generation += 1; previewCurrent = false; saveStatus = "Unsaved"
        saveTask?.cancel()
        let name = name
        saveTask = Task {
            do {
                try await Task.sleep(for: .milliseconds(700)); try Task.checkCancellation()
                let previous = saveQueue
                let write = Task {
                    await previous?.value
                    do {
                        _ = try await api.call("saveXdltDocument", ["name": name, "source": value])
                        if self.name == name && source == value { saveStatus = "Saved" }
                    } catch { if self.name == name && source == value { saveStatus = "Save failed"; self.error = error.localizedDescription } }
                }
                saveQueue = write; await write.value
            } catch is CancellationError { } catch { saveStatus = "Save failed"; self.error = error.localizedDescription }
        }
        debounce?.cancel()
        if automatic && !composing { debounce = Task { try? await Task.sleep(for: .milliseconds(250)); if !Task.isCancelled { compile() } } }
    }
    func save() async {
        saveTask?.cancel()
        let previous = saveQueue, name = name, content = source
        guard !name.isEmpty else { return }
        saveStatus = "Saving…"
        let write = Task {
            await previous?.value
            do {
                _ = try await api.call("saveXdltDocument", ["name": name, "source": content])
                if self.name == name && source == content { saveStatus = "Saved" }
            } catch { saveStatus = "Save failed"; self.error = error.localizedDescription }
        }
        saveQueue = write
        await write.value
    }
    func compile() {
        debounce?.cancel(); generation += 1
        let token = generation, content = source, verify = verify, execute = execute, previous = queue
        previewCurrent = false; compiling = true
        queue = Task {
            await previous?.value
            guard token == generation else { return }
            do {
                var payload: [String: Any] = ["content": content, "mode": "fragment", "verify": verify, "execute": execute]
                var reply: [String: Any]
                if let session {
                    payload["sessionId"] = session
                    do { reply = try await api.envelope("updateXdltSession", payload) }
                    catch { if error.localizedDescription.contains("unknown session") { self.session = nil; payload.removeValue(forKey: "sessionId"); reply = try await api.envelope("createXdltSession", payload) } else { throw error } }
                } else { reply = try await api.envelope("createXdltSession", payload) }
                let continuing = payload["sessionId"] != nil && reply["sessionId"] == nil
                if let created = reply["sessionId"] as? String { session = created }
                let previousRevision = revision
                revision += 1
                if token == generation {
                    guard var compiled = reply["result"] as? [String: Any], compiled["html"] is String else { throw BackendError("Incomplete Writing compilation response") }
                    compiled["revision"] = revision
                    if continuing { compiled["previousRevision"] = previousRevision }
                    compiled["sourceMapUnit"] = "lines"
                    output = compiled; previewCurrent = true; compiling = false
                }
            } catch { if token == generation { output = [:]; self.error = error.localizedDescription; compiling = false } }
        }
    }
    func close() async {
        debounce?.cancel(); generation += 1
        await queue?.value; await saveTask?.value; await saveQueue?.value
        if let session { _ = try? await api.call("destroyXdltSession", ["sessionId": session]) }
        session = nil; compiling = false
    }
    func locate(_ id: String) {
        let maps = output["sourceMap"] as? [[String: Any]] ?? []
        guard let range = maps.first(where: { $0["renderId"] as? String == id })?["sourceRange"] as? [String: Any], let start = range["start"] as? Int, let end = range["end"] as? Int else { return }
        if output["sourceMapUnit"] as? String == "lines" || output["revision"] == nil {
            let lines = source.components(separatedBy: "\n")
            let prefix = lines.prefix(start).joined(separator: "\n")
            let body = lines.dropFirst(start).prefix(max(0, end - start)).joined(separator: "\n")
            selection = NSRange(location: prefix.utf16.count + (start > 0 ? 1 : 0), length: body.utf16.count)
            return
        }
        let scalars = source.unicodeScalars
        let a = scalars.index(scalars.startIndex, offsetBy: min(max(0, start), scalars.count))
        let b = scalars.index(scalars.startIndex, offsetBy: min(max(start, end), scalars.count))
        let offset = String(scalars[..<a]).utf16.count
        selection = NSRange(location: offset, length: String(scalars[a..<b]).utf16.count)
    }
}

struct WritingWorkspace: View {
    @StateObject private var store = WritingStore()
    var initialName: String? = nil
    var onBack: () -> Void
    @State private var debug = false
    @State private var creating = false
    @State private var title = ""
    @State private var sourceCaret = NSRange(location: 0, length: 0)
    @State private var equationRange: NSRange?
    @State private var equationDraft = ""
    @State private var replacingEquation = false
    @State private var compactPane = "Write"
    var body: some View {
        GeometryReader { size in
            VStack(spacing: 0) {
                HStack(spacing: 16) {
                    DarwinButton(title: "Documents", icon: "chevron.left") { Task { await store.close(); onBack() } }
                    Menu { ForEach(store.files, id: \.self) { name in Button(store.fileNames[name] ?? name) { Task { await store.open(name) } } } } label: {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(store.name.isEmpty ? "Writing" : writingTitle).font(.system(size: 17, weight: .semibold)).lineLimit(1)
                            Text("Writing · XDLT").font(.caption).foregroundStyle(DarwinTheme.secondary)
                        }.foregroundStyle(DarwinTheme.ink)
                    }.frame(maxWidth: .infinity, alignment: .leading)
                    DarwinButton(title: store.compiling ? "Compiling…" : "Compile", selected: true) { store.compile() }.disabled(store.name.isEmpty).keyboardShortcut(.return, modifiers: .command)
                    DarwinButton(title: store.saveStatus) { Task { await store.save() } }.keyboardShortcut("s")
                    Menu {
                        Button("New writing document", systemImage: "plus") { creating = true }
                        Divider()
                        Toggle("Auto compile", isOn: $store.automatic)
                        Toggle("Verify assertions", isOn: $store.verify)
                        Toggle("Run exec", isOn: $store.execute)
                        Divider()
                        Toggle("Show debug panel", isOn: $debug)
                    } label: { Image(systemName: "ellipsis.circle").font(.system(size: 21)).frame(width: 44, height: 44) }.accessibilityLabel("Writing options")
                }.padding(.horizontal, 16).padding(.vertical, 8).background(DarwinTheme.panel)
                Divider()
                if !store.name.isEmpty { Text(store.compiling ? "Compiling…" : store.previewCurrent ? "Compiled · current preview" : "Pending compilation").font(.caption).foregroundStyle(DarwinTheme.secondary).frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 12).padding(.vertical, 6) }
                if store.name.isEmpty {
                    List { Section("Writing documents") { ForEach(store.files, id: \.self) { name in Button(store.fileNames[name] ?? name) { Task { await store.open(name) } } } } }
                    if store.files.isEmpty { ContentUnavailableView("Writing workspace", systemImage: "doc.richtext", description: Text("Connect the NeoMath backend in Settings to open .hw documents.")) }
                } else {
                    if size.size.width >= 1000 { HStack(spacing: 1) { editor; preview } } else {
                        Picker("Writing pane", selection: $compactPane) { Text("Write").tag("Write"); Text("Preview").tag("Preview") }.pickerStyle(.segmented).padding(12)
                        if compactPane == "Write" { editor } else { preview }
                    }
                    if equationRange != nil {
                        VStack(spacing: 4) {
                            HStack {
                                Text(replacingEquation ? "Edit equation" : "Insert equation").font(.subheadline.weight(.semibold))
                                Spacer()
                                DarwinButton(title: "Cancel") { equationRange = nil }
                                DarwinButton(title: "Apply", selected: true) { applyEquation() }
                                    .disabled(equationDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || equationDraft.contains("□"))
                            }
                            MathInput(source: $equationDraft, compact: true, latexTemplates: true)
                        }.padding(.horizontal, 16).padding(.bottom, 8).frame(maxWidth: 800).frame(maxWidth: .infinity).background(DarwinTheme.panel)
                    }
                    let diagnostics = store.output["diagnostics"] as? [[String: Any]] ?? []
                    if !diagnostics.isEmpty { ScrollView { VStack(alignment: .leading) { ForEach(diagnostics.indices, id: \.self) { i in Text("\(diagnostics[i]["code"] as? String ?? ""): \(diagnostics[i]["message"] as? String ?? "")").font(.caption).foregroundStyle(DarwinTheme.fault) } }.frame(maxWidth: .infinity, alignment: .leading).padding(12) }.frame(maxHeight: 110) }
                    if debug { ScrollView { Text(debugText).font(.system(size: 11, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading).padding(12) }.frame(height: 180) }
                }
            }.background(DarwinTheme.canvas).foregroundStyle(DarwinTheme.ink)
        }.task { await store.refresh(); if let initialName { await store.open(initialName) } }
        .alert("New writing document", isPresented: $creating) { TextField("Name", text: $title); Button("Cancel", role: .cancel) { }; Button("Create") { Task { await store.create(title) } } }
        .onChange(of: store.name) { _, _ in equationRange = nil; sourceCaret = NSRange(location: 0, length: 0) }
        .onChange(of: store.automatic) { _, enabled in if enabled && !store.name.isEmpty { store.compile() } }
        .onChange(of: store.verify) { _, _ in if !store.name.isEmpty { store.compile() } }
        .onChange(of: store.execute) { _, _ in if !store.name.isEmpty { store.compile() } }
        .alert("Writing", isPresented: Binding(get: { store.error != nil }, set: { if !$0 { store.error = nil } })) { Button("OK") { store.error = nil } } message: { Text(store.error ?? "") }
    }
    private var writingTitle: String {
        let heading = store.source.components(separatedBy: "\n").first { $0.hasPrefix("# ") }
        return heading.map { String($0.dropFirst(2)) } ?? store.displayName
    }
    private func beginEquation() {
        let text = store.source as NSString
        let caret = min(sourceCaret.location, text.length)
        let pattern = #"(?m)^\$\$[^\n]*\n([\s\S]*?)^\$\$[ \t]*$"#
        if let regex = try? NSRegularExpression(pattern: pattern),
           let match = regex.matches(in: store.source, range: NSRange(location: 0, length: text.length)).first(where: { NSLocationInRange(caret, $0.range) }) {
            equationRange = match.range(at: 1)
            equationDraft = text.substring(with: match.range(at: 1)).trimmingCharacters(in: .newlines)
            replacingEquation = true
        } else {
            equationRange = NSRange(location: caret, length: min(sourceCaret.length, text.length - caret))
            equationDraft = ""
            replacingEquation = false
        }
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }
    private func applyEquation() {
        guard let range = equationRange else { return }
        let text = store.source as NSString
        guard NSMaxRange(range) <= text.length else { equationRange = nil; return }
        let replacement: String
        if replacingEquation { replacement = equationDraft + "\n" }
        else {
            let before = range.location > 0 && text.substring(with: NSRange(location: range.location - 1, length: 1)) != "\n" ? "\n\n" : ""
            replacement = before + "$$\n" + equationDraft + "\n$$\n\n"
        }
        store.edited(text.replacingCharacters(in: range, with: replacement), composing: false)
        sourceCaret = NSRange(location: range.location + replacement.utf16.count, length: 0)
        equationRange = nil
    }
    var editor: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Source").font(.caption)
                Spacer()
                DarwinButton(title: "Equation", icon: "function") { beginEquation() }
                    .disabled(equationRange != nil)
            }.padding(.horizontal, 12)
            WritingSource(text: store.source, selection: store.selection, changed: store.edited, selectionChanged: { sourceCaret = $0 })
                .padding(8).disabled(equationRange != nil)
        }.frame(maxWidth: .infinity, maxHeight: .infinity).background(DarwinTheme.panel)
    }
    var preview: some View { VStack(alignment: .leading, spacing: 0) {
        Text(store.previewCurrent ? "Preview" : "Preview · awaiting current compilation").font(.caption).padding(12)
        WritingPreview(output: store.output, css: store.css, locate: store.locate)
            .allowsHitTesting(store.previewCurrent)
            .overlay { if !store.previewCurrent && store.output.isEmpty { Text(store.compiling ? "Compiling current source…" : "Current source has no compilation result.").font(.caption).foregroundStyle(DarwinTheme.secondary) } }
    }.frame(maxWidth: .infinity, maxHeight: .infinity).background(DarwinTheme.panel) }
    var debugText: String { guard store.previewCurrent else { return "Current source has no compilation result." }; let value = store.output.filter { ["stats", "graph", "semanticDocument", "invalidatedSemanticIds", "revision"].contains($0.key) }; return "Revision: \(store.output["revision"] as? Int ?? 0)\nStats: \(store.output["stats"] ?? [:])\n" + ((try? String(data: JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]), encoding: .utf8)) ?? "") }
}
struct WritingSource: UIViewRepresentable {
    var text: String; var selection: NSRange?; var changed: (String, Bool) -> Void
    var fontSize: CGFloat = 16
    var minimumHeight: CGFloat? = nil
    var focused: () -> Void = {}
    var check: (() -> Void)? = nil
    var selectionChanged: (NSRange) -> Void = { _ in }
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> UITextView { let v = WritingTextView(); v.checkAction = check; v.font = .monospacedSystemFont(ofSize: fontSize, weight: .regular); v.autocorrectionType = .no; v.autocapitalizationType = .none; v.smartQuotesType = .no; v.smartDashesType = .no; v.smartInsertDeleteType = .no; v.backgroundColor = .clear; v.textColor = UIColor(DarwinTheme.ink); v.tintColor = UIColor(DarwinTheme.accent); v.isScrollEnabled = minimumHeight == nil; v.delegate = context.coordinator; v.accessibilityLabel = "Writing source"; return v }
    func updateUIView(_ v: UITextView, context: Context) { context.coordinator.updating = true; defer { context.coordinator.updating = false }; v.textColor = UIColor(DarwinTheme.ink); v.tintColor = UIColor(DarwinTheme.accent); (v as? WritingTextView)?.checkAction = check; context.coordinator.parent = self; if v.markedTextRange == nil && v.text != text { let caret = v.selectedRange; v.text = text; v.selectedRange = NSRange(location: min(caret.location, text.utf16.count), length: min(caret.length, max(0, text.utf16.count - caret.location))) }; if let selection, context.coordinator.selection != selection { v.selectedRange = selection; v.scrollRangeToVisible(selection); v.becomeFirstResponder(); context.coordinator.selection = selection } }
    func sizeThatFits(_ proposal: ProposedViewSize, uiView: UITextView, context: Context) -> CGSize? {
        guard let minimumHeight, let width = proposal.width else { return nil }
        return CGSize(width: width, height: max(minimumHeight, uiView.sizeThatFits(CGSize(width: width, height: .greatestFiniteMagnitude)).height))
    }
    final class Coordinator: NSObject, UITextViewDelegate { var parent: WritingSource; var selection: NSRange?; var updating = false; init(_ parent: WritingSource) { self.parent = parent }; func textViewDidBeginEditing(_ v: UITextView) { parent.focused() }; func textViewDidChange(_ v: UITextView) { parent.changed(v.text, v.markedTextRange != nil) }; func textViewDidChangeSelection(_ v: UITextView) { guard !updating else { return }; let range = v.selectedRange; DispatchQueue.main.async { self.parent.selectionChanged(range) } } }
}
final class WritingTextView: UITextView {
    var checkAction: (() -> Void)?
    override var keyCommands: [UIKeyCommand]? {
        guard checkAction != nil else { return super.keyCommands }
        let commands = [UIKeyModifierFlags.control, .command].map { modifier in
            let command = UIKeyCommand(input: "\r", modifierFlags: modifier, action: #selector(checkDocument))
            command.wantsPriorityOverSystemBehavior = true
            return command
        }
        return (super.keyCommands ?? []) + commands
    }
    @objc private func checkDocument() { if markedTextRange == nil { checkAction?() } }
}
struct WritingPreview: UIViewRepresentable {
    var output: [String: Any]; var css: String; var locate: (String) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration(); config.defaultWebpagePreferences.allowsContentJavaScript = false
        config.setURLSchemeHandler(PreviewAssetHandler(), forURLScheme: "neomath-preview")
        for name in ["katex.min.js", "typeset.js"] {
            if let url = Bundle.main.resourceURL?.appending(path: "PreviewAssets/" + name), let script = try? String(contentsOf: url, encoding: .utf8) {
                config.userContentController.addUserScript(WKUserScript(source: script, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
            }
        }
        config.userContentController.add(context.coordinator, name: "locate")
        config.userContentController.addUserScript(WKUserScript(source: "document.addEventListener('click',function(e){let n=e.target.closest('[data-xdlt-render-id],[data-xdlt-id]');if(n)window.webkit.messageHandlers.locate.postMessage(n.getAttribute('data-xdlt-render-id')||n.getAttribute('data-xdlt-id'));});", injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        let view = WKWebView(frame: .zero, configuration: config); view.navigationDelegate = context.coordinator; return view
    }
    func updateUIView(_ v: WKWebView, context: Context) {
        let c = context.coordinator; c.parent = self
        let html = output["html"] as? String ?? "", revision = output["revision"] as? Int
        guard c.document != html else { return }
        c.document = html
        if let revision, output["previousRevision"] as? Int == c.revision, let patches = output["htmlPatches"] as? [[String: Any]], let data = try? JSONSerialization.data(withJSONObject: patches), let json = String(data: data, encoding: .utf8) {
            v.evaluateJavaScript("""
            (()=>{let find=id=>Array.from(document.querySelectorAll('[data-xdlt-render-id],[data-xdlt-id]')).find(n=>(n.getAttribute('data-xdlt-render-id')||n.getAttribute('data-xdlt-id'))===id);for(const p of \(json)){let n=find(p.renderId);if(p.op==='replace-document')return false;if(p.op==='remove'){if(!n)return false;n.remove();}else if(p.op==='replace'){if(!n)return false;n.outerHTML=p.html;}else if(p.op==='insert'){let parent=find(p.parentRenderId);if(!parent)return false;let t=document.createElement('template');t.innerHTML=p.html;parent.insertBefore(t.content,parent.children[p.index]||null);}else return false;}if(window.neomathTypeset)window.neomathTypeset(document);return true;})()
            """) { result, error in
                guard c.document == html, c.revision == revision else { return }
                if result as? Bool != true || error != nil { c.load(v, html: html, css: css) }
            }
            c.revision = revision
        } else { c.revision = revision; c.load(v, html: html, css: css) }
    }
    final class Coordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate { var parent: WritingPreview; var document = ""; var revision: Int?;
        func load(_ v: WKWebView, html: String, css: String) {
            let katex = (try? String(contentsOf: Bundle.main.resourceURL!.appending(path: "PreviewAssets/katex.min.css"), encoding: .utf8)) ?? ""
            v.loadHTMLString("<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data: neomath-preview:\"><meta name='viewport' content='width=device-width, initial-scale=1'><style>\(css)\n\(katex)</style>\(html)", baseURL: URL(string: "neomath-preview://assets/"))
        }
        init(_ parent: WritingPreview) { self.parent = parent }; func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) { if let id = message.body as? String { parent.locate(id) } }; func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) { decisionHandler(navigationAction.navigationType == .linkActivated ? .cancel : .allow) } }
}

final class PreviewAssetHandler: NSObject, WKURLSchemeHandler {
    func webView(_ webView: WKWebView, start urlSchemeTask: WKURLSchemeTask) {
        guard let url = urlSchemeTask.request.url, let root = Bundle.main.resourceURL?.appending(path: "PreviewAssets") else { urlSchemeTask.didFailWithError(BackendError("Missing preview asset")); return }
        let file = root.appending(path: url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))).standardizedFileURL
        guard file.path.hasPrefix(root.path + "/"), let data = try? Data(contentsOf: file) else { urlSchemeTask.didFailWithError(BackendError("Missing preview asset")); return }
        let mime = ["woff2": "font/woff2", "woff": "font/woff", "ttf": "font/ttf"][file.pathExtension] ?? "application/octet-stream"
        urlSchemeTask.didReceive(URLResponse(url: url, mimeType: mime, expectedContentLength: data.count, textEncodingName: nil)); urlSchemeTask.didReceive(data); urlSchemeTask.didFinish()
    }
    func webView(_ webView: WKWebView, stop urlSchemeTask: WKURLSchemeTask) { }
}
