import { defineConfig } from 'vitest/config'

export default defineConfig({
  oxc: { jsx: { runtime: 'automatic' } },
  test: { environment: 'jsdom', include: ['tests/*.component.test.jsx'], setupFiles: ['tests/componentSetup.js'] },
})
