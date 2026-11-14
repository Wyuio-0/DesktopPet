import Foundation
import CoreFoundation
import Network
import Combine
import UIKit
import Security
import Darwin

private enum SyncDataFailure: Error { case invalid }

public final class SyncManager: ObservableObject {
    public static let shared = SyncManager()
    @Published public private(set) var isRunning = false
    @Published public private(set) var discoveredDevices: [DeviceInfo] = []
    @Published public private(set) var pairedDevices: [DeviceInfo] = []
    @Published public private(set) var statusText = "就绪"
    @Published public var incomingPair: IncomingPair?
    public var onTacticalDropReceived: ((String, String) -> Void)?
    public struct IncomingPair: Identifiable {
        public let id: String; public let name: String; public let ip: String; public let pin: String
    }
    private struct Peer: Codable {
        var device: DeviceInfo; var token: String; var secret: String
    }
    private final class Pending {
        let info: IncomingPair
        let event = DispatchSemaphore(value: 0)
        let deadline = ProcessInfo.processInfo.systemUptime + 30
        var accepted = false
        init(_ info: IncomingPair) { self.info = info }
    }
    private var tcpListener: NWListener?
    private var udpListener: NWListener?
    private var secure = SyncCrypto.Server()
    private let lock = NSRecursiveLock()
    private var peers: [String: Peer] = [:]
    private var pending: [String: Pending] = [:]
    private var attempts: [String: [TimeInterval]] = [:]
    private var connections: [UUID: NWConnection] = [:]
    private let port = 23335
    private let keychainService = "com.amiya.pet.sync-v2"
    private let deviceId: String
    private let deviceName: String

    private init() {
        deviceId = UserDefaults.standard.string(forKey: "pref_sync_device_id") ?? "ios_" + UUID().uuidString
        UserDefaults.standard.set(deviceId, forKey: "pref_sync_device_id")
        deviceName = UIDevice.current.name
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService, kSecAttrAccount as String: "peers",
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var result: CFTypeRef?
        if SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
           let data = result as? Data, let saved = try? JSONDecoder().decode([String: Peer].self, from: data) { peers = saved }
        pairedDevices = peers.values.map { $0.device }
    }
    private func savePeer(_ peer: Peer) throws {
        lock.lock(); defer { lock.unlock() }
        var updated = peers; updated[peer.device.deviceId] = peer
        try persistPeers(updated)
    }
    private func persistPeers(_ updated: [String: Peer]) throws {
        let data = try JSONEncoder().encode(updated)
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService, kSecAttrAccount as String: "peers"]
        var status = SecItemUpdate(query as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if status == errSecItemNotFound {
            var item = query; item[kSecValueData as String] = data
            item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            status = SecItemAdd(item as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw SyncCrypto.Failure.invalid }
        peers = updated
        let devices = updated.values.map { $0.device }
        DispatchQueue.main.async { self.pairedDevices = devices }
    }
    private func removePeer(_ id: String) throws {
        lock.lock(); defer { lock.unlock() }
        var updated = peers; updated.removeValue(forKey: id); try persistPeers(updated)
    }
    public func unpair(_ device: DeviceInfo) {
        do { try removePeer(device.deviceId); statusText = "已撤销本机对该设备的信任" }
        catch { statusText = "撤销失败，请重试" }
    }
    public func start() {
        guard !isRunning else { return }
        do {
            secure = SyncCrypto.Server()
            let listener = try NWListener(using: .tcp, on: NWEndpoint.Port(rawValue: UInt16(port))!)
            listener.newConnectionHandler = { [weak self] in self?.receive($0) }
            listener.stateUpdateHandler = { [weak self] state in
                if case .failed = state { DispatchQueue.main.async { self?.stop(); self?.statusText = "同步监听启动失败" } }
            }
            tcpListener = listener
            listener.start(queue: .global())
            let params = NWParameters.udp; params.allowLocalEndpointReuse = true
            let udp = try NWListener(using: params, on: NWEndpoint.Port(rawValue: 23332)!)
            udp.newConnectionHandler = { [weak self] connection in
                connection.start(queue: .global())
                connection.receiveMessage { data, _, _, _ in
                    guard let self = self, let data = data,
                        let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                        json["cmd"] as? String == "DISCOVER" else { connection.cancel(); return }
                    var info = self.info(); info["cmd"] = "DISCOVER_ACK"
                    if let bytes = try? JSONSerialization.data(withJSONObject: info) {
                        connection.send(content: bytes, completion: .contentProcessed { _ in connection.cancel() })
                    }
                }
            }
            udpListener = udp; udp.start(queue: .global())
            isRunning = true; statusText = "加密同步 v2 已开启"
        } catch { stop(); statusText = "同步监听启动失败" }
    }
    public func stop() {
        isRunning = false
        tcpListener?.cancel(); tcpListener = nil; udpListener?.cancel(); udpListener = nil
        lock.lock()
        let old = connections.values; connections.removeAll()
        for request in pending.values { request.event.signal() }; pending.removeAll()
        lock.unlock()
        for connection in old { connection.cancel() }
        incomingPair = nil
    }
    public func createPairingInvite() -> String { secure.createInvite() }
    private func info() -> [String: Any] {
        ["device_id": deviceId, "device_name": deviceName, "device_type": "ios", "http_port": port,
         "version": "1.9.6", "protocol": 2, "epoch": secure.epoch]
    }
    private func onMain<T>(_ body: () throws -> T) rethrows -> T {
        if Thread.isMainThread { return try body() }
        return try DispatchQueue.main.sync(execute: body)
    }
    private func send(_ connection: NWConnection, status: Int, body: Data) {
        let header = "HTTP/1.1 \(status) Sync\r\nContent-Type: application/json\r\nContent-Length: \(body.count)\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n"
        connection.send(content: Data(header.utf8) + body, completion: .contentProcessed { _ in connection.cancel() })
    }
    private func error(_ connection: NWConnection, _ status: Int) { send(connection, status: status, body: Data("{\"error\":\"Encrypted sync v2 required or authentication failed\"}".utf8)) }
    private func receive(_ connection: NWConnection) {
        let identifier = UUID()
        lock.lock()
        guard connections.count < 16 else { lock.unlock(); connection.start(queue: .global()); error(connection, 503); return }
        connections[identifier] = connection; lock.unlock()
        let timer = DispatchWorkItem { connection.cancel() }
        connection.stateUpdateHandler = { [weak self] state in
            if case .cancelled = state { self?.lock.lock(); self?.connections.removeValue(forKey: identifier); self?.lock.unlock(); timer.cancel() }
        }
        let queue = DispatchQueue(label: "amiya.sync.request.\(identifier)")
        connection.start(queue: queue); queue.asyncAfter(deadline: .now() + 5, execute: timer)
        var buffer = Data()
        func next() {
            connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data, _, complete, failure in
                if let data = data { buffer.append(data) }
                guard buffer.count <= SyncCrypto.maxWire + 16384 else { self.error(connection, 413); return }
                guard let marker = buffer.range(of: Data("\r\n\r\n".utf8)) else {
                    if buffer.count > 16384 || complete || failure != nil { self.error(connection, 400) } else { next() }; return
                }
                guard marker.upperBound <= 16384, let header = String(data: buffer[..<marker.lowerBound], encoding: .ascii) else { self.error(connection, 400); return }
                let lines = header.components(separatedBy: "\r\n")
                let first = lines[0].split(separator: " ")
                guard first.count == 3 else { self.error(connection, 400); return }
                let method = String(first[0]); let path = String(first[1])
                var headers: [String: String] = [:]
                for line in lines.dropFirst() {
                    guard let colon = line.firstIndex(of: ":") else { self.error(connection, 400); return }
                    let key = String(line[..<colon]).lowercased()
                    guard headers[key] == nil else { self.error(connection, 400); return }
                    headers[key] = String(line[line.index(after: colon)...]).trimmingCharacters(in: .whitespaces)
                }
                if headers["origin"] != nil || headers["sec-fetch-site"] != nil || method == "OPTIONS" { self.error(connection, 403); return }
                if method == "GET" && path == "/api/info" {
                    timer.cancel(); self.send(connection, status: 200, body: (try? JSONSerialization.data(withJSONObject: self.info())) ?? Data()); return
                }
                guard method == "POST", SyncCrypto.paths.contains(path), headers["x-rhodes-protocol"] == "2", headers["authorization"] == nil else { self.error(connection, 426); return }
                guard headers["transfer-encoding"] == nil, let raw = headers["content-length"], !raw.isEmpty,
                      raw.allSatisfy({ $0 >= "0" && $0 <= "9" }), let count = Int(raw), count >= 0,
                      headers["content-type"]?.lowercased().hasPrefix("application/json") == true else { self.error(connection, 400); return }
                let limit = path == "/api/pair/request" ? 4096 : (path == "/api/clipboard" ? 256 * 1024 : SyncCrypto.maxPlain)
                guard count <= (limit + 16) * 4 / 3 + 2048 else { self.error(connection, 413); return }
                guard buffer.count >= marker.upperBound + count else {
                    if complete || failure != nil { self.error(connection, 400) } else { next() }; return
                }
                timer.cancel()
                queue.asyncAfter(deadline: .now() + 40) { connection.cancel() }
                let body = buffer.subdata(in: marker.upperBound..<(marker.upperBound + count))
                DispatchQueue.global().async { self.route(connection, path, body, limit) }
            }
        }
        next()
    }
    private func route(_ connection: NWConnection, _ path: String, _ body: Data, _ limit: Int) {
        do {
            let envelope = try JSONDecoder().decode(SyncCrypto.Envelope.self, from: body)
            lock.lock(); let record = peers.values.first { (try? SyncCrypto.keyId($0.secret)) == envelope.kid }; lock.unlock()
            guard let secret = path == "/api/pair/request" ? secure.inviteSecret(envelope.kid) : record?.secret else { throw SyncCrypto.Failure.invalid }
            let plain = try secure.accept(secret, path, envelope)
            if path == "/api/pair/request" && !secure.claimInvite(secret, envelope.id) { throw SyncCrypto.Failure.invalid }
            defer { if path == "/api/pair/request" { secure.releaseInvite(secret, envelope.id) } }
            guard plain.count <= limit, let payload = try JSONSerialization.jsonObject(with: plain) as? [String: Any] else { throw SyncCrypto.Failure.invalid }
            var status = 200
            var result: [String: Any]
            if path == "/api/pair/request" {
                result = try pair(connection, payload, secret)
                if result["status"] as? String != "accepted" { status = 403 }
            } else {
                guard let token = payload["_auth_token"] as? String, !token.isEmpty, token == record?.token else { throw SyncCrypto.Failure.invalid }
                if path == "/api/pair/unpair" {
                    if payload["device_id"] as? String == record?.device.deviceId, let id = record?.device.deviceId {
                        try removePeer(id); result = ["status": "unpaired"]
                    } else { status = 403; result = ["error": "只能解除自身设备的配对"] }
                } else {
                    do { result = try onMain { try self.apply(path, payload) } }
                    catch is SyncDataFailure { status = 400; result = ["error": "同步数据格式无效，未应用"] }
                }
            }
            let bytes = try JSONSerialization.data(withJSONObject: result)
            let reply = try SyncCrypto.seal(secret, path, bytes, envelope, "response", status)
            send(connection, status: status, body: try JSONEncoder().encode(reply))
        } catch { self.error(connection, 401) }
    }
    private func remoteIP(_ connection: NWConnection) -> String {
        if case .hostPort(let host, _) = connection.endpoint { return String(describing: host) }
        return ""
    }
    private func pair(_ connection: NWConnection, _ payload: [String: Any], _ secret: String) throws -> [String: Any] {
        let pin = try SyncCrypto.pairingCode(secret)
        guard let id = payload["client_id"] as? String, !id.isEmpty, id.count <= 128,
              let name = payload["client_name"] as? String, !name.isEmpty, name.count <= 128,
              let remotePort = payload["client_port"] as? Int, (1...65535).contains(remotePort) else { throw SyncCrypto.Failure.invalid }
        let ip = remoteIP(connection); let now = ProcessInfo.processInfo.systemUptime
        let request = Pending(IncomingPair(id: UUID().uuidString, name: name, ip: ip, pin: pin))
        lock.lock()
        attempts = attempts.mapValues { $0.filter { now - $0 < 60 } }.filter { !$0.value.isEmpty }
        let history = attempts[ip] ?? []
        guard pending.count < 8, !pending.values.contains(where: { $0.info.ip == ip }), history.count < 5,
              attempts[ip] != nil || attempts.count < 128 else { lock.unlock(); throw SyncCrypto.Failure.invalid }
        attempts[ip] = history + [now]; pending[request.info.id] = request; lock.unlock()
        DispatchQueue.main.async { self.incomingPair = request.info }
        _ = request.event.wait(timeout: .now() + 30)
        lock.lock(); pending.removeValue(forKey: request.info.id); let accepted = request.accepted; lock.unlock()
        DispatchQueue.main.async { if self.incomingPair?.id == request.info.id { self.incomingPair = nil } }
        guard accepted else { return ["status": "rejected", "error": "配对被拒绝或过期"] }
        let token = "rhodes_i_" + SyncCrypto.newSecret()
        let device = DeviceInfo(deviceId: id, deviceName: name, deviceType: "peer", ip: ip, httpPort: remotePort, paired: true)
        try savePeer(Peer(device: device, token: token, secret: secret)); secure.consumeInvite(secret)
        return ["status": "accepted", "auth_token": token, "device_id": deviceId, "device_name": deviceName]
    }
    public func confirmPair(_ id: String, accept: Bool) {
        lock.lock(); defer { lock.unlock() }
        if let request = pending[id], request.deadline > ProcessInfo.processInfo.systemUptime { request.accepted = accept; request.event.signal() }
        incomingPair = nil
    }

    // All client calls use direct native TCP, bounded HTTP framing and no redirects/proxies.
    private func http(_ ip: String, _ port: Int, _ method: String, _ path: String, _ body: Data = Data()) throws -> (Int, Data) {
        guard (1...65535).contains(port) else { throw SyncCrypto.Failure.invalid }
        let connection = NWConnection(host: NWEndpoint.Host(ip), port: NWEndpoint.Port(rawValue: UInt16(port))!, using: .tcp)
        let queue = DispatchQueue(label: "amiya.sync.client")
        let done = DispatchSemaphore(value: 0)
        var result: Result<(Int, Data), Error>?
        var buffer = Data()
        func finish(_ value: Result<(Int, Data), Error>) { guard result == nil else { return }; result = value; connection.cancel(); done.signal() }
        func read() {
            connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data, _, complete, failure in
                if let data = data { buffer.append(data) }
                if buffer.count > SyncCrypto.maxWire + 16384 { finish(.failure(SyncCrypto.Failure.invalid)); return }
                if let marker = buffer.range(of: Data("\r\n\r\n".utf8)) {
                    guard marker.upperBound <= 16384, let text = String(data: buffer[..<marker.lowerBound], encoding: .ascii) else { finish(.failure(SyncCrypto.Failure.invalid)); return }
                    let lines = text.components(separatedBy: "\r\n"); let first = lines[0].split(separator: " ")
                    guard first.count >= 2, let status = Int(first[1]) else { finish(.failure(SyncCrypto.Failure.invalid)); return }
                    var lengths: [Int] = []
                    for line in lines.dropFirst() { if line.lowercased().hasPrefix("content-length:"), let length = Int(line.dropFirst(15).trimmingCharacters(in: .whitespaces)) { lengths.append(length) } }
                    guard lengths.count == 1, let length = lengths.first, length >= 0 && length <= SyncCrypto.maxWire else { finish(.failure(SyncCrypto.Failure.invalid)); return }
                    if buffer.count >= marker.upperBound + length { finish(.success((status, buffer.subdata(in: marker.upperBound..<(marker.upperBound + length))))); return }
                } else if buffer.count > 16384 { finish(.failure(SyncCrypto.Failure.invalid)); return }
                if complete || failure != nil { finish(.failure(SyncCrypto.Failure.invalid)) } else { read() }
            }
        }
        connection.stateUpdateHandler = { state in
            if case .ready = state {
                var header = "\(method) \(path) HTTP/1.1\r\nHost: \(ip):\(port)\r\nConnection: close\r\n"
                if method == "POST" { header += "X-Rhodes-Protocol: 2\r\nContent-Type: application/json\r\nContent-Length: \(body.count)\r\n" }
                connection.send(content: Data((header + "\r\n").utf8) + body, completion: .contentProcessed { error in
                    if let error = error { finish(.failure(error)) } else { read() }
                })
            } else if case .failed(let error) = state { finish(.failure(error)) }
        }
        connection.start(queue: queue)
        guard done.wait(timeout: .now() + (path == "/api/pair/request" ? 40 : 15)) == .success else { connection.cancel(); throw SyncCrypto.Failure.invalid }
        return try result!.get()
    }
    private func exchange(_ ip: String, _ port: Int, _ path: String, _ payload: [String: Any], _ secret: String, _ token: String? = nil) throws -> (Int, [String: Any]) {
        let (code, data) = try http(ip, port, "GET", "/api/info")
        guard code == 200, let info = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              info["protocol"] as? Int == 2, let epoch = info["epoch"] as? String else { throw SyncCrypto.Failure.invalid }
        var message = payload; if let token = token { message["_auth_token"] = token }
        let request = try SyncCrypto.request(secret, path, JSONSerialization.data(withJSONObject: message), epoch)
        let (status, response) = try http(ip, port, "POST", path, JSONEncoder().encode(request))
        let plain = try SyncCrypto.response(secret, path, JSONDecoder().decode(SyncCrypto.Envelope.self, from: response), request, status)
        guard let result = try JSONSerialization.jsonObject(with: plain) as? [String: Any] else { throw SyncCrypto.Failure.invalid }
        return (status, result)
    }
    public func requestPair(ip: String, port: Int, secret: String) {
        DispatchQueue.global().async {
            do {
                _ = try SyncCrypto.keyId(secret)
                let (status, result) = try self.exchange(ip, port, "/api/pair/request", ["client_id": self.deviceId,
                    "client_name": self.deviceName, "client_port": self.port, "pin": try SyncCrypto.pairingCode(secret)], secret)
                guard status == 200, let id = result["device_id"] as? String, let token = result["auth_token"] as? String, !id.isEmpty, !token.isEmpty else { throw SyncCrypto.Failure.invalid }
                let device = DeviceInfo(deviceId: id, deviceName: result["device_name"] as? String ?? ip, deviceType: "peer", ip: ip, httpPort: port, paired: true)
                try self.savePeer(Peer(device: device, token: token, secret: secret))
                DispatchQueue.main.async { self.statusText = "加密配对成功" }
            } catch { DispatchQueue.main.async { self.statusText = "配对失败，请检查目标设备、配对密钥及接收端确认" } }
        }
    }
    public func sendTacticalDrop(to device: DeviceInfo, text: String, title: String = "来自阿米娅 (iOS)") {
        operate(device, "/api/clipboard", ["text": text, "title": title])
    }
    public func pull(_ device: DeviceInfo) { operate(device, "/api/sync/pull", [:]) }
    public func push(_ device: DeviceInfo) { operate(device, "/api/sync/push", onMain { snapshot() }.merging(["mode": "merge"], uniquingKeysWith: { _, new in new })) }
    private func operate(_ device: DeviceInfo, _ path: String, _ payload: [String: Any]) {
        lock.lock(); let peer = peers[device.deviceId]; lock.unlock()
        guard let peer = peer else { statusText = "请先重新配对"; return }
        DispatchQueue.global().async {
            do {
                let (status, result) = try self.exchange(device.ip, device.httpPort, path, payload, peer.secret, peer.token)
                guard status == 200 else { throw SyncCrypto.Failure.invalid }
                if path == "/api/sync/pull" { _ = try self.onMain { try self.apply("/api/sync/push", result) } }
                DispatchQueue.main.async { self.statusText = "加密传输完成" }
            } catch { DispatchQueue.main.async { self.statusText = "加密传输失败，请检查连接或重新配对" } }
        }
    }
    public func broadcastSelf() {
        DispatchQueue.global().async {
            let fd = socket(AF_INET, SOCK_DGRAM, Int32(IPPROTO_UDP))
            guard fd >= 0 else { return }; defer { close(fd) }
            var yes: Int32 = 1; _ = setsockopt(fd, SOL_SOCKET, SO_BROADCAST, &yes, socklen_t(MemoryLayout.size(ofValue: yes)))
            var timeout = timeval(tv_sec: 0, tv_usec: 300000); _ = setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue: timeout)))
            var address = sockaddr_in(); address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size); address.sin_family = sa_family_t(AF_INET)
            address.sin_port = UInt16(23332).bigEndian; address.sin_addr.s_addr = inet_addr("255.255.255.255")
            var info = self.info(); info["cmd"] = "DISCOVER"
            guard let bytes = try? JSONSerialization.data(withJSONObject: info) else { return }
            _ = bytes.withUnsafeBytes { raw in withUnsafePointer(to: &address) { ptr in ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sendto(fd, raw.baseAddress, bytes.count, 0, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } } }
            let deadline = Date().addingTimeInterval(2)
            var devices: [DeviceInfo] = []
            while Date() < deadline {
                var buffer = [UInt8](repeating: 0, count: 2048); var sender = sockaddr_in(); var length = socklen_t(MemoryLayout<sockaddr_in>.size)
                let capacity = buffer.count
                let count = withUnsafeMutablePointer(to: &sender) { ptr in ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { recvfrom(fd, &buffer, capacity, 0, $0, &length) } }
                if count <= 0 { continue }
                if let json = try? JSONSerialization.jsonObject(with: Data(buffer.prefix(count))) as? [String: Any],
                    json["cmd"] as? String == "DISCOVER_ACK", let id = json["device_id"] as? String, id != self.deviceId,
                    let port = json["http_port"] as? Int, (1...65535).contains(port), !devices.contains(where: { $0.deviceId == id }) {
                    devices.append(DeviceInfo(deviceId: id, deviceName: json["device_name"] as? String ?? "设备", deviceType: json["device_type"] as? String ?? "peer", ip: String(cString: inet_ntoa(sender.sin_addr)), httpPort: port))
                }
            }
            let result = devices; DispatchQueue.main.async { self.discoveredDevices = result }
        }
    }

    private func snapshot() -> [String: Any] {
        let sched = ScheduleManager.shared; let formatter = DateFormatter(); formatter.dateFormat = "yyyy-MM-dd"
        let courses = (try? JSONSerialization.jsonObject(with: JSONEncoder().encode(sched.courses))) ?? []
        let notes = (try? JSONSerialization.jsonObject(with: JSONEncoder().encode(NotesManager.shared.notes))) ?? []
        let exams: [[String: Any]] = ExamManager.shared.exams.map { ["id": $0.id, "title": $0.title, "examTimeMillis": $0.examTimeMillis,
            "durationMinutes": $0.durationMinutes, "location": $0.location, "seatNumber": $0.seatNumber, "examType": $0.examType, "note": $0.note] }
        return ["schedule": ["term_start": sched.termStart.map { formatter.string(from: $0) } ?? "", "sections": sched.sections, "courses": courses], "notes": notes, "exams": exams]
    }
    private func apply(_ path: String, _ payload: [String: Any]) throws -> [String: Any] {
        if path == "/api/sync/pull" { return snapshot() }
        if path == "/api/status" { return ["status": "ok"] }
        if path == "/api/clipboard" {
            guard let text = payload["text"] as? String else { throw SyncCrypto.Failure.invalid }
            let title = payload["title"] as? String ?? "来自配对设备"
            UIPasteboard.general.string = text; _ = NotesManager.shared.addNote(content: text, title: title)
            onTacticalDropReceived?(text, title); return ["status": "ok"]
        }
        guard path == "/api/sync/push" else { throw SyncCrypto.Failure.invalid }
        let mode = payload["mode"] ?? "merge"
        guard let mode = mode as? String, mode == "merge" || mode == "replace" else { throw SyncDataFailure.invalid }
        let replace = mode == "replace"
        if let value = payload["schedule"], !(value is [String: Any]) { throw SyncDataFailure.invalid }
        if let schedule = payload["schedule"] as? [String: Any] {
            if let value = schedule["courses"], !(value is [[String: Any]]) { throw SyncDataFailure.invalid }
            if let value = schedule["sections"], !(value is [String: String]) { throw SyncDataFailure.invalid }
            if let value = schedule["term_start"] {
                guard let text = value as? String else { throw SyncDataFailure.invalid }
                if !text.isEmpty {
                    let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.isLenient = false
                    guard let date = f.date(from: text), f.string(from: date) == text else { throw SyncDataFailure.invalid }
                }
            }
        }
        for key in ["exams", "notes"] {
            if let value = payload[key], !(value is [[String: Any]]) { throw SyncDataFailure.invalid }
        }
        for rows in [(payload["schedule"] as? [String: Any])?["courses"], payload["exams"], payload["notes"]] {
            if let rows = rows as? [[String: Any]] {
                var ids = Set<String>()
                for row in rows where row["id"] != nil {
                    guard let id = row["id"] as? String, !id.isEmpty, ids.insert(id).inserted else { throw SyncDataFailure.invalid }
                }
            }
        }
        var incomingCourses: [Course]?; var incomingExams: [ExamItem]?; var incomingNotes: [Note]?
        if let schedule = payload["schedule"] as? [String: Any], let rows = schedule["courses"] as? [[String: Any]] {
            incomingCourses = try rows.map { row in
                guard let name = row["name"] as? String, !name.isEmpty, let day = row["weekday"] as? Int, (1...7).contains(day),
                      row["sec_start"] is Int, row["sec_end"] is Int else { throw SyncDataFailure.invalid }
                return Course(id: row["id"] as? String ?? UUID().uuidString, name: name, weekday: day,
                    secStart: row["sec_start"] as? Int ?? 1, secEnd: row["sec_end"] as? Int ?? 1,
                    weekStart: row["week_start"] as? Int ?? 1, weekEnd: row["week_end"] as? Int ?? 20,
                    parity: row["parity"] as? String ?? "all", room: row["room"] as? String ?? "", teacher: row["teacher"] as? String ?? "",
                    campus: row["campus"] as? String ?? "", note: row["note"] as? String ?? "", customTime: row["custom_time"] as? String ?? "")
            }
        }
        if let rows = payload["exams"] as? [[String: Any]] {
            incomingExams = try rows.map { row in
                guard let title = row["title"] as? String, !title.isEmpty, let stamp = row["examTimeMillis"] as? NSNumber,
                      CFGetTypeID(stamp) != CFBooleanGetTypeID(), stamp.doubleValue.isFinite, stamp.doubleValue >= 0 else { throw SyncDataFailure.invalid }
                return ExamItem(id: row["id"] as? String ?? UUID().uuidString, title: title, examTimeMillis: stamp.int64Value,
                    durationMinutes: row["durationMinutes"] as? Int ?? 120, location: row["location"] as? String ?? "",
                    seatNumber: row["seatNumber"] as? String ?? "", examType: row["examType"] as? String ?? "闭卷", note: row["note"] as? String ?? "")
            }
        }
        if let rows = payload["notes"] {
            do { incomingNotes = try JSONDecoder().decode([Note].self, from: JSONSerialization.data(withJSONObject: rows)) }
            catch { throw SyncDataFailure.invalid }
        }
        let sched = ScheduleManager.shared
        if let courses = incomingCourses {
            if replace { sched.courses = courses } else {
                for course in courses {
                    let byId = sched.courses.firstIndex(where: { $0.id == course.id })
                    let index = byId ?? sched.courses.firstIndex(where: { $0.name == course.name && $0.weekday == course.weekday && $0.secStart == course.secStart && $0.secEnd == course.secEnd && $0.weekStart == course.weekStart && $0.weekEnd == course.weekEnd && $0.parity == course.parity && $0.customTime == course.customTime })
                    if let i = index { sched.courses[i] = course } else { sched.courses.append(course) }
                }
            }
        }
        if let settings = payload["schedule"] as? [String: Any] {
                if let sections = settings["sections"] as? [String: String] { sched.sections = sections }
                if let text = settings["term_start"] as? String { let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; sched.termStart = text.isEmpty ? nil : f.date(from: text) }
            sched.coursesVersion += 1; sched.save()
        }
        if let exams = incomingExams {
            if replace { ExamManager.shared.exams = exams } else {
                for exam in exams { if let i = ExamManager.shared.exams.firstIndex(where: { $0.id == exam.id }) { ExamManager.shared.exams[i] = exam } else { ExamManager.shared.exams.append(exam) } }
            }; ExamManager.shared.save()
        }
        if let notes = incomingNotes {
            if replace { NotesManager.shared.notes = notes } else {
                for note in notes { if let i = NotesManager.shared.notes.firstIndex(where: { $0.id == note.id }) { if NotesManager.shared.notes[i].updatedAt < note.updatedAt { NotesManager.shared.notes[i] = note } } else { NotesManager.shared.notes.append(note) } }
            }; NotesManager.shared.save()
        }
        return ["status": "ok", "result": ["schedule": incomingCourses?.count ?? 0, "exams": incomingExams?.count ?? 0, "notes": incomingNotes?.count ?? 0]]
    }
}
