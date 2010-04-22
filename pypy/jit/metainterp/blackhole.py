from pypy.rlib.unroll import unrolling_iterable
from pypy.rlib.rarithmetic import intmask, LONG_BIT, r_uint
from pypy.tool.sourcetools import func_with_new_name
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.lltypesystem.lloperation import llop


def arguments(*argtypes, **kwds):
    resulttype = kwds.pop('returns', None)
    assert not kwds
    def decorate(function):
        function.argtypes = argtypes
        function.resulttype = resulttype
        return function
    return decorate

class LeaveFrame(Exception):
    pass

class MissingValue(object):
    pass

def signedord(c):
    value = ord(c)
    value = intmask(value << (LONG_BIT-8)) >> (LONG_BIT-8)
    return value


class BlackholeInterpreter(object):

    def __init__(self, cpu=None):
        self.cpu = cpu
        self.registers_i = [MissingValue()] * 256
        self.registers_r = [MissingValue()] * 256
        self.registers_f = [MissingValue()] * 256

    def _freeze_(self):
        self.registers_i = [0] * 256
        self.registers_r = [NULL] * 256
        self.registers_f = [0.0] * 256
        return False

    def setup_insns(self, insns):
        assert len(insns) <= 256, "too many instructions!"
        self._insns = [None] * len(insns)
        for key, value in insns.items():
            assert self._insns[value] is None
            self._insns[value] = key
        #
        all_funcs = []
        for key in self._insns:
            assert key.count('/') == 1, "bad key: %r" % (key,)
            name, argcodes = key.split('/')
            all_funcs.append(self._get_method(name, argcodes))
        all_funcs = unrolling_iterable(enumerate(all_funcs))
        #
        def dispatch_loop(code, position):
            while True:
                opcode = ord(code[position])
                position += 1
                for i, func in all_funcs:
                    if opcode == i:
                        position = func(code, position)
                        break
                else:
                    raise AssertionError("bad opcode")
        dispatch_loop._dont_inline_ = True
        self.dispatch_loop = dispatch_loop

    def _get_method(self, name, argcodes):
        #
        def handler(code, position):
            args = ()
            next_argcode = 0
            for argtype in argtypes:
                if argtype == 'i':
                    # argcode can be 'i' or 'c'; 'c' stands for a single
                    # signed byte that gives the value of a small constant.
                    argcode = argcodes[next_argcode]
                    next_argcode = next_argcode + 1
                    if argcode == 'i':
                        value = self.registers_i[ord(code[position])]
                    elif argcode == 'c':
                        value = signedord(code[position])
                    else:
                        raise AssertionError("bad argcode")
                    position += 1
                elif argtype == 'L':
                    # argcode should be 'L' too
                    assert argcodes[next_argcode] == 'L'
                    next_argcode = next_argcode + 1
                    value = ord(code[position]) | (ord(code[position+1])<<8)
                    position += 2
                elif argtype == 'I' or argtype == 'R' or argtype == 'F':
                    assert argcodes[next_argcode] == argtype
                    next_argcode = next_argcode + 1
                    length = ord(code[position])
                    position += 1
                    value = []
                    for i in range(length):
                        index = ord(code[position+i])
                        if   argtype == 'I': reg = self.registers_i[index]
                        elif argtype == 'R': reg = self.registers_r[index]
                        elif argtype == 'F': reg = self.registers_f[index]
                        value.append(reg)
                    position += length
                elif argtype == 'pc':
                    value = position
                else:
                    raise AssertionError("bad argtype: %r" % (argtype,))
                args += (value,)
            result = boundmethod(*args)
            if resulttype == 'i':
                # argcode should be 'i' too
                assert argcodes[next_argcode] == 'i'
                next_argcode = next_argcode + 1
                self.registers_i[ord(code[position])] = result
                position += 1
            elif resulttype == 'L':
                position = result
            else:
                assert resulttype is None
                assert result is None
            assert next_argcode == len(argcodes)
            return position
        #
        boundmethod = getattr(self, 'opimpl_' + name)
        argtypes = unrolling_iterable(boundmethod.argtypes)
        resulttype = boundmethod.resulttype
        handler = func_with_new_name(handler, 'handler_' + name)
        return handler

    def setarg_i(self, index, value):
        self.registers_i[index] = value

    def run(self, jitcode, position):
        self.copy_constants(self.registers_i, jitcode.constants_i)
        self.copy_constants(self.registers_r, jitcode.constants_r)
        self.copy_constants(self.registers_f, jitcode.constants_f)
        code = jitcode.code
        try:
            self.dispatch_loop(code, position)
        except LeaveFrame:
            pass

    # XXX must be specialized
    # XXX the real performance impact of the following loop is unclear
    def copy_constants(self, registers, constants):
        """Copy jitcode.constants[0] to registers[255],
                jitcode.constants[1] to registers[254],
                jitcode.constants[2] to registers[253], etc."""
        i = len(constants) - 1
        while i >= 0:
            j = 255 - i
            assert j >= 0
            registers[j] = constants[i]
            i -= 1

    # ----------

    @arguments("i", "i", returns="i")
    def opimpl_int_add(self, a, b):
        return a + b

    @arguments("i", "i", returns="i")
    def opimpl_int_sub(self, a, b):
        return a - b

    @arguments("i", "i", returns="i")
    def opimpl_uint_floordiv(self, a, b):
        c = llop.uint_floordiv(lltype.Unsigned, r_uint(a), r_uint(b))
        return intmask(c)

    @arguments("i")
    def opimpl_int_return(self, a):
        self.result_i = a
        raise LeaveFrame

    @arguments("i", returns="i")
    def opimpl_int_copy(self, a):
        return a

    @arguments("r", returns="r")
    def opimpl_ref_copy(self, a):
        return a

    @arguments("f", returns="f")
    def opimpl_float_copy(self, a):
        return a

    @arguments("L", "i", "i", "pc", returns="L")
    def opimpl_goto_if_not_int_lt(self, target, a, b, pc):
        if a < b:
            return pc
        else:
            return target

    @arguments("L", "i", "i", "pc", returns="L")
    def opimpl_goto_if_not_int_le(self, target, a, b, pc):
        if a <= b:
            return pc
        else:
            return target

    @arguments("L", "i", "i", "pc", returns="L")
    def opimpl_goto_if_not_int_eq(self, target, a, b, pc):
        if a == b:
            return pc
        else:
            return target

    @arguments("L", "i", "i", "pc", returns="L")
    def opimpl_goto_if_not_int_ne(self, target, a, b, pc):
        if a != b:
            return pc
        else:
            return target

    @arguments("L", "i", "i", "pc", returns="L")
    def opimpl_goto_if_not_int_gt(self, target, a, b, pc):
        if a > b:
            return pc
        else:
            return target

    @arguments("L", "i", "i", "pc", returns="L")
    def opimpl_goto_if_not_int_ge(self, target, a, b, pc):
        if a >= b:
            return pc
        else:
            return target

    @arguments("L", returns="L")
    def opimpl_goto(self, target):
        return target

    @arguments("i", "I", "R", returns="i")
    def opimpl_residual_call_ir_i(self, function, args_i, args_r):
        # XXX!
        assert not args_r
        return function(*args_i)

    @arguments("i", "I", "R", returns="r")
    def opimpl_residual_call_ir_r(self, function, args_i, args_r):
        # XXX!
        assert not args_r
        return function(*args_i)

    @arguments("i", "R", returns="i")
    def opimpl_residual_call_r_i(self, function, args_r):
        # XXX!
        return function(*args_r)

    @arguments("i", "R", returns="r")
    def opimpl_residual_call_r_r(self, function, args_r):
        # XXX!
        return function(*args_r)
