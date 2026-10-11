import SwiftUI
import UIKit

// Source remains one UITextView body. Formula views only replace inactive lines visually.
struct LiveEditor: UIViewRepresentable {
    var doc: Notebook
    var trace: TraceResult?
    var changed: (String, Bool) -> Void
    var inspect: (UUID, Bool) -> Void
    var complete: (UUID) -> Void
    var activeChanged: (UUID) -> Void
    var completionRequest = 0
    var editRequest: UUID?
    var didFinish: () -> Void
    var editEquation: ((UUID) -> Void)? = nil
    var externallyEditing: UUID? = nil
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> UITextView {
        let view = LiveBodyTextView()
        view.backgroundColor = UIColor(DarwinTheme.panel)
        view.textContainerInset = UIEdgeInsets(top: 32, left: 64, bottom: 120, right: 32)
        view.textContainer.lineFragmentPadding = 0
        view.autocorrectionType = .no; view.autocapitalizationType = .none
        view.smartQuotesType = .no; view.smartDashesType = .no
        view.font = .monospacedSystemFont(ofSize: 24, weight: .regular)
        view.text = LiveSource.project(doc.cells); view.delegate = context.coordinator
        view.accessibilityLabel = "Derivation source"
        let toolbar = UIToolbar()
        toolbar.items = [UIBarButtonItem(title: "Inspect", style: .plain, target: context.coordinator, action: #selector(Coordinator.inspectCurrent)), UIBarButtonItem(title: "Complete", style: .plain, target: context.coordinator, action: #selector(Coordinator.completeCurrent)), UIBarButtonItem(systemItem: .flexibleSpace), UIBarButtonItem(title: "Done", style: .done, target: context.coordinator, action: #selector(Coordinator.done))]
        toolbar.sizeToFit(); view.inputAccessoryView = toolbar
        view.completionAction = { [weak c = context.coordinator] in c?.completeCurrent() }
        context.coordinator.view = view
        context.coordinator.render()
        return view
    }
    func updateUIView(_ view: UITextView, context: Context) {
        let c = context.coordinator; c.parent = self
        if c.lastCompletionRequest != completionRequest { c.lastCompletionRequest = completionRequest; DispatchQueue.main.async { c.completeCurrent() } }
        let source = LiveSource.project(doc.cells)
        if view.markedTextRange == nil {
            if view.text != source { let range = view.selectedRange; c.updating = true; view.text = source; view.selectedRange = NSRange(location: min(range.location, source.utf16.count), length: min(range.length, max(0, source.utf16.count - range.location))); c.updating = false }
            c.render()
            if let id = editRequest, id != c.lastEditRequest {
                c.lastEditRequest = id
                let lines = LiveSource.lines(doc.cells); var offset = 0
                for line in lines {
                    if line.cell.id == id {
                        let location = offset, length = line.source.utf16.count
                        DispatchQueue.main.async { view.becomeFirstResponder(); view.selectedRange = NSRange(location: location, length: length); view.scrollRangeToVisible(view.selectedRange) }
                        break
                    }
                    offset += line.source.utf16.count + 1
                }
            } else if editRequest == nil { c.lastEditRequest = nil }
        }
    }
    final class Coordinator: NSObject, UITextViewDelegate, UIPopoverPresentationControllerDelegate {
        var parent: LiveEditor
        weak var view: UITextView?
        var updating = false
        var overlays: [UIView] = []
        var active: Cell?
        var lastEditRequest: UUID?
        var lastExternalEdit: UUID?
        var lastCompletionRequest = 0
        init(_ parent: LiveEditor) { self.parent = parent }
        @objc func done() { view?.resignFirstResponder(); parent.didFinish(); render() }
        @objc func inspectCurrent() { if let active { parent.inspect(active.id, false) } }
        @objc func completeCurrent() {
            guard let view, let active, active.kind != "markdown", let step = parent.doc.cells.filter({ $0.kind != "markdown" }).firstIndex(where: { $0.id == active.id }) else { return }
            let source = parent.doc.cells.filter { $0.kind != "markdown" }.prefix(step + 1).map(\.source).joined(separator: "\n")
            let snapshot = parent.doc
            Task {
                let items: [MathCompletion]
                do {
                    if UserDefaults.standard.bool(forKey: "darwin.useBackend") {
                        let raw = try await BackendClient().call("getCompletions", ["engine": "auto", "source": source, "step": step])
                        items = try JSONDecoder().decode([MathCompletion].self, from: JSONSerialization.data(withJSONObject: raw))
                    } else { items = try JSONDecoder().decode(CompletionEnvelope.self, from: MathCoreBridge.completions(source, step: step)).items ?? [] }
                } catch { parent.complete(active.id); return }
                guard snapshot.cells == parent.doc.cells else { return }
                var responder: UIResponder? = view
                while responder != nil && !(responder is UIViewController) { responder = responder?.next }
                guard let presenter = responder as? UIViewController else { return }
                let navigation = CompletionNavigation()
                let available = items.filter(\.available)
                let controller = CompletionController(rootView: CompletionPopover(items: available, navigation: navigation, apply: { item in
                    controllerDismiss(presenter, restore: { view.becomeFirstResponder() })
                    Task {
                        do {
                            let result: TransformResult
                            if UserDefaults.standard.bool(forKey: "darwin.useBackend") {
                                let raw = try await BackendClient().call("executeTransformation", ["engine": "auto", "source": source, "step": step, "intent": ["intent": item.id]])
                                result = try JSONDecoder().decode(TransformResult.self, from: JSONSerialization.data(withJSONObject: raw))
                            } else { result = try JSONDecoder().decode(TransformResult.self, from: MathCoreBridge.transform(source, step: step, intent: item.id)) }
                            guard snapshot.cells == self.parent.doc.cells, result.applied == true, let target = result.source, let index = snapshot.cells.firstIndex(where: { $0.id == active.id }) else { return }
                            var doc = snapshot; doc.cells.insert(Cell(source: target), at: index + 1)
                            self.parent.changed(LiveSource.project(doc.cells), false)
                        } catch { self.parent.complete(active.id) }
                    }
                }, more: { controllerDismiss(presenter, restore: { view.becomeFirstResponder() }); self.parent.complete(active.id) }))
                controller.navigation = navigation
                navigation.count = available.count
                navigation.activate = { [weak controller, weak navigation] in
                    guard let controller, let navigation, available.indices.contains(navigation.index) else { return }
                    controller.rootView.apply(available[navigation.index])
                }
                navigation.escape = { [weak presenter, weak view] in presenter?.dismiss(animated: true) { view?.becomeFirstResponder() } }
                controller.modalPresentationStyle = .popover; controller.preferredContentSize = CGSize(width: 340, height: min(480, CGFloat(items.count) * 76 + 60))
                controller.popoverPresentationController?.delegate = self
                controller.popoverPresentationController?.sourceView = view
                controller.popoverPresentationController?.sourceRect = view.selectedTextRange.map { view.caretRect(for: $0.end) } ?? CGRect(x: 64, y: 64, width: 1, height: 32)
                view.resignFirstResponder()
                presenter.present(controller, animated: true) { controller.becomeFirstResponder() }
            }
        }
        func presentationControllerDidDismiss(_ presentationController: UIPresentationController) { view?.becomeFirstResponder() }
        func textViewDidBeginEditing(_ textView: UITextView) { render() }
        func textViewDidEndEditing(_ textView: UITextView) { render() }
        func textViewDidChangeSelection(_ textView: UITextView) { if !updating && textView.markedTextRange == nil { render() } }
        func textViewDidChange(_ textView: UITextView) {
            guard !updating else { return }
            parent.changed(textView.text, textView.markedTextRange != nil)
            if textView.markedTextRange == nil { render() }
        }
        func render() {
            guard let view, !updating, view.markedTextRange == nil else { return }
            updating = true; defer { updating = false }
            overlays.forEach { $0.removeFromSuperview() }; overlays = []
            let source = view.text ?? "", lines = LiveSource.lines(parent.doc.cells), range = view.selectedRange
            let text = NSMutableAttributedString(string: source)
            let full = NSRange(location: 0, length: text.length)
            text.addAttributes([.font: UIFont.monospacedSystemFont(ofSize: 24, weight: .regular), .foregroundColor: UIColor(DarwinTheme.ink)], range: full)
            var offset = 0, records: [(Cell, NSRange, MathLabelContainer?)] = []
            let previousActive = active?.id
            active = nil
            for line in lines {
                let count = line.source.utf16.count
                guard offset + count <= text.length else { break }
                let lineRange = NSRange(location: offset, length: count)
                let activeLine = view.isFirstResponder && (range.length == 0 ? range.location >= offset && range.location <= offset + count : NSIntersectionRange(range, lineRange).length > 0)
                if activeLine { active = line.cell }
                let paragraph = NSMutableParagraphStyle(); paragraph.paragraphSpacing = 18
                paragraph.minimumLineHeight = line.cell.kind == "markdown" ? 28 : 48
                var formula: MathLabelContainer?
                if line.cell.kind != "markdown" {
                    let math = MathLabelContainer(); math.label.fontSize = 26; math.label.textColor = UIColor(DarwinTheme.ink); math.label.latex = MathDisplay.latex(line.source.isEmpty ? "\\square" : line.source)
                    paragraph.minimumLineHeight = max(48, math.measured().height + 8)
                    if !activeLine { text.addAttribute(.foregroundColor, value: UIColor.clear, range: lineRange); formula = math }
                } else {
                    text.addAttribute(.font, value: UIFont.systemFont(ofSize: 16), range: lineRange)
                    if !activeLine && line.source.hasPrefix("# ") { text.addAttribute(.foregroundColor, value: UIColor.clear, range: NSRange(location: offset, length: min(2, count))) }
                }
                text.addAttribute(.paragraphStyle, value: paragraph, range: NSRange(location: offset, length: min(count + 1, text.length - offset)))
                records.append((line.cell, lineRange, formula)); offset += count + 1
            }
            if let id = active?.id, id != previousActive { DispatchQueue.main.async { self.parent.activeChanged(id) } }
            view.attributedText = text; view.selectedRange = range
            view.typingAttributes = [.font: UIFont.monospacedSystemFont(ofSize: active?.kind == "markdown" ? 16 : 24, weight: .regular), .foregroundColor: UIColor(DarwinTheme.ink)]
            view.layoutManager.ensureLayout(for: view.textContainer)
            let maths = parent.doc.cells.filter { $0.kind != "markdown" }
            view.accessibilityCustomActions = maths.enumerated().flatMap { index, cell in [
                UIAccessibilityCustomAction(name: "Inspect step \(index + 1)") { _ in self.parent.inspect(cell.id, false); return true },
                UIAccessibilityCustomAction(name: "Edit equation step \(index + 1)") { _ in self.parent.editEquation?(cell.id); return true }
            ] }
            if parent.externallyEditing == nil { lastExternalEdit = nil }
            var shown = Set<UUID>(), anchors: [(String, CGFloat)] = []
            for (cell, lineRange, formula) in records {
                let glyph = view.layoutManager.glyphRange(forCharacterRange: NSRange(location: lineRange.location, length: min(max(1, lineRange.length), max(0, text.length - lineRange.location))), actualCharacterRange: nil)
                let rect = view.layoutManager.boundingRect(forGlyphRange: glyph, in: view.textContainer)
                if let formula {
                    let size = formula.measured()
                    formula.frame = CGRect(x: view.textContainerInset.left, y: rect.minY + view.textContainerInset.top, width: size.width, height: size.height)
                    if parent.externallyEditing == cell.id {
                        let highlight = UIView(frame: formula.frame.insetBy(dx: -12, dy: -8))
                        highlight.backgroundColor = UIColor(DarwinTheme.accent).withAlphaComponent(0.10)
                        highlight.layer.cornerRadius = 10
                        highlight.layer.borderWidth = 1
                        highlight.layer.borderColor = UIColor(DarwinTheme.accent).withAlphaComponent(0.5).cgColor
                        highlight.isUserInteractionEnabled = false
                        view.addSubview(highlight); overlays.append(highlight)
                        if lastExternalEdit != cell.id {
                            lastExternalEdit = cell.id
                            let target = highlight.frame.insetBy(dx: 0, dy: -24)
                            DispatchQueue.main.async { view.scrollRectToVisible(target, animated: false) }
                        }
                    }
                    formula.isUserInteractionEnabled = true; formula.isAccessibilityElement = false
                    let tap = EquationTapGesture(target: self, action: #selector(editFormula(_:)))
                    tap.cell = cell.id
                    formula.addGestureRecognizer(tap)
                    view.addSubview(formula); overlays.append(formula)
                }
                if view.isFirstResponder, let selected = view.selectedTextRange, range.location >= lineRange.location, range.location <= lineRange.location + lineRange.length {
                    let line = (source as NSString).substring(with: lineRange)
                    var positions: [Int] = []
                    if line.range(of: #"[+\-*/^=<>]\s*$"#, options: .regularExpression) != nil { positions.append(lineRange.location + lineRange.length) }
                    if let regex = try? NSRegularExpression(pattern: #"\(\s*\)"#) { for match in regex.matches(in: line, range: NSRange(location: 0, length: line.utf16.count)) { positions.append(lineRange.location + match.range.location + 1) } }
                    for offset in positions {
                        guard let position = view.position(from: view.beginningOfDocument, offset: offset) else { continue }
                        let caret = view.caretRect(for: position)
                        let slot = PlaceholderButton(type: .system); slot.offset = offset; slot.setTitle("□", for: .normal); slot.tintColor = UIColor(DarwinTheme.tertiary); slot.accessibilityLabel = "Fill expression"
                        slot.frame = CGRect(x: caret.maxX + 4, y: caret.minY, width: 24, height: 32); slot.addTarget(self, action: #selector(fillSlot(_:)), for: .touchUpInside); view.addSubview(slot); overlays.append(slot)
                    }
                    _ = selected
                }
                if shown.insert(cell.id).inserted, let index = maths.firstIndex(where: { $0.id == cell.id }), let steps = parent.trace?.steps, steps.indices.contains(index), steps[index].status != "valid" {
                    anchors.append((steps[index].status, rect.minY + view.textContainerInset.top + 22))
                    let button = DiagnosticButton(type: .system); button.cell = cell.id
                    button.setImage(UIImage(systemName: steps[index].status == "tainted" ? "arrow.turn.down.right" : "exclamationmark.circle.fill"), for: .normal)
                    button.tintColor = UIColor(DarwinTheme.tone(steps[index].status)); button.accessibilityLabel = steps[index].title
                    button.frame = CGRect(x: 14, y: rect.minY + view.textContainerInset.top, width: 44, height: 44)
                    button.addTarget(self, action: #selector(diagnostic(_:)), for: .touchUpInside)
                    view.addSubview(button); overlays.append(button)
                }
            }
            if let fault = anchors.first(where: { ["root_fault", "parse_error"].contains($0.0) }) {
                let affected = anchors.filter { $0.0 == "tainted" && $0.1 > fault.1 }.map(\.1)
                if !affected.isEmpty {
                    let connector = DependencyConnector(frame: CGRect(x: 0, y: 0, width: 64, height: view.contentSize.height))
                    connector.isOpaque = false; connector.backgroundColor = .clear; connector.start = fault.1; connector.targets = affected; connector.isUserInteractionEnabled = false; connector.isAccessibilityElement = false
                    view.insertSubview(connector, at: 0); overlays.append(connector)
                }
            }
        }
        @objc private func fillSlot(_ sender: PlaceholderButton) { view?.selectedRange = NSRange(location: sender.offset, length: 0); view?.becomeFirstResponder() }
        @objc private func editFormula(_ sender: EquationTapGesture) {
            if let id = sender.cell { view?.resignFirstResponder(); parent.editEquation?(id) }
        }
        @objc private func diagnostic(_ sender: DiagnosticButton) { if let id = sender.cell { parent.inspect(id, true) } }
    }
}
final class PlaceholderButton: UIButton { var offset = 0 }
final class DiagnosticButton: UIButton { var cell: UUID? }
final class EquationTapGesture: UITapGestureRecognizer { var cell: UUID? }
final class LiveBodyTextView: UITextView {
    var completionAction: (() -> Void)?
    override var keyCommands: [UIKeyCommand]? {
        let command = UIKeyCommand(input: ".", modifierFlags: .control, action: #selector(showCompletion))
        command.wantsPriorityOverSystemBehavior = true
        return [command] + (super.keyCommands ?? [])
    }
    // UITextView's hardware input handling can consume Control-Space before
    // UIKeyCommand dispatch. Handle the physical press without inserting a space.
    override func pressesBegan(_ presses: Set<UIPress>, with event: UIPressesEvent?) {
        let completion = presses.filter { press in
            guard let key = press.key else { return false }
            return key.keyCode == .keyboardPeriod && key.modifierFlags.contains(.control)
                && key.modifierFlags.intersection([.command, .alternate, .shift]).isEmpty && markedTextRange == nil
        }
        if !completion.isEmpty { showCompletion() }
        let remaining = presses.subtracting(completion)
        if !remaining.isEmpty { super.pressesBegan(remaining, with: event) }
    }
    @objc private func showCompletion() { guard markedTextRange == nil else { return }; completionAction?() }
}

private func controllerDismiss(_ presenter: UIViewController, restore: @escaping () -> Void) { presenter.dismiss(animated: true, completion: restore) }
struct CompletionPopover: View {
    var items: [MathCompletion]
    @ObservedObject var navigation: CompletionNavigation
    var apply: (MathCompletion) -> Void; var more: () -> Void
    var body: some View {
        VStack(spacing: 0) {
            Text("Next step · ↑↓ select · Enter insert · Esc close").font(.system(size: 11)).foregroundStyle(DarwinTheme.secondary).padding(10)
            if items.isEmpty { Text("No available suggestions for this step.").font(.caption).padding(16) }
            ScrollViewReader { reader in ScrollView { VStack(spacing: 0) { ForEach(items) { item in
                Button { apply(item) } label: {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack { Text(item.label).font(.system(size: 14, weight: .semibold)); Spacer(); if item.risk != "safe" { Image(systemName: "exclamationmark.triangle").foregroundStyle(DarwinTheme.caution) } }
                        if !item.preview.isEmpty { TypesetMath(source: item.preview, size: 19) }
                        Text(item.riskDescription).font(.system(size: 11)).foregroundStyle(item.risk == "safe" ? DarwinTheme.secondary : DarwinTheme.caution)
                    }.frame(maxWidth: .infinity, alignment: .leading).padding(12)
                }.buttonStyle(.plain).background(items.indices.contains(navigation.index) && items[navigation.index].id == item.id ? DarwinTheme.accent.opacity(0.1) : .clear).id(item.id).disabled(!item.available).opacity(item.available ? 1 : 0.45)
                Divider()
            } } }.onChange(of: navigation.index) { _, index in if items.indices.contains(index) { reader.scrollTo(items[index].id) } } }
            Button("Transformation with arguments…", action: more).frame(height: 48)
        }.background(DarwinTheme.panel).foregroundStyle(DarwinTheme.ink)
    }
}
final class DependencyConnector: UIView {
    var start: CGFloat = 0; var targets: [CGFloat] = []
    override func draw(_ rect: CGRect) {
        guard let end = targets.last else { return }
        let path = UIBezierPath(); path.move(to: CGPoint(x: 36, y: start)); path.addLine(to: CGPoint(x: 20, y: start)); path.addLine(to: CGPoint(x: 20, y: end))
        for y in targets { path.move(to: CGPoint(x: 20, y: y)); path.addLine(to: CGPoint(x: 36, y: y)) }
        UIColor(DarwinTheme.caution).withAlphaComponent(0.6).setStroke(); path.lineWidth = 1.5; path.stroke()
    }
}

final class CompletionNavigation: ObservableObject {
    @Published var index = 0
    var count = 0
    var activate: (() -> Void)?
    var escape: (() -> Void)?
}
final class CompletionController: UIHostingController<CompletionPopover> {
    var navigation: CompletionNavigation?
    override var canBecomeFirstResponder: Bool { true }
    override var keyCommands: [UIKeyCommand]? {
        let commands = [UIKeyCommand(input: UIKeyCommand.inputDownArrow, modifierFlags: [], action: #selector(down)), UIKeyCommand(input: UIKeyCommand.inputUpArrow, modifierFlags: [], action: #selector(up)), UIKeyCommand(input: "\r", modifierFlags: [], action: #selector(insert)), UIKeyCommand(input: UIKeyCommand.inputEscape, modifierFlags: [], action: #selector(close))]
        commands.forEach { $0.wantsPriorityOverSystemBehavior = true }
        return commands
    }
    @objc private func down() { guard let navigation, navigation.count > 0 else { return }; navigation.index = (navigation.index + 1) % navigation.count }
    @objc private func up() { guard let navigation, navigation.count > 0 else { return }; navigation.index = (navigation.index + navigation.count - 1) % navigation.count }
    @objc private func insert() { navigation?.activate?() }
    @objc private func close() { navigation?.escape?() }
}
