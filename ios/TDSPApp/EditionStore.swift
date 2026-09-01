import Combine
import Foundation

@MainActor
final class EditionStore: ObservableObject {
    @Published private(set) var baseball: BaseballEdition?
    @Published private(set) var football: FootballEdition?
    @Published private(set) var isRefreshing = false
    @Published private(set) var isShowingCachedEdition = false
    @Published private(set) var errorMessage: String?

    private let client: APIClient
    private let cache: EditionCache

    init(client: APIClient = APIClient(), cache: EditionCache = EditionCache()) {
        self.client = client
        self.cache = cache
    }

    func load(market: String) async {
        isRefreshing = true
        errorMessage = nil
        defer { isRefreshing = false }

        do {
            async let baseballRequest = client.baseball(market: market)
            async let footballRequest = client.football(market: market)
            let editions = try await (baseballRequest, footballRequest)
            baseball = editions.0
            football = editions.1
            isShowingCachedEdition = false
            try? cache.save(editions.0, named: "\(market)-baseball")
            try? cache.save(editions.1, named: "\(market)-football")
        } catch {
            baseball = cache.load(BaseballEdition.self, named: "\(market)-baseball")
            football = cache.load(FootballEdition.self, named: "\(market)-football")
            isShowingCachedEdition = baseball != nil || football != nil
            errorMessage = isShowingCachedEdition
                ? "You’re offline. Showing the most recently downloaded edition."
                : "The latest edition could not be loaded. Pull down to try again."
        }
    }
}

struct EditionCache {
    private let directory: URL

    init(fileManager: FileManager = .default) {
        directory = fileManager.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appending(path: "DailySportsPage", directoryHint: .isDirectory)
        try? fileManager.createDirectory(at: directory, withIntermediateDirectories: true)
    }

    func save<T: Encodable>(_ value: T, named name: String) throws {
        try JSONEncoder.tdsp.encode(value).write(
            to: directory.appending(path: "\(name).json"),
            options: .atomic
        )
    }

    func load<T: Decodable>(_ type: T.Type, named name: String) -> T? {
        guard let data = try? Data(contentsOf: directory.appending(path: "\(name).json")) else {
            return nil
        }
        return try? JSONDecoder.tdsp.decode(type, from: data)
    }
}
