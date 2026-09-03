import UIKit
import UserNotifications
import Combine

@MainActor
final class AppRouteStore: ObservableObject {
    static let shared = AppRouteStore()

    @Published var destination = URL(string: "https://thedailysportspage.com/subscriber/current/")!

    func open(_ shortcutType: String) {
        switch shortcutType {
        case "com.thedailysportspage.app.baseball":
            destination = URL(string: "https://thedailysportspage.com/subscriber/current/")!
        case "com.thedailysportspage.app.football":
            destination = URL(string: "https://thedailysportspage.com/subscriber/current/football/")!
        case "com.thedailysportspage.app.leaders":
            destination = URL(string: "https://thedailysportspage.com/subscriber/current/#league-leaders")!
        default:
            break
        }
    }

    func openNotification(_ userInfo: [AnyHashable: Any]) {
        if let rawURL = userInfo["url"] as? String,
           let url = URL(string: rawURL),
           url.host == "thedailysportspage.com" || url.host == "www.thedailysportspage.com" {
            destination = url
        } else if let path = userInfo["path"] as? String,
                  path.hasPrefix("/"),
                  let url = URL(string: "https://thedailysportspage.com\(path)") {
            destination = url
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        center.requestAuthorization(options: [.alert, .badge, .sound]) { granted, _ in
            guard granted else { return }
            DispatchQueue.main.async {
                application.registerForRemoteNotifications()
            }
        }

        if let shortcut = launchOptions?[.shortcutItem] as? UIApplicationShortcutItem {
            Task { @MainActor in AppRouteStore.shared.open(shortcut.type) }
            return false
        }
        return true
    }

    func application(
        _ application: UIApplication,
        performActionFor shortcutItem: UIApplicationShortcutItem,
        completionHandler: @escaping (Bool) -> Void
    ) {
        Task { @MainActor in
            AppRouteStore.shared.open(shortcutItem.type)
            completionHandler(true)
        }
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        UserDefaults.standard.set(token, forKey: "apnsDeviceToken")
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .badge, .sound])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        Task { @MainActor in
            AppRouteStore.shared.openNotification(response.notification.request.content.userInfo)
            completionHandler()
        }
    }
}
