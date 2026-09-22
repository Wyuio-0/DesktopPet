import Foundation

public struct ReleaseInfo {
    public let tagName: String
    public let version: String
    public let releaseNotes: String
    public let htmlUrl: String
    public let hasUpdate: Bool
}

public class UpdateManager {
    public static let shared = UpdateManager()
    public static let currentVersion = "1.9.3"
    private static let repo = "Wyuio-0/DesktopPet"

    public func checkUpdate(completion: @escaping (Result<ReleaseInfo?, Error>) -> Void) {
        guard let url = URL(string: "https://api.github.com/repos/\(UpdateManager.repo)/releases/latest") else {
            return
        }

        var request = URLRequest(url: url)
        request.addValue("application/vnd.github.v3+json", forHTTPHeaderField: "Accept")
        request.timeoutInterval = 8

        URLSession.shared.dataTask(with: request) { data, _, err in
            if let err = err {
                DispatchQueue.main.async { completion(.failure(err)) }
                return
            }
            guard let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let tagName = json["tag_name"] as? String else {
                DispatchQueue.main.async { completion(.success(nil)) }
                return
            }

            let htmlUrl = json["html_url"] as? String ?? "https://github.com/\(UpdateManager.repo)/releases"
            let body = json["body"] as? String ?? ""
            let latestVer = tagName.trimmingCharacters(in: CharacterSet(charactersIn: "vV"))
            let hasUpdate = latestVer.compare(UpdateManager.currentVersion, options: .numeric) == .orderedDescending

            let info = ReleaseInfo(tagName: tagName, version: latestVer, releaseNotes: body, htmlUrl: htmlUrl, hasUpdate: hasUpdate)
            DispatchQueue.main.async {
                completion(.success(info))
            }
        }.resume()
    }
}
