using Sts2AgentBridge.Successors.GenericEventReleaseV5;
using System;
using System.Globalization;
using System.Text;
namespace Sts2AgentBridge.Successors.GenericEventReleaseV9;
internal static class GenericEventTransportLimits
{
    internal const int Port=43117, Backlog=8, MaximumHandlers=4, MaximumRequestHead=1024, RequestBufferSize=1025, MaximumBody=65536;
    internal const int MaximumReads=2048, MaximumParentPosts=12, MaximumChildPosts=40, MaximumTotalPosts=52;
    internal const int HeaderReadMilliseconds=1000, ResponseWriteMilliseconds=1000, ConnectionLifetimeMilliseconds=2000, ShutdownJoinMilliseconds=2000;
}
internal enum GenericEventTransportRoute { DecisionGet=1, ParentPost=2, ChildPost=3 }
internal readonly record struct ParsedGenericEventTransportRequest(GenericEventTransportRoute Route,
    int AuthorizationOffset,int AuthorizationLength,int DecisionOffset,int DecisionLength,int ActionOffset,int ActionLength,
    int ChildOrdinal,int ParentDecisionOffset,int ParentDecisionLength,int ParentActionOffset,int ParentActionLength)
{
    internal bool IsPost => Route is GenericEventTransportRoute.ParentPost or GenericEventTransportRoute.ChildPost;
    internal bool IsChild => Route==GenericEventTransportRoute.ChildPost;
}
internal static class GenericEventTransportRequestParser
{
    private static ReadOnlySpan<byte> GetLine => "GET /probe/generic-event-v7/public/decision HTTP/1.1"u8;
    private static ReadOnlySpan<byte> PostLine => "POST /probe/generic-event-v7/public/action HTTP/1.1"u8;
    private static ReadOnlySpan<byte> Auth => "Authorization: Bearer "u8;
    private static ReadOnlySpan<byte> Decision => "X-Sts2-Decision-Id: "u8;
    private static ReadOnlySpan<byte> Action => "X-Sts2-Action-Id: "u8;
    private static ReadOnlySpan<byte> Ordinal => "X-Sts2-Child-Ordinal: "u8;
    private static ReadOnlySpan<byte> ParentDecision => "X-Sts2-Parent-Decision-Id: "u8;
    private static ReadOnlySpan<byte> ParentAction => "X-Sts2-Parent-Action-Id: "u8;
    internal static bool TryParse(ReadOnlySpan<byte> head,GenericEventReleaseSelection selection,out ParsedGenericEventTransportRequest request)
    {
        request=default;
        if(selection!=GenericEventReleaseSelection.Generic||head.Length is <4 or >1024||!head[^4..].SequenceEqual("\r\n\r\n"u8))return false;
        Span<Line> lines=stackalloc Line[11];
        if(!Split(head,lines,out int count)||count is not (5 or 7 or 10))return false;
        bool post=head[lines[0].Slice].SequenceEqual(PostLine);
        if(!post&&!head[lines[0].Slice].SequenceEqual(GetLine))return false;
        if((post&&count==5)||(!post&&count!=5)||!head[lines[1].Slice].SequenceEqual("Host: 127.0.0.1:43117"u8)||
            !head[lines[3].Slice].SequenceEqual("Accept: application/json"u8)||!Field(head,lines[2],Auth,64,true,out int auth))return false;
        int decision=0,action=0,actionLength=0,ordinal=0,pd=0,pa=0,paLength=0;
        bool child=count==10;
        if(post)
        {
            if(!Field(head,lines[4],Decision,64,true,out decision)||!Field(head,lines[5],Action,-1,false,out action))return false;
            actionLength=lines[5].Length-Action.Length;
            var value=head.Slice(action,actionLength);
            if(child ? !ChildAction(value) : !ParentActionValue(value))return false;
            if(child)
            {
                if(!Field(head,lines[6],Ordinal,1,false,out int od)||head[od] is <(byte)'1' or >(byte)'4'||
                    !Field(head,lines[7],ParentDecision,64,true,out pd)||!Field(head,lines[8],ParentAction,-1,false,out pa))return false;
                ordinal=head[od]-(byte)'0';paLength=lines[8].Length-ParentAction.Length;
                if(!ParentActionValue(head.Slice(pa,paLength)))return false;
            }
        }
        if(!head[lines[count-1].Slice].SequenceEqual("Connection: close"u8))return false;
        request=new(!post?GenericEventTransportRoute.DecisionGet:child?GenericEventTransportRoute.ChildPost:GenericEventTransportRoute.ParentPost,
            auth,64,decision,post?64:0,action,actionLength,ordinal,pd,child?64:0,pa,paLength);
        return true;
    }
    private static bool Field(ReadOnlySpan<byte> h,Line line,ReadOnlySpan<byte> prefix,int size,bool hex,out int offset)
    {
        offset=line.Start+prefix.Length;
        var v=h[line.Slice];
        if(!v.StartsWith(prefix)||v.Length<=prefix.Length||(size>=0&&v.Length!=prefix.Length+size))return false;
        if(hex)foreach(byte c in v[prefix.Length..])if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
        return true;
    }
    internal static bool ParentActionValue(ReadOnlySpan<byte> value)=>value.Length==8&&value[..7].SequenceEqual("choose:"u8)&&value[7] is >=(byte)'0' and <=(byte)'7';
    internal static bool ChildAction(ReadOnlySpan<byte> value)
    {
        if(value.SequenceEqual("preview"u8)||value.SequenceEqual("confirm"u8))return true;
        bool item=value.StartsWith("collect:"u8);
        int prefix=item?8:7;
        if(!item&&!value.StartsWith("select:"u8)||value.Length<=prefix||value.Length>prefix+(item?3:2))return false;
        var digits=value[prefix..];if(digits.Length>1&&digits[0]=='0')return false;
        int n=0;foreach(byte c in digits){if(c<'0'||c>'9')return false;n=n*10+c-'0';}return n<=(item?255:63);
    }
    private static bool Split(ReadOnlySpan<byte> source,Span<Line> lines,out int count)
    {
        count=0;int start=0;
        for(int i=0;i<source.Length-1;i++)if(source[i] is <0x20 or >0x7e)
        {
            if(source[i]!='\r'||source[i+1]!='\n')return false;
            if(i==start)return i+2==source.Length;
            if(count>=lines.Length)return false;
            lines[count++]=new(start,i-start);start=i+2;i++;
        }
        return false;
    }
    private readonly record struct Line(int Start,int Length){internal Range Slice=>Start..(Start+Length);}
}
internal static class GenericEventTransportServiceBody
{
    internal static byte[] Build(string decision,string action,int ordinal=0,string? parentDecision=null,string? parentAction=null)=>Encoding.ASCII.GetBytes(
        "{\"decision_id\":\""+decision+"\",\"action_id\":\""+action+"\",\"child\":"+(ordinal==0?"null":
        "{\"ordinal\":"+ordinal.ToString(CultureInfo.InvariantCulture)+",\"parent_decision_id\":\""+parentDecision+"\",\"parent_action_id\":\""+parentAction+"\"}")+"}");
}
internal static class GenericEventTransportHttpEncoder
{
    internal static byte[] Wrap(byte[] body, GenericEventDiagnosticCode diagnostic = GenericEventDiagnosticCode.NotCaptured)
    {
        if(body.Length is <1 or >65536)throw new InvalidOperationException("Invalid service body length.");
        byte[] header=Encoding.ASCII.GetBytes("HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: "+body.Length.ToString(CultureInfo.InvariantCulture)+
            "\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nX-Sts2-Native-Diagnostic: "+GenericEventDiagnosticCodec.Encode(diagnostic)+"\r\nConnection: close\r\n\r\n");
        try{var response=new byte[header.Length+body.Length];header.CopyTo(response,0);body.CopyTo(response,header.Length);return response;}
        finally{Array.Clear(header);}
    }
}
