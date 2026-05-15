// swift-tools-version: 5.8
import PackageDescription

let package = Package(
    name: "ProxyGatewayDesktop",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "ProxyGatewayDesktop", targets: ["ProxyGatewayDesktop"])
    ],
    targets: [
        .executableTarget(
            name: "ProxyGatewayDesktop",
            path: "Sources/ProxyGatewayDesktop"
        ),
        .testTarget(
            name: "ProxyGatewayDesktopTests",
            dependencies: ["ProxyGatewayDesktop"],
            path: "Tests/ProxyGatewayDesktopTests"
        )
    ]
)
