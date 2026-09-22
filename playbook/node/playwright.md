---
tool: playwright
scope: node
tier: optional
summary: "Built-app browser checks for desktop and mobile web flows"
targets: ["playwright.config.ts", "package.json", ".github/workflows/ci.yml"]
detect: ["playwright.config.*", "svelte.config.js", "vite.config.ts"]
---

# Playwright browser checks

## What

Run browser tests against the production build's local preview server. Cover the
few flows that depend on real navigation, browser storage, or responsive layout.
Keep unit tests for parsing and other logic that does not need a browser.

## Why

A built-app check catches routing, hydration, and Back/Forward failures that
unit tests cannot. Desktop and mobile viewports exercise the same user flows
without duplicating a large test suite.

## Config

Install `@playwright/test` as a dev dependency. Set the preview command and port
to match the app. `playwright.config.ts`:

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { browserName: 'chromium', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
  },
});
```

Add `"test:e2e": "playwright test"` to `package.json`. Build before running it:

```sh
npm run build
npx playwright install chromium
npm run test:e2e
```

For GitHub Actions, keep the existing `make ci` step and run browser checks
after it builds the app:

```yaml
      - uses: actions/cache@v4
        with:
          path: ~/.cache/ms-playwright
          key: ${{ runner.os }}-playwright-${{ hashFiles('package-lock.json') }}
          restore-keys: |
            ${{ runner.os }}-playwright-
      - run: npx playwright install --with-deps chromium
      - run: npm run test:e2e
      - uses: actions/upload-artifact@v7
        if: failure()
        with:
          name: playwright-traces
          path: test-results
          if-no-files-found: ignore
```

## Gotchas

- Run against the built app. A development server can hide production routing
  and hydration failures.
- Keep the browser matrix small. Add another engine only for a concrete browser
  risk or a supported platform requirement.
- Preserve traces on failure so CI failures can be diagnosed without rerunning
  the entire suite.
