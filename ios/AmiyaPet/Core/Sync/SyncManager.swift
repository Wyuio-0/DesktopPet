import Foundation
import Network
import Combine
import UIKit

public class SyncManager: ObservableObject {
    public static let shared = SyncManager()

    @Published public var isRunning: Bool = false
    @Published public var discoveredDevices: [DeviceInfo] = []
    @Published public var pairedDevices: [DeviceInfo] = []

    public var onTacticalDropReceived: ((String, String) -> Void)?

    private var udpListener: NWListener?
    private var tcpListener: NWListener?
    private let broadcastPort: UInt16 = 23333
    private let syncPort: UInt16 = 23334

    private let deviceId: String
    private let deviceName: String

    private init() {
        let defaults = UserDefaults.standard
        if let savedId = defaults.string(forKey: "pref_sync_device_id") {
            self.deviceId = savedId
        } else {
            let newId = "ios_" + UUID().uuidString.prefix(8).lowercased()
            defaults.set(newId, forKey: "pref_sync_device_id")
            self.deviceId = newId
        }
        self.deviceName = UIDevice.current.name
    }

    public func start() {
        guard !isRunning else { return }
        isRunning = true
        startUdpListener()
        startTcpListener()
        broadcastSelf()
    }

    public func stop() {
        isRunning = false
        udpListener?.cancel()
        udpListener = nil
        tcpListener?.cancel()
        tcpListener = nil
    }

    private func startUdpListener() {
        do {
            let params = NWParameters.udp
            params.allowLocalEndpointReuse = true
            udpListener = try NWListener(using: params, on: NWEndpoint.Port(rawValue: broadcastPort)!)
            udpListener?.stateUpdateHandler = { state in
                if case .ready = state {
                    print("UDP Discovery Listener ready on port \(self.broadcastPort)")
                }
            }
            udpListener?.newConnectionHandler = { [weak self] connection in
                self?.handleUdpConnection(connection)
            }
            udpListener?.start(queue: .global())
        } catch {
            print("Failed to start UDP listener: \(error)")
        }
    }

    private func handleUdpConnection(_ connection: NWConnection) {
        connection.start(queue: .global())
        connection.receiveMessage { [weak self] content, _, _, _ in
            guard let self = self, let data = content,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let action = json["action"] as? String, action == "discover",
                  let senderId = json["device_id"] as? String, senderId != self.deviceId else {
                return
            }

            let remoteIp = (connection.endpoint as? NWEndpoint)?.debugDescription ?? ""
            let name = json["device_name"] as? String ?? "未知设备"
            let type = json["device_type"] as? String ?? "pc"
            let port = json["http_port"] as? Int ?? 23333
            let ver = json["version"] as? String ?? "1.0.0"

            let device = DeviceInfo(deviceId: senderId, deviceName: name, deviceType: type, ip: remoteIp, httpPort: port, version: ver)
            DispatchQueue.main.async {
                if !self.discoveredDevices.contains(where: { $0.deviceId == device.deviceId }) {
                    self.discoveredDevices.append(device)
                }
            }
        }
    }

    private func startTcpListener() {
        do {
            let tcpListener = try NWListener(using: .tcp, on: NWEndpoint.Port(rawValue: syncPort)!)
            tcpListener.newConnectionHandler = { [weak self] connection in
                self?.handleTcpConnection(connection)
            }
            tcpListener.start(queue: .global())
            self.tcpListener = tcpListener
        } catch {
            print("Failed to start TCP listener: \(error)")
        }
    }

    private func handleTcpConnection(_ connection: NWConnection) {
        connection.start(queue: .global())
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] content, _, _, _ in
            guard let self = self, let data = content else { return }
            if let drop = try? JSONDecoder().decode(TacticalDrop.self, from: data) {
                DispatchQueue.main.async {
                    self.onTacticalDropReceived?(drop.text, drop.title)
                    _ = NotesManager.shared.addNote(content: drop.text, title: drop.title)
                }
            }
        }
    }

    public func broadcastSelf() {
        // 向局域网广播本设备信息
        let payload: [String: Any] = [
            "action": "discover",
            "device_id": deviceId,
            "device_name": deviceName,
            "device_type": "ios",
            "http_port": syncPort,
            "version": "1.9.3"
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: payload) else { return }

        let broadcastHost = NWEndpoint.Host("255.255.255.255")
        let broadcastPort = NWEndpoint.Port(rawValue: self.broadcastPort)!
        let connection = NWConnection(host: broadcastHost, port: broadcastPort, using: .udp)
        connection.start(queue: .global())
        connection.send(content: data, completion: .contentProcessed({ _ in
            connection.cancel()
        }))
    }

    public func sendTacticalDrop(to device: DeviceInfo, text: String, title: String = "来自阿米娅(iOS)的战术快传") {
        let drop = TacticalDrop(text: text, title: title)
        guard let data = try? JSONEncoder().encode(drop) else { return }

        let host = NWEndpoint.Host(device.ip)
        let port = NWEndpoint.Port(rawValue: UInt16(device.httpPort))!
        let connection = NWConnection(host: host, port: port, using: .tcp)
        connection.start(queue: .global())
        connection.send(content: data, completion: .contentProcessed({ _ in
            connection.cancel()
        }))
    }
}
