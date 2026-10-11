# Writing preview assets

KaTeX 0.19.0, identical tarball integrity to the original Darwin lockfile at `44a0d4f9362c3a7e65e3d2938837d40a6e2a3a60`.

- Package: https://registry.npmjs.org/katex/-/katex-0.19.0.tgz
- Integrity: `sha512-v6Tznz3zJ7u3niRCoDTsumM2+HA2XXcCu+WAacCeHD2z3p9A9Ks987o5FzfTGBN0e8A0vjEgIDvLbICrXpdw/Q==`
- Bundle: `NeoMathDarwin/PreviewAssets` (JavaScript, stylesheet, fonts, MIT license).
- `typeset.js` ports the original `src/math-format.ts` MathML adapter.

These trusted, bundled scripts typeset HTML supplied by the original XDLT compiler. Document scripts are disabled; the preview blocks external network subresources. SwiftUI supplies the native writing UI and UIKit the source editor.
