import XCTest
@testable import TDSPApp

final class EditionDecodingTests: XCTestCase {
    func testBaseballEditionDecodesCurrentContract() throws {
        let data = Data(
            """
            {
              "edition": {
                "date": "2026-09-01",
                "generated_at": "2026-09-01T10:17:44.190677Z",
                "market_label": "Dallas"
              },
              "lead_story": {
                "headline": "Rangers win",
                "deck": "A close game.",
                "paragraphs": ["First.", "Second."]
              },
              "games": [{
                "game_id": 1,
                "status": "final",
                "game_time_et": "8:05 PM ET",
                "away": {"team_abbr": "TEX", "team_name": "Texas Rangers", "runs": 4},
                "home": {"team_abbr": "SEA", "team_name": "Seattle Mariners", "runs": 3}
              }],
              "secondary_stories": []
            }
            """.utf8
        )

        let edition = try JSONDecoder.tdsp.decode(BaseballEdition.self, from: data)

        XCTAssertEqual(edition.edition.marketLabel, "Dallas")
        XCTAssertEqual(edition.leadStory?.paragraphs.count, 2)
        XCTAssertEqual(edition.games.first?.away.teamAbbr, "TEX")
    }

    func testFootballEditionDecodesCurrentContract() throws {
        let data = Data(
            """
            {
              "edition_date": "2026-09-01",
              "generated_at": "2026-09-01T10:17:44Z",
              "market_label": "Dallas",
              "week_label": "Week 1",
              "lead": {
                "headline": "Cowboys win",
                "paragraphs": ["First.", "Second.", "Third."]
              },
              "scoreboard": [{
                "id": "401",
                "status": "Final",
                "detail": "Final",
                "date_label": "Sun, Sep 6",
                "time": "8:20 PM ET",
                "away": {"abbr": "DAL", "name": "Dallas Cowboys", "score": "24", "record": "1-0", "winner": true},
                "home": {"abbr": "NYG", "name": "New York Giants", "score": "17", "record": "0-1", "winner": false}
              }]
            }
            """.utf8
        )

        let edition = try JSONDecoder.tdsp.decode(FootballEdition.self, from: data)

        XCTAssertEqual(edition.weekLabel, "Week 1")
        XCTAssertEqual(edition.scoreboard.first?.away.abbr, "DAL")
        XCTAssertEqual(edition.lead?.headline, "Cowboys win")
    }
}
