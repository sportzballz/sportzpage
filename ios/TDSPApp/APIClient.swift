import Foundation

struct APIClient {
    private let baseURL = URL(string: "https://thedailysportspage.com")!
    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func baseball(market: String) async throws -> BaseballEdition {
        try await fetch(path: "/editions/\(market)/edition.json")
    }

    func football(market: String) async throws -> FootballEdition {
        try await fetch(path: "/editions/\(market)/football/edition.json")
    }

    private func fetch<T: Decodable>(path: String) async throws -> T {
        let url = baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadRevalidatingCacheData
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }

        return try JSONDecoder.tdsp.decode(T.self, from: data)
    }
}

extension JSONDecoder {
    static var tdsp: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)
            let normalized: String
            if let separator = value.firstIndex(of: " ") {
                normalized = value.replacingCharacters(in: separator...separator, with: "T")
            } else {
                normalized = value
            }
            let fractional = ISO8601DateFormatter()
            fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = fractional.date(from: normalized) {
                return date
            }
            let standard = ISO8601DateFormatter()
            if let date = standard.date(from: normalized) {
                return date
            }
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Invalid ISO-8601 date: \(value)"
            )
        }
        return decoder
    }
}

extension JSONEncoder {
    static var tdsp: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }
}
