/**
 * Regenerate the README screenshots from the running app.
 *
 *   1. start the backend with the rate limit raised - this script fires several
 *      analyses back to back and the 5/min default will reject its own run:
 *        RATE_LIMIT_PER_MINUTE=60 uvicorn app.main:app --app-dir backend
 *   2. build the frontend: npm run build
 *   3. node scripts/screenshots.mjs
 *
 * Uses puppeteer-core against the locally installed Chrome, so nothing is
 * downloaded. Waits for the pipeline to actually finish rather than guessing at
 * a delay - the LLM call is a real network round trip and its timing varies.
 */

import { existsSync, mkdirSync } from 'node:fs'
import { platform } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import puppeteer from 'puppeteer-core'

const HERE = dirname(fileURLToPath(import.meta.url))
const OUT_DIR = resolve(HERE, '../../docs/screenshots')
const BASE_URL = process.env.SHOT_BASE_URL ?? 'http://127.0.0.1:8000'

const CHROME_CANDIDATES =
  platform() === 'win32'
    ? [
        `${process.env.LOCALAPPDATA}\\Google\\Chrome\\Application\\chrome.exe`,
        `${process.env.ProgramFiles}\\Google\\Chrome\\Application\\chrome.exe`,
        `${process.env['ProgramFiles(x86)']}\\Google\\Chrome\\Application\\chrome.exe`,
      ]
    : [
        '/usr/bin/google-chrome',
        '/usr/bin/chromium',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      ]

const SHOTS = [
  {
    name: 'dashboard',
    request: 'Upgrade payment-service from Spring Boot 2.7 to 3.2',
    fullPage: true,
  },
  {
    name: 'risk-score',
    request: 'Upgrade payment-service from Spring Boot 2.7 to 3.2',
    selector: '[data-shot="risk-score"]',
  },
  {
    // The framework upgrade is the widest blast radius in the demo dataset -
    // five affected services. A one-service scenario photographs as an empty
    // graph and undersells what the view is for.
    name: 'blast-radius',
    request: 'Upgrade payment-service from Spring Boot 2.7 to 3.2',
    selector: '[data-shot="blast-radius"]',
  },
  {
    name: 'pipeline',
    request: 'Remove customerEmail field from order-created Kafka event',
    selector: '[data-shot="pipeline"]',
  },
]

function findChrome() {
  const found = CHROME_CANDIDATES.find((path) => path && existsSync(path))
  if (!found) {
    throw new Error(
      `Chrome not found. Tried:\n${CHROME_CANDIDATES.join('\n')}\n` +
        'Set CHROME_PATH to override.',
    )
  }
  return found
}

async function main() {
  mkdirSync(OUT_DIR, { recursive: true })

  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH || findChrome(),
    headless: 'shell',
    args: ['--hide-scrollbars', '--disable-gpu'],
  })

  try {
    const page = await browser.newPage()
    // deviceScaleFactor 2 so the text stays crisp on a HiDPI display, which is
    // where most people will read the README.
    await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })

    for (const shot of SHOTS) {
      const url = `${BASE_URL}/?q=${encodeURIComponent(shot.request)}`
      await page.goto(url, { waitUntil: 'networkidle2' })

      // The score breakdown only renders once agent 7 has returned and the
      // report is set, so it is a reliable "pipeline finished" signal.
      await page.waitForSelector('[data-shot="risk-score"]', { timeout: 60_000 })
      await page.waitForFunction(
        () => !document.querySelector('button[type="submit"]')?.disabled,
        { timeout: 60_000 },
      )
      // Let the React Flow fitView transition settle.
      await new Promise((done) => setTimeout(done, 900))

      const target = shot.selector ? await page.$(shot.selector) : page
      if (!target) throw new Error(`selector not found: ${shot.selector}`)

      const path = resolve(OUT_DIR, `${shot.name}.png`)
      await target.screenshot({ path, fullPage: shot.fullPage ?? false })
      console.log(`wrote ${shot.name}.png`)
    }
  } finally {
    await browser.close()
  }
}

main().catch((error) => {
  console.error(error.message)
  process.exit(1)
})
