import sys,json,stat,subprocess
from pathlib import Path
root=Path(sys.argv[1]);repo=Path('/home/scott/Projects/PearPlay');sys.path.insert(0,str(repo))
from helper.install import plan,uninstall
out={}
for name in (sys.argv[2:] or ['xdg','lookup','browser']):
 kwargs=dict(extension_id='gndkmajngklgjkcmbolddaodljgoabma',browser='chrome',config_parent=root/name,python=repo/'.venv/bin/python',source=repo)
 paths,payloads=plan(**kwargs)
 installed={key:dict(path=str(p),exists=p.exists(),exact=p.read_bytes()==payloads[key][0],mode=oct(stat.S_IMODE(p.stat().st_mode))) for key,p in paths.items()}
 assert all(x['exact'] for x in installed.values())
 sentinel=paths['manifest'].parent/'pearplay-test-unknown.keep'
 if not sentinel.exists():
  with sentinel.open('x') as stream: stream.write('Owned test sentinel: uninstall must preserve unknown files.\n')
  sentinel.chmod(0o600)
 preserved=uninstall(**kwargs)
 absent={key:not p.exists() for key,p in paths.items()};assert all(absent.values());assert sentinel.read_text()=='Owned test sentinel: uninstall must preserve unknown files.\n'
 out[name]=dict(installed=installed,uninstall_preserved=preserved,removed=absent,unknown_file_preserved=str(sentinel))
(root/('install-uninstall-latest.json' if len(sys.argv)>2 else 'install-uninstall.json')).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
