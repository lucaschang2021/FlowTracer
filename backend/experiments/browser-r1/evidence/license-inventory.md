# R1 dependency and redistribution inventory

The machine-readable inventory is `sbom.cdx.json` (CycloneDX 1.6, 231
components: 23 installed Python distributions, 206 Debian packages, Chromium
headless shell, and FFmpeg). Every Debian component has an SPDX expression or
stable `LicenseRef-Debian-Notice-*`, normalized raw header values, a persistent
notice-file path, and a SHA-256 in
`debian-license-inventory.json`. The 206 original Debian copyright files are
persisted under `debian-notices/`; their hashes are in both inventory and SBOM.
The final inventory contains 5 components with an exact, manually reviewed SPDX
mapping and 201 components with a notice-backed
`LicenseRef-Debian-Notice-*`. Its SHA-256 is
`bee9c30ae016be592521c383b9bb0be74f39892415ed28f9122d5b7ccced81da`;
both final-fix images generated the same stream.

## Python and browser components

| Component | Version | Declared license |
| --- | --- | --- |
| scrapling | 0.4.15 | BSD-3-Clause |
| patchright | 1.62.3 | Apache-2.0 |
| playwright | 1.62.0 | Apache-2.0 |
| anyio | 4.14.2 | MIT |
| apify-fingerprint-datapoints | 0.15.0 | Apache-2.0 |
| browserforge | 1.2.4 | Apache-2.0 |
| certifi | 2026.7.22 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| cssselect | 1.5.0 | BSD-3-Clause |
| curl-cffi | 0.16.3 | MIT |
| greenlet | 3.5.5 | MIT AND PSF-2.0 |
| idna | 3.19 | BSD-3-Clause |
| lxml | 6.1.3 | BSD-3-Clause |
| msgspec | 0.21.1 | BSD-3-Clause |
| orjson | 3.12.0 | MPL-2.0 AND (Apache-2.0 OR MIT) |
| pip | 26.2.1 | MIT; inherited from pinned base image |
| protego | 0.6.2 | BSD-3-Clause |
| pycparser | 3.0 | BSD-3-Clause |
| pyee | 13.0.1 | MIT |
| tld | 0.13.2 | MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later |
| typing-extensions | 4.16.0 | PSF-2.0 |
| w3lib | 2.4.1 | BSD-3-Clause |
| Chromium headless shell | 151.0.7922.34, r1234 | BSD-3-Clause plus bundled third-party notices |
| FFmpeg | Playwright r1011 | LGPL-2.1-or-later |

## Redistribution evidence and conclusion

- Chromium source license: <https://chromium.googlesource.com/chromium/src/+/main/LICENSE>
- Playwright browser/version documentation: <https://playwright.dev/python/docs/browsers>
- Playwright Python v1.62.0 license: <https://github.com/microsoft/playwright-python/blob/v1.62.0/LICENSE>
- Patchright license: <https://github.com/Kaliiiiiiiiii-Vinyzu/patchright/blob/main/LICENSE>
- Chrome for Testing project: <https://github.com/GoogleChromeLabs/chrome-for-testing>

The persistent Chromium notice is `notices/chromium-LICENSE.headless_shell`
(2,120,830 bytes, SHA-256
`334f3e2d8a58954bc7152a8150bdd3e7f35e0d9bcf30dd323d4edcb7df5f36d5`).
The persistent FFmpeg notice is `notices/ffmpeg-COPYING.LGPLv2.1` (SHA-256
`b634ab5640e258563c536e658cad87080553df6f34f62269a21d554844e58bfe`).
The SBOM component hashes are deliberately the actual Chromium executable
(`e11fc9ce65c96313476f7ee9844b6fb6a9220fb048693cfe9eee00acf4170a9f`)
and FFmpeg executable (`460d44f3416005662f528d4b92e7b94ace924e8a0288106d3803b73c56eaadc8`),
not the notice hashes. The notices remain separate named properties.
No Widevine component was present. Redistribution is acceptable for this
internal candidate provided these bundled notices and corresponding dependency
notices accompany any later image distribution. R1 does not publish the image
to a registry and does not authorize production distribution.
