import py, struct
from pypy.jit.backend.x86.rx86 import *
globals().update(R.__dict__)

class CodeBuilderMixin(object):
    def __init__(self):
        self.buffer = []

    def writechar(self, c):
        assert isinstance(c, str) and len(c) == 1
        self.buffer.append(c)    # append a character

    def getvalue(self):
        return ''.join(self.buffer)

    def tell(self):
        return 0x76543210 + len(self.buffer)


class CodeBuilder32(CodeBuilderMixin, X86_32_CodeBuilder):
    pass

def test_mov_ri():
    s = CodeBuilder32()
    s.MOV_ri(ecx, -2)
    assert s.getvalue() == '\xB9\xFE\xFF\xFF\xFF'

def test_mov_rr():
    s = CodeBuilder32()
    s.MOV_rr(ebx, ebp)
    assert s.getvalue() == '\x89\xEB'

def test_mov_br():
    s = CodeBuilder32()
    s.MOV_br(-36, edx)
    assert s.getvalue() == '\x89\x55\xDC'

def test_mov_rb():
    s = CodeBuilder32()
    s.MOV_rb(edx, -36)
    assert s.getvalue() == '\x8B\x55\xDC'

def test_mov_rm():
    s = CodeBuilder32()
    s.MOV_rm(edx, (edi, 0))
    s.MOV_rm(edx, (edi, -128))
    s.MOV_rm(edx, (edi, 128))
    assert s.getvalue() == '\x8B\x17\x8B\x57\x80\x8B\x97\x80\x00\x00\x00'

def test_mov_mr():
    s = CodeBuilder32()
    s.MOV_mr((edi, 0), edx)
    s.MOV_mr((edi, -128), edx)
    s.MOV_mr((edi, 128), edx)
    assert s.getvalue() == '\x89\x17\x89\x57\x80\x89\x97\x80\x00\x00\x00'

def test_mov_ra():
    s = CodeBuilder32()
    s.MOV_ra(edx, (esi, edi, 2, 0))
    s.MOV_ra(edx, (esi, edi, 2, -128))
    s.MOV_ra(edx, (esi, edi, 2, 128))
    assert s.getvalue() == ('\x8B\x14\xBE' +
                            '\x8B\x54\xBE\x80' +
                            '\x8B\x94\xBE\x80\x00\x00\x00')

def test_mov_ar():
    s = CodeBuilder32()
    s.MOV_ar((esi, edi, 2, 0), edx)
    s.MOV_ar((esi, edi, 2, -128), edx)
    s.MOV_ar((esi, edi, 2, 128), edx)
    assert s.getvalue() == ('\x89\x14\xBE' +
                            '\x89\x54\xBE\x80' +
                            '\x89\x94\xBE\x80\x00\x00\x00')

def test_nop_add_rr():
    s = CodeBuilder32()
    s.NOP()
    s.ADD_rr(eax, eax)
    assert s.getvalue() == '\x90\x01\xC0'

def test_lea_rb():
    s = CodeBuilder32()
    s.LEA_rb(ecx, -36)
    assert s.getvalue() == '\x8D\x4D\xDC'

def test_lea32_rb():
    s = CodeBuilder32()
    s.LEA32_rb(ecx, -36)
    assert s.getvalue() == '\x8D\x8D\xDC\xFF\xFF\xFF'

def test_call_l(s=None):
    s = s or CodeBuilder32()
    s.CALL_l(0x01234567)
    ofs = 0x01234567 - (0x76543210+5)
    assert s.getvalue() == '\xE8' + struct.pack("<i", ofs)

def test_jmp_l():
    s = CodeBuilder32()
    s.JMP_l(0x01234567)
    ofs = 0x01234567 - (0x76543210+5)
    assert s.getvalue() == '\xE9' + struct.pack("<i", ofs)

def test_j_il():
    s = CodeBuilder32()
    s.J_il(5, 0x01234567)
    ofs = 0x01234567 - (0x76543210+6)
    assert s.getvalue() == '\x0F\x85' + struct.pack("<i", ofs)

def test_set_ir():
    s = CodeBuilder32()
    s.SET_ir(5, 2)
    assert s.getvalue() == '\x0F\x95\xC2'

def test_xchg_rj():
    s = CodeBuilder32()
    s.XCHG_rj(edx, 0x01234567)
    assert s.getvalue() == '\x87\x15\x67\x45\x23\x01'

def test_movsd_rj():
    s = CodeBuilder32()
    s.MOVSD_rj(xmm2, 0x01234567)
    assert s.getvalue() == '\xF2\x0F\x10\x15\x67\x45\x23\x01'

def test_movzx8_rm():
    s = CodeBuilder32()
    s.MOVZX8_rm(ecx, (eax, 16))
    assert s.getvalue() == '\x0F\xB6\x48\x10'

def test_movzx16_rm():
    s = CodeBuilder32()
    s.MOVZX16_rm(ecx, (eax, 16))
    assert s.getvalue() == '\x0F\xB7\x48\x10'

def test_div():
    s = CodeBuilder32()
    s.DIV_r(ecx)
    assert s.getvalue() == '\xF7\xF1'

def test_imul_rri():
    s = CodeBuilder32()
    # Multiply ecx by 0x01234567 and store the result in ebx
    s.IMUL_rri(ebx, ecx, 0x01234567)
    assert s.getvalue() == '\x69\xD9\x67\x45\x23\x01'

    s = CodeBuilder32()
    s.IMUL_rri(ebx, ecx, 0x2A)
    assert s.getvalue() == '\x6B\xD9\x2A'

class CodeBuilder64(CodeBuilderMixin, X86_64_CodeBuilder):
    pass

def test_mov_ri_64():
    s = CodeBuilder64()
    s.MOV_ri(ecx, -2)
    s.MOV_ri(r12, 0x80000042)
    assert s.getvalue() == ('\x48\xC7\xC1\xFE\xFF\xFF\xFF' +
                            '\x49\xBC\x42\x00\x00\x80\x00\x00\x00\x00')

def test_mov_rm_64():
    s = CodeBuilder64()
    s.MOV_rm(edx, (edi, 0))
    s.MOV_rm(edx, (r12, 0))
    s.MOV_rm(edx, (r13, 0))
    assert s.getvalue() == '\x48\x8B\x17\x49\x8b\x14\x24\x49\x8b\x55\x00'

def test_mov_rm_negative_64():
    s = CodeBuilder64()
    s.MOV_rm(edx, (edi, -1))
    assert s.getvalue() == '\x48\x8B\x57\xFF'

def test_call_l_64():
    # first check that it works there too
    test_call_l(CodeBuilder64())
    # then check the other case
    s = CodeBuilder64()
    target = 0x0123456789ABCDEF
    s.CALL_l(target)     # becomes indirect, via RAX
    assert s.getvalue() == '\x48\xB8' + struct.pack("<q", target) + '\xFF\xD0'
