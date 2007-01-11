from pypy.rlib.objectmodel import specialize
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.jit.codegen.model import AbstractRGenOp, GenLabel, GenBuilder
from pypy.jit.codegen.model import GenVar, GenConst, CodeGenSwitch
from pypy.jit.codegen.i386.ri386 import *
from pypy.jit.codegen.i386 import conftest


WORD = 4    # bytes


class Operation(GenVar):
    def allocate_registers(self, allocator):
        pass
    def generate(self, allocator):
        raise NotImplementedError

class Op1(Operation):
    def __init__(self, x):
        self.x = x
    def allocate_registers(self, allocator):
        allocator.using(self.x)
    def generate(self, allocator):
        try:
            loc = allocator.var2loc[self]
        except KeyError:
            return    # simple operation whose result is not used anyway
        op = allocator.load_location_with(loc, self.x)
        self.emit(allocator.mc, op)
        allocator.store_back_location(loc, op)

class OpSameAs(Op1):
    emit = staticmethod(lambda mc, x: None)

class Op2(Operation):
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def allocate_registers(self, allocator):
        allocator.using(self.x)
        allocator.using(self.y)
    def generate(self, allocator):
        try:
            loc = allocator.var2loc[self]
        except KeyError:
            return    # simple operation whose result is not used anyway
        op1 = allocator.load_location_with(loc, self.x)
        op2 = allocator.get_operand(self.y)
        self.emit(allocator.mc, op1, op2)
        allocator.store_back_location(loc, op1)

class OpIntAdd(Op2):
    opname = 'int_add'
    emit = staticmethod(I386CodeBuilder.ADD)

class OpIntSub(Op2):
    opname = 'int_sub'
    emit = staticmethod(I386CodeBuilder.SUB)

class OpIntGt(Op2):
    opname = 'int_gt'
    @staticmethod
    def emit(mc, x, y):
        mc.CMP(x, y)
        mc.SETG(cl)
        mc.MOVZX(x, cl)

class JumpIfFalse(Operation):
    def __init__(self, gv_condition, targetbuilder):
        self.gv_condition = gv_condition
        self.targetbuilder = targetbuilder
    def allocate_registers(self, allocator):
        allocator.using(self.gv_condition)
    def generate(self, allocator):
        op = allocator.get_operand(self.gv_condition)
        mc = allocator.mc
        mc.CMP(op, imm8(0))
        targetbuilder = self.targetbuilder
        targetbuilder.set_coming_from(mc, insn=I386CodeBuilder.JE)
        targetbuilder.inputoperands = [allocator.get_operand(gv)
                                       for gv in targetbuilder.inputargs_gv]

# ____________________________________________________________

class IntConst(GenConst):

    def __init__(self, value):
        self.value = value

    def operand(self, builder):
        return imm(self.value)

    def nonimmoperand(self, builder, tmpregister):
        builder.mc.MOV(tmpregister, self.operand(builder))
        return tmpregister

    @specialize.arg(1)
    def revealconst(self, T):
        if isinstance(T, lltype.Ptr):
            return lltype.cast_int_to_ptr(T, self.value)
        elif T is llmemory.Address:
            return llmemory.cast_int_to_adr(self.value)
        else:
            return lltype.cast_primitive(T, self.value)

    def __repr__(self):
        "NOT_RPYTHON"
        try:
            return "const=%s" % (imm(self.value).assembler(),)
        except TypeError:   # from Symbolics
            return "const=%r" % (self.value,)

    def repr(self):
        return "const=$%s" % (self.value,)

class AddrConst(GenConst):

    def __init__(self, addr):
        self.addr = addr

    def operand(self, builder):
        return imm(llmemory.cast_adr_to_int(self.addr))

    def nonimmoperand(self, builder, tmpregister):
        builder.mc.MOV(tmpregister, self.operand(builder))
        return tmpregister

    @specialize.arg(1)
    def revealconst(self, T):
        if T is llmemory.Address:
            return self.addr
        elif isinstance(T, lltype.Ptr):
            return llmemory.cast_adr_to_ptr(self.addr, T)
        elif T is lltype.Signed:
            return llmemory.cast_adr_to_int(self.addr)
        else:
            assert 0, "XXX not implemented"

    def __repr__(self):
        "NOT_RPYTHON"
        return "const=%r" % (self.addr,)

    def repr(self):
        return "const=<0x%x>" % (llmemory.cast_adr_to_int(self.addr),)

# ____________________________________________________________

def setup_opclasses(base):
    d = {}
    for name, value in globals().items():
        if type(value) is type(base) and issubclass(value, base):
            if hasattr(value, 'opname'):
                assert value.opname not in d
                d[value.opname] = value
    return d
OPCLASSES1 = setup_opclasses(Op1)
OPCLASSES2 = setup_opclasses(Op2)
del setup_opclasses

OPCLASSES1['int_is_true'] = None


class StackOpCache:
    INITIAL_STACK_EBP_OFS = -4
stack_op_cache = StackOpCache()
stack_op_cache.lst = []

def stack_op(n):
    "Return the mem operand that designates the nth stack-spilled location"
    assert n >= 0
    lst = stack_op_cache.lst
    while len(lst) <= n:
        ofs = WORD * (StackOpCache.INITIAL_STACK_EBP_OFS - len(lst))
        lst.append(mem(ebp, ofs))
    return lst[n]

def stack_n_from_op(op):
    ofs = op.ofs_relative_to_ebp()
    return StackOpCache.INITIAL_STACK_EBP_OFS - ofs / WORD


class RegAllocator(object):
    AVAILABLE_REGS = [eax, edx, ebx, esi, edi]   # XXX ecx reserved for stuff

    # 'gv' -- GenVars, used as arguments and results of operations
    #
    # 'loc' -- location, a small integer that represents an abstract
    #          register number
    #
    # 'operand' -- a concrete machine code operand, which can be a
    #              register (ri386.eax, etc.) or a stack memory operand

    def __init__(self):
        self.nextloc = 0
        self.var2loc = {}
        self.available_locs = []
        self.force_loc2operand = {}
        self.force_operand2loc = {}
        self.initial_moves = []

    def set_final(self, final_vars_gv):
        for v in final_vars_gv:
            if not v.is_const and v not in self.var2loc:
                self.var2loc[v] = self.nextloc
                self.nextloc += 1

    def creating(self, v):
        try:
            loc = self.var2loc[v]
        except KeyError:
            pass
        else:
            self.available_locs.append(loc)   # now available again for reuse

    def using(self, v):
        if not v.is_const and v not in self.var2loc:
            try:
                loc = self.available_locs.pop()
            except IndexError:
                loc = self.nextloc
                self.nextloc += 1
            self.var2loc[v] = loc

    def allocate_locations(self, operations):
        # assign locations to gvars
        self.operations = operations
        for i in range(len(operations)-1, -1, -1):
            v = operations[i]
            self.creating(v)
            v.allocate_registers(self)

    def force_var_operands(self, force_vars, force_operands, at_start):
        force_loc2operand = self.force_loc2operand
        force_operand2loc = self.force_operand2loc
        for i in range(len(force_vars)):
            v = force_vars[i]
            try:
                loc = self.var2loc[v]
            except KeyError:
                pass
            else:
                operand = force_operands[i]
                if loc in force_loc2operand or operand in force_operand2loc:
                    if not at_start: raise NotImplementedError
                    self.initial_moves.append((loc, operand))
                else:
                    force_loc2operand[loc] = operand
                    force_operand2loc[operand] = loc

    def allocate_registers(self):
        # assign registers to locations that don't have one already
        force_loc2operand = self.force_loc2operand
        operands = []
        seen_regs = 0
        seen_stackn = {}
        for op in force_loc2operand.values():
            if isinstance(op, REG):
                seen_regs |= 1 << op.op
            elif isinstance(op, MODRM):
                seen_stackn[stack_n_from_op(op)] = None
        i = 0
        stackn = 0
        for loc in range(self.nextloc):
            try:
                operand = force_loc2operand[loc]
            except KeyError:
                # grab the next free register
                try:
                    while True:
                        operand = RegAllocator.AVAILABLE_REGS[i]
                        i += 1
                        if not (seen_regs & (1 << operand.op)):
                            break
                except IndexError:
                    while stackn in seen_stackn:
                        stackn += 1
                    operand = stack_op(stackn)
                    stackn += 1
            operands.append(operand)
        self.operands = operands
        self.required_frame_depth = stackn

    def get_operand(self, gv_source):
        if isinstance(gv_source, IntConst):
            return imm(gv_source.value)
        else:
            loc = self.var2loc[gv_source]
            return self.operands[loc]

    def load_location_with(self, loc, gv_source):
        dstop = self.operands[loc]
        if not isinstance(dstop, REG):
            dstop = ecx
        srcop = self.get_operand(gv_source)
        if srcop != dstop:
            self.mc.MOV(dstop, srcop)
        return dstop

    def store_back_location(self, loc, operand):
        dstop = self.operands[loc]
        if operand != dstop:
            self.mc.MOV(dstop, operand)

    def generate_initial_moves(self):
        initial_moves = self.initial_moves
        # first make sure that the reserved stack frame is big enough
        last_n = self.required_frame_depth - 1
        for loc, srcoperand in initial_moves:
            if isinstance(srcoperand, MODRM):
                n = stack_n_from_op(srcoperand)
                if last_n < n:
                    last_n = n
        if last_n >= 0:
            self.mc.LEA(esp, stack_op(last_n))
        # XXX naive algo for now
        for loc, srcoperand in initial_moves:
            self.mc.PUSH(srcoperand)
        initial_moves.reverse()
        for loc, srcoperand in initial_moves:
            self.mc.POP(self.operands[loc])


class Builder(GenBuilder):
    coming_from = 0

    def __init__(self, rgenop, inputargs_gv, inputoperands):
        self.rgenop = rgenop
        self.inputargs_gv = inputargs_gv
        self.inputoperands = inputoperands

    def start_writing(self):
        self.operations = []

    def generate_block_code(self, final_vars_gv, force_vars=[],
                                                 force_operands=[]):
        allocator = RegAllocator()
        allocator.set_final(final_vars_gv)
        allocator.allocate_locations(self.operations)
        allocator.force_var_operands(force_vars, force_operands,
                                     at_start=False)
        allocator.force_var_operands(self.inputargs_gv, self.inputoperands,
                                     at_start=True)
        allocator.allocate_registers()
        mc = self.start_mc()
        allocator.mc = mc
        allocator.generate_initial_moves()
        for op in self.operations:
            op.generate(allocator)
        self.operations = None
        self.inputargs_gv = [GenVar() for v in final_vars_gv]
        self.inputoperands = [allocator.get_operand(v) for v in final_vars_gv]
        return mc

    def enter_next_block(self, kinds, args_gv):
        mc = self.generate_block_code(args_gv)
        args_gv[:] = self.inputargs_gv
        self.set_coming_from(mc)
        self.rgenop.close_mc(mc)
        self.start_writing()

    def set_coming_from(self, mc, insn=I386CodeBuilder.JMP):
        self.coming_from_insn = insn
        self.coming_from = mc.tell()
        insn(mc, rel32(0))

    def start_mc(self):
        mc = self.rgenop.open_mc()
        # update the coming_from instruction
        start = self.coming_from
        if start:
            targetaddr = mc.tell()
            end = start + 6    # XXX hard-coded, enough for JMP and Jcond
            oldmc = self.rgenop.InMemoryCodeBuilder(start, end)
            insn = self.coming_from_insn
            insn(oldmc, rel32(targetaddr))
            oldmc.done()
            self.coming_from = 0
        return mc

    def jump_if_false(self, gv_condition, args_for_jump_gv):
        newbuilder = Builder(self.rgenop, list(args_for_jump_gv), None)
        self.operations.append(JumpIfFalse(gv_condition, newbuilder))
        return newbuilder

    def finish_and_return(self, sigtoken, gv_returnvar):
        mc = self.generate_block_code([gv_returnvar], [gv_returnvar], [eax])
        # --- epilogue ---
        mc.LEA(esp, mem(ebp, -12))
        mc.POP(edi)
        mc.POP(esi)
        mc.POP(ebx)
        mc.POP(ebp)
        mc.RET()
        # ----------------
        self.rgenop.close_mc(mc)

    def end(self):
        pass

    @specialize.arg(1)
    def genop1(self, opname, gv_arg):
        cls = OPCLASSES1[opname]
        if cls is None:     # identity
            return gv_arg
        op = cls(gv_arg)
        self.operations.append(op)
        return op

    @specialize.arg(1)
    def genop2(self, opname, gv_arg1, gv_arg2):
        cls = OPCLASSES2[opname]
        op = cls(gv_arg1, gv_arg2)
        self.operations.append(op)
        return op


class RI386GenOp(AbstractRGenOp):
    from pypy.jit.codegen.i386.codebuf import MachineCodeBlock
    from pypy.jit.codegen.i386.codebuf import InMemoryCodeBuilder

    MC_SIZE = 65536
    
    def __init__(self):
        self.mcs = []   # machine code blocks where no-one is currently writing
        self.keepalive_gc_refs = [] 
        self.total_code_blocks = 0

    def open_mc(self):
        if self.mcs:
            # XXX think about inserting NOPS for alignment
            return self.mcs.pop()
        else:
            # XXX supposed infinite for now
            self.total_code_blocks += 1
            return self.MachineCodeBlock(self.MC_SIZE)

    def close_mc(self, mc):
        # an open 'mc' is ready for receiving code... but it's also ready
        # for being garbage collected, so be sure to close it if you
        # want the generated code to stay around :-)
        self.mcs.append(mc)

    def check_no_open_mc(self):
        assert len(self.mcs) == self.total_code_blocks

    def newgraph(self, sigtoken, name):
        # --- prologue ---
        mc = self.open_mc()
        entrypoint = mc.tell()
        if conftest.option.trap:
            mc.BREAKPOINT()
        mc.PUSH(ebp)
        mc.MOV(ebp, esp)
        mc.PUSH(ebx)
        mc.PUSH(esi)
        mc.PUSH(edi)
        self.close_mc(mc)
        # NB. a bit of a hack: the first generated block of the function
        # will immediately follow, by construction
        # ----------------
        numargs = sigtoken     # for now
        inputargs_gv = []
        inputoperands = []
        for i in range(numargs):
            inputargs_gv.append(GenVar())
            inputoperands.append(mem(ebp, WORD * (2+i)))
        builder = Builder(self, inputargs_gv, inputoperands)
        builder.start_writing()
        #ops = [OpSameAs(v) for v in inputargs_gv]
        #builder.operations.extend(ops)
        #inputargs_gv = ops
        return builder, IntConst(entrypoint), inputargs_gv[:]

##    def replay(self, label, kinds):
##        return ReplayBuilder(self), [dummy_var] * len(kinds)

    @specialize.genconst(1)
    def genconst(self, llvalue):
        T = lltype.typeOf(llvalue)
        if T is llmemory.Address:
            return AddrConst(llvalue)
        elif isinstance(T, lltype.Primitive):
            return IntConst(lltype.cast_primitive(lltype.Signed, llvalue))
        elif isinstance(T, lltype.Ptr):
            lladdr = llmemory.cast_ptr_to_adr(llvalue)
            if T.TO._gckind == 'gc':
                self.keepalive_gc_refs.append(lltype.cast_opaque_ptr(llmemory.GCREF, llvalue))
            return AddrConst(lladdr)
        else:
            assert 0, "XXX not implemented"
    
    # attached later constPrebuiltGlobal = global_rgenop.genconst

    @staticmethod
    @specialize.memo()
    def fieldToken(T, name):
        FIELD = getattr(T, name)
        if isinstance(FIELD, lltype.ContainerType):
            fieldsize = 0      # not useful for getsubstruct
        else:
            fieldsize = llmemory.sizeof(FIELD)
        return (llmemory.offsetof(T, name), fieldsize)

    @staticmethod
    @specialize.memo()
    def allocToken(T):
        return llmemory.sizeof(T)

    @staticmethod
    @specialize.memo()
    def varsizeAllocToken(T):
        if isinstance(T, lltype.Array):
            return RI386GenOp.arrayToken(T)
        else:
            # var-sized structs
            arrayfield = T._arrayfld
            ARRAYFIELD = getattr(T, arrayfield)
            arraytoken = RI386GenOp.arrayToken(ARRAYFIELD)
            length_offset, items_offset, item_size = arraytoken
            arrayfield_offset = llmemory.offsetof(T, arrayfield)
            return (arrayfield_offset+length_offset,
                    arrayfield_offset+items_offset,
                    item_size)

    @staticmethod
    @specialize.memo()    
    def arrayToken(A):
        return (llmemory.ArrayLengthOffset(A),
                llmemory.ArrayItemsOffset(A),
                llmemory.ItemOffset(A.OF))

    @staticmethod
    @specialize.memo()
    def kindToken(T):
        if T is lltype.Float:
            py.test.skip("not implemented: floats in the i386 back-end")
        return None     # for now

    @staticmethod
    @specialize.memo()
    def sigToken(FUNCTYPE):
        numargs = 0
        for ARG in FUNCTYPE.ARGS:
            if ARG is not lltype.Void:
                numargs += 1
        return numargs     # for now

    @staticmethod
    def erasedType(T):
        if T is llmemory.Address:
            return llmemory.Address
        if isinstance(T, lltype.Primitive):
            return lltype.Signed
        elif isinstance(T, lltype.Ptr):
            return llmemory.GCREF
        else:
            assert 0, "XXX not implemented"

global_rgenop = RI386GenOp()
RI386GenOp.constPrebuiltGlobal = global_rgenop.genconst
