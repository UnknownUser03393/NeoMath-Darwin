import Foundation
import SwiftUI
import UniformTypeIdentifiers

// Retain unknown fields from imported .nm documents instead of dropping desktop metadata.
indirect enum JSONValue: Codable, Equatable {
    case string(String), number(Double), bool(Bool), array([JSONValue]), object([String: JSONValue]), null
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .array(v) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }
    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }
    var string: String? { if case .string(let v) = self { return v }; return nil }
}

struct NotebookFile: FileDocument {
    static var readableContentTypes: [UTType] { [.json, .data] }
    var data: Data
    init(data: Data) { self.data = data }
    init(configuration: ReadConfiguration) throws { data = configuration.file.regularFileContents ?? Data() }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: data) }
}

enum DocumentTransfer {
    static func read(_ data: Data) throws -> Notebook {
        if var native = try? JSONDecoder().decode(Notebook.self, from: data) {
            native.id = UUID()
            return native
        }
        let raw = try JSONDecoder().decode([String: JSONValue].self, from: data)
        var doc = Notebook(title: raw["title"]?.string ?? "Imported", cells: [])
        doc.original = raw
        if case .number(let timestamp) = raw["updatedAt"] { doc.updatedAt = timestamp }
        if case .array(let cells) = raw["cells"] {
            for item in cells {
                guard case .object(let cell) = item,
                      let source = cell["source"]?.string,
                      let kind = cell["kind"]?.string,
                      ["math", "transform", "markdown"].contains(kind) else {
                    throw CocoaError(.fileReadCorruptFile)
                }
                doc.cells.append(Cell(kind: kind, source: source, original: cell))
            }
        } else if let source = raw["source"]?.string {
            doc.cells = source.components(separatedBy: .newlines).map { Cell(source: $0) }
        } else { throw CocoaError(.fileReadCorruptFile) }
        if let encoded = raw["darwinPencilKit"]?.string, let ink = Data(base64Encoded: encoded) { doc.ink = ink }
        // Browser darwinInk remains in original metadata. It is not a PKDrawing.
        return doc
    }
    static func export(_ doc: Notebook) throws -> Data {
        var raw = doc.original ?? [:]
        raw["title"] = .string(doc.title)
        raw["id"] = doc.backendName == nil ? .string(doc.id.uuidString) : doc.original?["id"] ?? .string(doc.id.uuidString)
        raw["fileName"] = .string(doc.backendName ?? doc.id.uuidString + ".nm")
        raw["updatedAt"] = .number(Date().timeIntervalSince1970 * 1000)
        raw["cells"] = .array(doc.cells.map { cell in
            var fields = cell.original ?? [:]
            fields["id"] = cell.original?["id"] ?? .string(cell.id.uuidString)
            fields["kind"] = .string(cell.kind)
            fields["source"] = .string(cell.source)
            fields["executionState"] = .string("idle")
            fields["outputCollapsed"] = fields["outputCollapsed"] ?? .bool(false)
            fields.removeValue(forKey: "result") // Never export stale math results.
            return .object(fields)
        })
        raw["source"] = .string(doc.cells.filter { $0.kind != "markdown" }.map(\.source).joined(separator: "\n"))
        raw["darwinPencilKit"] = .string(doc.ink.base64EncodedString())
        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(raw)
    }
}
