import SwiftUI
import WebKit

struct RootView: View {
    @StateObject private var routes = AppRouteStore.shared
    @ObservedObject var subscriptionStore: SubscriptionStore

    var body: some View {
        Group {
            if subscriptionStore.isLoading {
                ZStack {
                    Color(red: 0.96, green: 0.94, blue: 0.88).ignoresSafeArea()
                    ProgressView("Checking subscription…")
                        .font(.system(.body, design: .serif))
                }
            } else if subscriptionStore.hasAccess,
                      let signedTransaction = subscriptionStore.signedTransaction {
                ZStack(alignment: .bottomTrailing) {
                    DailySportsPageWebView(
                        destination: routes.destination,
                        signedTransaction: signedTransaction
                    )

                    Menu {
                        Button("Manage Subscription") {
                            Task { await subscriptionStore.manageSubscriptions() }
                        }
                        Button("Restore Purchases") {
                            Task { await subscriptionStore.restorePurchases() }
                        }
                    } label: {
                        Image(systemName: "person.crop.circle")
                            .font(.title2)
                            .foregroundStyle(.black)
                            .padding(10)
                            .background(.ultraThinMaterial, in: Circle())
                            .shadow(radius: 3, y: 1)
                    }
                    .padding(14)
                    .accessibilityLabel("Subscription settings")
                }
            } else {
                SubscriptionView(store: subscriptionStore)
            }
        }
    }
}

private struct DailySportsPageWebView: UIViewRepresentable {
    let destination: URL
    let signedTransaction: String

    private static let accessURL = URL(
        string: "https://thedailysportspage.com/api/access/apple"
    )!

    func makeCoordinator() -> Coordinator {
        Coordinator(homeURL: destination)
    }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .automatic

        let refreshControl = UIRefreshControl()
        refreshControl.addTarget(
            context.coordinator,
            action: #selector(Coordinator.refresh(_:)),
            for: .valueChanged
        )
        webView.scrollView.refreshControl = refreshControl
        context.coordinator.webView = webView

        context.coordinator.authorize(
            webView,
            signedTransaction: signedTransaction
        )
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        context.coordinator.homeURL = destination
        guard webView.url?.absoluteString != destination.absoluteString else { return }
        guard context.coordinator.isAuthorized else { return }
        webView.load(URLRequest(url: destination, cachePolicy: .reloadRevalidatingCacheData))
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        weak var webView: WKWebView?
        var homeURL: URL
        private(set) var isAuthorized = false

        init(homeURL: URL) {
            self.homeURL = homeURL
        }

        func authorize(_ webView: WKWebView, signedTransaction: String) {
            var request = URLRequest(
                url: DailySportsPageWebView.accessURL,
                cachePolicy: .reloadIgnoringLocalCacheData
            )
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            var destination = homeURL.path
            if let fragment = homeURL.fragment {
                destination += "#\(fragment)"
            }
            request.httpBody = try? JSONSerialization.data(withJSONObject: [
                "signedTransaction": signedTransaction,
                "destination": destination
            ])
            webView.load(request)
        }

        @objc func refresh(_ sender: UIRefreshControl) {
            if webView?.url == nil {
                webView?.load(URLRequest(url: homeURL, cachePolicy: .reloadIgnoringLocalCacheData))
            } else {
                webView?.reloadFromOrigin()
            }
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation?) {
            webView.scrollView.refreshControl?.endRefreshing()
            if webView.url?.path == DailySportsPageWebView.accessURL.path {
                isAuthorized = true
                webView.load(
                    URLRequest(url: homeURL, cachePolicy: .reloadIgnoringLocalCacheData)
                )
            }
        }

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationResponse: WKNavigationResponse,
            decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void
        ) {
            if navigationResponse.response.url?.path == DailySportsPageWebView.accessURL.path,
               let response = navigationResponse.response as? HTTPURLResponse,
               !(200...299).contains(response.statusCode) {
                isAuthorized = false
            }
            decisionHandler(.allow)
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation?, withError error: Error) {
            webView.scrollView.refreshControl?.endRefreshing()
        }

        func webView(
            _ webView: WKWebView,
            didFailProvisionalNavigation navigation: WKNavigation?,
            withError error: Error
        ) {
            webView.scrollView.refreshControl?.endRefreshing()
        }

        func webView(
            _ webView: WKWebView,
            createWebViewWith configuration: WKWebViewConfiguration,
            for navigationAction: WKNavigationAction,
            windowFeatures: WKWindowFeatures
        ) -> WKWebView? {
            if let url = navigationAction.request.url {
                webView.load(URLRequest(url: url))
            }
            return nil
        }

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
        ) {
            guard let url = navigationAction.request.url else {
                decisionHandler(.cancel)
                return
            }

            if (url.scheme == "http" || url.scheme == "https"),
               url.host == "thedailysportspage.com" || url.host == "www.thedailysportspage.com" {
                if url.path.hasPrefix("/subscriber/") {
                    isAuthorized = true
                }
                decisionHandler(.allow)
            } else if url.scheme != "http" && url.scheme != "https" {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
            } else {
                decisionHandler(.cancel)
            }
        }
    }
}
