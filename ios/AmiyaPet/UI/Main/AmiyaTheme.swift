import SwiftUI

public extension Color {
    init(hex: String) {
        let scanner = Scanner(string: hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted))
        var int: UInt64 = 0
        scanner.scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }

    // 罗德岛科技配色板
    static let amiyaPrimary = Color(hex: "#0284C7")
    static let amiyaCyan = Color(hex: "#00E5FF")
    static let amiyaLightBlue = Color(hex: "#38BDF8")
    static let amiyaAmber = Color(hex: "#F59E0B")
    static let amiyaBackground = Color(UIColor.systemGroupedBackground)
    static let amiyaCardBg = Color(UIColor.secondarySystemGroupedBackground)
}

public struct CardModifier: ViewModifier {
    public func body(content: Content) -> some View {
        content
            .background(Color.amiyaCardBg)
            .cornerRadius(14)
            .shadow(color: Color.black.opacity(0.04), radius: 6, x: 0, y: 2)
    }
}

public extension View {
    func amiyaCardStyle() -> some View {
        self.modifier(CardModifier())
    }
}
