import Foundation

public struct DeviceInfo: Codable, Identifiable, Hashable {
    public var id: String { deviceId }
    public var deviceId: String
    public var deviceName: String
    public var deviceType: String // "pc", "android", "ios"
    public var ip: String
    public var httpPort: Int
    public var version: String
    public var paired: Bool

    public init(
        deviceId: String,
        deviceName: String,
        deviceType: String = "ios",
        ip: String,
        httpPort: Int = 23334,
        version: String = "1.9.3",
        paired: Bool = false
    ) {
        self.deviceId = deviceId
        self.deviceName = deviceName
        self.deviceType = deviceType
        self.ip = ip
        self.httpPort = httpPort
        self.version = version
        self.paired = paired
    }

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case deviceName = "device_name"
        case deviceType = "device_type"
        case ip
        case httpPort = "http_port"
        case version
        case paired
    }
}

public struct TacticalDrop: Codable {
    public let text: String
    public let title: String
    public let timestamp: Int64

    public init(text: String, title: String = "战术快传", timestamp: Int64 = Int64(Date().timeIntervalSince1970 * 1000)) {
        self.text = text
        self.title = title
        self.timestamp = timestamp
    }
}
