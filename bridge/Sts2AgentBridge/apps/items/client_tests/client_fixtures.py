from __future__ import annotations
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
from dataclasses import replace
import unittest
from unittest import mock

ROOT = Path(__file__).absolute().parents[1]
sys.path[:0] = [str(ROOT / 'client'), str(ROOT / 'operations'), str(ROOT.parents[1])]
import secure_operator as reader
import run_live as client
import manage_live_campaign as manager
import manage_live_campaign_fixtures as manager_fixtures
from components.item_transport.transport import item_transport as transport
from components.item_transport.transport_tests.test_item_transport import READY, ACCEPTED, RESOLVED, http

class Fixture:
    def __enter__(self):
        self.context = tempfile.TemporaryDirectory(prefix='item-client-fixture-', dir='/private/tmp')
        self.root = Path(self.context.__enter__())
        self.home = self.root / 'synthetic-profile'
        self.item = self.home / 'Library' / 'Application Support' / 'Sts2AgentBridge' / 'item_v1'
        self.item.mkdir(parents=True, mode=0o700)
        for p in [self.home, self.home/'Library', self.item.parent.parent, self.item.parent, self.item]: p.chmod(0o700)
        (self.item/'config.json').write_bytes(reader.ENABLED)
        (self.item/'credential.hex').write_bytes(b'a5'*32)
        for p in self.item.iterdir(): p.chmod(0o600)
        self.state = SimpleNamespace()
        for prefix, p in [('application_support',self.item.parent.parent),('operator',self.item.parent),
                          ('config',self.item),('config_file',self.item/'config.json'),('credential',self.item/'credential.hex')]:
            s=p.stat(); setattr(self.state,prefix+'_device',s.st_dev); setattr(self.state,prefix+'_inode',s.st_ino)
        self.opened=[]; self.closed=[]; self.read_buffers=[]; self.fail_close=False; self.read_hook=None
        actual_os=os
        fixture=self
        class Ops:
            def __getattr__(self,name): return getattr(actual_os,name)
            def open(self,name,flags,*,dir_fd=None):
                fd=actual_os.open(fixture.root if name=='/' else name,flags,dir_fd=dir_fd)
                fixture.opened.append(fd); return fd
            def stat(self,name,**kwargs): return actual_os.stat(fixture.root if name=='/' else name,**kwargs)
            def close(self,fd):
                fixture.closed.append(fd); actual_os.close(fd)
                if fixture.fail_close: raise OSError('synthetic cleanup')
            def readv(self,fd,buffers):
                fixture.read_buffers.append(buffers[0].obj)
                count=actual_os.readv(fd,buffers)
                if fixture.read_hook: fixture.read_hook(fd,count)
                return count
        self.ops=Ops()
        return self
    def read(self,acl=lambda fd:None):
        with mock.patch.object(reader,'os',self.ops):
            return reader.read_credential(Path('/synthetic-profile'),os.geteuid(),self.state,acl)
    def __exit__(self,*args):
        try:
            if sorted(self.opened)!=sorted(self.closed): raise AssertionError('descriptor leak')
        finally: self.context.__exit__(*args)

class ClientTests(unittest.TestCase):
    def test_exact_transfer_after_cleanup(self):
        with Fixture() as f:
            token=f.read(manager.require_no_granting_acl_fd)
            self.assertEqual(token,bytearray(b'a5'*32))
            self.assertEqual(sorted(f.opened),sorted(f.closed))
            self.assertTrue(all(not any(b) for b in f.read_buffers if b is not token))
            reader.zero(token)

    def test_config_failures_no_credential_read(self):
        values=[reader.ENABLED.replace(b'true',b'false'),b'{}',reader.ENABLED+b'\n',reader.ENABLED.replace(b'item_probe_v1',b'live_probe_v0')]
        for data in values:
            with self.subTest(data_size=len(data)), Fixture() as f:
                (f.item/'config.json').write_bytes(data)
                with self.assertRaises(reader.OperatorFailure): f.read()
                self.assertTrue(all(not any(b) for b in f.read_buffers))
                self.assertLessEqual(len(f.opened),8)

    def test_metadata_and_pins(self):
        for mutation in ('mode','symlink','hardlink','directory','wrong_pin','upper','short','long','parent_mode'):
            with self.subTest(mutation=mutation), Fixture() as f:
                path=f.item/'credential.hex'
                if mutation=='mode': path.chmod(0o644)
                elif mutation=='symlink': path.rename(f.item/'saved'); path.symlink_to('saved')
                elif mutation=='hardlink': os.link(path,f.item/'linked')
                elif mutation=='directory': path.unlink(); path.mkdir()
                elif mutation=='wrong_pin': f.state.credential_inode+=1
                elif mutation=='upper': path.write_bytes(b'AF'*32)
                elif mutation=='short': path.write_bytes(b'a'*63)
                elif mutation=='long': path.write_bytes(b'a'*65)
                else: f.item.parent.chmod(0o755)
                with self.assertRaises((reader.OperatorFailure,OSError)): f.read()
                self.assertTrue(all(not any(b) for b in f.read_buffers))

    def test_replacement_and_in_place_mutation(self):
        for mutation in ('replace_config','replace_credential','in_place'):
            with self.subTest(mutation=mutation), Fixture() as f:
                triggered=False
                def change(fd,count):
                    nonlocal triggered
                    if triggered or not count: return
                    if mutation=='replace_config' or len(f.read_buffers)>2:
                        triggered=True
                        path=f.item/('config.json' if mutation=='replace_config' else 'credential.hex')
                        if mutation=='in_place': path.write_bytes(b'b'*64)
                        else:
                            path.rename(f.item/'moved'); path.write_bytes(reader.ENABLED if mutation=='replace_config' else b'a5'*32); path.chmod(0o600)
                f.read_hook=change
                with self.assertRaises(reader.OperatorFailure): f.read()
                self.assertTrue(triggered)
                self.assertTrue(all(not any(b) for b in f.read_buffers))

    def test_acl_failure_and_close_failure(self):
        with Fixture() as f:
            def bad_acl(fd): raise reader.OperatorFailure()
            with self.assertRaises(reader.OperatorFailure): f.read(bad_acl)
        with Fixture() as f:
            f.fail_close=True
            with self.assertRaises(reader.OperatorFailure): f.read()
            self.assertTrue(all(not any(b) for b in f.read_buffers))

    def test_interrupted_and_failed_read_zeroing(self):
        for error, close_fault in ((KeyboardInterrupt(),False),(OSError('synthetic'),False),(KeyboardInterrupt(),True)):
            with Fixture() as f:
                def stop(fd,count):
                    if len(f.read_buffers)>2: raise error
                f.read_hook=stop
                f.fail_close=close_fault
                with self.assertRaises(type(error)): f.read()
                self.assertTrue(all(not any(b) for b in f.read_buffers))

    def test_composition_one_call_and_zero(self):
        for error in (None,RuntimeError('synthetic'),KeyboardInterrupt()):
            token=bytearray(b'a5'*32); calls=[]
            def collect(value):
                calls.append(value)
                if error: raise error
                return {'schema_version':1,'status':'failed','code':'item_transport_failure'}
            operation=lambda: client.run_once('0'*64,lambda value:(SimpleNamespace(user_profile=Path('/synthetic')),object()),lambda *args:token,collect,lambda fd:None)
            if isinstance(error,KeyboardInterrupt):
                with self.assertRaises(type(error)): operation()
            else: self.assertEqual(operation()['status'],'failed')
            self.assertEqual(len(calls),1); self.assertFalse(any(token))

    def test_preflight_failure_never_calls_reader_or_transport(self):
        for where in ('validate','read'):
            calls=[]
            def validate(value):
                if where=='validate': raise ValueError()
                return SimpleNamespace(user_profile=Path('/synthetic')),object()
            def read(*args): calls.append('read'); raise ValueError()
            with self.assertRaises(ValueError): client.run_once('0'*64,validate,read,lambda value:calls.append('collect'),lambda fd:None)
            self.assertNotIn('collect',calls)
            if where=='validate': self.assertEqual(calls,[])

    def test_real_manager_reader_client_binding(self):
        with Fixture() as f:
            tree=manager_fixtures.FixtureTree(f.root/'composed')
            manager_fixtures._install(tree)
            f.root=tree.root
            layout=replace(tree.layout,user_profile=Path('/synthetic-profile'))
            calls=[]
            def collect(token):
                calls.append(token)
                self.assertEqual(token,bytearray(b'a5'*32))
                return {'schema_version':1,'status':'failed','code':'item_transport_failure'}
            with (mock.patch.object(manager.pwd,'getpwuid',return_value=SimpleNamespace(pw_dir='/synthetic-profile')),
                  mock.patch.object(manager,'_production_layout',return_value=layout),
                  mock.patch.object(manager,'CANONICAL_ARTIFACTS',manager_fixtures._POLICY),
                  mock.patch.object(manager,'_read_mutable_file',side_effect=AssertionError('duplicate credential read')),
                  mock.patch.object(reader,'os',f.ops)):
                result=client.run_once(tree.state_sha256,manager.validate_installed_for_client,
                                       reader.read_credential,collect,manager.require_no_granting_acl_fd)
            self.assertEqual(result['status'],'failed'); self.assertEqual(len(calls),1)
            self.assertFalse(any(calls[0]))

    def test_cli_invalid_inputs_sanitized(self):
        for args in ([],['--path','/synthetic-secret'],['--expected-state-sha256','BAD']):
            result=subprocess.run([sys.executable,'-B','-I','-S',str(ROOT/'client'/'run_live.py'),*args],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,4); self.assertEqual(result.stderr,'')
            self.assertEqual(json.loads(result.stdout),{'schema_version':1,'status':'failed','code':'item_client_preflight_failed'})

    def test_ephemeral_frozen_controller_success_and_uncertainty(self):
        for uncertain in (False,True):
            with self.subTest(uncertain=uncertain), Fixture() as f:
                listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM); listener.bind(('127.0.0.1',0)); listener.listen(3); listener.settimeout(4)
                endpoint=listener.getsockname(); requests=[]; errors=[]
                responses=[READY,None] if uncertain else [READY,ACCEPTED,RESOLVED]
                def serve():
                    try:
                        for body in responses:
                            conn,_=listener.accept()
                            with conn:
                                conn.settimeout(3); request=bytearray()
                                while True:
                                    chunk=conn.recv(1024)
                                    if not chunk: break
                                    request.extend(chunk)
                                    if len(request)>4096: raise AssertionError('request overrun')
                                requests.append(request)
                                if body is not None: conn.sendall(http(body))
                    except BaseException as exc: errors.append(type(exc).__name__)
                    finally: listener.close()
                thread=threading.Thread(target=serve); thread.start()
                class Redirect:
                    def __init__(self): self.socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                    def connect(self,actual):
                        if actual!=('127.0.0.1',43117): raise AssertionError()
                        self.socket.connect(endpoint)
                    def __getattr__(self,name): return getattr(self.socket,name)
                def collect(token):
                    import time
                    return transport._run_with_socket_factory(token,Redirect,clock=time.monotonic,sleep=time.sleep)
                with mock.patch.object(reader,'os',f.ops):
                    result=client.run_once('0'*64,lambda value:(SimpleNamespace(user_profile=Path('/synthetic-profile')),f.state),reader.read_credential,collect,lambda fd:None)
                thread.join(5)
                self.assertFalse(thread.is_alive()); self.assertEqual(errors,[])
                self.assertEqual(result['status'],'failed' if uncertain else 'passed')
                self.assertEqual(sum(r.startswith(b'POST ') for r in requests),1)
                self.assertEqual(len(requests),2 if uncertain else 3)
                self.assertTrue(all(not any(b) for b in f.read_buffers))
                for request in requests: reader.zero(request)

if __name__=='__main__':
    result=unittest.TextTestRunner(stream=sys.stderr,verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(ClientTests))
    if result.wasSuccessful(): print(json.dumps({'schema_version':1,'status':'passed','suite':'item_v1_client','check_count':result.testsRun},separators=(',',':')))
    raise SystemExit(0 if result.wasSuccessful() else 1)
