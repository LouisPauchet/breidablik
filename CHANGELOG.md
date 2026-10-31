# Changelog

## [0.7.0](https://github.com/LouisPauchet/breidablik/compare/breidablik-v0.6.0...breidablik-v0.7.0) (2026-10-31)


### Features

* add admin action guards ([4805099](https://github.com/LouisPauchet/breidablik/commit/48050993fdf5f755c10f51affd6e4d1cd828c4b9))
* add audit log model and helper ([1e3d400](https://github.com/LouisPauchet/breidablik/commit/1e3d400032fa0b46ff0eab4dbf2685f340035213))
* add audit log page ([ff7e00f](https://github.com/LouisPauchet/breidablik/commit/ff7e00f6891ad9b882ce8e582c2969be8f1f01ad))
* add optional Google and GitHub account linking ([4ce6a45](https://github.com/LouisPauchet/breidablik/commit/4ce6a454f17848c35999513a3a9a368394315826))
* add passkey registration and management ([39d4b03](https://github.com/LouisPauchet/breidablik/commit/39d4b0333e3fa45be534c83049eac6bb47ad3b10))
* add passwordless mode ([78b453e](https://github.com/LouisPauchet/breidablik/commit/78b453e78b51418bfeaaad50033feb84d3c8bdfa))
* add public password reset page ([eb47cf1](https://github.com/LouisPauchet/breidablik/commit/eb47cf11087013dc8cc8d6723eea6eba9795750d))
* add reset link action to the members page ([bb2d3e2](https://github.com/LouisPauchet/breidablik/commit/bb2d3e2b6a59906f9d43ddbfd54008c4bbfa3adb))
* add user deactivation and passwordless login flags to the schema ([0f98049](https://github.com/LouisPauchet/breidablik/commit/0f98049060e4ecce6f1b7fb52a4cdf622924415c))
* allow sign-in with a linked Google or GitHub account ([7f4f94d](https://github.com/LouisPauchet/breidablik/commit/7f4f94d6c520bc4fee5933cb2dbc5d3ea67d1135))
* allow sign-in with a passkey ([b66c746](https://github.com/LouisPauchet/breidablik/commit/b66c7467f7a6131eddf28920a1687475f12725f6))
* let admins deactivate and reactivate members ([fb0b48d](https://github.com/LouisPauchet/breidablik/commit/fb0b48d0cb85ce7a236d05f105e46115dc47268a))
* let admins force logout and change roles ([474ab70](https://github.com/LouisPauchet/breidablik/commit/474ab7015193570f9537f969b96730eec2f31f49))
* let admins generate password reset links ([781c8c3](https://github.com/LouisPauchet/breidablik/commit/781c8c34ec02caf894fdc69048dfe32fb779420c))
* password reset links, admin tools, social login and passkeys ([5d2bc3b](https://github.com/LouisPauchet/breidablik/commit/5d2bc3b29ef59575f380e76ec0ff8ef5aced5697))


### Documentation

* document reset links, admin tools, social login and passkeys ([2a73c02](https://github.com/LouisPauchet/breidablik/commit/2a73c025b8b1192ffbb405d1e9d6f82e548dfbe7))

## [0.6.0](https://github.com/LouisPauchet/breidablik/compare/breidablik-v0.5.0...breidablik-v0.6.0) (2026-09-09)


### Features

* add contest duties with a monthly best-performer award ([a146b0a](https://github.com/LouisPauchet/breidablik/commit/a146b0a5102f3460ad9a80a34a300982be480996))
* make duty completion status private to the assignee ([5625964](https://github.com/LouisPauchet/breidablik/commit/56259644ee5385794f9fff14edc58006c97d8975))
* private contest counts, a logging cooldown, and a home-screen option ([cbc6663](https://github.com/LouisPauchet/breidablik/commit/cbc66633769d5243d33cf7682d2d20f6aec90094))

## [0.5.0](https://github.com/LouisPauchet/breidablik/compare/breidablik-v0.4.1...breidablik-v0.5.0) (2026-09-02)


### Features

* add monthly awards (Duty Master + community award) ([68821b2](https://github.com/LouisPauchet/breidablik/commit/68821b25b6153e2a3846ed3114f4c09f6868833f))
* surface monthly awards on Home, with badges and a history page ([aae126d](https://github.com/LouisPauchet/breidablik/commit/aae126d0277fc5c0710db936cfe7257923669d82))

## [0.4.1](https://github.com/LouisPauchet/breidablik/compare/breidablik-v0.4.0...breidablik-v0.4.1) (2026-09-02)


### Bug Fixes

* missing ownership check on push-subscription removal (IDOR) ([3249445](https://github.com/LouisPauchet/breidablik/commit/324944517cec5ab0ed945460852469e3d6ef11e1))
* no brute-force throttling on TOTP/recovery-code login ([02e8248](https://github.com/LouisPauchet/breidablik/commit/02e8248ef5a17fbdd43b6b15f3a5dbd58f1dfbac))
* password change/reset didn't invalidate other login sessions ([a215b7d](https://github.com/LouisPauchet/breidablik/commit/a215b7d8056907e16402d209368857745e2ac1e9))
* path traversal in the SPA static-file fallback route ([4a9d3c6](https://github.com/LouisPauchet/breidablik/commit/4a9d3c604f5a3bf2e83522a2765c65d45b56f587))
* PIN lockout counter bypassable via concurrent requests ([23861bb](https://github.com/LouisPauchet/breidablik/commit/23861bb5f47d68eb27a41d6a9f3ced734d226bc4))
* shopping-list duty notification never fired for team-attached duties ([89fc4a0](https://github.com/LouisPauchet/breidablik/commit/89fc4a0458192c585066f656b15cf35803616ced))
* tar-slip fallback in passenger_update.py's archive extraction ([5cf3e0b](https://github.com/LouisPauchet/breidablik/commit/5cf3e0b7ece91e6115f1df0a2aa4127f8a9aa125))

## [0.4.0](https://github.com/LouisPauchet/breidablik/compare/breidablik-v0.3.0...breidablik-v0.4.0) (2026-09-01)


### Features

* add a wall-display dashboard for a shared household screen ([abc0566](https://github.com/LouisPauchet/breidablik/commit/abc05669596f90defef9988239c4a23b929eb138))
* make the dashboard's "Coming up" list configurable per link ([a374467](https://github.com/LouisPauchet/breidablik/commit/a3744675b437e6553e671f5801ef7ed2814eaac7))
* notify the whole collective when an event is created ([7266cb0](https://github.com/LouisPauchet/breidablik/commit/7266cb0cb5da64ab433a62b1c476d14b63048da5))
* show the quote of the day on the app home screen ([eb7175e](https://github.com/LouisPauchet/breidablik/commit/eb7175e9dbc7f130677a49fd9d048515104bd55f))


### Bug Fixes

* harden the PWA against leaving iOS standalone mode ([99e860e](https://github.com/LouisPauchet/breidablik/commit/99e860e7d066e01a2fd118688fea2b69b6e35792))

## [0.3.0](https://github.com/LouisPauchet/breidablik/compare/breidablik-v0.2.0...breidablik-v0.3.0) (2026-09-01)


### Features

* invite members by link instead of setting a password for them ([f2073b2](https://github.com/LouisPauchet/breidablik/commit/f2073b2a6504598ba63b55630e1ad5f8d4e4b4d5))
* let members change their own password ([9389cc7](https://github.com/LouisPauchet/breidablik/commit/9389cc73b85fd01daf5973cedadaf5e4c5a85bd2))


### Bug Fixes

* let passenger_update.py bootstrap a brand-new, empty deploy target ([724f3f8](https://github.com/LouisPauchet/breidablik/commit/724f3f8d06853dee76a04172413016bf8556c8a3))
* make the test suite hermetic against COOKIE_SECURE ([3d8c096](https://github.com/LouisPauchet/breidablik/commit/3d8c096e9b940cfcb6e77ee108fd731ee2e6d9cc))
* redispatch a duty team's pending occurrences when membership changes ([6980df6](https://github.com/LouisPauchet/breidablik/commit/6980df6303b1ab4a7656d7caab5794112cba5164))
* regenerate frontend package-lock.json to match package.json ([8d5de65](https://github.com/LouisPauchet/breidablik/commit/8d5de65f6c766cfdded4dfc83f53e265fb6c2bab))
