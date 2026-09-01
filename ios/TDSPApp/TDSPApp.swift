import SwiftUI

@main
struct TDSPApp: App {
    @StateObject private var store = EditionStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(store)
        }
    }
}
