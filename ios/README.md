# The Daily Sports Page for iOS

This SwiftUI app reads the existing live market-edition JSON feeds. Daily content updates do not require an App Store release.

## Open and run

1. Install the current Xcode from the Mac App Store.
2. Open `TDSPApp.xcodeproj`.
3. Select the `TDSPApp` target, then choose your Apple Developer team under Signing & Capabilities.
4. Run on an iPhone or iPad simulator.

The default bundle identifier is `com.thedailysportspage.app`. Change it before App Store submission if that identifier is unavailable in your developer account.

## First-release behavior

- Uses StoreKit 2 to require an active monthly subscription in the iOS app.
- Offers a 7-day introductory trial when configured in App Store Connect.
- Supports purchase restoration and Apple subscription management.
- Displays the live baseball and football editions for subscribers.
- Remembers the selected market with `AppStorage`.
- Caches the latest successfully downloaded editions for offline reading.
- Supports pull-to-refresh, Dynamic Type, VoiceOver labels, and native sharing.
- Does not embed the website or include external tipping links.

The monthly StoreKit product identifier is `com.thedailysportspage.app.monthly`.
Create a one-month auto-renewable subscription with that exact identifier in the
`The Daily Sports Page` subscription group. Configure its U.S. price at $2.99
and add a seven-day free-trial introductory offer before distributing Build 9.

The app currently declares no tracking or collected data in `PrivacyInfo.xcprivacy`. Revisit both the manifest and App Store privacy answers before adding accounts or native feedback submission.
