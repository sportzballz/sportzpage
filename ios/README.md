# The Daily Sports Page for iOS

This SwiftUI app reads the existing live market-edition JSON feeds. Daily content updates do not require an App Store release.

## Open and run

1. Install the current Xcode from the Mac App Store.
2. Open `TDSPApp.xcodeproj`.
3. Select the `TDSPApp` target, then choose your Apple Developer team under Signing & Capabilities.
4. Run on an iPhone or iPad simulator.

The default bundle identifier is `com.thedailysportspage.app`. Change it before App Store submission if that identifier is unavailable in your developer account.

## First-release behavior

- Downloads baseball and football editions for the selected market.
- Remembers the selected market with `AppStorage`.
- Caches the latest successfully downloaded editions for offline reading.
- Supports pull-to-refresh, Dynamic Type, VoiceOver labels, and native sharing.
- Does not embed the website or include external tipping links.

The app currently declares no tracking or collected data in `PrivacyInfo.xcprivacy`. Revisit both the manifest and App Store privacy answers before adding analytics, notifications, accounts, or native feedback submission.
