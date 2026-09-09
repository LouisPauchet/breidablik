# Changelog

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
