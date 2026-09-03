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

indirect enum JSONValue: Codable, Hashable {
    case object([String: JSONValue])
    case array([JSONValue])
    case string(String)
    case number(Double)
    case bool(Bool)
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null }
        else if let value = try? container.decode(Bool.self) { self = .bool(value) }
        else if let value = try? container.decode(Double.self) { self = .number(value) }
        else if let value = try? container.decode(String.self) { self = .string(value) }
        else if let value = try? container.decode([JSONValue].self) { self = .array(value) }
        else { self = .object(try container.decode([String: JSONValue].self)) }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}

struct AnyCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int? = nil

    init?(stringValue: String) { self.stringValue = stringValue }
    init?(intValue: Int) { return nil }
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
    let completeGames: [JSONValue]
    let supplementalSections: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case edition, games
        case leadStory = "lead_story"
        case secondaryStories = "secondary_stories"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        edition = try values.decode(BaseballMetadata.self, forKey: .edition)
        leadStory = try values.decodeIfPresent(Story.self, forKey: .leadStory)
        games = try values.decodeIfPresent([BaseballGame].self, forKey: .games) ?? []
        secondaryStories = try values.decodeIfPresent([Story].self, forKey: .secondaryStories) ?? []
        completeGames = try values.decodeIfPresent([JSONValue].self, forKey: .games) ?? []

        let dynamic = try decoder.container(keyedBy: AnyCodingKey.self)
        let known = Set(CodingKeys.allCases.map(\.rawValue))
        supplementalSections = try Dictionary(uniqueKeysWithValues: dynamic.allKeys.compactMap { key in
            guard !known.contains(key.stringValue) else { return nil }
            return (key.stringValue, try dynamic.decode(JSONValue.self, forKey: key))
        })
    }

    func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(edition, forKey: .edition)
        try values.encodeIfPresent(leadStory, forKey: .leadStory)
        try values.encode(completeGames, forKey: .games)
        try values.encode(secondaryStories, forKey: .secondaryStories)
        var dynamic = encoder.container(keyedBy: AnyCodingKey.self)
        for (name, value) in supplementalSections {
            try dynamic.encode(value, forKey: AnyCodingKey(stringValue: name)!)
        }
    }
}

extension BaseballEdition.CodingKeys: CaseIterable {}

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
    let completeScoreboard: [JSONValue]
    let supplementalSections: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case editionDate = "edition_date"
        case generatedAt = "generated_at"
        case marketLabel = "market_label"
        case lead, scoreboard
        case weekLabel = "week_label"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        editionDate = try values.decode(String.self, forKey: .editionDate)
        generatedAt = try values.decodeIfPresent(Date.self, forKey: .generatedAt)
        marketLabel = try values.decode(String.self, forKey: .marketLabel)
        lead = try values.decodeIfPresent(Story.self, forKey: .lead)
        scoreboard = try values.decodeIfPresent([FootballGame].self, forKey: .scoreboard) ?? []
        weekLabel = try values.decodeIfPresent(String.self, forKey: .weekLabel)
        completeScoreboard = try values.decodeIfPresent([JSONValue].self, forKey: .scoreboard) ?? []

        let dynamic = try decoder.container(keyedBy: AnyCodingKey.self)
        let known = Set(CodingKeys.allCases.map(\.rawValue))
        supplementalSections = try Dictionary(uniqueKeysWithValues: dynamic.allKeys.compactMap { key in
            guard !known.contains(key.stringValue) else { return nil }
            return (key.stringValue, try dynamic.decode(JSONValue.self, forKey: key))
        })
    }

    func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(editionDate, forKey: .editionDate)
        try values.encodeIfPresent(generatedAt, forKey: .generatedAt)
        try values.encode(marketLabel, forKey: .marketLabel)
        try values.encodeIfPresent(lead, forKey: .lead)
        try values.encode(completeScoreboard, forKey: .scoreboard)
        try values.encodeIfPresent(weekLabel, forKey: .weekLabel)
        var dynamic = encoder.container(keyedBy: AnyCodingKey.self)
        for (name, value) in supplementalSections {
            try dynamic.encode(value, forKey: AnyCodingKey(stringValue: name)!)
        }
    }
}

extension FootballEdition.CodingKeys: CaseIterable {}

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
