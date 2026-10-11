import SwiftUI
import Foundation
import MathCoreBridge
@main struct ProbeApp: App {
 var body: some Scene { WindowGroup { ProbeView() } }
}
struct ProbeView: View {
 @State private var output = "Tap to test original C++ core"
 var body: some View { VStack { Text(output); Button("Run lost-root check") {
 let data = MathCoreBridge.trace("x*(x-1)=0\nx-1=0")
 output = String(data: data, encoding: .utf8) ?? "Invalid response"
 } }.padding() }
}
