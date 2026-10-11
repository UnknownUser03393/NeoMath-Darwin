import SwiftUI
import PencilKit

// The canvas shares the equation content's fixed coordinate space; scrolling belongs to SwiftUI.
struct InkCanvas: UIViewRepresentable {
    @Environment(\.colorScheme) private var colorScheme
    @Binding var data: Data
    var erasing: Bool
    var fingerDrawing = false
    var selectingInk = false
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> PKCanvasView {
        let view = PKCanvasView()
        view.backgroundColor = .clear
        view.isOpaque = false
        view.isScrollEnabled = false
        view.drawingPolicy = fingerDrawing ? .anyInput : .pencilOnly
        view.delegate = context.coordinator
        if let drawing = try? PKDrawing(data: data) { view.drawing = drawing }
        return view
    }
    func updateUIView(_ view: PKCanvasView, context: Context) {
        context.coordinator.parent = self
        view.overrideUserInterfaceStyle = colorScheme == .dark ? .dark : .light
        view.drawingPolicy = fingerDrawing ? .anyInput : .pencilOnly
        // PencilKit adapts black ink to white in dark appearance. Supplying an
        // already inverted SwiftUI color would invert it a second time.
        let ink = UIColor.black
        let toolKey = "\(selectingInk)-\(erasing)-\(colorScheme)"
        if context.coordinator.toolKey != toolKey {
            context.coordinator.toolKey = toolKey
            if selectingInk { view.tool = PKLassoTool() } else { view.tool = erasing ? PKEraserTool(.vector) : PKInkingTool(.pen, color: ink, width: 2) }
        }
        if context.coordinator.loadedData != data {
            context.coordinator.updating = true
            view.drawing = (try? PKDrawing(data: data)) ?? PKDrawing()
            context.coordinator.loadedData = data
            context.coordinator.updating = false
        }
    }
    final class Coordinator: NSObject, PKCanvasViewDelegate {
        var parent: InkCanvas
        var updating = false
        var loadedData: Data
        var toolKey = ""
        var usingTool = false
        init(_ parent: InkCanvas) { self.parent = parent; loadedData = parent.data }
        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            guard !updating, !usingTool else { return }
            #if DEBUG
            let report = "INK INPUT bounds=\(canvasView.bounds) strokes=\(canvasView.drawing.strokes.count) last=\(String(describing: canvasView.drawing.strokes.last?.renderBounds))"
            try? report.write(to: URL.documentsDirectory.appending(path: "ink-input-debug.txt"), atomically: true, encoding: .utf8)
            #endif
            loadedData = canvasView.drawing.dataRepresentation()
            parent.data = loadedData
        }
        func canvasViewDidBeginUsingTool(_ canvasView: PKCanvasView) { usingTool = true }
        func canvasViewDidEndUsingTool(_ canvasView: PKCanvasView) {
            usingTool = false
            canvasViewDrawingDidChange(canvasView)
        }
    }
}

// The browser's world coordinates are identical to the native canvas world.
enum BrowserInk {
    static func migrate(_ doc: Notebook) -> Data? {
        guard doc.ink.isEmpty, case .array(let raw) = doc.original?["darwinInk"] else { return nil }
        var strokes: [PKStroke] = []
        for stroke in raw {
            guard case .array(let samples) = stroke else { continue }
            let points = samples.enumerated().compactMap { i, sample -> PKStrokePoint? in
                guard case .array(let pair) = sample, pair.count >= 2, case .number(let x) = pair[0], case .number(let y) = pair[1], x.isFinite, y.isFinite else { return nil }
                return PKStrokePoint(location: CGPoint(x: x, y: y), timeOffset: Double(i) * 0.01, size: CGSize(width: 2.4, height: 2.4), opacity: 1, force: 1, azimuth: 0, altitude: .pi/2)
            }
            if !points.isEmpty { strokes.append(PKStroke(ink: PKInk(.pen, color: .black), path: PKStrokePath(controlPoints: points, creationDate: Date(timeIntervalSince1970: 0)))) }
        }
        return PKDrawing(strokes: strokes).dataRepresentation()
    }
}
