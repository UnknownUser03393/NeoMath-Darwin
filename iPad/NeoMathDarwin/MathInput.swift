import SwiftUI
import UIKit

/// Templates use the same ordinary expression syntax accepted by Core and CAS.
struct MathInput: View {
    @Binding var source: String
    var compact = false
    var latexTemplates = false
    @State private var systemKeyboard = false
    @State private var command: MathInputCommand?
    private func latexTemplate(_ value: String) -> String {
        ["(□)/(□)": "\\frac{□}{□}", "sqrt(□)": "\\sqrt{□}", "^(□)": "^{□}", "±": "\\pm ", "<=": "\\le ", ">=": "\\ge ", "sin(□)": "\\sin(□)", "pi": "\\pi " ][value] ?? value
    }
    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 6 : 12) {
            if !compact { ScrollView(.horizontal) {
                TypesetMath(source: source.isEmpty ? "\\square" : source, size: 30).padding(12)
            }.frame(minHeight: 72).background(DarwinTheme.panel, in: RoundedRectangle(cornerRadius: 12)) }
            MathInputText(source: $source, command: command, systemKeyboard: !compact || systemKeyboard)
                .frame(height: compact ? 38 : 76).padding(10).background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 12))
            ScrollView(.horizontal) {
                HStack(spacing: 8) {
                    ForEach([("a/b", "(□)/(□)"), ("√", "sqrt(□)"), ("xⁿ", "^(□)"), ("x²", "^2"), ("( )", "(□)"), ("±", "±"), ("=", "="), ("≤", "<="), ("≥", ">="), ("sin", "sin(□)"), ("π", "pi")], id: \.0) { title, template in
                        DarwinButton(title: title, selected: true) { command = MathInputCommand(action: .insert(latexTemplates ? latexTemplate(template) : template)) }
                    }
                }
            }
            HStack {
                DarwinButton(title: "Previous blank", icon: "chevron.left") { command = MathInputCommand(action: .blank(backward: true)) }
                DarwinButton(title: "Next blank", icon: "chevron.right") { command = MathInputCommand(action: .blank(backward: false)) }
                DarwinButton(title: "Exit", icon: "arrow.turn.down.right") { command = MathInputCommand(action: .exit) }
                if compact {
                    Spacer(minLength: 0)
                    DarwinButton(title: "Select all") { command = MathInputCommand(action: .selectAll) }
                    DarwinButton(title: "", icon: systemKeyboard ? "number" : "keyboard") { systemKeyboard.toggle() }
                        .accessibilityLabel(systemKeyboard ? "Math keypad" : "System keyboard")
                }
            }
            if compact {
                if !systemKeyboard {
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 8), spacing: 6) {
                        ForEach(["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", ".", "x", "+", "−", "×", "⌫"], id: \.self) { key in
                            Button {
                                command = MathInputCommand(action: key == "⌫" ? .delete : .insert(key == "×" ? (latexTemplates ? "\\cdot " : "*") : key == "−" ? "-" : key))
                            } label: {
                                Text(key).font(.system(size: 21, weight: .medium)).frame(maxWidth: .infinity, minHeight: 44)
                                    .background(DarwinTheme.subtle, in: RoundedRectangle(cornerRadius: 8))
                            }.buttonStyle(DarwinPressStyle()).accessibilityLabel(key == "⌫" ? "Delete" : "Insert " + key)
                        }
                    }
                }
            } else { Text("Tap a template, then fill its □ blanks. You can also type x^2=2 or sqrt(2). Select an expression before tapping a template to wrap it.")
                .font(.caption).foregroundStyle(DarwinTheme.secondary) }
        }
    }
}

private struct MathInputCommand {
    enum Action { case insert(String), blank(backward: Bool), exit, delete, selectAll }
    var id = UUID()
    var action: Action
}

private struct MathInputText: UIViewRepresentable {
    @Binding var source: String
    var command: MathInputCommand?
    var systemKeyboard = true
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIView(context: Context) -> UITextView {
        let view = UITextView()
        view.delegate = context.coordinator
        view.backgroundColor = .clear
        view.font = .monospacedSystemFont(ofSize: 24, weight: .regular)
        view.autocorrectionType = .no
        view.autocapitalizationType = .none
        view.smartQuotesType = .no
        view.smartDashesType = .no
        view.text = source
        view.inputView = systemKeyboard ? nil : UIView(frame: .zero)
        view.inputAssistantItem.leadingBarButtonGroups = []
        view.inputAssistantItem.trailingBarButtonGroups = []
        view.accessibilityLabel = "Equation input"
        return view
    }
    func updateUIView(_ view: UITextView, context: Context) {
        let c = context.coordinator
        c.parent = self
        if systemKeyboard != (view.inputView == nil) {
            view.inputView = systemKeyboard ? nil : UIView(frame: .zero)
            view.reloadInputViews()
            if systemKeyboard { DispatchQueue.main.async { view.becomeFirstResponder() } }
        }
        view.textColor = UIColor(DarwinTheme.ink)
        view.tintColor = UIColor(DarwinTheme.accent)
        if view.markedTextRange == nil, view.text != source {
            let range = view.selectedRange
            view.text = source
            view.selectedRange = NSRange(location: min(range.location, (source as NSString).length), length: 0)
        }
        if let command, c.lastCommand != command.id {
            c.lastCommand = command.id
            // UIKit edits and binding writes must happen after SwiftUI's update pass.
            DispatchQueue.main.async { c.perform(command.action, in: view) }
        }
    }
    final class Coordinator: NSObject, UITextViewDelegate {
        var parent: MathInputText
        var lastCommand: UUID?
        init(_ parent: MathInputText) { self.parent = parent }
        func textViewDidChange(_ textView: UITextView) { parent.source = textView.text }
        func perform(_ action: MathInputCommand.Action, in view: UITextView) {
            guard view.markedTextRange == nil else { return }
            view.becomeFirstResponder()
            let text = view.text as NSString
            switch action {
            case .selectAll:
                view.selectedRange = NSRange(location: 0, length: text.length)
            case .delete:
                view.deleteBackward()
                parent.source = view.text
            case .exit:
                let start = min(text.length, NSMaxRange(view.selectedRange))
                let close = text.rangeOfCharacter(from: CharacterSet(charactersIn: ")}"), options: [], range: NSRange(location: start, length: text.length - start))
                view.selectedRange = NSRange(location: close.location == NSNotFound ? text.length : NSMaxRange(close), length: 0)
            case .insert(var template):
                let range = view.selectedRange
                if range.length > 0, template.hasPrefix("^"), text.substring(with: range) != "□" {
                    template = "(" + text.substring(with: range) + ")" + template
                } else if range.length > 0, template.contains("□"), text.substring(with: range) != "□" {
                    let blank = (template as NSString).range(of: "□")
                    template = (template as NSString).replacingCharacters(in: blank, with: text.substring(with: range))
                }
                view.text = text.replacingCharacters(in: range, with: template)
                let blank = (template as NSString).range(of: "□")
                view.selectedRange = blank.location == NSNotFound
                    ? NSRange(location: range.location + (template as NSString).length, length: 0)
                    : NSRange(location: range.location + blank.location, length: 1)
                parent.source = view.text
            case .blank(let backward):
                let caret = view.selectedRange
                let start = backward ? caret.location : min(text.length, NSMaxRange(caret))
                let region = backward ? NSRange(location: 0, length: start) : NSRange(location: start, length: text.length - start)
                var match = text.range(of: "□", options: backward ? .backwards : [], range: region)
                if match.location == NSNotFound { match = text.range(of: "□", options: backward ? .backwards : []) }
                if match.location != NSNotFound { view.selectedRange = match; view.scrollRangeToVisible(match) }
            }
        }
    }
}

/// Selected-equation actions remain next to the workspace rather than behind a picker.
struct EquationActions: View {
    var edit: () -> Void
    var more: () -> Void
    var apply: (String, String) async -> Bool
    @State private var busy = false
    @State private var parameterOperation: String?
    @State private var argument = "2"
    private func run(_ operation: String, _ value: String = "") {
        busy = true
        Task { defer { busy = false }; if await apply(operation, value) { parameterOperation = nil } }
    }
    var body: some View {
        ScrollView(.horizontal) {
            HStack(spacing: 8) {
                DarwinButton(title: "Edit equation", icon: "pencil") { edit() }
                DarwinButton(title: "Simplify") { run("simplify") }
                DarwinButton(title: "Move terms") { run("move_terms") }
                DarwinButton(title: "Solve", selected: true) { run("solve") }
                Menu("Both sides") {
                    Button("Multiply…") { parameterOperation = "multiply" }
                    Button("Divide…") { parameterOperation = "divide" }
                    Button("Square") { run("square_both_sides") }
                }.frame(minHeight: 44)
                DarwinButton(title: "More…") { more() }
                if busy { ProgressView() }
            }.disabled(busy)
        }
        .popover(isPresented: Binding(get: { parameterOperation != nil }, set: { if !$0 { parameterOperation = nil } })) {
            VStack(alignment: .leading, spacing: 16) {
                Text(parameterOperation == "divide" ? "Divide both sides" : "Multiply both sides").font(.headline)
                MathInput(source: $argument)
                DarwinButton(title: "Apply", selected: true) { if let operation = parameterOperation { run(operation, argument) } }
                    .disabled(busy || argument.trimmingCharacters(in: .whitespaces).isEmpty || argument.contains("□"))
            }.padding(20).frame(width: 380).presentationCompactAdaptation(.popover)
        }
    }
}
