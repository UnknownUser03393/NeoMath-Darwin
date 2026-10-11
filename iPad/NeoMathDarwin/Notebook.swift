import Foundation
import SwiftUI

struct Cell: Codable, Identifiable, Equatable {
    var id = UUID()
    var kind = "math"
    var source: String
    var original: [String: JSONValue]?
}
struct Notebook: Codable, Identifiable, Equatable {
    var id = UUID()
    var title: String
    var cells: [Cell]
    var ink = Data()
    var updatedAt: Double?
    var backendName: String?
    var original: [String: JSONValue]?
    static func example(_ index: Int) -> Notebook {
        let examples = [("Lost roots", ["x*(x-1)=0", "x-1=0", "x=1"]),
                        ("Squaring", ["sqrt(x)=x-2", "x=(x-2)^2"]),
                        ("等价推导", ["2x+3=7", "2x=4", "x=2"]),
                        ("Domain change", ["(x^2-1)/(x-1)=2", "x+1=2"]),
                        ("无理根与正负号", ["x^2=2", "x=±sqrt(2)"]),
                        ("三次方程", ["x^3=2", "x=2^(1/3)"]),
                        ("不等式", ["x^2<4", "abs(x)<2"]),
                        ("函数化简与微积分", ["sin(x)^2+cos(x)^2", "1"]),
                        ("求导与积分", ["x^3+sin(x)"]) ]
        let e = examples[index]
        return Notebook(title: e.0, cells: e.1.map { Cell(source: $0) })
    }
}
struct StepResult: Decodable {
    var source: String
    var solutions: String
    var domain: String
    var status: String
    var title: String
    var message: String
    var reason: String
    var lost: [String]?
    var gained: [String]?
    var relation: String?
    var witness: String?
    var before: String?
    var after: String?
    var engine: String?
    var trust: String?
    var verification: Verification?
    var variable: String?
    var left: String?
    var right: String?
    var previousLeft: String?
    var previousRight: String?
    var domainExpanded: Bool?
    var domainShrunk: Bool?
}
struct Verification: Decodable { var status: String; var target: String; var method: String; var limitations: [String] }
struct TraceResult: Decodable {
    var backendTrace: [String: JSONValue]?
    var method: String?
    var steps: [StepResult]?
    var durationMs: Double?
    var cacheHits: Int?
    var engine: String?
    var error: String?
}
struct TransformResult: Decodable {
    var applied: Bool?
    var source: String?
    var reason: String?
    var error: String?
}

@MainActor final class NotebookStore: ObservableObject {
    @Published var documents: [Notebook] = []
    @Published var selected: UUID?
    @Published var result: TraceResult?
    @Published var error: String?
    @Published var checking = false
    @Published var saving = "Saved"
    private var saveQueue: Task<Void, Never>?
    @Published var autoCheck = UserDefaults.standard.object(forKey: "darwin.autoCheck") as? Bool ?? true { didSet { UserDefaults.standard.set(autoCheck, forKey: "darwin.autoCheck"); if !autoCheck { cancelCheck() } } }
    var composing = false
    private var task: Task<Void, Never>?
    private var generation = 0
    private var checkedSource: [String] = []
    private let url: URL
    init(url: URL? = nil) {
        self.url = url ?? URL.documentsDirectory.appending(path: "NeoMath-notebooks.json")
        do {
            if FileManager.default.fileExists(atPath: self.url.path) {
                documents = try JSONDecoder().decode([Notebook].self, from: Data(contentsOf: self.url))
            } else { documents = [Notebook.example(0)] }
        } catch { self.error = "读取文档失败，原文件已保留：\(error.localizedDescription)" }
        selected = documents.first?.id
    }
    var current: Notebook? { documents.first { $0.id == selected } }
    func save() {
        do { try JSONEncoder().encode(documents).write(to: url, options: .atomic) }
        catch { self.error = "保存失败：\(error.localizedDescription)" }
        if UserDefaults.standard.bool(forKey: "darwin.useBackend"), let doc = current {
            saving = "Saving…"
            let previous = saveQueue
            saveQueue = Task {
                await previous?.value
                do {
                    let data = try DocumentTransfer.export(doc)
                    let object = try JSONSerialization.jsonObject(with: data)
                    _ = try await BackendClient().call("saveNotebook", ["name": doc.backendName ?? doc.id.uuidString + ".nm", "document": object])
                    if current == doc { saving = "Saved" }
                } catch { saving = "Save failed"; self.error = error.localizedDescription }
            }
        }
    }
    func refreshRemote() async {
        guard UserDefaults.standard.bool(forKey: "darwin.useBackend") else { return }
        do {
            await saveQueue?.value
            let result = try await BackendClient().call("listNotebooks") as? [String: Any] ?? [:]
            for file in result["files"] as? [[String: Any]] ?? [] {
                guard let name = file["fileName"] as? String ?? file["name"] as? String else { continue }
                let loaded = try await BackendClient().call("loadNotebook", ["name": name]) as? [String: Any] ?? [:]
                guard let object = loaded["document"] else { continue }
                var doc = try DocumentTransfer.read(JSONSerialization.data(withJSONObject: object)); doc.backendName = name
                if let index = documents.firstIndex(where: { $0.backendName == name || $0.id.uuidString == doc.original?["id"]?.string }) { doc.id = documents[index].id; documents[index] = doc }
                else { documents.append(doc) }
            }
            try JSONEncoder().encode(documents).write(to: url, options: .atomic)
        } catch { self.error = error.localizedDescription }
    }
    func open(_ id: UUID) { checkedSource = []; selected = id; invalidate(); check() }
    func add(_ notebook: Notebook) { documents.append(notebook); open(notebook.id); save() }
    func update(_ notebook: Notebook) {
        guard let index = documents.firstIndex(where: { $0.id == notebook.id }) else { return }
        let old = documents[index].cells.filter { $0.kind != "markdown" }.map(\.source)
        var notebook = notebook
        notebook.updatedAt = Date().timeIntervalSince1970 * 1000
        documents[index] = notebook
        save()
        if old != notebook.cells.filter({ $0.kind != "markdown" }).map(\.source) { invalidate(); if autoCheck && !composing { check() } }
    }
    func cancelCheck() { generation += 1; task?.cancel(); result = nil; checking = false }
    func invalidate() { generation += 1; task?.cancel(); result = nil; checking = false }
    func check() {
        guard !composing, let doc = current else { return }
        task?.cancel(); generation += 1
        let token = generation
        let source = doc.cells.filter { $0.kind != "markdown" }.map(\.source).joined(separator: "\n")
        result = nil; checking = true
        task = Task {
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            if UserDefaults.standard.bool(forKey: "darwin.useBackend") {
                do {
                    let lines = source.components(separatedBy: "\n")
                    let changed = Array(zip(checkedSource, lines)).firstIndex(where: { $0.0 != $0.1 }) ?? min(checkedSource.count, lines.count)
                    let method = checkedSource.isEmpty ? "runTrace" : "replay"
                    let reply = try await BackendClient().envelope(method, ["engine": "auto", "source": source, "changedStep": changed])
                    guard !Task.isCancelled, generation == token else { return }
                    result = try BackendTrace.decode(reply, expectedSteps: lines.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }.count, method: method); checkedSource = lines
                } catch { guard !Task.isCancelled, generation == token else { return }; result = TraceResult(error: error.localizedDescription); self.error = error.localizedDescription }
            } else {
                let data = await Task.detached { MathCoreBridge.trace(source) }.value
                guard !Task.isCancelled, generation == token else { return }
                do { result = try JSONDecoder().decode(TraceResult.self, from: data) }
                catch { self.error = error.localizedDescription }
            }
            checking = false
        }
    }
    func transform(cellID: UUID, intent: String, argument: String = "") async -> Bool {
        guard var doc = current, let cellIndex = doc.cells.firstIndex(where: { $0.id == cellID }), let step = doc.cells.filter({ $0.kind != "markdown" }).firstIndex(where: { $0.id == cellID }) else { return false }
        let snapshot = doc.cells
        let source = doc.cells.filter { $0.kind != "markdown" }.prefix(step + 1).map(\.source).joined(separator: "\n")
        do {
            let data: Data
            if UserDefaults.standard.bool(forKey: "darwin.useBackend") {
                let reply = try await BackendClient().call("executeTransformation", ["engine": "auto", "source": source, "step": step, "intent": ["intent": intent, "confidence": 1, "arguments": argument.isEmpty ? [:] : ["expression": argument]]])
                data = try JSONSerialization.data(withJSONObject: reply)
            } else { data = argument.isEmpty ? MathCoreBridge.transform(source, step: step, intent: intent) : MathCoreBridge.transform(source, step: step, intent: intent, argument: argument) }
            let result = try JSONDecoder().decode(TransformResult.self, from: data)
            guard current?.id == doc.id, current?.cells == snapshot else { return false }
            guard result.applied == true, let target = result.source else { error = result.error ?? result.reason ?? "Transformation unavailable"; return false }
            doc.cells.insert(Cell(source: target), at: cellIndex + 1); update(doc)
            return true
        } catch { self.error = error.localizedDescription; return false }
    }
}
