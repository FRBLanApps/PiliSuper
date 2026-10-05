<div align="center">
    <img width="200" height="200" src="assets/images/logo/logo.png" alt="PiliSuper logo">
    <h1>PiliSuper</h1>
</div>

<div align="center">

[中文](README.md) | English

![GitHub Repo stars](https://img.shields.io/github/stars/FRBLanApps/PiliSuper?style=flat&logo=Github)
![GitHub repo size](https://img.shields.io/github/repo-size/FRBLanApps/PiliSuper?style=flat&logo=Github)
![GitHub License](https://img.shields.io/github/license/FRBLanApps/PiliSuper?style=flat&logo=GNU&link=https%3A%2F%2Fwww.gnu.org%2Flicenses%2Fgpl-3.0.en.html)
![GitHub all releases](https://img.shields.io/github/downloads/FRBLanApps/PiliSuper/total?style=flat&logo=Github)

</div>

<div align="center">
    <p>A third-party Bilibili client built with Flutter</p>

<img src="assets/screenshots/510shots_so.png" width="32%" alt="PiliSuper mobile screenshot" />
<img src="assets/screenshots/174shots_so.png" width="32%" alt="PiliSuper mobile screenshot" />
<img src="assets/screenshots/850shots_so.png" width="32%" alt="PiliSuper mobile screenshot" />
<br/>
<img src="assets/screenshots/main_screen.png" width="96%" alt="PiliSuper desktop screenshot" />
<br/>
</div>

<br/>

## Download

Download a build from [PiliSuper Releases](https://github.com/FRBLanApps/PiliSuper/releases), or clone this repository and build it locally.

## Build

Install [Flutter](https://docs.flutter.dev/install/custom), the [dependencies for your target platform](https://docs.flutter.dev/platform-integration), and [Python](https://www.python.org/downloads/). Clone `https://github.com/FRBLanApps/PiliSuper.git`, then run `flutter pub get` before building. The build scripts use `--no-pub`, so run it again after changing `pubspec.yaml`.

For an Android release, run these commands from the repository root:

```sh
python tool/build/rename.py --pkg-id org.frblanapps.pilisuper --app-name PiliSuper
python tool/build/prebuild.py --platform android
flutter pub get
VERSION=$(sed -n 's/^version: //p' pubspec.yaml)
python tool/build/patch.py android
python tool/build/build_android.py --version "$VERSION" --output dist
```

For other platforms and packaging options, see the [full build instructions in Chinese](README.md#编译).

## Disclaimer

PiliSuper is a personal project developed for educational purposes, intended only for learning and testing. Follow your local laws when using this software.
All APIs used were collected from the official website. This project does not provide any cracked content.

Credit to [bggRGjQaUbCoE/PiliPlus](https://github.com/bggRGjQaUbCoE/PiliPlus), the project this fork is based on.
Credit to the original project: [guozhigq/pilipala](https://github.com/guozhigq/pilipala).
Credit to the upstream project: [orz12/PiliPalaX](https://github.com/orz12/PiliPalaX).
This repository makes more extensive changes. Thank you to the original authors for sharing their work as open source.

Thank you for using PiliSuper.

## Acknowledgements

- [bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)
- [flutter_meedu_videoplayer](https://github.com/zezo357/flutter_meedu_videoplayer)
- [media-kit](https://github.com/media-kit/media-kit)
- [dio](https://pub.dev/packages/dio)
- And others

## Star History

<a href="https://www.star-history.com/#FRBLanApps/PiliSuper&Date">
 <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=FRBLanApps/PiliSuper&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=FRBLanApps/PiliSuper&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=FRBLanApps/PiliSuper&type=Date" />
 </picture>
</a>
