# Third-party notices

The MIT license in LICENSE applies to owner-confirmed original code/documentation only. Dependencies, Oracle software and third-party materials retain their own terms. No Oracle Database binaries, container layers, wallets or proprietary product documentation are redistributed. Factual synthetic benchmark observations do not grant rights in Oracle software or trademarks.

## Redistributed frontend code / generated assets

The following notices were read from the exact installed locked packages. Full upstream license files are preserved byte-for-byte, including Lucide ISC and Feather-derived MIT attribution. Vite aggregate notices are retained conservatively for the included build helper/polyfill; compiler/development packages are not otherwise redistributed as installations.

| Package | Installed version | Declared license | Exact preserved license | SHA-256 |
| --- | --- | --- | --- | --- |
| react | 19.3.1 | MIT | [react](third_party_licenses/react.txt) | da6d3703ed11cbe42bd212c725957c98da23cbff1998c05fa4b3d976d1a58e93 |
| react-dom | 19.3.1 | MIT | [react-dom](third_party_licenses/react-dom.txt) | da6d3703ed11cbe42bd212c725957c98da23cbff1998c05fa4b3d976d1a58e93 |
| scheduler | 0.28.0 | MIT | [scheduler](third_party_licenses/scheduler.txt) | da6d3703ed11cbe42bd212c725957c98da23cbff1998c05fa4b3d976d1a58e93 |
| lucide-react | 1.61.0 | ISC | [lucide-react](third_party_licenses/lucide-react.txt) | b495047bd93a9b06913511076f504daba17d5bbeb3e0650f3bb53a4220329c57 |
| tailwindcss | 4.3.3 | MIT | [tailwindcss](third_party_licenses/tailwindcss.txt) | 60e0b68c0f35c078eef3a5d29419d0b03ff84ec1df9c3f9d6e39a519a5ae7985 |
| vite | 8.3.5 | MIT | [vite](third_party_licenses/vite.txt) | a22152baa1aef74402443008e767e7c689a524c0909d19b0431d97f5ab066a13 |

## Dependencies installed separately

Python and frontend tooling dependencies remain governed by their upstream distributions/licenses and are installed independently from the pinned requirements/lockfile. Local .venv and node_modules, wheels, native libraries and browser binaries are not distribution files. The final bundle module inventory must contain only reviewed packages covered above; an unexpected bundled package fails release verification.

Oracle Database is separately obtained under its applicable Oracle terms; this export does not include or relicense it. Oracle, Java and related marks remain their respective owners. OSPA is an independent educational engineering project, not an Oracle product and not affiliated with or certified by Oracle.
