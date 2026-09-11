"""Isolated policy process. It receives public action replies, never cases."""
from __future__ import annotations
import importlib
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback

WIRE=sys.stdout
sys.stdout=sys.stderr


def send(value):
    WIRE.write(json.dumps(value,allow_nan=False,separators=(',',':'))+'\n');WIRE.flush()


def receive():
    line=sys.stdin.readline()
    if not line:raise EOFError('Evaluator disconnected')
    return json.loads(line)


def protect(root):
    allowed=[root.resolve(),Path(sys.base_prefix).resolve(),Path(__file__).resolve().parent]
    def audit(event,args):
        if event.startswith(('socket.','subprocess.','ctypes.')) or event in ('os.system','os.exec','os.posix_spawn','os.spawn'):
            raise PermissionError('Comparison worker forbids network/process/native actions')
        if event=='open':
            path,mode,flags=args
            if isinstance(mode,str) and any(c in mode for c in 'wax+') or isinstance(flags,int) and flags & (1|2|64|512|1024):
                raise PermissionError('Comparison worker is read-only')
            if isinstance(path,(str,bytes)):
                resolved=Path(path).resolve()
                if not any(resolved.is_relative_to(p) for p in allowed):raise PermissionError('Read outside worker roots')
    sys.addaudithook(audit)


class PublicProxy:
    __slots__=('position','current_channel','virtual_time_s','entered','exited')
    def __init__(self):
        self.position=(0.,0.);self.current_channel=1;self.virtual_time_s=0.;self.entered=False;self.exited=False
    def exchange(self,path,payload=None):
        send({'type':'action','path':path,'payload':payload or {}})
        answer=receive()
        if 'error' in answer:raise RuntimeError(answer['error'])
        state=answer['public_state'];self.position=tuple(state['position']);self.current_channel=state['current_channel']
        self.virtual_time_s=state['virtual_time_s']
        if path=='/enter':self.entered=True
        if path=='/exit':self.exited=True
        return answer['response']
    def enter(self):return self.exchange('/enter')
    def exit(self):return self.exchange('/exit')
    def check_budget(self):
        if not self.entered or self.exited or self.virtual_time_s>=360000:raise RuntimeError('Public action budget exhausted')
    def measure(self,position,channel):
        return self.exchange('/measure',{'position':{'x':position[0],'y':position[1]},'channel':channel})
    def clear(self,position,channel):
        return self.exchange('/clear',{'position':{'x':position[0],'y':position[1]},'channel':channel})


def main():
    implementation,root_text,problem_text=sys.argv[1:4];root=Path(root_text).resolve();problem=int(problem_text)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(root));protect(root)
    if implementation=='teammate':
        config=json.loads((root/f'problem{problem}/config.json').read_text(encoding='utf-8-sig'))
        expected='phase3_intercept' if problem==3 else 'phase3_optical_nonuniform'
        if config['branch']!=expected:raise ValueError('Unexpected archived default')
        protocol=importlib.import_module('problem3.protocol')
        factory=importlib.import_module('problem3.phase3_intercept' if problem==3 else 'problem4.phase3_candidate').factory
    else:
        target=sys.argv[4] if len(sys.argv)>4 else ('problem3.experiments_v3.optical_band:AggressiveBandPolicy' if problem==3 else 'problem4.experiments_v3.posterior:Shared21Policy')
        module,name=target.split(':')
        if not module.startswith(f'problem{problem}.'):raise ValueError('Target must match the selected problem')
        policy_class=getattr(importlib.import_module(module),name)
        config={'branch':module+':'+name}
    imported={name:str(Path(module.__file__).resolve()) for name,module in list(sys.modules.items())
              if name.startswith(('problem3','problem4')) and getattr(module,'__file__',None)}
    if any(not Path(path).is_relative_to(root) for path in imported.values()):raise RuntimeError('Namespace contamination')
    hashes={name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in imported.items()}
    send({'type':'ready','implementation':implementation,'problem':problem,'config':config,'imports':imported,'imports_sha256':hashes})
    while True:
        command=receive()
        if command.get('type')=='stop':return
        if command.get('type')!='run':raise ValueError('Only a run token is accepted; no case data')
        proxy=PublicProxy();started=time.perf_counter();cpu=time.process_time();result={};error=None
        try:
            if implementation=='teammate':
                api=protocol.Client(proxy.exchange,real_guard=True)
                options=config.get('candidate_options',{}) if problem==3 else {}
                policy=factory(api,problem,parameters=config['parameters'],**options)
                result=policy.run()
            else:
                proxy.enter();policy=policy_class(problem=problem);result=policy.run(proxy);proxy.exit()
        except BaseException as exc:
            error=f'{type(exc).__name__}: {exc}'
            traceback.print_exc(file=sys.stderr)
        ended_normally=proxy.exited
        # Cleanup is recorded separately; it never converts an error to success.
        if proxy.entered and not proxy.exited:
            try:proxy.exit()
            except Exception:pass
        send({'type':'result','policy':result,'error':error,'normal_exit':ended_normally,'exited':proxy.exited,
              'policy_cpu_s':time.process_time()-cpu,'policy_wall_s':time.perf_counter()-started})


if __name__=='__main__':main()
