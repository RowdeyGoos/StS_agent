using System.Reflection.Metadata;
using System.Collections.Immutable;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Reflection.Emit;
using System.Security.Cryptography;
using System.Text.Json;
using Sts2AgentBridge.Verifier;

if(args.Length!=2)throw new Exception("usage: verified-sts2-dll selectors-file");
var path=Path.GetFullPath(args[0]);
const string pin="e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18";
for(var part=new FileInfo(path) as FileSystemInfo;part is not null;part=part is FileInfo f?f.Directory:((DirectoryInfo)part).Parent)
 if(part.LinkTarget is not null)throw new Exception("symlink");
if(new FileInfo(path).Length>100_000_000)throw new Exception("size");
var image=File.ReadAllBytes(path);
if(Convert.ToHexString(SHA256.HashData(image)).ToLowerInvariant()!=pin)throw new Exception("pin");
using var pe=new PEReader(ImmutableArray.Create(image));
var r=pe.GetMetadataReader();var p=new MetadataNames();
string Entity(EntityHandle h)=>h.Kind switch{
 HandleKind.MethodDefinition=>MetadataNames.MethodDefinitionIdentity(r,(MethodDefinitionHandle)h,p),
 HandleKind.MemberReference=>MetadataNames.MemberReferenceIdentity(r,(MemberReferenceHandle)h,p),
 HandleKind.MethodSpecification=>Entity(r.GetMethodSpecification((MethodSpecificationHandle)h).Method)+"<"+string.Join(",",r.GetMethodSpecification((MethodSpecificationHandle)h).DecodeSignature(p,null))+">",
 HandleKind.FieldDefinition=>MetadataNames.TypeDefinitionName(r,r.GetFieldDefinition((FieldDefinitionHandle)h).GetDeclaringType())+"."+r.GetString(r.GetFieldDefinition((FieldDefinitionHandle)h).Name),
 _=>MetadataNames.EntityTypeName(r,h,p)};
var ops=typeof(OpCodes).GetFields().Where(f=>f.FieldType==typeof(OpCode)).Select(f=>(OpCode)f.GetValue(null)!).ToDictionary(o=>unchecked((ushort)o.Value),o=>o.Name);
var extras=File.ReadAllLines(args[1]);
var ts=r.TypeDefinitions.Select(h=>(h,n:MetadataNames.TypeDefinitionName(r,h))).Where(t=>(t.n.StartsWith("MegaCrit.Sts2.Core.Models.Events.")&&!t.n.StartsWith("MegaCrit.Sts2.Core.Models.Events.Mocks."))||extras.Any(e=>t.n==e||t.n.StartsWith(e+"+"))).OrderBy(t=>t.n).ToArray();
if(ts.Length>1800)throw new Exception("type_limit");
var rows=new List<object>();int bodies=0;
foreach(var (h,n) in ts){var td=r.GetTypeDefinition(h);var ms=new List<object>();
 foreach(var mh in td.GetMethods()){
  var m=r.GetMethodDefinition(mh);if(n=="MegaCrit.Sts2.Core.Models.ModelDb"&&r.GetString(m.Name)!="get_AllSharedEvents")continue;var id=Entity(mh);
  var ins=m.RelativeVirtualAddress==0?Array.Empty<IlInstruction>():IlDecoder.Decode(pe.GetMethodBody(m.RelativeVirtualAddress).GetILBytes()!).ToArray();
  if(ins.Length>15000)throw new Exception("body_limit");if(ins.Length>0)bodies++;
  ms.Add(new{name=r.GetString(m.Name),id,token=MetadataTokens.GetToken(mh),instructions=ins.Select(i=>new{offset=i.Offset,op=ops[i.OpCode],member=i.MetadataToken is int t?((t&unchecked((int)0xff000000))==0x70000000?"string:"+r.GetUserString(MetadataTokens.UserStringHandle(t&0xffffff)):Entity(MetadataTokens.EntityHandle(t))):null,constant=i.IntegerConstant,variable=i.VariableIndex,branch=i.BranchTarget,targets=i.SwitchTargets.ToArray()}).ToArray()});
 }
 rows.Add(new{type=n,baseType=td.BaseType.IsNil?null:Entity(td.BaseType),methods=ms});
}
Console.WriteLine(JsonSerializer.Serialize(new{schema_version=1,sha256=pin,evidence="static_il_not_execution",types=ts.Length,bodies,catalog=r.TypeDefinitions.Select(h=>MetadataNames.TypeDefinitionName(r,h)).Where(n=>!n.Contains("+")&&(n.Contains("EventPool")||n.StartsWith("MegaCrit.Sts2.Core.Models.Acts.")||n.Contains("CrystalSphere")||n.Contains("Ancient")&&n.Contains("Nodes"))).ToArray(),rows}));
CryptographicOperations.ZeroMemory(image);
namespace Sts2AgentBridge.Verifier{internal sealed class VerificationException(string code):Exception(code);}
