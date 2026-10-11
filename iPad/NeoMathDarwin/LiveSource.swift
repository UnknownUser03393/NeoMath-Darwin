import Foundation

enum LiveSource {
    struct Line { var cell: Cell; var source: String }
    static func lines(_ cells: [Cell]) -> [Line] {
        cells.flatMap { cell in cell.source.components(separatedBy: "\n").map { Line(cell: cell, source: cell.kind == "markdown" && !$0.isEmpty ? "# " + $0 : $0) } }
    }
    static func project(_ cells: [Cell]) -> String { lines(cells).map(\.source).joined(separator: "\n") }
    static func apply(_ source: String, to cells: [Cell]) -> [Cell] {
        let old = lines(cells), next = source.components(separatedBy: "\n")
        if project(cells) == source { return cells }
        var prefix = 0, suffix = 0
        while prefix < min(old.count, next.count), old[prefix].source == next[prefix] { prefix += 1 }
        while suffix < min(old.count, next.count) - prefix, old[old.count - 1 - suffix].source == next[next.count - 1 - suffix] { suffix += 1 }
        var used = Set<UUID>(), result: [Cell] = [], lastGroup: UUID?
        for (i, line) in next.enumerated() {
            let oldIndex: Int? = i < prefix ? i : i >= next.count - suffix ? old.count - (next.count - i) : i < old.count - suffix ? i : nil
            let previous = oldIndex.map { old[$0] }
            let prose = line.trimmingCharacters(in: .whitespaces).hasPrefix("#") || line.trimmingCharacters(in: .whitespaces).isEmpty
            let kind = prose ? "markdown" : previous?.cell.kind == "transform" && previous?.source == line ? "transform" : "math"
            let body = prose && line.trimmingCharacters(in: .whitespaces).hasPrefix("#") ? line.replacingOccurrences(of: "^\\s*# ?", with: "", options: .regularExpression) : line
            if kind == "markdown", let group = previous?.cell.id, lastGroup == group, result.last?.kind == "markdown" { result[result.count - 1].source += "\n" + body; continue }
            var cell = previous?.cell ?? Cell(source: body)
            if used.contains(cell.id) { cell.id = UUID(); cell.original?.removeValue(forKey: "id") }
            used.insert(cell.id); cell.kind = kind; cell.source = body
            if previous?.source != line { cell.original?["executionState"] = .string("idle"); cell.original?.removeValue(forKey: "result") }
            result.append(cell); lastGroup = previous?.cell.id
        }
        return result
    }
}
