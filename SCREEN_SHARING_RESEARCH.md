# PBG Universal Challenge — Screen Sharing Without an App

## Executive conclusion
The exact requirement — **open a link on any phone, install nothing, then let a remote operator continuously view the phone screen while the customer navigates other websites/apps** — cannot be implemented as one universal browser-only experience across iPhone and Android.

A browser page can request screen capture where the platform/browser exposes the Screen Capture API, but the capability is permission-gated and browser-dependent. The web API requires HTTPS, a user interaction, and a fresh permission decision; support is not universal. [MDN — getDisplayMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia)

## iPhone / iOS
A normal web page cannot be treated as a general-purpose remote-support agent that silently captures the entire iPhone while the user switches among arbitrary apps. System-level screen capture is controlled by iOS and native frameworks. Apple documents ReplayKit/ScreenCaptureKit for app-based capture and requires user permission for screen recording. [Apple — ScreenCaptureKit](https://developer.apple.com/documentation/ScreenCaptureKit)

Therefore, a zero-install web link is not a reliable way to obtain continuous whole-device screen sharing across other iOS apps.

**Practical alternative:** use a native iOS app (or a remote-support product with an iOS app/extension) when whole-device sharing is a hard requirement. If zero installation is mandatory, limit the experience to what the browser can expose and design the workflow around the customer's current browser page rather than promising arbitrary app-level visibility.

## Android
Android provides `MediaProjection` for screen capture, with an explicit OS permission flow. Android documentation states that the OS asks the user for permission before granting access. Android 14+ requires user consent for each capture session. [Android — MediaProjection](https://developer.android.com/media/platform/av-capture)

Android 14 QPR2+ also supports sharing a single app window, which improves privacy but means that the sharing scope is still controlled by the user/system. [Android — app screen sharing](https://developer.android.com/about/versions/14/features/app-screen-sharing)

**Practical alternative:** a native Android app can provide a robust screen-sharing flow. A browser-only solution should not promise unrestricted cross-app screen sharing on all Android devices/browsers.

## Desktop
Desktop browsers have a much stronger fit for the requested zero-install model. `navigator.mediaDevices.getDisplayMedia()` lets a user select a display, window, or tab and returns a media stream that can be transmitted through WebRTC. It requires HTTPS and explicit user interaction/permission. [MDN — getDisplayMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia)

**Practical solution:** a web support page + WebRTC session. The customer opens a secure link, clicks “Share screen,” chooses the screen/window/tab, and the support agent receives the stream. The permission is controlled by the browser/OS rather than silently granted to the website.

## Recommended product architecture
If the business requirement is “support customers on any device,” I would use a **progressive capability model**:

1. **Universal web entry point:** HTTPS support link, no account/app installation required.
2. **Desktop:** browser-based WebRTC screen sharing using `getDisplayMedia()`.
3. **Android:** detect capability and offer a native Android path when full-device sharing is required; use browser-only capture only where supported and acceptable.
4. **iPhone:** offer a native iOS/remote-support path for whole-device sharing. If installation cannot be accepted, provide a browser-guided workflow with explicit limitations.
5. **Security:** short-lived session token, explicit consent, visible sharing state, session expiry, audit logging, and no assumption that permission persists.

This is preferable to pretending a single browser link can bypass OS privacy boundaries.

## Sources
- [MDN — MediaDevices.getDisplayMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia)
- [MDN — Using the Screen Capture API](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Capture_API/Using_Screen_Capture)
- [Apple — ScreenCaptureKit](https://developer.apple.com/documentation/ScreenCaptureKit)
- [Android Developers — MediaProjection](https://developer.android.com/media/platform/av-capture)
- [Android Developers — App screen sharing](https://developer.android.com/about/versions/14/features/app-screen-sharing)
