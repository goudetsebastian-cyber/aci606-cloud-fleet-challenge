// Isolated application acceptance test; no user browser profile is accessed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.API_BASE || 'http://127.0.0.1:8016';
const out = process.env.PROOF_DIR || 'output/cross-device';
const phase = process.argv[2] || 'before';
fs.mkdirSync(out,{recursive:true});

(async()=>{
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH});
  const errors=[];
  async function device(viewport) {
    const context = await browser.newContext({viewport});
    await context.addInitScript(()=>{
      Object.defineProperty(AbortSignal,'timeout',{value:undefined,configurable:true});
      Object.defineProperty(Crypto.prototype,'randomUUID',{value:undefined,configurable:true});
      Object.defineProperty(Crypto.prototype,'subtle',{get(){throw Error('Unavailable cryptography');},configurable:true});
      Storage.prototype.getItem=()=>{throw Error('Storage blocked');};
      Storage.prototype.setItem=()=>{throw Error('Storage blocked');};
    });
    await context.route('**/*',route=>{
      const path = new URL(route.request().url()).pathname;
      if(['/metrics','/health','/robots','/demo/scenario','/predict','/telemetry'].includes(path)||path.startsWith('/robots/')) return route.abort('blockedbyclient');
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', e=>errors.push(e.message));
    page.setDefaultTimeout(60000);
    return {context,page};
  }
  try {
    if (phase==='after') {
      const ref=JSON.parse(fs.readFileSync(out+'/reference.json','utf8'));
      const {page}=await device({width:390,height:844});
      await page.goto(base+'/dashboard?proof='+ref.proof_id);
      await page.locator('#proof-status').filter({hasText:'recuperada de la nube'}).waitFor();
      await page.getByRole('button',{name:'Verificar tras reinicio',exact:true}).click();
      await page.locator('#proof-status').filter({hasText:'Persistencia confirmada'}).waitFor();
      await page.screenshot({path:out+'/after-restart.png',fullPage:true});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.deepEqual(errors,[]);
      console.log(JSON.stringify({passed:true,phase,proof_id:ref.proof_id,checks:['fresh mobile context','storage blocked','legacy crypto unavailable','tracking paths blocked','125 samples identical after server restart']}));
    } else {
      const {page,context}=await device({width:1440,height:1100});
      await page.goto(base+'/dashboard');
      await page.locator('#api-status').filter({hasText:'Operativo'}).waitFor();
      await page.getByRole('button',{name:'Iniciar demostración',exact:true}).click();
      await page.locator('#demo-status').filter({hasText:'2 rondas guardadas'}).waitFor();
      const prefix=await page.locator('#search').inputValue();
      await page.getByRole('button',{name:'Detener demostración',exact:true}).click();
      await page.locator('#history-caption').filter({hasText:'muestras guardadas'}).waitFor();
      for(const feature of ['battery','motor_temp','vibration','speed']) await page.locator('#chart-feature').selectOption(feature);
      await page.locator('#condition').selectOption('CRITICAL');
      await page.locator('#condition').selectOption('');
      await page.locator('#search').fill('NO-SUCH-ROBOT');
      await page.locator('#empty').filter({hasText:'Sin coincidencias'}).waitFor();
      await page.locator('#search').fill(prefix);
      await page.getByRole('button',{name:'Pausar',exact:true}).click();
      await page.getByRole('button',{name:'Reanudar',exact:true}).click();
      await page.locator('#presentation-checks > summary').click();
      await page.getByRole('button',{name:'Obtener predicción',exact:true}).click();
      await page.locator('#check-status').filter({hasText:'HTTP 200'}).waitFor();
      await page.getByRole('button',{name:'Probar dato inválido',exact:true}).click();
      await page.locator('#check-status').filter({hasText:'HTTP 422'}).waitFor();
      await page.getByRole('button',{name:'Pausar',exact:true}).click();
      await page.getByRole('button',{name:'Guardar 125 muestras',exact:true}).click();
      await page.locator('#proof-status').filter({hasText:'125 muestras guardadas.'}).waitFor();
      assert.equal(await page.locator('#pause').innerText(),'Pausar');
      const id=await page.locator('#proof-select').inputValue();
      assert.match(id,/^[a-f0-9]{32}$/);
      const ref=await (await context.request.get(base+'/dashboard/proofs/'+id)).json();
      assert.equal(ref.count,125); assert.equal(ref.intact,true); assert.equal(ref.restarted,false);
      fs.writeFileSync(out+'/reference.json',JSON.stringify(ref,null,2));
      await page.getByRole('button',{name:'Verificar tras reinicio',exact:true}).click();
      await page.locator('#proof-status').filter({hasText:'sigue igual'}).waitFor();
      await page.screenshot({path:out+'/desktop.png',fullPage:true});
      const other=await device({width:390,height:844});
      await other.page.goto(base+'/dashboard');
      await other.page.locator('#presentation-checks > summary').click();
      await other.page.getByRole('button',{name:'Recuperar pruebas',exact:true}).click();
      await other.page.locator('#proof-status').filter({hasText:'Pruebas recuperadas'}).waitFor();
      await other.page.locator('#proof-select').selectOption(id);
      await other.page.locator('#proof-status').filter({hasText:'Prueba recuperada'}).waitFor();
      await other.page.getByRole('button',{name:'Verificar tras reinicio',exact:true}).click();
      await other.page.locator('#proof-status').filter({hasText:'125/125 muestras intactas'}).waitFor();
      assert.equal(await other.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await other.page.screenshot({path:out+'/other-device.png',fullPage:true});
      await other.page.reload();
      await other.page.locator('#proof-status').filter({hasText:'Prueba recuperada de la nube'}).waitFor();
      assert.equal(await other.page.locator('#proof-select').inputValue(),id);
      assert.deepEqual(errors,[]);
      console.log(JSON.stringify({passed:true,phase,proof_id:id,checks:['demo start/stop','charts','search','condition','pause/resume','prediction 200','validation 422','atomic 125 sample save','verify unchanged instance','cloud recovery from different profile','reload without local storage','mobile layout','tracking paths blocked','modern crypto disabled','no JS errors']}));
    }
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
