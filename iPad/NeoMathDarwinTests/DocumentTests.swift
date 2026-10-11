import Foundation

@main struct DocumentTests {
    @MainActor static func main() async throws {
        precondition(MathDisplay.latex("(x^2-1)/(x-1)") == #"\frac{x^{2} - 1}{x - 1}"#)
        precondition(MathDisplay.latex("sqrt(1+sqrt(x))") == #"\sqrt{1 + \sqrt{x}}"#)
        precondition(MathDisplay.latex("1/2") == #"\frac{1}{2}"#)
        precondition(MathDisplay.latex("x=±1") == #"x = \pm 1"#)
        precondition(MathDisplay.latex(#"\frac{x+1}{x-1}"#) == #"\frac{x+1}{x-1}"#)
        precondition(MathDisplay.latex("sin(x)^2+cos(x)^2").contains(#"\sin\left(x\right)^{2}"#))
        precondition(MathDisplay.latex("x=2^(1/3)").contains(#"^{\frac{1}{3}}"#))
        precondition(MathDisplay.latex("abs(x)<2").contains(#"\left|x\right|"#))
        let raw = Data(#"{"title":"Test","custom":{"keep":true},"darwinInk":[[[1,2],[3,4]]],"cells":[{"id":"legacy-id","kind":"math","source":"x=1","label":"keep me"},{"id":"note","kind":"markdown","source":"a\nb"}]}"#.utf8)
        var doc = try DocumentTransfer.read(raw)
        precondition(doc.cells.count == 2 && doc.cells[1].source == "a\nb")
        doc.cells[0].source = "x=2"
        doc.ink = Data([1,2,3])
        let output = try DocumentTransfer.export(doc)
        let json = try JSONDecoder().decode([String: JSONValue].self, from: output)
        precondition(json["custom"] == doc.original?["custom"])
        precondition(json["darwinInk"] == doc.original?["darwinInk"])
        let imported = try DocumentTransfer.read(output)
        precondition(imported.cells[0].source == "x=2")
        precondition(imported.cells[0].original?["label"] == .string("keep me"))
        precondition(imported.ink == doc.ink)
        let sourceDoc = try DocumentTransfer.read(Data(#"{"title":"Old","source":"x=1\nx-1=0"}"#.utf8))
        precondition(sourceDoc.cells.count == 2)
        do {
            _ = try DocumentTransfer.read(Data(#"{"cells":[{"kind":"unknown","source":"x"}]}"#.utf8))
            fatalError("Unsupported cell must be rejected")
        } catch { }
        let edited = LiveSource.apply("x=3\n# a\n# b", to: doc.cells)
        precondition(edited[0].id == doc.cells[0].id && edited[0].original?["label"] == .string("keep me"))
        precondition(edited[1].id == doc.cells[1].id && edited[1].source == "a\nb")
        precondition(LiveSource.project(edited) == "x=3\n# a\n# b")
        let inserted = LiveSource.apply("x=0\nx=2\n# a\n# b", to: doc.cells)
        precondition(inserted[1].id == doc.cells[0].id && inserted[2].id == doc.cells[1].id)
        let remote = try BackendTrace.decode(["ok": true, "result": ["engine": "cas", "states": [["source": "x^2<4", "solutionSet": ["kind": "interval", "lower": "-2", "upper": "2", "lowerInclusive": false, "upperInclusive": false], "domain": ["kind": "all_real"], "trustLevel": "symbolic", "verification": ["status": "verified", "target": "real solution set", "method": "SymPy", "limitations": ["real variables only"]]]], "diagnostics": [["status": "valid"]]], "metrics": ["durationMs": 10.5, "cacheHits": 2]])
        precondition(remote.steps?[0].solutions == "(-2, 2)" && remote.steps?[0].verification?.limitations == ["real variables only"] && remote.cacheHits == 2)
        precondition(BackendTrace.set(["kind": "unverified"]).hasPrefix("Unknown"))
        precondition(BackendTrace.set(["kind": "interval", "lower": "0", "lowerInclusive": true, "upperInclusive": true]) == "[0, ∞)")
        precondition(BackendTrace.set(["kind": "real_excluding_finite", "excluded": ["0"]]) == "ℝ ∖ {0}")
        do { _ = try BackendTrace.decode(["ok": true, "result": ["states": [], "diagnostics": []]], expectedSteps: 2); fatalError("Empty CAS trace accepted") } catch { }
        let exportedCells = json["cells"]
        if case .array(let cells) = exportedCells, case .object(let first) = cells[0] { precondition(first["id"] == .string("legacy-id")) } else { fatalError("Missing exported cells") }
        let url = URL.temporaryDirectory.appending(path: UUID().uuidString + ".json")
        defer { try? FileManager.default.removeItem(at: url) }
        let store = NotebookStore(url: url)
        store.add(doc)
        let reopened = NotebookStore(url: url)
        precondition(reopened.documents.contains { $0.id == doc.id && $0.ink == doc.ink })
        store.composing = true
        store.update(Notebook(id: doc.id, title: doc.title, cells: [Cell(source: "x=7")]))
        precondition(!store.checking && store.result == nil)
        store.composing = false; store.check()
        try await Task.sleep(for: .milliseconds(700))
        precondition(store.result?.steps?.first?.solutions == "{7}")
        if ProcessInfo.processInfo.environment["NEOMATH_BACKEND_TEST"] == "1" {
            let client = BackendClient()
            let health = try await client.envelope("health")
            precondition(health["ok"] as? Bool == true)
            let response = try await client.envelope("runTrace", ["source": "x^2=2\nx=±sqrt(2)"])
            let cas = try BackendTrace.decode(response, expectedSteps: 2)
            precondition(cas.engine == "sympy" && cas.steps?[1].status == "valid" && cas.steps?[1].solutions == "{-sqrt(2), sqrt(2)}")
            let computed = try BackendTrace.decode(await client.envelope("runTrace", ["source": "sin(x)^2+cos(x)^2\n1"]), expectedSteps: 2)
            precondition(computed.steps?.allSatisfy { $0.status == "unverified" && $0.title == "Unverified" && $0.reason.contains("remains unknown") } == true)
            let unknownReply = try await client.envelope("runTrace", ["source": "sin(x)=x"])
            let unknown = try BackendTrace.decode(unknownReply, expectedSteps: 1)
            precondition(unknown.steps?[0].status == "unverified" && unknown.steps?[0].verification?.status == "unknown" && unknown.steps?[0].solutions.hasPrefix("Unknown") == true)
            let transformed = try await client.call("executeTransformation", ["source": "x^2=2", "step": 0, "intent": ["intent": "multiply", "arguments": ["expression": "3"]]]) as? [String: Any]
            precondition(transformed?["applied"] as? Bool == true && transformed?["source"] as? String == "3*x^2=6")
            do { _ = try await client.call("executeTransformation", ["source": "x^2=2", "step": 0, "intent": ["intent": "divide", "arguments": ["expression": "0"]]]); fatalError("Division by zero accepted") } catch let error as BackendError { precondition(error.code == "CAS_INPUT") }
            UserDefaults.standard.set(true, forKey: "darwin.useBackend")
            defer { UserDefaults.standard.removeObject(forKey: "darwin.useBackend") }
            store.check(); precondition(store.result == nil)
            try await Task.sleep(for: .milliseconds(600)); precondition(store.result?.steps?.first?.status == "valid")
            store.update(Notebook(id: doc.id, title: doc.title, cells: [Cell(source: "x^50+x+1=0")]))
            precondition(store.result == nil)
            try await Task.sleep(for: .seconds(8))
            precondition(store.result?.steps == nil && store.result?.error?.contains("CAS_TIMEOUT") == true && !store.checking)
            store.cancelCheck(); precondition(store.result == nil)
            print("Real backend client tests passed: CAS document envelope, auto dispatch, complete roots, Unknown, parameter transform, division error, timeout clears stale verification.")
        }
        print("Document tests passed: metadata preservation, multiline prose, ink roundtrip, legacy source, invalid cells, atomic persistence, stale-check cancellation.")
    }
}
