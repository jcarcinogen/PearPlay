import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'..');
const read=p=>readFileSync(resolve(root,p),'utf8');
const html=read('docs/index.html');
const template=read('assets/landing/page.html');
const site='https://jcarcinogen.github.io/PearPlay/';

test('landing metadata names the product, browser video and Apple TV',()=>{
  assert.match(html,/<title>PearPlay — Send Browser Video to Apple TV<\/title>/);
  assert.ok(html.includes(`<link rel="canonical" href="${site}">`));
  assert.match(html,/<meta name="description" content="PearPlay is a Chrome extension/);
  assert.match(html,/<meta property="og:url"/);
  assert.match(html,/<meta name="twitter:card" content="summary_large_image"/);
  assert.equal((html.match(/<h1>/g)||[]).length,1);
});
test('Pages is the exact rendered template using existing branded assets',()=>{
  const assets={MARK:['assets/brand/mark.svg','image/svg+xml'],POPUP_LIGHT:['assets/store/popup-light-viewport.png','image/png'],POPUP_DARK:['assets/store/popup-dark-viewport.png','image/png']};
  const rendered=template.replace(/\{\{([A-Z_]+)\}\}/g,(_,key)=>{const [path,type]=assets[key];return `data:${type};base64,${readFileSync(resolve(root,path)).toString('base64')}`;});
  assert.equal(html,rendered);
});
test('Store link is prominent without implying preview Store approval',()=>{
  assert.match(html,/<a class="button" href="https:\/\/chromewebstore.google.com\/detail\/pearplay\/eoadahoncjfpnennmkjifohclbafjkol">Add to Chrome/);
  assert.match(html,/Chrome Web Store currently offers 0\.2\.9/);
  assert.match(html,/Store approval is separate/);
  assert.match(html,/separate PearPlay Helper is required/);
});
test('installation warnings, all platform links and copy controls are retained',()=>{
  assert.match(html,/<h2>Install PearPlay and connect the helper<\/h2><p><strong>Flatpak-installed/);
  for(const phrase of ['Fedora helper','Mac screenshot guide','Stop if blocked','Do not remove quarantine','Safari extension development is paused','all-sites access','TV seeking and volume remain unsupported']) assert.ok(html.includes(phrase),phrase);
  for(const id of ['setup','linux']) assert.ok(html.includes(`data-copy="${id}"`) && html.includes(`id="${id}"`));
});
test('structured data has no fabricated rating or review',()=>{
  const schema=JSON.parse(html.match(/<script type="application\/ld\+json">\s*([\s\S]*?)<\/script>/)[1]);
  assert.equal(schema.name,'PearPlay');
  assert.equal(schema.url,site);
  assert.equal(schema.applicationCategory,'MultimediaApplication');
  assert.equal(schema.aggregateRating,undefined);
  assert.equal(schema.review,undefined);
});
test('sitemap contains only public page and privacy URLs',()=>{
  const urls=[...read('docs/sitemap.xml').matchAll(/<loc>(.*?)<\/loc>/g)].map(m=>m[1]);
  assert.deepEqual(urls,[site,site+'privacy.html']);
});
