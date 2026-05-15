import Foundation

enum MacVpnImportKind: Equatable {
    case upstreamAdapter
    case encryptedProfile

    init?(url: URL) {
        switch url.lastPathComponent {
        case "upstream.json":
            self = .upstreamAdapter
        case "profile.json.enc":
            self = .encryptedProfile
        default:
            return nil
        }
    }

    var importCommand: String {
        switch self {
        case .upstreamAdapter:
            return "import-upstream"
        case .encryptedProfile:
            return "import-encrypted-profile"
        }
    }

    var resultCommandName: String {
        switch self {
        case .upstreamAdapter:
            return "import-upstream"
        case .encryptedProfile:
            return "import-encrypted-profile"
        }
    }

    var shouldRenderAndValidate: Bool {
        switch self {
        case .upstreamAdapter:
            return true
        case .encryptedProfile:
            return false
        }
    }
}
