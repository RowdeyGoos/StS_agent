using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Linq;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using Sts2AgentBridge.Verifier;

internal static class PeMutations
{
    internal static byte[] ChangeNativeFlags(byte[] source, bool callingConvention)
    {
        byte[] result = source.ToArray();
        using var pe = Open(result, out MetadataReader reader);
        MethodDefinitionHandle methodHandle = reader.MethodDefinitions.First(handle =>
        {
            MethodDefinition method = reader.GetMethodDefinition(handle);
            return (method.Attributes & System.Reflection.MethodAttributes.PinvokeImpl) != 0 &&
                reader.GetString(method.GetImport().Name) == "getuid";
        });
        Tables tables = Tables.Parse(result, MetadataOffset(pe));
        int rowSize = tables.RowSize((int)TableIndex.ImplMap);
        int methodRow = MetadataTokens.GetRowNumber(methodHandle);
        for (int row = 0; row < tables.Rows[(int)TableIndex.ImplMap]; row++)
        {
            int offset = tables.TableOffset((int)TableIndex.ImplMap) + row * rowSize;
            int member = tables.ReadIndex(result, offset + 2, tables.CodedSize(1, 4, 6));
            if (member == ((methodRow << 1) | 1))
            {
                ushort flags = BinaryPrimitives.ReadUInt16LittleEndian(result.AsSpan(offset, 2));
                flags = callingConvention
                    ? (ushort)((flags & ~0x0700) | 0x0100)
                    : (ushort)(flags ^ 0x0040);
                BinaryPrimitives.WriteUInt16LittleEndian(result.AsSpan(offset, 2), flags);
                return result;
            }
        }
        throw new InvalidOperationException("ImplMap row not found");
    }

    internal static byte[] ChangeMemberReferenceName(byte[] source)
    {
        byte[] result = source.ToArray();
        using var pe = Open(result, out MetadataReader reader);
        MemberReference reference = reader.GetMemberReference(reader.MemberReferences.First(handle =>
            reader.GetString(reader.GetMemberReference(handle).Name) == "ToString"));
        int heapOffset = MetadataTokens.GetHeapOffset(reference.Name);
        Tables tables = Tables.Parse(result, MetadataOffset(pe));
        int offset = tables.MetadataOffset + tables.StringsOffset + heapOffset;
        if (result[offset] == 0) throw new InvalidOperationException();
        result[offset] = result[offset] == (byte)'Z' ? (byte)'Y' : (byte)'Z';
        return result;
    }

    internal static byte[] ChangeMemberReferenceNameToForceClick(byte[] source)
    {
        byte[] result = source.ToArray();
        using var pe = Open(result, out MetadataReader reader);
        MemberReference reference = reader.GetMemberReference(reader.MemberReferences.First(handle =>
            reader.GetString(reader.GetMemberReference(handle).Name) == "GetAwaiter"));
        ChangeString(result, pe, MetadataTokens.GetHeapOffset(reference.Name), "GetAwaiter", "ForceClick");
        return result;
    }

    internal static byte[] ChangeBenignOpcode(byte[] source)
    {
        byte[] result = source.ToArray();
        using var pe = Open(result, out MetadataReader reader);
        foreach (MethodDefinitionHandle handle in reader.MethodDefinitions)
        {
            MethodDefinition method = reader.GetMethodDefinition(handle);
            if (method.RelativeVirtualAddress == 0) continue;
            MethodBodyBlock body = pe.GetMethodBody(method.RelativeVirtualAddress);
            byte[]? il = body.GetILBytes();
            if (il is null) continue;
            IlInstruction? candidate = IlDecoder.Decode(il).FirstOrDefault(item => item.OpCode is 0x0016 or 0x0017);
            if (candidate is IlInstruction instruction)
            {
                int start = IlStart(result, RvaOffset(pe, method.RelativeVirtualAddress));
                result[start + instruction.Offset] = instruction.OpCode == 0x0016 ? (byte)0x17 : (byte)0x16;
                return result;
            }
        }
        throw new InvalidOperationException("constant opcode not found");
    }

    internal static byte[] ChangeMethodNameToSynthetic(byte[] source)
    {
        byte[] result = source.ToArray();
        using var pe = Open(result, out MetadataReader reader);
        MethodDefinition method = reader.GetMethodDefinition(reader.MethodDefinitions.First(handle =>
            reader.GetString(reader.GetMethodDefinition(handle).Name) == "TryDetach"));
        ChangeString(result, pe, MetadataTokens.GetHeapOffset(method.Name), "TryDetach", "Synthetic");
        return result;
    }

    internal static byte[] ChangeInitializerAttributeName(byte[] source)
    {
        byte[] result = source.ToArray();
        using var pe = Open(result, out MetadataReader reader);
        TypeReferenceHandle handle = reader.TypeReferences.Single(item =>
            reader.GetString(reader.GetTypeReference(item).Name) == "ModInitializerAttribute");
        TypeReference type = reader.GetTypeReference(handle);
        ChangeString(result, pe, MetadataTokens.GetHeapOffset(type.Name),
            "ModInitializerAttribute", "NodInitializerAttribute");
        return result;
    }

    internal static byte[] ChangeAssemblyReferenceName(byte[] source)
    {
        byte[] result = source.ToArray();
        using var pe = Open(result, out MetadataReader reader);
        AssemblyReference reference = reader.GetAssemblyReference(reader.AssemblyReferences.First());
        string name = reader.GetString(reference.Name);
        if (name.Length == 0) throw new InvalidOperationException("assembly reference name missing");
        string changed = (name[0] == 'Z' ? 'Y' : 'Z') + name[1..];
        ChangeString(result, pe, MetadataTokens.GetHeapOffset(reference.Name), name, changed);
        return result;
    }

    internal static byte[] ChangeCalledTypeNamespaceToReflection(byte[] source)
    {
        byte[] result = source.ToArray();
        using var pe = Open(result, out MetadataReader reader);
        TypeReferenceHandle handle = reader.TypeReferences.Single(item =>
        {
            TypeReference type = reader.GetTypeReference(item);
            return reader.GetString(type.Namespace) == "System.Net.Sockets" &&
                reader.GetString(type.Name) == "Socket";
        });
        TypeReference value = reader.GetTypeReference(handle);
        ChangeStringShorter(result, pe, MetadataTokens.GetHeapOffset(value.Namespace),
            "System.Net.Sockets", "System.Reflection");
        return result;
    }

    private static void ChangeString(
        byte[] image,
        PEReader pe,
        int heapOffset,
        string expected,
        string replacement)
    {
        if (expected.Length != replacement.Length) throw new InvalidOperationException();
        Tables tables = Tables.Parse(image, MetadataOffset(pe));
        int offset = tables.MetadataOffset + tables.StringsOffset + heapOffset;
        byte[] bytes = System.Text.Encoding.UTF8.GetBytes(expected);
        if (!image.AsSpan(offset, bytes.Length).SequenceEqual(bytes))
            throw new InvalidOperationException("string heap mismatch");
        System.Text.Encoding.UTF8.GetBytes(replacement).CopyTo(image, offset);
    }

    private static void ChangeStringShorter(
        byte[] image,
        PEReader pe,
        int heapOffset,
        string expected,
        string replacement)
    {
        if (replacement.Length >= expected.Length) throw new InvalidOperationException();
        Tables tables = Tables.Parse(image, MetadataOffset(pe));
        int offset = tables.MetadataOffset + tables.StringsOffset + heapOffset;
        byte[] expectedBytes = System.Text.Encoding.UTF8.GetBytes(expected);
        if (!image.AsSpan(offset, expectedBytes.Length).SequenceEqual(expectedBytes))
            throw new InvalidOperationException("string heap mismatch");
        image.AsSpan(offset, expectedBytes.Length).Clear();
        System.Text.Encoding.UTF8.GetBytes(replacement).CopyTo(image, offset);
    }

    private static PEReader Open(byte[] image, out MetadataReader reader)
    {
        var pe = new PEReader(new System.IO.MemoryStream(image, writable: false));
        reader = pe.GetMetadataReader();
        return pe;
    }

    private static int MetadataOffset(PEReader pe) =>
        RvaOffset(pe, pe.PEHeaders.CorHeader?.MetadataDirectory.RelativeVirtualAddress ?? throw new InvalidOperationException());

    private static int RvaOffset(PEReader pe, int rva)
    {
        foreach (SectionHeader section in pe.PEHeaders.SectionHeaders)
        {
            int span = Math.Max(section.VirtualSize, section.SizeOfRawData);
            if (rva >= section.VirtualAddress && rva < section.VirtualAddress + span)
                return section.PointerToRawData + rva - section.VirtualAddress;
        }
        throw new InvalidOperationException("RVA outside sections");
    }

    private static int IlStart(byte[] image, int body)
    {
        byte first = image[body];
        if ((first & 3) == 2) return body + 1;
        if ((first & 3) == 3)
        {
            ushort flags = BinaryPrimitives.ReadUInt16LittleEndian(image.AsSpan(body, 2));
            return body + ((flags >> 12) * 4);
        }
        throw new InvalidOperationException("invalid method header");
    }

    private sealed class Tables
    {
        private readonly byte _heapSizes;
        private readonly ulong _valid;
        private readonly int _dataOffset;

        private Tables(int metadataOffset, int stringsOffset, byte heapSizes, ulong valid, int[] rows, int dataOffset)
        {
            MetadataOffset = metadataOffset;
            StringsOffset = stringsOffset;
            _heapSizes = heapSizes;
            _valid = valid;
            Rows = rows;
            _dataOffset = dataOffset;
        }

        internal int MetadataOffset { get; }
        internal int StringsOffset { get; }
        internal int[] Rows { get; }

        internal static Tables Parse(byte[] image, int metadata)
        {
            if (BinaryPrimitives.ReadUInt32LittleEndian(image.AsSpan(metadata, 4)) != 0x424a5342) throw new InvalidOperationException();
            int versionLength = BinaryPrimitives.ReadInt32LittleEndian(image.AsSpan(metadata + 12, 4));
            int position = Align4(metadata + 16 + versionLength);
            int streamCount = BinaryPrimitives.ReadUInt16LittleEndian(image.AsSpan(position + 2, 2));
            position += 4;
            int tablesOffset = -1;
            int stringsOffset = -1;
            for (int index = 0; index < streamCount; index++)
            {
                int offset = BinaryPrimitives.ReadInt32LittleEndian(image.AsSpan(position, 4));
                position += 8;
                int nameStart = position;
                while (image[position] != 0) position++;
                string name = System.Text.Encoding.ASCII.GetString(image, nameStart, position - nameStart);
                position = Align4(position + 1);
                if (name is "#~" or "#-") tablesOffset = offset;
                if (name == "#Strings") stringsOffset = offset;
            }
            if (tablesOffset < 0 || stringsOffset < 0) throw new InvalidOperationException();
            int tables = metadata + tablesOffset;
            byte heapSizes = image[tables + 6];
            ulong valid = BinaryPrimitives.ReadUInt64LittleEndian(image.AsSpan(tables + 8, 8));
            var rows = new int[64];
            position = tables + 24;
            for (int table = 0; table < 64; table++)
            {
                if ((valid & (1UL << table)) == 0) continue;
                rows[table] = BinaryPrimitives.ReadInt32LittleEndian(image.AsSpan(position, 4));
                position += 4;
            }
            return new Tables(metadata, stringsOffset, heapSizes, valid, rows, position);
        }

        internal int TableOffset(int target)
        {
            int offset = _dataOffset;
            for (int table = 0; table < target; table++)
                if ((_valid & (1UL << table)) != 0) offset += checked(Rows[table] * RowSize(table));
            return offset;
        }

        internal int RowSize(int table) => table switch
        {
            0 => 2 + StringSize + GuidSize * 3,
            1 => CodedSize(2, 0, 26, 35, 1) + StringSize * 2,
            2 => 4 + StringSize * 2 + CodedSize(2, 2, 1, 27) + Index(4) + Index(6),
            3 => Index(4),
            4 => 2 + StringSize + BlobSize,
            5 => Index(6),
            6 => 8 + StringSize + BlobSize + Index(8),
            7 => Index(8),
            8 => 4 + StringSize,
            9 => Index(2) + CodedSize(2, 2, 1, 27),
            10 => CodedSize(3, 2, 1, 26, 6, 27) + StringSize + BlobSize,
            11 => 2 + CodedSize(2, 4, 8, 23) + BlobSize,
            12 => CodedSize(5, 6, 4, 1, 2, 8, 9, 10, 0, 14, 23, 20, 17, 26, 27, 32, 35, 38, 39, 40, 42, 44, 43) + CodedSize(3, 6, 10) + BlobSize,
            13 => CodedSize(1, 4, 8) + BlobSize,
            14 => 2 + CodedSize(2, 2, 6, 32) + BlobSize,
            15 => 6 + Index(2),
            16 => 4 + Index(4),
            17 => BlobSize,
            18 => Index(2) + Index(20),
            19 => Index(20),
            20 => 2 + StringSize + CodedSize(2, 2, 1, 27),
            21 => Index(2) + Index(23),
            22 => Index(23),
            23 => 2 + StringSize + BlobSize,
            24 => 2 + Index(6) + CodedSize(1, 20, 23),
            25 => Index(2) + CodedSize(1, 6, 10) * 2,
            26 => StringSize,
            27 => BlobSize,
            28 => 2 + CodedSize(1, 4, 6) + StringSize + Index(26),
            _ => throw new InvalidOperationException("unsupported metadata table before ImplMap"),
        };

        internal int CodedSize(int tagBits, params int[] tables)
        {
            int maximum = tables.Max(table => Rows[table]);
            return maximum < (1 << (16 - tagBits)) ? 2 : 4;
        }

        internal int ReadIndex(byte[] image, int offset, int size) => size == 2
            ? BinaryPrimitives.ReadUInt16LittleEndian(image.AsSpan(offset, 2))
            : BinaryPrimitives.ReadInt32LittleEndian(image.AsSpan(offset, 4));

        private int Index(int table) => Rows[table] < 65_536 ? 2 : 4;
        private int StringSize => (_heapSizes & 1) == 0 ? 2 : 4;
        private int GuidSize => (_heapSizes & 2) == 0 ? 2 : 4;
        private int BlobSize => (_heapSizes & 4) == 0 ? 2 : 4;
        private static int Align4(int value) => (value + 3) & ~3;
    }
}
