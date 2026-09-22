import Foundation
import Combine

public enum PetState: String, Codable {
    case normal
    case dragging
    case focusing
    case urgent
    case sleepy
}

public struct PetSkin: Identifiable, Hashable {
    public let id: String
    public let name: String
    public let shortName: String
    public let description: String
    public let defaultAssetName: String
    public let blinkAssetName: String?
    public let dragAssetName: String?
    public let focusAssetName: String?
    public let urgentAssetName: String?
    public let sleepAssetName: String?
    public let themeColor: String

    public init(
        id: String,
        name: String,
        shortName: String,
        description: String,
        defaultAssetName: String,
        blinkAssetName: String? = nil,
        dragAssetName: String? = nil,
        focusAssetName: String? = nil,
        urgentAssetName: String? = nil,
        sleepAssetName: String? = nil,
        themeColor: String = "#38BDF8"
    ) {
        self.id = id
        self.name = name
        self.shortName = shortName
        self.description = description
        self.defaultAssetName = defaultAssetName
        self.blinkAssetName = blinkAssetName
        self.dragAssetName = dragAssetName
        self.focusAssetName = focusAssetName
        self.urgentAssetName = urgentAssetName
        self.sleepAssetName = sleepAssetName
        self.themeColor = themeColor
    }

    public func assetName(for state: PetState) -> String {
        switch state {
        case .normal: return defaultAssetName
        case .dragging: return dragAssetName ?? defaultAssetName
        case .focusing: return focusAssetName ?? defaultAssetName
        case .urgent: return urgentAssetName ?? defaultAssetName
        case .sleepy: return sleepAssetName ?? defaultAssetName
        }
    }
}

public struct Operator: Identifiable, Hashable {
    public let id: String
    public let displayName: String
    public let emojiPrefix: String
    public let profession: String
    public let defaultSkinId: String
    public let skins: [PetSkin]

    public func getSkin(skinId: String) -> PetSkin {
        return skins.first(where: { $0.id.caseInsensitiveCompare(skinId) == .orderedSame })
            ?? skins.first(where: { $0.id == defaultSkinId })
            ?? skins.first!
    }
}

public class PetSkinRepository: ObservableObject {
    public static let shared = PetSkinRepository()

    public static let OPERATORS: [Operator] = [
        Operator(
            id: "amiya",
            displayName: "阿米娅",
            emojiPrefix: "🐰",
            profession: "罗德岛领袖",
            defaultSkinId: "amiya_caster",
            skins: [
                PetSkin(
                    id: "amiya_caster",
                    name: "术师 · 庆典",
                    shortName: "术师",
                    description: "经典庆典巫师帽与花簇装束",
                    defaultAssetName: "avatar_amiya",
                    blinkAssetName: "avatar_amiya_blink",
                    dragAssetName: "avatar_amiya_drag",
                    focusAssetName: "avatar_amiya_focus",
                    urgentAssetName: "avatar_amiya_urgent",
                    sleepAssetName: "avatar_amiya_sleep",
                    themeColor: "#38BDF8"
                ),
                PetSkin(
                    id: "amiya_guard",
                    name: "近卫 · 影霄",
                    shortName: "骑士",
                    description: "近卫升变形态，执掌黑剑影霄，英姿飒爽",
                    defaultAssetName: "avatar_amiya_guard",
                    blinkAssetName: "avatar_amiya_guard_blink",
                    dragAssetName: "avatar_amiya_guard_drag",
                    focusAssetName: "avatar_amiya_guard_focus",
                    urgentAssetName: "avatar_amiya_guard_urgent",
                    sleepAssetName: "avatar_amiya_guard_sleep",
                    themeColor: "#00E5FF"
                ),
                PetSkin(
                    id: "amiya_postman",
                    name: "见习联络员 · 报童",
                    shortName: "报童",
                    description: "报童见习装束，元气满满的联络官",
                    defaultAssetName: "avatar_amiya_fresh",
                    blinkAssetName: "avatar_amiya_fresh_blink",
                    dragAssetName: "avatar_amiya_fresh_drag",
                    focusAssetName: "avatar_amiya_fresh_focus",
                    urgentAssetName: "avatar_amiya_fresh_urgent",
                    sleepAssetName: "avatar_amiya_fresh_sleep",
                    themeColor: "#F59E0B"
                )
            ]
        )
    ]

    private let defaults = UserDefaults.standard
    private let skinKey = "pref_current_skin_id"
    private let operatorKey = "pref_current_operator_id"

    @Published public var currentOperator: Operator
    @Published public var currentSkin: PetSkin

    private init() {
        let op = PetSkinRepository.OPERATORS.first!
        currentOperator = op
        let savedSkinId = defaults.string(forKey: skinKey) ?? op.defaultSkinId
        currentSkin = op.getSkin(skinId: savedSkinId)
    }

    public func setSkin(skinId: String) {
        currentSkin = currentOperator.getSkin(skinId: skinId)
        defaults.set(skinId, forKey: skinKey)
    }
}
