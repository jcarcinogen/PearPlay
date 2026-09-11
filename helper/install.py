"""User-scoped, no-overwrite installer. Source, venv and credentials are never removed."""
import json
import os
from pathlib import Path
import re
import shlex
import stat

def main(argv=None):
    import argparse
    import sys
    class Parser(argparse.ArgumentParser):
        def error(self, message): raise ValueError('invalid_install_arguments')
    parser=Parser(description='No-overwrite PearPlay user native host installer')
    parser.add_argument('action',choices=['install','uninstall'])
    parser.add_argument('--extension-id',required=True)
    parser.add_argument('--browser',required=True,choices=['chrome','brave'])
    parser.add_argument('--config-parent',required=True,type=Path)
    parser.add_argument('--python',required=True,type=Path)
    try:
        args=parser.parse_args(argv)
        kwargs=dict(extension_id=args.extension_id,browser=args.browser,config_parent=args.config_parent,python=args.python,source=Path(__file__).resolve().parents[1])
        result=install(**kwargs) if args.action=='install' else uninstall(**kwargs)
        print(json.dumps({'ok':True,'action':args.action,'preserved':result if isinstance(result,list) else []}))
        return 0
    except Exception:
        print('{"ok":false,"error":"install_failed"}')
        return 1

NAME = 'com.pearplay.helper'
BROWSERS = {'chrome': 'google-chrome', 'brave': 'BraveSoftware/Brave-Browser'}

def plan(*, extension_id, browser, config_parent, python, source, require_runtime=True):
    if not isinstance(extension_id, str) or not re.fullmatch(r'[a-p]{32}', extension_id) or browser not in BROWSERS:
        raise ValueError('invalid_install_arguments')
    parent, python, source = Path(config_parent), Path(python), Path(source)
    if not all(p.is_absolute() and '..' not in p.parts for p in (parent, python, source)):
        raise ValueError('absolute_paths_required')
    if require_runtime and (not python.is_file() or not os.access(python, os.X_OK) or not (source/'helper/native.py').is_file() or not (source/'spikes/002-command/command.py').is_file()):
        raise ValueError('missing_runtime')
    folder = parent/BROWSERS[browser]/'NativeMessagingHosts'
    paths = {'manifest':folder/(NAME+'.json'), 'launcher':folder/(NAME+'.launcher')}
    launcher = '#!/bin/sh\n# PearPlay owned launcher v1; URLs only on stdin.\nexec ' + shlex.quote(str(python)) + ' ' + shlex.quote(str(source/'helper/native.py')) + ' native --extension-id ' + extension_id + ' "$@"\n'
    manifest = json.dumps(dict(name=NAME, description='PearPlay experimental AirPlay helper', path=str(paths['launcher']), type='stdio', allowed_origins=['chrome-extension://'+extension_id+'/']), indent=2)+'\n'
    return paths, {'manifest':(manifest.encode(),0o600), 'launcher':(launcher.encode(),0o700)}

def directory(path, create):
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if create:
                try: os.mkdir(part,0o700,dir_fd=fd)
                except FileExistsError: pass
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd
        info=os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o022: raise ValueError('unsafe_install_directory')
        return fd
    except BaseException:
        os.close(fd);raise

def matches(fd, name, content, mode):
    try:
        file=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
    except FileNotFoundError: return None
    except OSError: return False
    with os.fdopen(file,'rb') as stream:
        info=os.fstat(stream.fileno())
        return stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==mode and stream.read(len(content)+1)==content

def install(**kwargs):
    paths, payloads=plan(**kwargs)
    fd=directory(paths['manifest'].parent,True)
    created=[]
    try:
        for key,path in paths.items():
            if matches(fd,path.name,*payloads[key]) is False: raise ValueError('existing_file_not_owned')
        for key in ('launcher','manifest'):
            path=paths[key];content,mode=payloads[key]
            if matches(fd,path.name,content,mode): continue
            file=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode,dir_fd=fd)
            created.append(key)
            with os.fdopen(file,'wb') as stream:
                os.fchmod(stream.fileno(),mode);stream.write(content);stream.flush();os.fsync(stream.fileno())
        os.fsync(fd)
        return paths
    except BaseException:
        for key in created:
            if matches(fd,paths[key].name,*payloads[key]): os.unlink(paths[key].name,dir_fd=fd)
        raise
    finally: os.close(fd)

def uninstall(**kwargs):
    paths,payloads=plan(**kwargs, require_runtime=False)
    try: fd=directory(paths['manifest'].parent,False)
    except FileNotFoundError: return []
    preserved=[]
    try:
        for key,path in paths.items():
            match=matches(fd,path.name,*payloads[key])
            if match: os.unlink(path.name,dir_fd=fd)
            elif match is False: preserved.append(key)
        os.fsync(fd)
    finally: os.close(fd)
    return preserved

if __name__ == '__main__':
    raise SystemExit(main())
