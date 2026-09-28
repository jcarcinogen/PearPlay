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
test('public marketing copy avoids naming trial sites and test machines', () => {
  for (const path of ['README.md','assets/landing/readme.html','assets/landing/page.html','docs/index.html','docs/store-listing.md','docs/claims.md','docs/positioning.md']) {
    const content=read(path).toString();
    assert.doesNotMatch(content,/\b(?:FOX(?: 13)?|Acer|LG C5|Xubuntu|Fedora\/GNOME)\b/,path);
    assert.match(content,/Apple TV/,path);
  }
});

test('public screenshots and Pages reflect reported browser playback without unwanted claims', () => {
  for (const path of ['assets/store/listing-light.html','assets/store/listing-dark.html','assets/landing/page.html','docs/store-listing.md','README.md']) {
    const content=read(path).toString();
    assert.match(content,/Chrome/i,path);
    assert.match(content,/Brave/i,path);
    assert.match(content,/Chromium/i,path);
    assert.doesNotMatch(content,/Brave\/Chromium unverified|Brave playback remains unverified|Brave registration is implemented; end-to-end integration remains unverified|TV pause\/resume unavailable|not a live TV claim|not a live-playback claim|LG HLS/i,path);
  }
  for(const path of ['assets/store/listing-light.html','assets/store/listing-dark.html','assets/landing/page.html']) {
    assert.match(read(path).toString(),/Chrome, Brave (?:and |&amp; )?Chromium/i,path);
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
  assert.equal(m.version,'0.2.7');
  assert.deepEqual(m.permissions,['activeTab','scripting','webRequest','webNavigation','nativeMessaging','alarms','storage']);
  assert.deepEqual(m.optional_host_permissions,['http://*/*','https://*/*']);
});

test('landing template stays synchronized with the edited site (preserved install edits)', () => {
  const page=read('assets/landing/page.html').toString();
  for (const phrase of ['Flatpak-installed','Chrome Web Store','currently 0.2.6','Fedora helper','Store installs do not need that folder','Closing only a tab or reloading the extension is not enough']) {
    assert.match(page,new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')),phrase);
  }
  assert.doesNotMatch(page,/not yet submitted or public/);
  assert.doesNotMatch(page,/Keep the unpacked extension folder in place until the Store listing is available/);
});

test('compact popup and marketing frames use 400px width, not the old 360px viewport', () => {
  assert.match(read('extension/popup.html').toString(),/width:400px/);
  for (const path of ['assets/store/listing-light.html','assets/store/listing-dark.html']) {
    const c=read(path).toString();
    assert.match(c,/width:400px/,path);
    assert.doesNotMatch(c,/width:360px/,path);
  }
  const page=read('assets/landing/page.html').toString();
  assert.match(page,/width:min\(100%,400px\)/,'page product width');
  assert.doesNotMatch(page,/width="360"/,'page product img width');
});

test('store and landing copy drop the stale scroll-for-session instruction', () => {
  for (const path of ['assets/landing/page.html','assets/store/listing-light.html','assets/store/listing-dark.html']) {
    assert.doesNotMatch(read(path).toString(),/scroll for session|Scroll in the popup/,path);
  }
});

test('manifest version is well-formed and the offline verifier does not pin a stale version', () => {
  const m=JSON.parse(read('extension/manifest.json'));
  assert.match(m.version,/^\d+\.\d+\.\d+$/);
  assert.doesNotMatch(read('scripts/verify-brand-assets.py').toString(),/current\["version"\] == "0\.2\.5"/);
});
