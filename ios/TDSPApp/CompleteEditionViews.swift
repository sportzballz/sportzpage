import SwiftUI

struct CompleteEditionSections: View {
    let games: [JSONValue]
    let sections: [String: JSONValue]

    private let preferredOrder = [
        "game_recaps", "standings", "league_leaders", "team_game_leaders",
        "team_season_leaders", "news", "around_the_league", "injuries",
        "transactions", "historical_items", "week_detail", "season_label",
        "leaders_season_label", "canonical_path", "generation_metadata",
    ]

    var body: some View {
        VStack(spacing: 20) {
            if !games.isEmpty {
                NewspaperSection(title: "Complete Box Scores") {
                    JSONCollection(value: .array(games), depth: 0)
                }
            }

            ForEach(orderedSections, id: \.0) { name, value in
                if value.hasVisibleContent {
                    NewspaperSection(title: name.displayLabel) {
                        JSONCollection(value: value, depth: 0)
                    }
                }
            }
        }
    }

    private var orderedSections: [(String, JSONValue)] {
        sections.sorted { left, right in
            let leftIndex = preferredOrder.firstIndex(of: left.key) ?? preferredOrder.count
            let rightIndex = preferredOrder.firstIndex(of: right.key) ?? preferredOrder.count
            return leftIndex == rightIndex ? left.key < right.key : leftIndex < rightIndex
        }
    }
}

private struct NewspaperSection<Content: View>: View {
    let title: String
    let content: Content

    init(title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.system(.title2, design: .serif, weight: .bold))
            Rectangle().frame(height: 2)
            content
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 4))
    }
}

private struct JSONCollection: View {
    let value: JSONValue
    let depth: Int

    var body: some View {
        switch value {
        case .array(let values):
            VStack(alignment: .leading, spacing: 14) {
                ForEach(Array(values.enumerated()), id: \.offset) { index, item in
                    JSONCollection(value: item, depth: depth + 1)
                    if index < values.count - 1 { Divider() }
                }
            }
        case .object(let object):
            JSONRecord(object: object, depth: depth)
        case .string(let string):
            Text(string).fixedSize(horizontal: false, vertical: true)
        case .number(let number):
            Text(number.formattedForSports)
        case .bool(let value):
            Text(value ? "Yes" : "No")
        case .null:
            EmptyView()
        }
    }
}

private struct JSONRecord: View {
    let object: [String: JSONValue]
    let depth: Int

    private let titleKeys = ["headline", "label", "name", "title", "team_name", "player_name"]
    private let hiddenKeys = Set(["player_id", "team_id", "espn_game_id", "recap_anchor", "source_url", "canonical_path"])

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let title {
                Text(title)
                    .font(depth <= 1 ? .headline : .subheadline.weight(.bold))
                    .fixedSize(horizontal: false, vertical: true)
            }

            ForEach(scalarEntries, id: \.0) { key, value in
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(key.displayLabel)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                        .frame(minWidth: 54, alignment: .leading)
                    Text(value.scalarText ?? "")
                        .font(.subheadline.monospacedDigit())
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
            }

            ForEach(complexEntries, id: \.0) { key, value in
                VStack(alignment: .leading, spacing: 8) {
                    Text(key.displayLabel)
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(.secondary)
                    JSONCollection(value: value, depth: depth + 1)
                }
                .padding(.top, 4)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var title: String? {
        for key in titleKeys {
            if let text = object[key]?.scalarText, !text.isEmpty { return text }
        }
        if let away = object["away"]?.objectValue,
           let home = object["home"]?.objectValue,
           let awayName = away["team_name"]?.scalarText ?? away["name"]?.scalarText,
           let homeName = home["team_name"]?.scalarText ?? home["name"]?.scalarText {
            return "\(awayName) at \(homeName)"
        }
        return nil
    }

    private var visibleEntries: [(String, JSONValue)] {
        object.filter { key, value in
            !titleKeys.contains(key) && !hiddenKeys.contains(key) && value.hasVisibleContent
        }.sorted { $0.key.displayPriority < $1.key.displayPriority }
    }

    private var scalarEntries: [(String, JSONValue)] {
        visibleEntries.filter { $0.1.scalarText != nil }
    }

    private var complexEntries: [(String, JSONValue)] {
        visibleEntries.filter { $0.1.scalarText == nil }
    }
}

private extension JSONValue {
    var objectValue: [String: JSONValue]? {
        guard case .object(let object) = self else { return nil }
        return object
    }

    var scalarText: String? {
        switch self {
        case .string(let value): return value
        case .number(let value): return value.formattedForSports
        case .bool(let value): return value ? "Yes" : "No"
        case .null, .object, .array: return nil
        }
    }

    var hasVisibleContent: Bool {
        switch self {
        case .null: return false
        case .string(let value): return !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        case .array(let values): return values.contains(where: \.hasVisibleContent)
        case .object(let object): return object.values.contains(where: \.hasVisibleContent)
        case .number, .bool: return true
        }
    }
}

private extension Double {
    var formattedForSports: String {
        rounded() == self ? String(Int(self)) : formatted(.number.precision(.fractionLength(0...3)))
    }
}

private extension String {
    var displayLabel: String {
        replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { word in
                let upper = word.uppercased()
                return ["AL", "NL", "NFL", "MLB", "RBI", "ERA", "SO", "IP", "BB"].contains(upper)
                    ? upper
                    : word.prefix(1).uppercased() + word.dropFirst()
            }
            .joined(separator: " ")
    }

    var displayPriority: String {
        let priorities = ["rank", "team_abbr", "abbr", "position", "value", "wins", "losses", "ties", "pct", "score", "runs", "hits", "errors", "status", "date_label", "time"]
        let index = priorities.firstIndex(of: self) ?? priorities.count
        return String(format: "%02d-%@", index, self)
    }
}
