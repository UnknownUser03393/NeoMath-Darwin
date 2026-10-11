import SwiftUI

struct DarwinDocuments: View {
    // Example constructors generate cell UUIDs. Keep preview identities stable
    // across SwiftUI updates instead of recreating all math views while scrolling.
    private static let exampleOrder = [4, 5, 6, 7, 8, 0, 1, 3]
    private static let exampleDocuments = Dictionary(uniqueKeysWithValues: exampleOrder.map { ($0, Notebook.example($0)) })
    var documents: [Notebook]
    var onOpen: (UUID) -> Void
    var onExample: (Int) -> Void
    var onNew: () -> Void
    var onWriting: (String?) -> Void
    var onImport: () -> Void
    var onSettings: () -> Void
    var onRefresh: () -> Void
    @State private var writings: [[String: String]] = []
    @State private var query = ""
    @State private var connected = false
    @State private var busy = false
    @State private var failure: String?
    @State private var layout = "list"
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("NeoMath").font(.system(size: 20, weight: .semibold)).padding(.leading, 8)
                Spacer()
                DarwinButton(title: "Settings") { onSettings() }
                DarwinButton(title: "Import") { onImport() }
                DarwinButton(title: "New writing document", selected: true) { Task { await newWriting() } }
                Button(action: onNew) { Text("New derivation").font(.system(size: 15, weight: .semibold)).padding(.horizontal, 20).frame(minHeight: 44).background(DarwinTheme.accent, in: Capsule()).foregroundStyle(DarwinTheme.onAccent) }.buttonStyle(DarwinPressStyle())
            }.padding(.horizontal, 16).padding(.vertical, 14).background(DarwinTheme.panel)
            Rectangle().fill(DarwinTheme.separator).frame(height: 1)
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 24) {
                    HStack {
                        Text("Documents").font(.system(size: 28, weight: .semibold))
                        Spacer()
                        Text(busy ? "Working…" : connected ? "MathCore connected" : "Connecting / offline")
                            .font(.system(size: 13)).padding(8).background(DarwinTheme.subtle, in: Capsule())
                    }
                    if let failure { Text(failure).font(.caption).foregroundStyle(DarwinTheme.fault) }
                    HStack(spacing: 10) {
                        Image(systemName: "magnifyingglass").foregroundStyle(DarwinTheme.tertiary)
                        TextField("Search documents", text: $query).textInputAutocapitalization(.never)
                    }.padding(14).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 12))
                    examples
                    Group {
                        Text("Writing · XDLT").font(.system(size: 20, weight: .semibold))
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 16)], spacing: 16) {
                            ForEach(writings.indices.filter { query.isEmpty || (writings[$0]["title"] ?? "").localizedCaseInsensitiveContains(query) }, id: \.self) { i in
                                Button { onWriting(writings[i]["name"]) } label: { VStack(alignment: .leading, spacing: 8) { Text(writings[i]["title"] ?? "Writing").font(.system(size: 17, weight: .semibold)); Text("Incremental compile and preview").font(.caption).foregroundStyle(DarwinTheme.secondary) }.frame(maxWidth: .infinity, alignment: .leading).padding(20).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 18)) }.buttonStyle(DarwinPressStyle())
                            }
                        }
                    }
                    Group {
                        HStack { Text("Recent").font(.system(size: 20, weight: .semibold)); Spacer(); DarwinButton(title: "Refresh") { onRefresh(); Task { await refreshWriting() } }; ForEach(["list", "grid"], id: \.self) { mode in DarwinButton(title: mode.capitalized, selected: layout == mode) { layout = mode } } }
                        let files = documents.filter { query.isEmpty || $0.title.localizedCaseInsensitiveContains(query) }.sorted { ($0.updatedAt ?? 0) > ($1.updatedAt ?? 0) }
                        if files.isEmpty {
                            ContentUnavailableView("No documents yet", systemImage: "doc", description: Text("Create a derivation, import a notebook or start with an example."))
                        } else if layout == "list" {
                            LazyVStack(spacing: 0) { ForEach(files) { doc in documentRow(doc); if doc.id != files.last?.id { Divider().padding(.leading, 64) } } }
                                .background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 18))
                        } else {
                            LazyVGrid(columns: [GridItem(.adaptive(minimum: 250), spacing: 16)], spacing: 16) {
                                ForEach(files) { doc in
                                    Button { onOpen(doc.id) } label: {
                                        VStack(alignment: .leading, spacing: 20) {
                                            Image(systemName: "doc.text").font(.system(size: 24)).foregroundStyle(DarwinTheme.accent)
                                            TypesetMath(source: doc.cells.first { $0.kind != "markdown" }?.source ?? "", size: 22).frame(height: 48)
                                            Text(doc.title).font(.system(size: 17, weight: .semibold))
                                            Text("Derivation · \(doc.cells.filter { $0.kind != "markdown" }.count) steps").font(.caption).foregroundStyle(DarwinTheme.secondary)
                                        }.frame(maxWidth: .infinity, alignment: .leading).padding(24).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 18))
                                    }.buttonStyle(DarwinPressStyle())
                                }
                            }
                        }
                    }
                }.padding(24).frame(maxWidth: 1024).frame(maxWidth: .infinity)
            }
        }
        .task { await refreshWriting() }
    }
    private func refreshWriting() async {
        do { _ = try await BackendClient().call("health"); connected = true; failure = nil; let result = try await BackendClient().call("listXdltDocuments") as? [String: Any] ?? [:]; writings = (result["files"] as? [[String: Any]] ?? []).compactMap { file in guard let name = file["name"] as? String else { return nil }; return ["name": name, "title": file["title"] as? String ?? name] } } catch { connected = false; failure = error.localizedDescription }
    }
    private func newWriting() async {
        busy = true
        defer { busy = false }
        let name = UUID().uuidString + ".xdlt"
        do {
            _ = try await BackendClient().call("saveXdltDocument", ["name": name, "source": "# Untitled writing\n\nWrite your mathematical document here.\n"])
            onWriting(name)
        } catch { failure = error.localizedDescription }
    }
    private func documentRow(_ doc: Notebook) -> some View {
        Button { onOpen(doc.id) } label: {
            HStack(spacing: 16) {
                Image(systemName: "doc.text").font(.system(size: 22)).foregroundStyle(DarwinTheme.accent).frame(width: 32)
                VStack(alignment: .leading, spacing: 6) {
                    Text(doc.title).font(.system(size: 17, weight: .medium))
                    Text(doc.updatedAt.map { Date(timeIntervalSince1970: $0 / 1000).formatted(date: .numeric, time: .shortened) } ?? "On this iPad").font(.system(size: 13)).foregroundStyle(DarwinTheme.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.system(size: 12, weight: .medium)).foregroundStyle(DarwinTheme.tertiary)
            }.padding(20).frame(minHeight: 88)
        }.buttonStyle(DarwinPressStyle())
    }
    private var examples: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Examples").font(.system(size: 20, weight: .semibold))
            Text("Open a new copy, then Check with MathCore / SymPy CAS.").font(.system(size: 13)).foregroundStyle(DarwinTheme.secondary)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 12)], spacing: 12) {
                ForEach(Self.exampleOrder.filter { query.isEmpty || Self.exampleDocuments[$0]!.title.localizedCaseInsensitiveContains(query) }, id: \.self) { index in
                    let example = Self.exampleDocuments[index]!
                    Button { onExample(index) } label: {
                        VStack(alignment: .leading, spacing: 14) {
                            VStack(alignment: .leading, spacing: 8) {
                                ForEach(example.cells) { cell in TypesetMath(source: cell.source, size: 20) }
                            }.frame(maxWidth: .infinity, minHeight: 112, alignment: .leading).padding(12).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 12))
                            Text(example.title).font(.system(size: 17, weight: .semibold))
                            Text(["Dividing by a variable", "Adding a solution", "Keep every step equivalent", "Keep the original domain", "SymPy · 二次方程等价验证", "SymPy · 求解并检查", "SymPy · 实数区间解集", "Ctrl+. · 化简、求导、积分", "SymPy · 选中公式，变形 → differentiate / integrate"][index]).font(.system(size: 13)).foregroundStyle(DarwinTheme.secondary)
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(20).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 18))
                    }.buttonStyle(DarwinPressStyle())
                }
            }
        }
    }
}
