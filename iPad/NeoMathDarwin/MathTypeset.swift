import SwiftUI
import SwiftMath

// The neutral UIView wrapper keeps SwiftUI's layer geometry separate from the math label's flipped CoreText layer.
final class MathLabelContainer: UIView {
    let label = MTMathUILabel()
    var renderedSource: String?
    var renderedSize: CGFloat?
    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .clear
        label.backgroundColor = .clear
        label.preferredMaxLayoutWidth = 10000
        label.contentInsets = UIEdgeInsets(top: 4, left: 2, bottom: 4, right: 2)
        addSubview(label)
        isAccessibilityElement = true
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func layoutSubviews() {
        super.layoutSubviews()
        label.frame = bounds
        label.setNeedsLayout()
        label.layoutIfNeeded()
    }
    func measured() -> CGSize {
        let measured = label.sizeThatFits(CGSize(width: 10000, height: 10000))
        return CGSize(width: max(8, measured.width + 8), height: max(label.fontSize * 1.5, measured.height))
    }
    override var intrinsicContentSize: CGSize { measured() }
}

struct TypesetMath: UIViewRepresentable {
    var source: String
    var size: CGFloat = 26
    func makeUIView(context: Context) -> MathLabelContainer { MathLabelContainer() }
    func updateUIView(_ view: MathLabelContainer, context: Context) {
        view.label.textColor = UIColor(DarwinTheme.ink)
        if view.renderedSource != source || view.renderedSize != size {
            view.renderedSource = source
            view.renderedSize = size
            view.label.fontSize = size
            view.label.latex = MathDisplay.latex(source)
            view.accessibilityLabel = source
            view.invalidateIntrinsicContentSize()
            view.setNeedsLayout()
        }
    }
    func sizeThatFits(_ proposal: ProposedViewSize, uiView: MathLabelContainer, context: Context) -> CGSize? { uiView.measured() }
}
