using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Linq;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;

namespace Sts2AgentBridge.Successors.GenericEventReleaseV9;

internal readonly record struct IlInstruction(
    int Offset,
    int EndOffset,
    ushort OpCode,
    int? MetadataToken,
    long? IntegerConstant,
    int? VariableIndex,
    int? BranchTarget,
    ImmutableArray<int> SwitchTargets)
{
    public bool IsCall => OpCode is 0x0027 or 0x0028 or 0x006f or 0x0073 or 0xfe06 or 0xfe07;

    public bool IsTypeOperation =>
        OpCode is 0x0070 or 0x0071 or 0x0074 or 0x0075 or 0x0079 or 0x0081 or
            0x008c or 0x008d or 0x008f or 0x00a3 or 0x00a4 or 0x00a5 or 0x00c2 or
            0x00c6 or 0xfe15 or 0xfe16 or 0xfe1c;

    public bool IsFieldOperation => OpCode is >= 0x007b and <= 0x0080;

    public bool IsLoadToken => OpCode == 0x00d0;

    public bool IsIsInst => OpCode == 0x0075;
}

internal static class IlDecoder
{
    public static IReadOnlyList<IlInstruction> Decode(byte[] bytes)
    {
        var instructions = new List<IlInstruction>();
        int offset = 0;
        while (offset < bytes.Length)
        {
            int instructionOffset = offset;
            byte first = ReadByte(bytes, ref offset);
            ushort opCode;
            byte second = 0;
            if (first == 0xfe)
            {
                second = ReadByte(bytes, ref offset);
                opCode = (ushort)(0xfe00 | second);
            }
            else
            {
                opCode = first;
            }

            int? token = null;
            long? constant = ConstantForNoOperand(opCode);
            int? variableIndex = VariableForNoOperand(opCode);
            int? branchRelative = null;
            List<int>? switchRelatives = null;
            OperandKind operandKind = GetOperandKind(first, second);
            switch (operandKind)
            {
                case OperandKind.None:
                    break;
                case OperandKind.Byte:
                    int byteValue = ReadByte(bytes, ref offset);
                    if (IsByteVariableOperand(opCode))
                    {
                        variableIndex = byteValue;
                    }
                    else
                    {
                        constant = byteValue;
                    }
                    break;
                case OperandKind.SByte:
                    int signedByte = unchecked((sbyte)ReadByte(bytes, ref offset));
                    if (IsShortBranch(opCode))
                    {
                        branchRelative = signedByte;
                    }
                    else
                    {
                        constant = signedByte;
                    }
                    break;
                case OperandKind.UInt16:
                    int unsignedShort = ReadUInt16(bytes, ref offset);
                    if (IsUInt16VariableOperand(opCode))
                    {
                        variableIndex = unsignedShort;
                    }
                    else
                    {
                        constant = unsignedShort;
                    }
                    break;
                case OperandKind.Int32:
                    int intValue = ReadInt32(bytes, ref offset);
                    if (IsLongBranch(opCode))
                    {
                        branchRelative = intValue;
                    }
                    else
                    {
                        constant = intValue;
                    }
                    break;
                case OperandKind.UInt32Token:
                    token = ReadInt32(bytes, ref offset);
                    break;
                case OperandKind.Int64:
                    constant = ReadInt64(bytes, ref offset);
                    break;
                case OperandKind.Single:
                    constant = unchecked((uint)ReadInt32(bytes, ref offset));
                    break;
                case OperandKind.Double:
                    constant = ReadInt64(bytes, ref offset);
                    break;
                case OperandKind.Switch:
                    int count = ReadInt32(bytes, ref offset);
                    if (count < 0 || count > (bytes.Length - offset) / 4)
                    {
                        throw new VerificationException("invalid_il_switch");
                    }

                    switchRelatives = new List<int>(count);
                    for (int index = 0; index < count; index++)
                    {
                        switchRelatives.Add(ReadInt32(bytes, ref offset));
                    }
                    break;
                default:
                    throw new VerificationException("invalid_il_operand");
            }

            int endOffset = offset;
            int? branchTarget = branchRelative.HasValue
                ? checked(endOffset + branchRelative.Value)
                : null;
            ImmutableArray<int> switchTargets = switchRelatives is null
                ? ImmutableArray<int>.Empty
                : switchRelatives.Select(relative => checked(endOffset + relative)).ToImmutableArray();
            instructions.Add(new IlInstruction(
                instructionOffset,
                endOffset,
                opCode,
                token,
                constant,
                variableIndex,
                branchTarget,
                switchTargets));
        }

        return instructions;
    }

    public static EntityHandle RequireEntityHandle(int token)
    {
        try
        {
            EntityHandle handle = MetadataTokens.EntityHandle(token);
            if (handle.IsNil)
            {
                throw new VerificationException("unresolved_il_token");
            }

            return handle;
        }
        catch (ArgumentException)
        {
            throw new VerificationException("unresolved_il_token");
        }
    }

    private static OperandKind GetOperandKind(byte first, byte second)
    {
        if (first == 0xfe)
        {
            return second switch
            {
                0x06 or 0x07 or 0x15 or 0x16 or 0x1c => OperandKind.UInt32Token,
                0x09 or 0x0a or 0x0b or 0x0c or 0x0d or 0x0e => OperandKind.UInt16,
                0x12 or 0x19 => OperandKind.Byte,
                0x00 or 0x01 or 0x02 or 0x03 or 0x04 or 0x05 or 0x0f or 0x11 or
                    0x13 or 0x14 or 0x17 or 0x18 or 0x1a or 0x1d or 0x1e => OperandKind.None,
                _ => throw new VerificationException("invalid_il_opcode"),
            };
        }

        if (first is >= 0x0e and <= 0x13)
        {
            return OperandKind.Byte;
        }

        if (first == 0x1f || first is >= 0x2b and <= 0x37 || first == 0xde)
        {
            return OperandKind.SByte;
        }

        if (first == 0x20 || first is >= 0x38 and <= 0x44 || first == 0xdd)
        {
            return OperandKind.Int32;
        }

        if (first == 0x21)
        {
            return OperandKind.Int64;
        }

        if (first == 0x22)
        {
            return OperandKind.Single;
        }

        if (first == 0x23)
        {
            return OperandKind.Double;
        }

        if (first == 0x45)
        {
            return OperandKind.Switch;
        }

        if (first is 0x27 or 0x28 or 0x29 or 0x6f or 0x70 or 0x71 or 0x72 or 0x73 or
            0x74 or 0x75 or 0x79 or 0x7b or 0x7c or 0x7d or 0x7e or 0x7f or 0x80 or
            0x81 or 0x8c or 0x8d or 0x8f or 0xa3 or 0xa4 or 0xa5 or 0xc2 or 0xc6 or 0xd0)
        {
            return OperandKind.UInt32Token;
        }

        if (IsKnownNoOperand(first))
        {
            return OperandKind.None;
        }

        throw new VerificationException("invalid_il_opcode");
    }

    private static bool IsKnownNoOperand(byte opCode)
    {
        return opCode is <= 0x0d or
            >= 0x14 and <= 0x1e or
            0x25 or 0x26 or 0x2a or
            >= 0x46 and <= 0x6e or
            0x76 or 0x7a or
            >= 0x82 and <= 0x8b or
            0x8e or
            >= 0x90 and <= 0xa2 or
            >= 0xb3 and <= 0xba or
            0xc3 or
            >= 0xd1 and <= 0xdc or
            0xdf or 0xe0;
    }

    private static long? ConstantForNoOperand(ushort opCode)
    {
        return opCode switch
        {
            0x0015 => -1,
            >= 0x0016 and <= 0x001e => opCode - 0x0016,
            _ => null,
        };
    }

    private static int? VariableForNoOperand(ushort opCode)
    {
        return opCode switch
        {
            >= 0x0002 and <= 0x0005 => opCode - 0x0002,
            >= 0x0006 and <= 0x0009 => opCode - 0x0006,
            >= 0x000a and <= 0x000d => opCode - 0x000a,
            _ => null,
        };
    }

    private static bool IsByteVariableOperand(ushort opCode) =>
        opCode is >= 0x000e and <= 0x0013;

    private static bool IsUInt16VariableOperand(ushort opCode) =>
        opCode is >= 0xfe09 and <= 0xfe0e;

    private static bool IsShortBranch(ushort opCode) =>
        opCode is >= 0x002b and <= 0x0037 or 0x00de;

    private static bool IsLongBranch(ushort opCode) =>
        opCode is >= 0x0038 and <= 0x0044 or 0x00dd;

    private static byte ReadByte(byte[] bytes, ref int offset)
    {
        if ((uint)offset >= (uint)bytes.Length)
        {
            throw new VerificationException("truncated_il");
        }

        return bytes[offset++];
    }

    private static ushort ReadUInt16(byte[] bytes, ref int offset)
    {
        uint low = ReadByte(bytes, ref offset);
        uint high = ReadByte(bytes, ref offset);
        return (ushort)(low | high << 8);
    }

    private static int ReadInt32(byte[] bytes, ref int offset)
    {
        uint value = ReadByte(bytes, ref offset);
        value |= (uint)ReadByte(bytes, ref offset) << 8;
        value |= (uint)ReadByte(bytes, ref offset) << 16;
        value |= (uint)ReadByte(bytes, ref offset) << 24;
        return unchecked((int)value);
    }

    private static long ReadInt64(byte[] bytes, ref int offset)
    {
        ulong low = unchecked((uint)ReadInt32(bytes, ref offset));
        ulong high = unchecked((uint)ReadInt32(bytes, ref offset));
        return unchecked((long)(low | high << 32));
    }

    private enum OperandKind
    {
        None,
        Byte,
        SByte,
        UInt16,
        Int32,
        UInt32Token,
        Int64,
        Single,
        Double,
        Switch,
    }
}
