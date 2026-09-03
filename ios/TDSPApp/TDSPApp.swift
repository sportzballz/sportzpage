import SwiftUI

@main
struct TDSPApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var subscriptionStore = SubscriptionStore()

    var body: some Scene {
        WindowGroup {
            RootView(subscriptionStore: subscriptionStore)
        }
    }
}
