// Captura la pestaña de Eliminatorias (requiere backend con la BD demo + dev server).
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

mkdirSync("screenshots", { recursive: true });
const BASE = "http://localhost:5173";

for (let i = 0; i < 60; i++) {
  try {
    const r = await fetch(`${BASE}/api/health`);
    if (r.ok) break;
  } catch {
    /* arrancando */
  }
  await new Promise((r) => setTimeout(r, 700));
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1480, height: 1040 }, deviceScaleFactor: 1.5 });

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.locator("input").first().fill("admin");
await page.locator('input[type="password"]').fill("admin123");
await page.getByRole("button", { name: /Iniciar sesión/i }).click();
await page.waitForTimeout(1500);

await page.goto(`${BASE}/partidos`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: /Eliminatorias/ }).click();
await page.getByText("Ronda de 32").first().waitFor({ timeout: 12000 });
await page.waitForTimeout(700);
await page.screenshot({ path: "screenshots/08-eliminatorias.png" });
console.log("captura: 08-eliminatorias");

await browser.close();
console.log("OK");
