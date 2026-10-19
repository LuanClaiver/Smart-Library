# LEGADO: nao use para instalacao; prefira Ferramentas/Instalar-Servico.ps1.
"""Servico Windows nativo (ctypes, sem pywin32/NSSM). Instalar via admin."""
from __future__ import annotations
import ctypes, os, subprocess, sys, threading, traceback
from ctypes import wintypes
from pathlib import Path

NAME = 'SmartLibraryLocal'
DISPLAY = 'Smart Library - Biblioteca Local'
BASE = Path(__file__).resolve().parent.parent
LOG = BASE / 'Dados' / 'servico.log'


def manage(action):
    if os.name != 'nt':
        raise RuntimeError('Instalacao de servico disponivel somente no Windows.')
    if action == 'install':
        # Usar o Python EXATO que executou o instalador. O script roda com caminho absoluto.
        command = subprocess.list2cmdline([str(Path(sys.executable).resolve()), str(Path(__file__).resolve()), 'run'])
        res = subprocess.run(['sc.exe','create', NAME, 'binPath=', command, 'start=', 'auto', 'DisplayName=',DISPLAY], capture_output=True, text=True, errors='replace')
        if res.returncode:raise RuntimeError('Falha ao criar o servico: '+(res.stdout+res.stderr))
        subprocess.run(['sc.exe','description',NAME,'Catalogo multimidia local na porta 3000.'],capture_output=True)
        # Service recovery em caso de falha de processo, com atraso.
        subprocess.run(['sc.exe','failure', NAME,'reset=', '86400','actions=', 'restart/60000/restart/60000/none/0'],capture_output=True)
        try:
            start = subprocess.run(['sc.exe','start',NAME], capture_output=True, text=True, errors='replace')
            if start.returncode:print('[AVISO] Instalado, mas nao iniciou. Verifique porta 3000 e Dados\\servico.log.\n'+start.stdout+start.stderr)
            else:print('Servico instalado e iniciado. URL: http://127.0.0.1:3000')
        except Exception as e:print('Servico criado. Erro ao iniciar:',e)
    elif action == 'uninstall':
        subprocess.run(['sc.exe','stop',NAME],capture_output=True)
        import time
        for _ in range(15):
            s=subprocess.run(['sc.exe','query',NAME],capture_output=True,text=True,errors='replace')
            if 'STOPPED' in s.stdout or '1060' in s.stdout:break
            time.sleep(1)
        res=subprocess.run(['sc.exe','delete',NAME],capture_output=True,text=True,errors='replace')
        if res.returncode:raise RuntimeError(res.stdout+' '+res.stderr)
        print('Servico removido; dados e arquivos mantidos.')
    elif action in ('start','stop','query'):
        subprocess.run(['sc.exe',action,NAME],check=True)


def service_main():
    if os.name != 'nt':raise RuntimeError('Somente Windows')
    from ctypes import WINFUNCTYPE
    SERVICE_WIN32_OWN_PROCESS=0x10
    SERVICE_START_PENDING=2;SERVICE_RUNNING=4;SERVICE_STOP_PENDING=3;SERVICE_STOPPED=1
    SERVICE_ACCEPT_STOP=1; SERVICE_CONTROL_STOP=1; SERVICE_CONTROL_SHUTDOWN=5
    class SERVICE_STATUS(ctypes.Structure):
        _fields_=[('dwServiceType',wintypes.DWORD),('dwCurrentState',wintypes.DWORD),('dwControlsAccepted',wintypes.DWORD),('dwWin32ExitCode',wintypes.DWORD),('dwServiceSpecificExitCode',wintypes.DWORD),('dwCheckPoint',wintypes.DWORD),('dwWaitHint',wintypes.DWORD)]
    Handler=WINFUNCTYPE(wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.LPVOID)
    ServiceMain=WINFUNCTYPE(None,wintypes.DWORD,ctypes.POINTER(wintypes.LPWSTR))
    class TABLE(ctypes.Structure):
        _fields_=[('name',wintypes.LPWSTR),('main',ServiceMain)]
    adv=ctypes.WinDLL('advapi32',use_last_error=True)
    adv.RegisterServiceCtrlHandlerExW.argtypes=(wintypes.LPCWSTR, Handler, wintypes.LPVOID)
    adv.RegisterServiceCtrlHandlerExW.restype=wintypes.HANDLE
    adv.SetServiceStatus.argtypes=(wintypes.HANDLE,ctypes.POINTER(SERVICE_STATUS))
    adv.SetServiceStatus.restype=wintypes.BOOL
    adv.StartServiceCtrlDispatcherW.argtypes=(ctypes.POINTER(TABLE),)
    adv.StartServiceCtrlDispatcherW.restype=wintypes.BOOL
    stopped=threading.Event()
    service_handle=None
    def report(state,accepted=0,wait=0,code=0):
        status=SERVICE_STATUS(SERVICE_WIN32_OWN_PROCESS,state,accepted,code,0,0,wait)
        if service_handle:adv.SetServiceStatus(service_handle,ctypes.byref(status))
    @Handler
    def on_control(control,event_type,event_data,context):
        if control in (SERVICE_CONTROL_STOP,SERVICE_CONTROL_SHUTDOWN):
            report(SERVICE_STOP_PENDING,wait=10000)
            stopped.set()
        return 0
    @ServiceMain
    def main_cb(argc,argv):
        nonlocal service_handle
        service_handle=adv.RegisterServiceCtrlHandlerExW(NAME,on_control,None)
        if not service_handle:return
        report(SERVICE_START_PENDING,wait=10000)
        BASE.joinpath('Dados').mkdir(exist_ok=True)
        # Servicos nao tem console. Redireciona logs somente durante execucao.
        import server
        os.environ['SMART_LIBRARY_SERVICE']='1'
        server.SERVICE_MODE=True
        try:
            with LOG.open('a',encoding='utf-8',buffering=1) as output:
                sys.stdout=output;sys.stderr=output
                print('\n[SMART LIBRARY] Servico iniciando...',flush=True)
                report(SERVICE_RUNNING,accepted=SERVICE_ACCEPT_STOP)
                server.main(stop_event=stopped,service_mode=True)
                print('[SMART LIBRARY] Servico encerrado.',flush=True)
        except BaseException:
            try:
                with LOG.open('a',encoding='utf-8') as f:traceback.print_exc(file=f)
            except OSError:pass
        finally:
            report(SERVICE_STOPPED)
    t=(TABLE*2)()
    t[0].name=NAME;t[0].main=main_cb
    t[1].name=None
    if not adv.StartServiceCtrlDispatcherW(t):
        raise ctypes.WinError(ctypes.get_last_error())

if __name__=='__main__':
    try:
        cmd=sys.argv[1] if len(sys.argv)>1 else 'run'
        if cmd=='run':service_main()
        else:manage(cmd)
    except Exception as e:
        print('ERRO:',e,file=sys.stderr)
        sys.exit(1)
