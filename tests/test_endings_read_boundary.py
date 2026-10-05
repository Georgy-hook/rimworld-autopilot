"""Run the actual pure C# read-boundary helper against a reentrant scratch getter.

No Unity process, API, game assembly or model is invoked.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class EndingReadBoundaryTests(unittest.TestCase):
    def test_actual_csharp_helper_survives_reentrant_scratch_callbacks(self):
        dotnet = Path.home() / ".dotnet/dotnet.exe"
        if not dotnet.exists():
            found=shutil.which("dotnet")
            if not found:self.skipTest(".NET SDK unavailable")
            dotnet=Path(found)
        sdk=subprocess.run([str(dotnet),"--list-sdks"],capture_output=True,text=True,timeout=15)
        if "8.0." not in sdk.stdout:self.skipTest(".NET 8 SDK unavailable")
        helper=Path(__file__).resolve().parents[1]/"vendor/RIMAPI/Source/RIMAPI/RimworldRestApi/Helpers/EndingReadBoundary.cs"
        with tempfile.TemporaryDirectory(prefix="laya-ending-read-boundary-") as temp:
            root=Path(temp)
            (root/"Boundary.csproj").write_text(f'''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup><ItemGroup><Compile Include="{helper.as_posix()}" Link="EndingReadBoundary.cs" /></ItemGroup></Project>''',encoding="utf-8")
            (root/"NuGet.Config").write_text('<configuration><packageSources><clear /></packageSources></configuration>',encoding="utf-8")
            (root/"Program.cs").write_text(r'''
using RIMAPI.Helpers;
using System.Text.Json;
class Pawn { public int Id; public string Name; }
class Option { public bool Disabled; public string Label; public Action Action; }
class Scratch {
    readonly List<Pawn> buffer=new();
    public int Reads;
    public List<Pawn> Read() {
        Reads++; buffer.Clear();
        for(int i=1;i<=3;i++)buffer.Add(new Pawn{Id=i,Name="Pawn"+i});
        return buffer;
    }
}
class Program {
 static void Check(bool condition,string reason){if(!condition)throw new Exception(reason);}
 static void Main() {
    // Reproduce EndingController's previous enabled-job body: the nested getter clears the outer List.
    var broken=new Scratch(); bool invalidated=false;
    try { foreach(var p in broken.Read()) { var labels=broken.Read().Select(p=>p.Name).ToArray(); } }
    catch(InvalidOperationException ex) { invalidated=ex.Message.Contains("Collection was modified"); }
    Check(invalidated,"old native scratch enumeration must actually fail");
    int previews=0,invokedActions=0,enabled=0,disabled=0;
    var source=new Scratch();
    for(int cycle=0;cycle<8;cycle++) {
        var owned=EndingReadBoundary.Capture(source.Read);
        var labels=EndingReadBoundary.Project(owned,p=>p.Name);
        var rows=EndingReadBoundary.Project(owned,p=> {
            // Simulate native option/inspect callbacks which reuse the same getter on this same thread.
            source.Read();
            previews++;
            var preview=EndingReadBoundary.Capture(()=>new[]{new Option{
                Disabled=(cycle+p.Id)%2==0,Label="Option"+p.Id,Action=()=>invokedActions++}});
            source.Read(); // inspect callback also refills the borrowed list
            foreach(var option in preview){if(option.Disabled)disabled++;else enabled++;}
            return new {pawn_id=p.Id,colonists=labels,options=preview.Select(o=>new{o.Label,o.Disabled}).ToArray()};
        });
        Check(rows.Length==3 && rows.Select(r=>r.pawn_id).SequenceEqual(new[]{1,2,3}),"all original captured pawns must survive callbacks");
        Check(rows.All(r=>r.colonists.SequenceEqual(new[]{"Pawn1","Pawn2","Pawn3"})),"snapshot labels changed");
        // After rendering, another native getter must not alter the already materialized response.
        string before=JsonSerializer.Serialize(rows);source.Read();
        Check(before==JsonSerializer.Serialize(rows),"response retained a lazy borrowed game collection");
    }
    Check(previews==24,"preview evaluated more than once per site/pawn/cycle");
    Check(enabled==12 && disabled==12,"enabled/disabled alternatives lost across replay cycles");
    Check(invokedActions==0,"read preview invoked a native action");
    // Per-map owned arrays remain independent when the next map's getter reuses a global scratch buffer.
    var first=EndingReadBoundary.Capture(source.Read);var second=EndingReadBoundary.Capture(source.Read);
    source.Read();Check(first.Length==3 && second.Length==3,"map capture retained shared scratch list");
    Console.WriteLine("old-invalidated=true; captured-cycles=8; previews=24; enabled=12; disabled=12; actions=0");
 }
}
''',encoding="utf-8")
            env={**os.environ,"DOTNET_CLI_TELEMETRY_OPTOUT":"1","DOTNET_NOLOGO":"1"}
            result=subprocess.run([str(dotnet),"run","--project",str(root/"Boundary.csproj"),"--configuration","Release","--verbosity","quiet"],cwd=root,env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("old-invalidated=true; captured-cycles=8; previews=24; enabled=12; disabled=12; actions=0",result.stdout)


if __name__=="__main__":unittest.main()
