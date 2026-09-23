import { readdir, stat } from 'node:fs/promises'
import { join } from 'node:path'

const assetsDirectory = new URL('../dist/assets/', import.meta.url)
const maxBytes = 500 * 1024
const files = await readdir(assetsDirectory)
const javascriptFiles = files.filter((file) => file.endsWith('.js'))

if (!javascriptFiles.length) {
  throw new Error('No built JavaScript assets found. Run npm run build first.')
}

const sizes = await Promise.all(
  javascriptFiles.map(async (file) => ({
    file,
    bytes: (await stat(join(assetsDirectory.pathname, file))).size,
  })),
)
const largest = sizes.toSorted((left, right) => right.bytes - left.bytes)[0]
console.log(`Largest JavaScript chunk: ${largest.file} (${(largest.bytes / 1024).toFixed(1)} KiB)`)

const oversized = sizes.filter(({ bytes }) => bytes > maxBytes)
if (oversized.length) {
  for (const { file, bytes } of oversized) {
    console.error(`${file} exceeds 500 KiB (${(bytes / 1024).toFixed(1)} KiB)`)
  }
  process.exitCode = 1
}
