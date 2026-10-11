// swift-tools-version: 5.9
import PackageDescription
import AppleProductTypes
let package = Package(name: "NeoMathProbe", platforms: [.iOS(.v17)], products: [
 .iOSApplication(name: "NeoMathProbe", targets: ["AppModule"], bundleIdentifier: "com.neomath.swiftpmprobe", teamIdentifier: "", displayVersion: "1.0", bundleVersion: "1", appIcon: .placeholder(icon: .star), accentColor: .presetColor(.blue), supportedDeviceFamilies: [.pad], supportedInterfaceOrientations: [.portrait, .landscapeLeft, .landscapeRight])
], dependencies: [.package(path: "Packages/MathCorePackage")], targets: [
 .executableTarget(name: "AppModule", dependencies: [.product(name: "MathCoreBridge", package: "MathCorePackage")], path: "Sources")
])
