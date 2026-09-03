import Combine
import StoreKit
import SwiftUI
import UIKit

@MainActor
final class SubscriptionStore: ObservableObject {
    nonisolated static let monthlyProductID = "com.thedailysportspage.app.monthly"

    @Published private(set) var product: Product?
    @Published private(set) var hasAccess = false
    @Published private(set) var isLoading = true
    @Published private(set) var isPurchasing = false
    @Published var errorMessage: String?

    private var updatesTask: Task<Void, Never>?

    init() {
        updatesTask = observeTransactions()
        Task { await prepare() }
    }

    deinit {
        updatesTask?.cancel()
    }

    func prepare() async {
        isLoading = true
        errorMessage = nil

        do {
            product = try await Product.products(for: [Self.monthlyProductID]).first
            if product == nil {
                errorMessage = "The subscription is temporarily unavailable. Please try again."
            }
        } catch {
            errorMessage = "The subscription could not be loaded. Please check your connection and try again."
        }

        await refreshEntitlement()
        isLoading = false
    }

    func purchase() async {
        guard let product else {
            await prepare()
            return
        }

        isPurchasing = true
        errorMessage = nil
        defer { isPurchasing = false }

        do {
            let result = try await product.purchase()
            switch result {
            case .success(let verification):
                let transaction = try verified(verification)
                await transaction.finish()
                await refreshEntitlement()
            case .pending:
                errorMessage = "Your purchase is pending approval. Access will unlock when Apple completes it."
            case .userCancelled:
                break
            @unknown default:
                errorMessage = "The purchase could not be completed. Please try again."
            }
        } catch {
            errorMessage = "The purchase could not be completed. Please try again."
        }
    }

    func restorePurchases() async {
        isPurchasing = true
        errorMessage = nil
        defer { isPurchasing = false }

        do {
            try await AppStore.sync()
            await refreshEntitlement()
            if !hasAccess {
                errorMessage = "No active subscription was found for this Apple Account."
            }
        } catch {
            errorMessage = "Purchases could not be restored. Please try again."
        }
    }

    func manageSubscriptions() async {
        guard let scene = UIApplication.shared.connectedScenes
            .compactMap({ $0 as? UIWindowScene })
            .first(where: { $0.activationState == .foregroundActive }) else {
            errorMessage = "Subscription settings are not available right now."
            return
        }

        do {
            try await AppStore.showManageSubscriptions(in: scene)
        } catch {
            errorMessage = "Subscription settings could not be opened."
        }
    }

    func refreshEntitlement() async {
        var entitled = false

        for await result in Transaction.currentEntitlements {
            guard case .verified(let transaction) = result,
                  transaction.productID == Self.monthlyProductID,
                  transaction.revocationDate == nil else {
                continue
            }
            entitled = true
            break
        }

        hasAccess = entitled
    }

    private func observeTransactions() -> Task<Void, Never> {
        Task { [weak self] in
            for await result in Transaction.updates {
                guard let self else { return }
                if case .verified(let transaction) = result {
                    await transaction.finish()
                    await self.refreshEntitlement()
                }
            }
        }
    }

    private func verified<T>(_ result: VerificationResult<T>) throws -> T {
        switch result {
        case .verified(let value):
            return value
        case .unverified:
            throw SubscriptionError.failedVerification
        }
    }
}

private enum SubscriptionError: Error {
    case failedVerification
}

struct SubscriptionView: View {
    @ObservedObject var store: SubscriptionStore

    private var offerLine: String {
        guard let product = store.product else { return "$2.99 per month" }
        if product.subscription?.introductoryOffer?.paymentMode == .freeTrial {
            return "7 days free, then \(product.displayPrice) per month"
        }
        return "\(product.displayPrice) per month"
    }

    private var purchaseLabel: String {
        if store.product?.subscription?.introductoryOffer?.paymentMode == .freeTrial {
            return "Start 7-Day Free Trial"
        }
        return "Subscribe"
    }

    var body: some View {
        ZStack {
            Color(red: 0.96, green: 0.94, blue: 0.88)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 24) {
                    VStack(spacing: 5) {
                        Text("The Daily Sports Page")
                            .font(.custom("Chomsky", size: 45))
                            .minimumScaleFactor(0.65)
                            .lineLimit(1)
                            .accessibilityAddTraits(.isHeader)
                        Rectangle()
                            .frame(height: 3)
                        Text("THE SPORTS SECTION, REIMAGINED")
                            .font(.caption.weight(.bold))
                            .tracking(1.4)
                    }
                    .foregroundStyle(.black)

                    VStack(alignment: .leading, spacing: 14) {
                        Text("Your front-row seat, every day.")
                            .font(.system(size: 29, weight: .black, design: .serif))
                        Text("Original stories and the complete sports page—built for fans who still love box scores with their morning coffee.")
                            .font(.system(.body, design: .serif))
                            .foregroundStyle(.secondary)

                        benefit("Daily baseball and weekly football editions")
                        benefit("Original headlines and game stories")
                        benefit("Box scores, standings, schedules, and league leaders")
                        benefit("Major-market editions and offline reading")
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)

                    VStack(spacing: 12) {
                        Text(offerLine)
                            .font(.headline)

                        Button {
                            Task { await store.purchase() }
                        } label: {
                            Group {
                                if store.isPurchasing {
                                    ProgressView().tint(.white)
                                } else {
                                    Text(purchaseLabel)
                                }
                            }
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .frame(height: 26)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.black)
                        .disabled(store.product == nil || store.isPurchasing)

                        if store.product == nil {
                            Button("Try Again") {
                                Task { await store.prepare() }
                            }
                            .disabled(store.isPurchasing)
                        }

                        if let errorMessage = store.errorMessage {
                            Text(errorMessage)
                                .font(.footnote)
                                .foregroundStyle(.red)
                                .multilineTextAlignment(.center)
                        }

                        Button("Restore Purchases") {
                            Task { await store.restorePurchases() }
                        }
                        .disabled(store.isPurchasing)

                        Button("Manage Subscription") {
                            Task { await store.manageSubscriptions() }
                        }
                    }

                    Text("Payment is charged to your Apple Account. The subscription renews automatically unless canceled at least 24 hours before the end of the current period. You can manage or cancel it in your App Store account settings.")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)

                    HStack(spacing: 18) {
                        Link("Terms of Use", destination: URL(string: "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/")!)
                        Link("Privacy Policy", destination: URL(string: "https://thedailysportspage.com/")!)
                    }
                    .font(.caption)
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 22)
                .frame(maxWidth: 620)
            }
        }
        .task {
            if store.product == nil {
                await store.prepare()
            }
        }
    }

    private func benefit(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 11) {
            Image(systemName: "checkmark.seal.fill")
                .foregroundStyle(.red)
            Text(text)
                .font(.subheadline.weight(.semibold))
        }
    }
}
