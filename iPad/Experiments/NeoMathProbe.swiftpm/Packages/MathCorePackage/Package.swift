// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "MathCorePackage", platforms: [.macOS(.v13), .iOS(.v17)], products: [.library(name: "MathCoreBridge", targets: ["MathCoreBridge"])], targets: [
 .target(name: "MathCoreBridge", publicHeadersPath: "include", cxxSettings: [.headerSearchPath("Headers")], linkerSettings: [.linkedFramework("Foundation")]),
 .executableTarget(name: "CoreProbe", dependencies: ["MathCoreBridge"])
], cxxLanguageStandard: .cxx20)
