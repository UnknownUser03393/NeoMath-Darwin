import SwiftUI

@main struct NeoMathDarwinApp: App {
    init() {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        if let index = args.firstIndex(of: "--backend-url"), args.indices.contains(index + 1) {
            UserDefaults.standard.set(args[index + 1], forKey: "darwin.backendURL")
            UserDefaults.standard.set(true, forKey: "darwin.useBackend")
        }
        if args.contains("--probe-backend") {
            Task {
                do {
                    let health = try await BackendClient().envelope("health")
                    print("DEVICE HEALTH: \(health)")
                    let trace = try await BackendClient().envelope("runTrace", ["source": "x^2=2\nx=±sqrt(2)"])
                    print("DEVICE CAS: \(trace)")
                } catch { print("DEVICE BACKEND ERROR: \(error)") }
            }
        }
        #endif
    }
    var body: some Scene { WindowGroup { WorkspaceView() } }
}
