// Smart Library - Windows Service host (.NET Framework 4.x built into Windows 11)
// Compilado no computador do usuario pelo Instalador (Windows PowerShell Add-Type).
// O servico hospeda o servidor Python como processo filho sem area de trabalho.
using System;
using System.IO;
using System.Diagnostics;
using System.ServiceProcess;
using System.Threading;
using System.Net;

namespace SmartLibraryService {
 public sealed class Host : ServiceBase {
  private Process child;
  private readonly object logLock = new object();
  private readonly string root;
  private readonly string logFile;
  private bool stopping;
  public Host() {
   ServiceName = "SmartLibraryLocal";
   CanStop = true;
   CanShutdown = true;
   AutoLog = true;
   root = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,".."));
   logFile = Path.Combine(root,"Dados","servico.log");
  }
  private void Log(string msg) {
   try { lock(logLock) { Directory.CreateDirectory(Path.GetDirectoryName(logFile));
     File.AppendAllText(logFile, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " | " + msg + Environment.NewLine); }
   } catch { }
  }
  protected override void OnStart(string[] args) {
   stopping=false;
   try {
    string python=File.ReadAllText(Path.Combine(root,"Servidor","python-servico.txt")).Trim();
    string script=Path.Combine(root,"Servidor","server.py");
    if (!File.Exists(python) || !File.Exists(script)) throw new FileNotFoundException("Python ou server.py nao encontrado. Execute Instalar Servico Windows.bat novamente.");
    ProcessStartInfo psi=new ProcessStartInfo(python,"-E -u -B \""+script+"\" --no-browser");
    psi.WorkingDirectory=root;
    psi.UseShellExecute=false;psi.CreateNoWindow=true;
    psi.RedirectStandardOutput=true;psi.RedirectStandardError=true;
    psi.EnvironmentVariables["SMART_LIBRARY_SERVICE"]="1";
    psi.EnvironmentVariables["PYTHONUNBUFFERED"]="1";
    // Nao herdar variaveis de instalacoes do Python incompatíveis.
    foreach(string k in new string[]{"PYTHONHOME","PYTHONPATH","PYTHONPLATLIBDIR","PYTHONUSERBASE"})
      psi.EnvironmentVariables.Remove(k);
    child = new Process();child.StartInfo=psi;
    child.EnableRaisingEvents=true;
    child.OutputDataReceived+=(s,e)=>{if(e.Data!=null)Log("PY | "+e.Data);};
    child.ErrorDataReceived+=(s,e)=>{if(e.Data!=null)Log("ERRO PY | "+e.Data);};
    child.Exited+=(s,e)=>{
      int exit=-1; try {exit=child.ExitCode;} catch { }
      Log("Servidor Python encerrou. ExitCode="+exit);
      if (!stopping) ThreadPool.QueueUserWorkItem(_=>{try {Stop();}catch{}});
    };
    if(!child.Start())throw new InvalidOperationException("Processo Python nao iniciou.");
    child.BeginOutputReadLine();child.BeginErrorReadLine();
    Log("Servico iniciado. Python="+python+" PID="+child.Id);
    // Nao bloqueia OnStart: o Windows precisa receber status RUNNING em poucos segundos.
    // Verificacao de prontidao em segundo plano e confirmacao adicional no instalador.
    ThreadPool.QueueUserWorkItem(_=>{
      bool ready=false;
      for(int i=0; i<25; i++) {
        try { if (child==null || child.HasExited) break; } catch { break; }
        try {
          HttpWebRequest request=(HttpWebRequest)WebRequest.Create("http://127.0.0.1:3000/api/status");
          request.Timeout=1200; request.ReadWriteTimeout=1200;
          using (HttpWebResponse response=(HttpWebResponse)request.GetResponse()) {
            if ((int)response.StatusCode==200) {ready=true;break;}
          }
        } catch (Exception) { }
        Thread.Sleep(500);
      }
      if(ready) Log("Servidor respondeu na porta 3000.");
      else Log("Servidor nao respondeu na porta 3000. Consulte este log para detalhes do Python.");
    });
   } catch(Exception e) { Log("FALHA START: "+e); throw; }
  }
  protected override void OnStop() {
   stopping=true;
   try {if(child!=null && !child.HasExited) { child.Kill();child.WaitForExit(5000); }}
   catch(Exception e){Log("Falha ao parar processo: "+e.Message);}
   finally {if(child!=null)child.Dispose(); Log("Servico parado.");}
  }
  protected override void OnShutdown() {OnStop();base.OnShutdown();}
  public static void Main(string[] args) {ServiceBase.Run(new Host());}
 }
}
