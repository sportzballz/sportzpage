import Foundation

struct Market: Identifiable, Hashable {
    let id: String
    let name: String

    static let all: [Market] = [
        Market(id: "philadelphia", name: "Philadelphia"),
        Market(id: "boston", name: "Boston"),
        Market(id: "new-york", name: "New York"),
        Market(id: "los-angeles", name: "Los Angeles"),
        Market(id: "chicago", name: "Chicago"),
        Market(id: "dallas", name: "Dallas"),
    ]
}

enum Sport: String, CaseIterable, Identifiable {
    case baseball = "Baseball"
    case football = "Football"

    var id: String { rawValue }
}

struct Story: Codable, Hashable {
    let headline: String
    let deck: String?
    let byline: String?
    let paragraphs: [String]
    let sourceURL: URL?

    enum CodingKeys: String, CodingKey {
        case headline, deck, byline, paragraphs
        case sourceURL = "source_url"
        case url
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        headline = try values.decode(String.self, forKey: .headline)
        deck = try values.decodeIfPresent(String.self, forKey: .deck)
        byline = try values.decodeIfPresent(String.self, forKey: .byline)
        paragraphs = try values.decodeIfPresent([String].self, forKey: .paragraphs) ?? []
        sourceURL = try values.decodeIfPresent(URL.self, forKey: .sourceURL)
            ?? values.decodeIfPresent(URL.self, forKey: .url)
    }

    func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(headline, forKey: .headline)
        try values.encodeIfPresent(deck, forKey: .deck)
        try values.encodeIfPresent(byline, forKey: .byline)
        try values.encode(paragraphs, forKey: .paragraphs)
        try values.encodeIfPresent(sourceURL, forKey: .sourceURL)
    }
}

struct BaseballEdition: Codable {
    let edition: BaseballMetadata
    let leadStory: Story?
    let games: [BaseballGame]
    let secondaryStories: [Story]

    enum CodingKeys: String, CodingKey {
        case edition, games
        case leadStory = "lead_story"
        case secondaryStories = "secondary_stories"
    }
}

struct BaseballMetadata: Codable {
    let date: String
    let generatedAt: Date?
    let marketLabel: String

    enum CodingKeys: String, CodingKey {
        case date
        case generatedAt = "generated_at"
        case marketLabel = "market_label"
    }
}

struct BaseballGame: Codable, Identifiable {
    let gameID: Int
    let status: String
    let gameTimeET: String?
    let home: BaseballTeam
    let away: BaseballTeam

    var id: Int { gameID }

    enum CodingKeys: String, CodingKey {
        case gameID = "game_id"
        case status, home, away
        case gameTimeET = "game_time_et"
    }
}

struct BaseballTeam: Codable {
    let teamAbbr: String
    let teamName: String
    let runs: Int?

    enum CodingKeys: String, CodingKey {
        case teamAbbr = "team_abbr"
        case teamName = "team_name"
        case runs
    }
}

struct FootballEdition: Codable {
    let editionDate: String
    let generatedAt: Date?
    let marketLabel: String
    let lead: Story?
    let scoreboard: [FootballGame]
    let weekLabel: String?

    enum CodingKeys: String, CodingKey {
        case editionDate = "edition_date"
        case generatedAt = "generated_at"
        case marketLabel = "market_label"
        case lead, scoreboard
        case weekLabel = "week_label"
    }
}

struct FootballGame: Codable, Identifiable {
    let id: String
    let status: String
    let detail: String?
    let dateLabel: String?
    let time: String?
    let home: FootballTeam
    let away: FootballTeam

    enum CodingKeys: String, CodingKey {
        case id, status, detail, time, home, away
        case dateLabel = "date_label"
    }
}

struct FootballTeam: Codable {
    let abbr: String
    let name: String
    let score: String?
    let record: String?
    let winner: Bool?
}
