import { readFileSync } from 'node:fs'

// The frontend package is the single build-time source for product labels.
export const versionDefine = {
  __APP_VERSION__: JSON.stringify(JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version),
}
