// Isolated, headless application test. Does not use the user's browser profile.
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const playwright = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  fs.mkdirSync('tmp/browser', {recursive:true});
  const outputDir=process.env.OUTPUT_DIR || 'reports';
  fs.mkdirSync(outputDir,{recursive:true});
  const browser = await playwright.chromium.launch({headless:true, executablePath: process.env.CHROME_PATH || undefined});
  const errors=[];
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1100},deviceScaleFactor:1});
    const page = await context.newPage();
    page.on('pageerror', error=>errors.push(error.message));
    await page.goto(process.env.API_URL || 'http://127.0.0.1:8000/dashboard');
    await page.locator('#api-status').filter({hasText:'Operativo'}).waitFor();
    await page.getByRole('button',{name:'Iniciar demostración',exact:true}).click();
    await page.locator('#demo-status').filter({hasText:'2 rondas guardadas'}).waitFor();
    const demoPrefix = await page.getByRole('searchbox').inputValue();
    const robotId = demoPrefix + 'R01';
    await page.locator('#rows tr').first().waitFor();
    await page.locator('#history-caption').filter({hasText:'muestras guardadas'}).waitFor();
    assert.equal(await page.locator('#error').isVisible(),false);
    await page.getByRole('button',{name:'Ver historial de '+robotId,exact:true}).click();
    await page.locator('#history-caption').filter({hasText:'muestras guardadas'}).waitFor();
    await page.screenshot({path:path.join(outputDir,'dashboard_desktop.png'),fullPage:true});
    await page.getByRole('searchbox').fill('NO-SUCH-ROBOT');
    assert.equal(await page.locator('#rows tr').count(),0);
    assert.match(await page.locator('#empty').innerText(),/Sin coincidencias/);
    await page.getByRole('searchbox').fill(robotId);
    await page.getByRole('button',{name:'Ver historial de '+robotId,exact:true}).click();
    await page.locator('#history-title').filter({hasText:robotId}).waitFor();
    await page.locator('#chart-feature').selectOption('motor_temp');
    assert.match(await page.locator('#chart').getAttribute('aria-label'),/Temperatura/);
    await page.getByRole('button',{name:'Pausar',exact:true}).click();
    assert.equal(await page.locator('#pause').getAttribute('aria-pressed'),'true');
    await page.getByRole('button',{name:'Reanudar',exact:true}).click();
    await page.locator('#live').filter({hasText:'Actualizando en vivo'}).waitFor();
    await page.getByRole('searchbox').fill(demoPrefix);
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(outputDir,'dashboard_mobile.png'),fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false,'Page overflows horizontally');
    await page.getByRole('button',{name:'Detener demostración',exact:true}).click();
    assert.equal(await page.locator('#demo-toggle').getAttribute('aria-pressed'),'false');
    const historyUrl = new URL('/robots/'+encodeURIComponent(robotId)+'/history',page.url()).href;
    const before = await (await context.request.get(historyUrl)).json();
    await page.waitForTimeout(4200);
    const after = await (await context.request.get(historyUrl)).json();
    assert.deepEqual(after,before,'Stopped demonstration kept sending telemetry');
    assert.ok(before.length>=2,'Browser telemetry was not persisted');
    assert.deepEqual(errors,[]);
    const result={passed:true,capture_url:process.env.API_URL || 'http://127.0.0.1:8000/dashboard',desktop:[1440,1100],mobile:[390,844],checks:['browser demo start','persisted browser telemetry','demo stop','live data','history selection','filter','chart variable','pause/resume','mobile overflow','no JavaScript errors']};
    fs.writeFileSync(path.join(outputDir,'dashboard_checks.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
