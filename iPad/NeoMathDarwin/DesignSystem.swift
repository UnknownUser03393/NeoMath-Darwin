import SwiftUI

// Literal semantic tokens from NEOMATH_DARWIN_UI_SPEC §4.1.
enum DarwinTheme {
    static func color(_ light: UInt32, _ dark: UInt32) -> Color {
        Color(uiColor: UIColor { traits in
            let hex = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: CGFloat((hex >> 16) & 255)/255, green: CGFloat((hex >> 8) & 255)/255, blue: CGFloat(hex & 255)/255, alpha: 1)
        })
    }
    static let canvas = color(0xF7F9FC, 0x121417)
    static let panel = color(0xFFFFFF, 0x1C1F25)
    static let elevated = color(0xFFFFFF, 0x252A32)
    static let subtle = color(0xEDF1F7, 0x292E38)
    static let ink = color(0x1A1E27, 0xF2F5FA)
    static let secondary = color(0x5B6575, 0xB0B9C6)
    static let tertiary = color(0x606C7D, 0x9AA5B5)
    static let accent = color(0x245DD8, 0xA6C0FF)
    static let onAccent = color(0xFFFFFF, 0x10213D)
    static let neutral = color(0x626C7B, 0xAFB9C8)
    static let dot = color(0xCFCFD6, 0x2A2A2D)
    static let fault = color(0xBD3545, 0xFF929B)
    static let caution = color(0x895B00, 0xF2C76E)
    static let verified = color(0x187046, 0x73D8A0)
    static let separator = color(0xDCE2EB, 0x3B424E)
    static func tone(_ status: String) -> Color {
        switch status {
        case "root_fault", "independent_fault", "parse_error": return fault
        case "tainted": return caution
        case "valid": return verified
        default: return neutral
        }
    }
}

struct DarwinButton: View {
    var title: String
    var icon: String? = nil
    var selected = false
    var action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if let icon { Image(systemName: icon).font(.system(size: 18)) }
                if !title.isEmpty { Text(title).font(.system(size: 15, weight: .medium)) }
            }
            .frame(minWidth: 44, minHeight: 44)
            .padding(.horizontal, title.isEmpty ? 0 : 12)
            .background(selected ? DarwinTheme.accent.opacity(0.10) : .clear, in: Capsule())
        }.foregroundStyle(DarwinTheme.accent).buttonStyle(DarwinPressStyle())
    }
}

struct WrappingToolbar: Layout {
    var spacing: CGFloat = 6
    private func arrangement(_ subviews: Subviews, width: CGFloat) -> (positions: [CGPoint], height: CGFloat) {
        var positions: [CGPoint] = [], x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > 0 && x + size.width > width { x = 0; y += rowHeight + spacing; rowHeight = 0 }
            positions.append(CGPoint(x: x, y: y)); x += size.width + spacing; rowHeight = max(rowHeight, size.height)
        }
        return (positions, y + rowHeight)
    }
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 800
        return CGSize(width: width, height: arrangement(subviews, width: width).height)
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let positions = arrangement(subviews, width: bounds.width).positions
        for (index, view) in subviews.enumerated() { view.place(at: CGPoint(x: bounds.minX + positions[index].x, y: bounds.minY + positions[index].y), anchor: .topLeading, proposal: .unspecified) }
    }
}

// Use system springs for interruptible layout changes and restrained content updates.
enum DarwinMotion {
    static let page = Animation.smooth(duration: 0.32)
    static let panel = Animation.snappy(duration: 0.28, extraBounce: 0)
}
struct DarwinPressStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .opacity(!enabled ? 0.4 : configuration.isPressed ? 0.8 : 1)
            .animation(reduceMotion ? nil : .smooth(duration: 0.15), value: configuration.isPressed)
    }
}
