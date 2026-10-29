const {test, describe, before, after} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const engines = require('playwright-core');

const frontend = path.resolve('frontend');
const origin = 'http://127.0.0.1:43210';
const mime = {'.html':'text/html', '.css':'text/css', '.js':'text/javascript', '.png':'image/png'};

async function openApp(browser, width, height) {
  const context = await browser.newContext({viewport:{width,height}, hasTouch:true,
    locale:'pt-BR', serviceWorkers:'block'});
  const page = await context.newPage();
  // Fully isolated app: actual HTML/CSS/JS, real IndexedDB, no server/model calls.
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    assert.equal(url.origin, origin);
    assert.equal(route.request().method(), 'GET');
    if (url.pathname === '/health') return route.fulfill({json:{status:'ok',llm_configured:true}});
    if (url.pathname === '/maps') return route.fulfill({json:[]});
    const relative = url.pathname === '/app/' ? 'index.html' : url.pathname.replace(/^\/app\//, '');
    const file = path.resolve(frontend, relative);
    assert.ok(file.startsWith(frontend + path.sep));
    try {
      await route.fulfill({body:await fs.readFile(file), contentType:mime[path.extname(file)] || 'application/octet-stream'});
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      await route.fulfill({status:404,body:''});
    }
  });
  await page.goto(origin + '/app/');
  await page.waitForFunction(() => !document.querySelector('#message-input').disabled);
  return {page, context};
}

async function visibleViewport(page, height, top = 0) {
  // Simulate VisualViewport events while keeping layout viewport dimensions
  // unchanged, as when an iOS keyboard opens. No claim of a physical keyboard.
  await page.evaluate(({height,top}) => {
    Object.defineProperty(window.visualViewport, 'height', {configurable:true,value:height});
    Object.defineProperty(window.visualViewport, 'offsetTop', {configurable:true,value:top});
    window.visualViewport.dispatchEvent(new Event('resize'));
    window.visualViewport.dispatchEvent(new Event('scroll'));
  }, {height,top});
  await page.waitForFunction(({height,top}) => {
    const shell = document.querySelector('.workspace').getBoundingClientRect();
    return Math.abs(shell.height-height) < 1 && Math.abs(shell.top-top) < 1;
  }, {height,top});
}

async function checkLayout(page, welcomeVisible = true) {
  const layout = await page.evaluate(() => {
    const rect = selector => {
      const r = document.querySelector(selector).getBoundingClientRect();
      return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,height:r.height};
    };
    const input = rect('#message-input');
    return {welcome:rect('#welcome'), stage:rect('.chat-stage'), composer:rect('.composer-shell'),
      input, shell:rect('.workspace'),
      inputHit:document.elementFromPoint(input.left+20, input.top+input.height/2)?.id,
      documentScroll:document.scrollingElement.scrollTop,
      documentWidth:document.scrollingElement.scrollWidth, width:window.innerWidth};
  });
  assert.ok(layout.stage.bottom <= layout.composer.top+1, JSON.stringify(layout));
  assert.ok(layout.input.bottom <= layout.composer.bottom+1, JSON.stringify(layout));
  assert.ok(layout.composer.bottom <= layout.shell.bottom+1, JSON.stringify(layout));
  assert.equal(layout.inputHit, 'message-input', JSON.stringify(layout));
  assert.equal(layout.documentScroll, 0);
  assert.ok(layout.documentWidth <= layout.width+1);
  if (welcomeVisible) {
    assert.ok(layout.welcome.top >= layout.stage.top-1, JSON.stringify(layout));
    assert.ok(layout.welcome.bottom <= layout.stage.bottom+1, JSON.stringify(layout));
  }
}

for (const name of (process.env.KRONO_LAYOUT_ENGINES || 'chromium').split(',')) {
  describe(`mobile layout / ${name}`, () => {
    let browser;
    before(async () => {
      browser = await engines[name].launch({headless:true,
        ...(name === 'chromium' && process.env.KRONO_CHROMIUM_PATH
          ? {executablePath:process.env.KRONO_CHROMIUM_PATH} : {})});
    });
    after(async () => {await browser?.close();});
    for (const [width,height,visible] of [[393,852,852], [393,852,380], [320,568,300],
      [430,932,430], [852,393,260], [1440,900,900]]) {
      test(`new conversation ${width}x${height}, visible height ${visible}`, async () => {
        const {page,context} = await openApp(browser,width,height);
        try {
          await page.locator('#message-input').focus();
          await visibleViewport(page,visible);
          await checkLayout(page);
          // Quick actions remain reachable within the welcome scroll area.
          const prompt = page.locator('#quick-prompts button').last();
          await prompt.scrollIntoViewIfNeeded();
          const buttonBox = await prompt.boundingBox();
          assert.ok(buttonBox.y+buttonBox.height <= (await page.locator('.composer-shell').boundingBox()).y+1);
          assert.ok(await prompt.evaluate(button => {
            const r = button.getBoundingClientRect();
            return button.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));
          }));
          await checkLayout(page);
          if (process.env.KRONO_LAYOUT_SCREENSHOTS) {
            await fs.mkdir('.cache/mobile-layout',{recursive:true});
            await page.screenshot({path:`.cache/mobile-layout/${name}-${width}-${visible}.png`});
          }
        } finally {await context.close();}
      });
    }
    test('existing chat → new conversation; keyboard open/close and multiline input', async () => {
      const {page,context} = await openApp(browser,393,852);
      try {
        await page.evaluate(() => addMessage('assistant', 'Uma resposta longa.\n\n'.repeat(60), {persist:false}));
        await page.locator('#message-input').focus();
        await visibleViewport(page,380,80);
        await checkLayout(page,false);
        await page.locator('#history-open').click();
        await page.locator('#clear-chat').click();
        await page.locator('#welcome').waitFor({state:'visible'});
        await page.locator('#history-dialog').waitFor({state:'hidden'});
        await checkLayout(page);
        await page.locator('#message-input').fill('Pergunta\ncom várias\nlinhas\npara testar\no campo.');
        await checkLayout(page);
        await page.locator('#message-input').blur();
        await visibleViewport(page,852);
        await checkLayout(page);
      } finally {await context.close();}
    });
  });
}
