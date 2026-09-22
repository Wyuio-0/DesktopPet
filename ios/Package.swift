// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AmiyaPet",
    platforms: [
        .iOS(.v16)
    ],
    products: [
        .library(
            name: "AmiyaPetCore",
            targets: ["AmiyaPetCore"]
        )
    ],
    targets: [
        .target(
            name: "AmiyaPetCore",
            path: "AmiyaPet/Core"
        )
    ]
)
