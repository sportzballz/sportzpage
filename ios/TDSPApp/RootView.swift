import SwiftUI

struct RootView: View {
    @EnvironmentObject private var store: EditionStore
    @AppStorage("selectedMarket") private var selectedMarket = "philadelphia"
    @State private var sport = Sport.baseball

    private var market: Market {
        Market.all.first { $0.id == selectedMarket } ?? Market.all[0]
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 20) {
                    masthead

                    if let message = store.errorMessage {
                        Label(message, systemImage: "wifi.slash")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .padding()
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
                    }

                    if sport == .baseball, let edition = store.baseball {
                        BaseballEditionView(edition: edition)
                    } else if sport == .football, let edition = store.football {
                        FootballEditionView(edition: edition)
                    } else if store.isRefreshing {
                        ProgressView("Fetching today’s edition…")
                            .padding(.vertical, 80)
                    } else {
                        ContentUnavailableView(
                            "Edition Unavailable",
                            systemImage: "newspaper",
                            description: Text("Pull down to try loading it again.")
                        )
                    }

                    Link(destination: URL(string: "https://thedailysportspage.com/#feedback")!) {
                        Label("Letter to the Editor", systemImage: "envelope")
                    }
                    .buttonStyle(.bordered)
                }
                .frame(maxWidth: 760)
                .padding()
                .frame(maxWidth: .infinity)
            }
            .background(Color(.systemGroupedBackground))
            .refreshable { await store.load(market: selectedMarket) }
            .navigationTitle("The Daily Sports Page")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Menu {
                        Picker("Local edition", selection: $selectedMarket) {
                            ForEach(Market.all) { market in
                                Text(market.name).tag(market.id)
                            }
                        }
                    } label: {
                        Label(market.name, systemImage: "mappin.and.ellipse")
                    }
                    .accessibilityLabel("Local edition: \(market.name)")
                }
            }
            .task(id: selectedMarket) { await store.load(market: selectedMarket) }
        }
    }

    private var masthead: some View {
        VStack(spacing: 12) {
            Text(market.name.uppercased())
                .font(.caption.weight(.bold))
                .tracking(1.5)
                .foregroundStyle(.secondary)

            Picker("Sport", selection: $sport) {
                ForEach(Sport.allCases) { sport in
                    Text(sport.rawValue).tag(sport)
                }
            }
            .pickerStyle(.segmented)
        }
    }
}

private struct BaseballEditionView: View {
    let edition: BaseballEdition

    var body: some View {
        VStack(spacing: 20) {
            if let story = edition.leadStory {
                StoryCard(story: story, editionDate: edition.edition.date)
            }
            ScoreSection(title: "Scoreboard") {
                ForEach(edition.games) { game in
                    BaseballScoreRow(game: game)
                    if game.id != edition.games.last?.id { Divider() }
                }
            }
            ForEach(edition.secondaryStories, id: \.self) { story in
                StoryCard(story: story, editionDate: nil)
            }
        }
    }
}

private struct FootballEditionView: View {
    let edition: FootballEdition

    var body: some View {
        VStack(spacing: 20) {
            if let story = edition.lead {
                StoryCard(story: story, editionDate: edition.editionDate)
            }
            ScoreSection(title: edition.weekLabel ?? "Scoreboard") {
                ForEach(edition.scoreboard) { game in
                    FootballScoreRow(game: game)
                    if game.id != edition.scoreboard.last?.id { Divider() }
                }
            }
        }
    }
}

private struct StoryCard: View {
    let story: Story
    let editionDate: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let editionDate {
                Text(editionDate)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
            Text(story.headline)
                .font(.system(.title, design: .serif, weight: .bold))
                .fixedSize(horizontal: false, vertical: true)
            if let deck = story.deck {
                Text(deck)
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }
            if let byline = story.byline {
                Text(byline.uppercased())
                    .font(.caption.weight(.bold))
                    .tracking(0.7)
            }
            ForEach(Array(story.paragraphs.enumerated()), id: \.offset) { _, paragraph in
                Text(paragraph)
                    .font(.system(.body, design: .serif))
                    .lineSpacing(4)
            }
            ShareLink(item: shareText) {
                Label("Share story", systemImage: "square.and.arrow.up")
            }
            .buttonStyle(.bordered)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
    }

    private var shareText: String {
        "\(story.headline) — The Daily Sports Page\nhttps://thedailysportspage.com"
    }
}

private struct ScoreSection<Content: View>: View {
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
            content
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
    }
}

private struct BaseballScoreRow: View {
    let game: BaseballGame

    var body: some View {
        VStack(spacing: 8) {
            team(game.away.teamName, abbreviation: game.away.teamAbbr, score: game.away.runs)
            team(game.home.teamName, abbreviation: game.home.teamAbbr, score: game.home.runs)
            Text(game.status.capitalized == "Final" ? "Final" : (game.gameTimeET ?? game.status.capitalized))
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.vertical, 4)
    }

    private func team(_ name: String, abbreviation: String, score: Int?) -> some View {
        HStack {
            Text(abbreviation).font(.caption.monospaced().weight(.bold)).frame(width: 36, alignment: .leading)
            Text(name).lineLimit(1)
            Spacer()
            if let score { Text(score, format: .number).font(.headline.monospacedDigit()) }
        }
    }
}

private struct FootballScoreRow: View {
    let game: FootballGame

    var body: some View {
        VStack(spacing: 8) {
            team(game.away)
            team(game.home)
            Text(game.detail ?? game.time ?? game.status)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.vertical, 4)
    }

    private func team(_ team: FootballTeam) -> some View {
        HStack {
            Text(team.abbr).font(.caption.monospaced().weight(.bold)).frame(width: 36, alignment: .leading)
            VStack(alignment: .leading, spacing: 1) {
                Text(team.name).lineLimit(1)
                if let record = team.record { Text(record).font(.caption2).foregroundStyle(.secondary) }
            }
            Spacer()
            if let score = team.score { Text(score).font(.headline.monospacedDigit()) }
        }
        .fontWeight(team.winner == true ? .bold : .regular)
    }
}
