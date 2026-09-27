using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

// A private, unnamed job owns the suspended root before it can spawn descendants.
public sealed class AdmissionOwnedJob : IDisposable {
    IntPtr job;
    public Process Process { get; private set; }
    [StructLayout(LayoutKind.Sequential)] struct IO { public ulong a,b,c,d,e,f; }
    [StructLayout(LayoutKind.Sequential)] struct BasicLimit {
        public long a,b; public uint flags; public UIntPtr min,max; public uint active;
        public UIntPtr affinity; public uint priority,scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] struct ExtendedLimit {
        public BasicLimit basic; public IO io; public UIntPtr process,job,peakProcess,peakJob;
    }
    [StructLayout(LayoutKind.Sequential)] struct Accounting {
        public long a,b,c,d; public uint faults,total,active,terminated;
    }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] struct Startup {
        public uint cb; public string reserved,desktop,title; public uint x,y,w,h,cw,ch,fill,flags;
        public ushort show,reserved2; public IntPtr reservedPtr,input,output,error;
    }
    [StructLayout(LayoutKind.Sequential)] struct Info { public IntPtr process,thread; public uint pid,tid; }
    [StructLayout(LayoutKind.Sequential)] struct Security { public uint length; public IntPtr descriptor; public int inherit; }
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr attributes,string name);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job,int type,ref ExtendedLimit info,uint size);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool QueryInformationJobObject(IntPtr job,int type,ref Accounting info,uint size,IntPtr length);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job,IntPtr process);
    [DllImport("kernel32.dll", SetLastError=true,CharSet=CharSet.Unicode)] static extern bool CreateProcess(string app,StringBuilder command,IntPtr pa,IntPtr ta,bool inherit,uint flags,IntPtr environment,string cwd,ref Startup startup,out Info info);
    [DllImport("kernel32.dll", SetLastError=true,CharSet=CharSet.Unicode)] static extern IntPtr CreateFile(string path,uint access,uint share,ref Security security,uint disposition,uint flags,IntPtr template);
    [DllImport("kernel32.dll", SetLastError=true)] static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool TerminateProcess(IntPtr process,uint code);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool CloseHandle(IntPtr handle);
    static void Check(bool ok) { if (!ok) throw new Win32Exception(Marshal.GetLastWin32Error()); }
    static string Quote(string value) {
        var b=new StringBuilder("\""); int slashes=0;
        foreach(char c in value) {
            if(c=='\\') { slashes++; continue; }
            b.Append('\\',c=='"' ? 2*slashes+1 : slashes); b.Append(c); slashes=0;
        }
        return b.Append('\\',2*slashes).Append('"').ToString();
    }
    public static AdmissionOwnedJob Start(string exe,string[] args,string cwd,string stdout,string stderr) {
        var result=new AdmissionOwnedJob(); var info=new Info();
        IntPtr output=IntPtr.Zero,error=IntPtr.Zero,input=IntPtr.Zero;
        try {
            result.job=CreateJobObject(IntPtr.Zero,null); Check(result.job!=IntPtr.Zero);
            var limits=new ExtendedLimit(); limits.basic.flags=0x2000; // KILL_ON_JOB_CLOSE
            Check(SetInformationJobObject(result.job,9,ref limits,(uint)Marshal.SizeOf(limits)));
            var security=new Security(); security.length=(uint)Marshal.SizeOf(security); security.inherit=1;
            output=CreateFile(stdout,0x40000000,3,ref security,1,0x80,IntPtr.Zero); // CREATE_NEW
            Check(output!=new IntPtr(-1));
            error=CreateFile(stderr,0x40000000,3,ref security,1,0x80,IntPtr.Zero); Check(error!=new IntPtr(-1));
            input=CreateFile("NUL",0x80000000,3,ref security,3,0x80,IntPtr.Zero); Check(input!=new IntPtr(-1));
            var startup=new Startup(); startup.cb=(uint)Marshal.SizeOf(startup); startup.flags=0x101;
            startup.input=input; startup.output=output; startup.error=error;
            var command=new StringBuilder(Quote(exe)); foreach(string arg in args) command.Append(' ').Append(Quote(arg));
            Check(CreateProcess(exe,command,IntPtr.Zero,IntPtr.Zero,true,0x08004004,IntPtr.Zero,cwd,ref startup,out info));
            Check(AssignProcessToJobObject(result.job,info.process));
            result.Process=Process.GetProcessById((int)info.pid);
            IntPtr retainedHandle=result.Process.Handle; // keep exit code available even after a fast exit
            Check(ResumeThread(info.thread)!=0xffffffff);
            return result;
        } catch {
            if(info.process!=IntPtr.Zero) TerminateProcess(info.process,1);
            result.Dispose(); throw;
        } finally {
            foreach(IntPtr h in new[]{output,error,input,info.thread,info.process})
                if(h!=IntPtr.Zero && h!=new IntPtr(-1)) CloseHandle(h);
        }
    }
    public uint ActiveCount {
        get { var info=new Accounting(); Check(QueryInformationJobObject(job,1,ref info,(uint)Marshal.SizeOf(info),IntPtr.Zero)); return info.active; }
    }
    public void Dispose() {
        if(job!=IntPtr.Zero) { IntPtr h=job; job=IntPtr.Zero; Check(CloseHandle(h)); }
    }
}
