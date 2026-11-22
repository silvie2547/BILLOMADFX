# Android release signing

`billomadfx-release.p12` signs every release APK so updates install in place
over previous versions (identical signature across releases).

- Store type: PKCS12
- Alias: `billomadfx-release`
- Store/key password: `billomadfx-release-signing`
- Certificate: CN=BILLOMADFX Release, O=BILLOMADFX, valid 30 years

The password is public because the keystore itself is in a public repo; it
protects nothing beyond the APK signature. If this repo ever becomes private
or the key must be rotated, generate a new PKCS12 (see scripts/gen_keystore.py)
and pass `ANDROID_KEYSTORE_FILE`, `ANDROID_KEYSTORE_PASSWORD` and
`ANDROID_KEY_ALIAS` as GitHub Actions secrets instead.
