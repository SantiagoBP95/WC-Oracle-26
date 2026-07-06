// Captura pantallas de la app (login + páginas). Requiere backend :8000 y dev server :5173.
// Ejecutar desde la raíz del repo:  node frontend/screenshot.mjs
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const OUT = "screenshots";
mkdirSync(OUT, { recursive: true });

const BASE = "http://localhost:5173";

// Espera a que el dev server y el backend (vía proxy) estén listos.
for (let i = 0; i < 60; i++) {
  try {
    const r = await fetch(`${BASE}/api/health`);
    if (r.ok) break;
  } catch {
    /* aún arrancando */
  }
  await new Promise((r) => setTimeout(r, 700));
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1480, height: 920 }, deviceScaleFactor: 1.5 });

async function shot(name) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("captura:", name);
}

// 1) Login
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await shot("01-login");

// 2) Autenticarse
await page.locator("input").first().fill("admin");
await page.locator('input[type="password"]').fill("admin123");
await page.getByRole("button", { name: /Iniciar sesión/i }).click();
await page.getByText("Probabilidades de título").waitFor({ timeout: 15000 });
await shot("02-dashboard");

// Cambiar de modelo con el selector del header (si hay varios disponibles).
const selector = page.locator("header select");
if (await selector.count()) {
  await selector.selectOption("xgboost").catch(() => {});
  await page.waitForTimeout(800);
  await shot("02b-dashboard-xgboost");
  await selector.selectOption("elo").catch(() => {});
  await page.waitForTimeout(400);
}

// 3) Resto de páginas (SPA con token en localStorage)
for (const [path, heading, name] of [
  ["/grupos", "Grupos", "03-grupos"],
  ["/bracket", "Camino al título", "04-bracket"],
  ["/comparador", "Comparador de modelos", "07-comparador"],
  ["/partidos", "fase de grupos", "05-partidos"],
  ["/admin", "Administración", "06-admin"],
]) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.getByText(heading).first().waitFor({ timeout: 15000 });
  await shot(name);
}

// Intervalos de credibilidad (bayesiano): hacer scroll a la sección y capturar.
await page.goto(`${BASE}/comparador`, { waitUntil: "networkidle" });
const ci = page.getByText("intervalo de credibilidad").first();
if (await ci.count()) {
  await ci.scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(600);
  await shot("07b-credibilidad");
}

await browser.close();
console.log("OK");
