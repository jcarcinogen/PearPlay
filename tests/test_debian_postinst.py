"""Real maintainer-hook execution in a root-mapped, networkless filesystem fixture."""
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import pytest

ROOT=Path(__file__).resolve().parents[1]

def builder():
    spec=importlib.util.spec_from_file_location('debian_build_tests',ROOT/'scripts/build_helper.py')
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def run_hook(fixture,script,action='configure',binds=()):
    if sys.platform!='linux' or not shutil.which('bwrap'):
        pytest.skip('requires Linux bubblewrap user namespaces; exercised on Acer')
    hook=fixture/'postinst';hook.write_text(script);hook.chmod(0o755)
    libraries=[arg for path in ('/lib','/lib64') if Path(path).exists() for arg in ('--ro-bind',path,path)]
    return subprocess.run(['bwrap','--unshare-all','--uid','0','--gid','0','--die-with-parent','--bind',str(fixture),'/',
                           '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin',*libraries,
                           '--dev','/dev','--proc','/proc',*binds,'--','/bin/sh','/postinst',action],
                          capture_output=True,text=True,timeout=15)

def test_configure_repairs_only_packaged_runtime_directories(tmp_path):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    generate=getattr(builder(),'debian_postinst',None)
    assert callable(generate),'Debian upgrade directory repair hook is missing'
    script=generate(stage)
    fixture=tmp_path/'fixture';(fixture/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    for directory in (fixture/'opt/pearplay',fixture/'opt/pearplay/PearPlayHelper',fixture/'opt/pearplay/PearPlayHelper/_internal'):
        directory.chmod(0o775)
    untouched=fixture/'opt/pearplay/not-in-package';untouched.mkdir(mode=0o700)
    data=fixture/'opt/pearplay/PearPlayHelper/_internal/build.json';data.write_text('untouched');data.chmod(0o644)
    home=fixture/'home/example';home.mkdir(parents=True,mode=0o700)
    before=(data.read_bytes(),stat.S_IMODE(data.stat().st_mode),stat.S_IMODE(home.stat().st_mode))
    result=run_hook(fixture,script)
    assert result.returncode==0,result.stderr
    for relative in ('opt/pearplay','opt/pearplay/PearPlayHelper','opt/pearplay/PearPlayHelper/_internal'):
        assert stat.S_IMODE((fixture/relative).stat().st_mode)==0o755
    assert stat.S_IMODE((fixture/'opt').stat().st_mode)==0o755
    assert stat.S_IMODE(untouched.stat().st_mode)==0o700
    assert before==(data.read_bytes(),stat.S_IMODE(data.stat().st_mode),stat.S_IMODE(home.stat().st_mode))
    assert run_hook(fixture,script).returncode==0,'configure must be idempotent'


def test_symlink_rejection_happens_before_any_directory_change(tmp_path):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    script=builder().debian_postinst(stage)
    fixture=tmp_path/'fixture';(fixture/'opt/pearplay/PearPlayHelper').mkdir(parents=True)
    outside=fixture/'outside';outside.mkdir(mode=0o700)
    (fixture/'opt/pearplay/PearPlayHelper/_internal').symlink_to('/outside')
    (fixture/'opt/pearplay').chmod(0o775)
    before=stat.S_IMODE((fixture/'opt/pearplay').stat().st_mode)
    result=run_hook(fixture,script)
    assert result.returncode!=0,'hook must reject symlinked packaged directory'
    assert stat.S_IMODE(outside.stat().st_mode)==0o700
    assert stat.S_IMODE((fixture/'opt/pearplay').stat().st_mode)==before


def test_foreign_owned_directory_rejected_before_any_repair(tmp_path):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    script=builder().debian_postinst(stage)
    fixture=tmp_path/'fixture';(fixture/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    (fixture/'opt/pearplay').chmod(0o775)
    # Host root is unmapped in this single-user namespace, not fixture root.
    result=run_hook(fixture,script,binds=('--ro-bind','/usr/share','/opt/pearplay/PearPlayHelper/_internal'))
    assert result.returncode!=0
    assert stat.S_IMODE((fixture/'opt/pearplay').stat().st_mode)==0o775


def test_world_writable_ancestor_rejected_before_any_repair(tmp_path):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    script=builder().debian_postinst(stage)
    fixture=tmp_path/'fixture';(fixture/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    (fixture/'opt').chmod(0o777)
    (fixture/'opt/pearplay').chmod(0o775)
    result=run_hook(fixture,script)
    assert result.returncode!=0,'world-writable ancestor must not be trusted'
    assert stat.S_IMODE((fixture/'opt/pearplay').stat().st_mode)==0o775


def test_debian_control_installs_executable_hook_under_restrictive_umask(tmp_path):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    build=builder();write_control=getattr(build,'write_debian_control',None)
    assert callable(write_control),'native Debian branch must emit the reviewed postinst'
    old=os.umask(0o077)
    try:control=write_control(stage,'amd64','2.39')
    finally:os.umask(old)
    assert (control/'postinst').read_text()==build.debian_postinst(stage)
    assert stat.S_IMODE((control/'postinst').stat().st_mode)==0o755
    assert stat.S_IMODE((control/'control').stat().st_mode)==0o644
    assert stat.S_IMODE(control.stat().st_mode)==0o755
    assert 'libc6 (>= 2.39)' in (control/'control').read_text()


def test_mode_stat_failure_is_fail_closed_before_any_repair(tmp_path):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    script=builder().debian_postinst(stage)
    fixture=tmp_path/'fixture';(fixture/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    (fixture/'opt/pearplay').chmod(0o775)
    fake=tmp_path/'stat-error';fake.write_text('#!/bin/sh\n[ "$2" != %a ] || exit 1\nprintf "0:0\\n"\n');fake.chmod(0o755)
    result=run_hook(fixture,script,binds=('--ro-bind',str(fake),'/usr/bin/stat'))
    assert result.returncode!=0,'failed metadata probe must never authorize chmod'
    assert stat.S_IMODE((fixture/'opt/pearplay').stat().st_mode)==0o775


@pytest.mark.parametrize('action', ['abort-upgrade','abort-remove','abort-deconfigure','triggered',''])
def test_non_configure_actions_are_noop(tmp_path,action):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    fixture=tmp_path/'fixture';fixture.mkdir()
    result=run_hook(fixture,builder().debian_postinst(stage),action)
    assert result.returncode==0,result.stderr
    assert not (fixture/'opt').exists()


@pytest.mark.parametrize('fault', ['ancestor-symlink','missing-directory','regular-file'])
def test_invalid_ancestry_and_targets_do_not_mutate_other_targets(tmp_path,fault):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    fixture=tmp_path/'fixture';(fixture/'opt/pearplay/PearPlayHelper').mkdir(parents=True)
    root=fixture/'opt/pearplay';root.chmod(0o775)
    if fault=='ancestor-symlink':
        (fixture/'opt').rename(fixture/'outside');(fixture/'opt').symlink_to('/outside')
        root=fixture/'outside/pearplay';(root/'PearPlayHelper/_internal').mkdir()
    elif fault=='regular-file':(root/'PearPlayHelper/_internal').write_text('not a directory')
    result=run_hook(fixture,builder().debian_postinst(stage))
    assert result.returncode!=0
    assert stat.S_IMODE(root.stat().st_mode)==0o775


def test_group_writable_global_ancestor_is_rejected_without_changing_it(tmp_path):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    fixture=tmp_path/'fixture';(fixture/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    (fixture/'opt').chmod(0o775);(fixture/'opt/pearplay').chmod(0o775)
    result=run_hook(fixture,builder().debian_postinst(stage))
    assert result.returncode!=0,'global group-write cannot be safely repaired or trusted'
    assert stat.S_IMODE((fixture/'opt').stat().st_mode)==0o775
    assert stat.S_IMODE((fixture/'opt/pearplay').stat().st_mode)==0o775


def test_each_repair_revalidates_after_locking_its_parent(tmp_path):
    stage=tmp_path/'stage';(stage/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    fixture=tmp_path/'fixture';(fixture/'opt/pearplay/PearPlayHelper/_internal').mkdir(parents=True)
    for path in (fixture/'opt/pearplay',fixture/'opt/pearplay/PearPlayHelper'):
        path.chmod(0o775)
    outside=fixture/'outside';outside.mkdir(mode=0o700)
    shim=tmp_path/'chmod-replace'
    shim.write_text('#!/bin/sh\nset -eu\n/chmod-real "$@"\nif [ "$3" = /opt/pearplay ]; then\n /usr/bin/rmdir /opt/pearplay/PearPlayHelper/_internal\n /usr/bin/ln -s /outside /opt/pearplay/PearPlayHelper/_internal\nfi\n');shim.chmod(0o755)
    result=run_hook(fixture,builder().debian_postinst(stage),binds=('--ro-bind','/usr/bin/chmod','/chmod-real','--ro-bind',str(shim),'/usr/bin/chmod'))
    assert result.returncode!=0,'replacement after preflight must be rejected'
    assert stat.S_IMODE(outside.stat().st_mode)==0o700

