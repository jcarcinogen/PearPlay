import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const read = p => readFileSync(resolve(root, p));
test('editable identity has a transparent canvas and no external assets', () => {
  for (const file of ['mark.svg', 'app-icon.svg', 'wordmark.svg']) {
    const svg = read(`assets/brand/${file}`).toString();
    assert.match(svg, /<svg/);
    assert.doesNotMatch(svg, /<image|<script|<foreignObject|@import|https?:\/\/(?!www\.w3\.org)/);
  }
});
test('required raster assets have exact dimensions', () => {
  const files = Object.fromEntries([16,32,48,128].map(n => [`extension/icons/icon${n}.png`,[n,n]]));
  Object.assign(files, {'extension/icons/icon.png':[1024,1024], 'assets/store/icon-1024.png':[1024,1024], 'assets/landing/social-preview.png':[1280,640], 'assets/store/listing-light.png':[1280,800], 'assets/store/listing-dark.png':[1280,800]});
  for (const [file,[w,h]] of Object.entries(files)) {
    const png=read(file);
    assert.equal(png.subarray(1,4).toString(),'PNG',file);
    assert.equal(png.readUInt32BE(16),w,file);
    assert.equal(png.readUInt32BE(20),h,file);
    if(file.endsWith('social-preview.png')) assert.ok(png.length < 1_000_000);
  }
});
test('current product pages consistently present Linux-only scope', () => {
  for (const path of ['README.md','helper/README.md','docs/install.md','docs/helper-onboarding.md','docs/web-store-readiness.md','docs/privacy.md','docs/positioning.md','docs/claims.md','docs/index.html','docs/store-listing.md','assets/landing/page.html','assets/landing/hero.html','assets/landing/social-preview.html','assets/store/listing-light.html','assets/store/listing-dark.html']) {
    const content=read(path).toString();
    assert.match(content,/Mac support is coming soon\./,path);
    assert.doesNotMatch(content,/Linux and macOS|Linux\/macOS|macOS or Linux|macOS playback unverified|id="mac"|data-copy="mac"/,path);
  }
});

test('onboarding keeps the established manifest permissions and identity', () => {
  const m=JSON.parse(read('extension/manifest.json'));
  assert.equal(m.version,'0.2.5');
  assert.deepEqual(m.permissions,['activeTab','scripting','webRequest','webNavigation','nativeMessaging','alarms','storage']);
  assert.deepEqual(m.optional_host_permissions,['http://*/*','https://*/*']);
});
