import { execFileSync } from 'node:child_process'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDir = resolve(fileURLToPath(new URL('..', import.meta.url)))
const generatedFile = join(frontendDir, 'src/types/openapi.generated.ts')
const openapiCli = join(frontendDir, 'node_modules/openapi-typescript/bin/cli.js')
const tempDir = await mkdtemp(join(tmpdir(), 'iterflow-openapi-types-'))
const tempFile = join(tempDir, 'openapi.generated.ts')

try {
  execFileSync(
    process.execPath,
    [openapiCli, '../spec/openapi-v1.5.yaml', '-o', tempFile],
    { cwd: frontendDir, stdio: 'inherit' },
  )
  const [committed, current] = await Promise.all([
    readFile(generatedFile, 'utf8'),
    readFile(tempFile, 'utf8'),
  ])
  if (committed !== current) {
    process.stderr.write('OpenAPI generated types are stale; run npm run generate:api-types.\n')
    process.exitCode = 1
  }
} finally {
  await rm(tempDir, { recursive: true, force: true })
}
