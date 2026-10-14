import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';

const root=new URL('../../',import.meta.url);
const read=file=>readFileSync(new URL(file,root),'utf8');
const current=['README.md','helper/README.md','docs/install.md','docs/helper-onboarding.md','docs/positioning.md','docs/privacy.md','docs/privacy.html','docs/claims.md','docs/store-listing.md','docs/cross-platform-preview.md'];
const macGuide='docs/mac-install.md';
test('Mac setup links to the screenshot guide with explicit unsigned safety and publication boundaries',()=>{
  const setup=read('extension/setup.html'),guide=read(macGuide);
  assert.match(setup,/id="macInstallGuide" href="https:\/\/github\.com\/jcarcinogen\/PearPlay\/blob\/main\/docs\/mac-install\.md"/);
  for(const term of [/Open Anyway/,/Apple silicon/,/releases\/tag\/v0\.3\.3/i,/not an Apple-signed or notarized release/,/will damage your computer/,/contains malware/,/Do not change/,/do not run|does not run/i,/Chrome and Brave share/,/not evidence|not proof|not.*evidence/i])assert.match(guide,term);
  const images=[...guide.matchAll(/!\[[^\]]*\]\(([^)]+)\)/g)].map(m=>m[1]);
  assert.ok(images.length>=2,'screenshot guide needs actual images');
  for(const image of images)assert.ok(existsSync(new URL(image,new URL(macGuide,root))),image);
});
test('active docs qualify preview availability without fabricated candidate release URLs',()=>{
  for(const file of current){
    const text=read(file);
    assert.match(text,/Mac|macOS/,file);assert.match(text,/Windows/,file);assert.match(text,/preview|candidate|experimental|unsigned/i,file);
    assert.doesNotMatch(text,/Mac support is coming soon\.|Windows is not supported/,file);
    assert.doesNotMatch(text,/no public Mac download yet/i,file);
  }
  const preview=read('docs/cross-platform-preview.md');
  for(const term of [/source-only/,/Gatekeeper/,/quarantine/,/SmartScreen/,/DPAPI/,/not portable/,/human/,/same.*network/,/physical remote/])assert.match(preview,term);
});
test('owned documentation local Markdown/HTML links resolve to real repository files',()=>{
  for(const file of [...current,macGuide,'docs/safari-lessons-port.md','docs/web-store-readiness.md','docs/store-submission.md','docs/linux-only-scope.md','docs/mac-terminal-install.md','docs/refresh-report.md','docs/fedora-install.md']){
    const text=read(file),links=[...text.matchAll(/\]\(([^)]+)\)/g),...text.matchAll(/href="([^"]+)"/g)].map(match=>match[1]);
    for(const href of links){
      if(/^(?:https?:|mailto:|#)/.test(href))continue;
      const url=new URL(href.split('#')[0],new URL(file,root));
      assert.ok(existsSync(url),`${file} -> ${href}`);
    }
  }
});
test('privacy Markdown and static HTML describe the same policy paragraphs',()=>{
  const markdown=read('docs/privacy.md'),html=read('docs/privacy.html');
  const plain=text=>text.replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').replace(/<[^>]*>/g,'').replace(/\*\*/g,'').replace(/\s+/g,' ').trim();
  const md=markdown.split(/\n\s*\n/).filter(text=>!text.startsWith('#')).map(plain);
  const rendered=[...html.matchAll(/<p>([\s\S]*?)<\/p>/g)].map(match=>plain(match[1]));
  assert.deepEqual(rendered,md);
});
