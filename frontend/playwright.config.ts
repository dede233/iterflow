import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 60000,
  use: {
    baseURL: process.env.ITERFLOW_WEB_URL || 'http://127.0.0.1:8080',
    browserName: 'chromium',
    headless: true,
  },
})
