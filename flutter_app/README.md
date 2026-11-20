# Al-Mu'allim Flutter foundation

This is the new **Flutter mobile client**, kept in the existing ReadandMemorisetheQuran repository. The Streamlit application remains unchanged.

## Implemented

- Material 3 ivory/sage foundation, mobile navigation, RTL Arabic word layout
- Read / Memorise / Listen mode selector
- Qur'an word data from Quran.com API v4 with multi-page loading and sequential verse validation
- Tap-to-select word, flag for revision, memorisation reveal/hide
- Local persistence of selected surah, mode, and review flags
- Best-effort local file cache of fully fetched surahs; reopening previously loaded surahs can work offline. First-time downloads require internet.

## Run locally

Install Flutter and Android Studio or Xcode, then:

```sh
cd flutter_app
flutter create --platforms=android,ios .
flutter pub get
flutter run
```

Flutter's generated Android and iOS native folders are not committed yet; `flutter create` generates them. For iOS builds you need macOS and Xcode.

## Next

Validate cached content against trusted surah verse counts and add offline download management, exact phrase audio playback, word study, accessible memorisation review, and native speech inference. The Listen tab is currently a placeholder and **does not play audio**. This foundation does not claim real-time Tajweed assessment. Check Quran.com API terms and content attribution before public distribution.
