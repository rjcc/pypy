from rpython.rlib.objectmodel import we_are_translated
from rpython.jit.metainterp.history import newconst
from rpython.jit.codewriter import longlong
from rpython.jit.metainterp.resoperation import rop

def do_call(cpu, argboxes, descr):
    from rpython.jit.metainterp.history import INT, REF, FLOAT, VOID
    from rpython.jit.metainterp.blackhole import NULL
    from rpython.jit.metainterp.executor import _separate_call_arguments
    rettype = descr.get_result_type()
    # count the number of arguments of the different types
    args_i, args_r, args_f = _separate_call_arguments(argboxes)
    # get the function address as an integer
    func = argboxes[0].getint()
    # do the call using the correct function from the cpu
    if rettype == INT:
        return newconst(cpu.bh_call_i(func, args_i, args_r, args_f, descr))
    if rettype == REF:
        return newconst(cpu.bh_call_r(func, args_i, args_r, args_f, descr))
    if rettype == FLOAT:
        return newconst(cpu.bh_call_f(func, args_i, args_r, args_f, descr))
    if rettype == VOID:
        # don't even need to call the void function, result will always match
        return None
    raise AssertionError("bad rettype")


class CompatibilityCondition(object):
    """ A collections of conditions that an object needs to fulfil. """
    def __init__(self, ptr):
        self.known_valid = ptr
        self.conditions = []
        self.last_quasi_immut_field_op = None
        # -1 means "stay on the original trace"
        self.jump_target = -1

    def record_condition(self, cond, res, optimizer):
        for oldcond in self.conditions:
            if oldcond.same_cond(cond, res):
                return
        cond.activate(res, optimizer)
        if self.conditions and self.conditions[-1].debug_mp_str == cond.debug_mp_str:
            cond.debug_mp_str = ''
        self.conditions.append(cond)

    def register_quasi_immut_field(self, op):
        self.last_quasi_immut_field_op = op

    def check_compat_and_activate(self, cpu, ref, loop_token):
        for cond in self.conditions:
            if not cond.check(cpu, ref):
                return False
        # need to tell all conditions, in case a quasi-immut needs to be registered
        for cond in self.conditions:
            cond.activate_secondary(ref, loop_token)
        return True

    def prepare_const_arg_call(self, op, optimizer):
        from rpython.jit.metainterp.quasiimmut import QuasiImmutDescr
        # replace further arguments by constants, if the optimizer knows them
        # already
        last_nonconst_index = -1
        for i in range(2, op.numargs()):
            arg = op.getarg(i)
            constarg = optimizer.get_constant_box(arg)
            if constarg is not None:
                op.setarg(i, constarg)
            else:
                last_nonconst_index = i
        copied_op = op.copy()
        copied_op.setarg(1, self.known_valid)
        if op.numargs() == 2:
            return copied_op, PureCallCondition(op, optimizer)
        arg2 = copied_op.getarg(2)
        if arg2.is_constant():
            # already a constant, can just use PureCallCondition
            if last_nonconst_index != -1:
                return None, None # a non-constant argument, can't optimize
            return copied_op, PureCallCondition(op, optimizer)
        if last_nonconst_index != 2:
            return None, None

        # really simple-minded pattern matching
        # the order of things is like this:
        # GUARD_COMPATIBLE(x)
        # QUASIIMMUT_FIELD(x)
        # y = GETFIELD_GC(x, f)
        # z = CALL_PURE(x, y, ...)
        # we want to discover this (and so far precisely this) situation and
        # make it possible for the GUARD_COMPATIBLE to still remove the call,
        # even though the second argument is not constant
        if arg2.getopnum() not in (rop.GETFIELD_GC_R, rop.GETFIELD_GC_I, rop.GETFIELD_GC_F):
            return None, None
        if not self.last_quasi_immut_field_op:
            return None, None
        qmutdescr = self.last_quasi_immut_field_op.getdescr()
        assert isinstance(qmutdescr, QuasiImmutDescr)
        fielddescr = qmutdescr.fielddescr # XXX
        same_arg = self.last_quasi_immut_field_op.getarg(0) is arg2.getarg(0)
        if arg2.getdescr() is not fielddescr or not same_arg:
            return None, None
        if not qmutdescr.is_still_valid_for(self.known_valid):
            return None, None
        copied_op.setarg(2, qmutdescr.constantfieldbox)
        self.last_quasi_immut_field_op = None
        return copied_op, QuasiimmutGetfieldAndPureCallCondition(
                op, qmutdescr, optimizer)

    def emit_conditions(self, op, short, optimizer):
        """ re-emit the conditions about variable op into the short preamble
        """
        for cond in self.conditions:
            cond.emit_condition(op, short, optimizer)

    def repr_of_conditions(self, argrepr="?"):
        return "\n".join([cond.repr(argrepr) for cond in self.conditions])



class Condition(object):
    def __init__(self, optimizer):
        self.metainterp_sd = optimizer.metainterp_sd
        # XXX maybe too expensive
        op = optimizer._last_debug_merge_point
        if op:
            jd_sd = self.metainterp_sd.jitdrivers_sd[op.getarg(0).getint()]
            s = jd_sd.warmstate.get_location_str(op.getarglist()[3:])
            s = s.replace(',', '.') # we use comma for argument splitting
        else:
            s = ''
        self.debug_mp_str = s
        self.rpyfunc = None

    def check(self, cpu, ref):
        raise NotImplementedError

    def activate(self, ref, optimizer):
        self.res = ref

    def activate_secondary(self, ref, loop_token):
        pass

    def same_cond(self, other, res):
        return False

    def repr(self):
        return ""

    def emit_condition(self, op, short, optimizer):
        raise NotImplementedError("abstract base class")

    def _repr_const(self, arg):
        from rpython.jit.metainterp.history import ConstInt, ConstFloat, ConstPtr
        from rpython.rtyper.annlowlevel import llstr, hlstr
        from rpython.rtyper.lltypesystem import llmemory, rstr, rffi, lltype

        if isinstance(arg, ConstInt):
            return str(arg.value)
        elif isinstance(arg, ConstPtr):
            if arg.value:
                # through all the layers and back
                if we_are_translated():
                    tid = self.metainterp_sd.cpu.get_actual_typeid(arg.getref_base())
                    sid = self.metainterp_sd.cpu.get_actual_typeid(rffi.cast(llmemory.GCREF, llstr("abc")))
                    if sid == tid:
                        return hlstr(rffi.cast(lltype.Ptr(rstr.STR), arg.getref_base()))
                return "<some const ptr>"
            else:
                return "None"
        elif isinstance(arg, ConstFloat):
            return str(arg.getfloat())
        return "<huh?>"

class PureCallCondition(Condition):
    const_args_start_at = 2

    def __init__(self, op, optimizer):
        from rpython.jit.metainterp.history import Const
        Condition.__init__(self, optimizer)
        args = op.getarglist()[:]
        args[1] = None
        self.args = args
        for index in range(self.const_args_start_at, len(args)):
            arg = args[index]
            assert isinstance(arg, Const)
        self.descr = op.getdescr()
        self.rpyfunc = op.rpyfunc

    def check(self, cpu, ref):
        from rpython.rlib.debug import debug_print, debug_start, debug_stop
        calldescr = self.descr
        # change exactly the first argument
        arglist = self.args
        arglist[1] = newconst(ref)
        try:
            res = do_call(cpu, arglist, calldescr)
        except Exception:
            debug_start("jit-guard-compatible")
            debug_print("call to elidable_compatible function raised")
            debug_stop("jit-guard-compatible")
            return False
        finally:
            arglist[1] = None
        if not res.same_constant(self.res):
            return False
        return True

    def same_cond(self, other, res):
        if type(other) is not PureCallCondition:
            return False
        if len(self.args) != len(other.args):
            return False
        if not self.res.same_constant(res):
            return False
        if self.descr is not other.descr:
            return False
        assert self.args[1] is other.args[1] is None
        for i in range(len(self.args)):
            if i == 1:
                continue
            if not self.args[i].same_constant(other.args[i]):
                return False
        return True

    def emit_condition(self, op, short, optimizer):
        from rpython.jit.metainterp.history import INT, REF, FLOAT, VOID
        from rpython.jit.metainterp.resoperation import rop, ResOperation
        # woah, mess
        args = self.args[:]
        args[1] = op
        descr = self.descr
        rettype = descr.get_result_type()
        if rettype == INT:
            call_op = ResOperation(rop.CALL_PURE_I, args, descr)
        elif rettype == FLOAT:
            call_op = ResOperation(rop.CALL_PURE_F, args, descr)
        elif rettype == REF:
            call_op = ResOperation(rop.CALL_PURE_R, args, descr)
        else:
            assert rettype == VOID
            # XXX maybe we should forbid this
            call_op = ResOperation(rop.CALL_PURE_R, args, descr)
            short.append(call_op)
            return
        short.append(call_op)
        short.append(ResOperation(rop.GUARD_VALUE, [call_op, self.res]))


    def repr(self, argrepr="?"):
        addr = self.args[0].getaddr()
        funcname = self.metainterp_sd.get_name_from_address(addr)
        if not funcname:
            funcname = hex(self.args[0].getint())
        result = self._repr_const(self.res)
        if len(self.args) == 2:
            extra = ''
        else:
            extra = ', ' + ', '.join([self._repr_const(arg) for arg in self.args[2:]])
        res = "compatible if %s == %s(%s%s)" % (result, funcname, argrepr, extra)
        if self.rpyfunc:
            res = "%s: %s" % (self.rpyfunc, res)
        if self.debug_mp_str:
            res = self.debug_mp_str + "\n" + res
        return res


class QuasiimmutGetfieldAndPureCallCondition(PureCallCondition):
    const_args_start_at = 3

    def __init__(self, op, qmutdescr, optimizer):
        PureCallCondition.__init__(self, op, optimizer)
        self.args[2] = None
        # XXX not 100% sure whether it's save to store the whole descr
        self.qmutdescr = qmutdescr
        self.qmut = qmutdescr.qmut
        self.mutatefielddescr = qmutdescr.mutatefielddescr
        self.fielddescr = qmutdescr.fielddescr

    def activate(self, ref, optimizer):
        # record the quasi-immutable
        optimizer.record_quasi_immutable_dep(self.qmut)
        # XXX can set self.qmut to None here?
        Condition.activate(self, ref, optimizer)

    def activate_secondary(self, ref, loop_token):
        from rpython.jit.metainterp.quasiimmut import get_current_qmut_instance
        # need to register the loop for invalidation as well!
        qmut = get_current_qmut_instance(loop_token.cpu, ref,
                                         self.mutatefielddescr)
        qmut.register_loop_token(loop_token.loop_token_wref)

    def check(self, cpu, ref):
        from rpython.rlib.debug import debug_print, debug_start, debug_stop
        from rpython.jit.metainterp.quasiimmut import QuasiImmutDescr
        calldescr = self.descr
        # change exactly the first argument
        arglist = self.args
        arglist[1] = newconst(ref)
        arglist[2] = QuasiImmutDescr._get_fieldvalue(self.fielddescr, ref, cpu)
        try:
            res = do_call(cpu, arglist, calldescr)
        except Exception:
            debug_start("jit-guard-compatible")
            debug_print("call to elidable_compatible function raised")
            debug_stop("jit-guard-compatible")
            return False
        finally:
            arglist[1] = arglist[2] = None
        if not res.same_constant(self.res):
            return False
        return True

    def same_cond(self, other, res):
        if type(other) is not QuasiimmutGetfieldAndPureCallCondition:
            return False
        if len(self.args) != len(other.args):
            return False
        if not self.res.same_constant(res):
            return False
        if self.descr is not other.descr:
            return False
        if self.fielddescr is not other.fielddescr:
            return False
        if self.mutatefielddescr is not other.mutatefielddescr:
            return False
        assert self.args[1] is other.args[1] is None
        assert self.args[2] is other.args[2] is None
        for i in range(len(self.args)):
            if i == 1 or i == 2:
                continue
            if not self.args[i].same_constant(other.args[i]):
                return False
        return True

    def emit_condition(self, op, short, optimizer):
        from rpython.jit.metainterp.resoperation import rop, ResOperation
        # more mess
        fielddescr = self.fielddescr
        if fielddescr.is_pointer_field():
            getfield_op = ResOperation(
                rop.GETFIELD_GC_R, [op], fielddescr)
        elif fielddescr.is_float_field():
            getfield_op = ResOperation(
                rop.GETFIELD_GC_F, [op], fielddescr)
        else:
            getfield_op = ResOperation(
                rop.GETFIELD_GC_I, [op], fielddescr)
        short.extend([
            ResOperation(
                rop.QUASIIMMUT_FIELD, [op], self.qmutdescr),
            ResOperation(
                rop.GUARD_NOT_INVALIDATED, []),
            getfield_op])
        index = len(short)
        PureCallCondition.emit_condition(self, op, short, optimizer)
        call_op = short[index]
        assert call_op.opnum in (
                rop.CALL_PURE_I, rop.CALL_PURE_R,
                rop.CALL_PURE_F, rop.CALL_PURE_N)
        call_op.setarg(2, getfield_op)

    def repr(self, argrepr="?"):
        addr = self.args[0].getaddr()
        funcname = self.metainterp_sd.get_name_from_address(addr)
        result = self._repr_const(self.res)
        if len(self.args) == 3:
            extra = ''
        else:
            extra = ', ' + ', '.join([self._repr_const(arg) for arg in self.args[3:]])
        attrname = self.fielddescr.repr_of_descr()
        res = "compatible if %s == %s(%s, %s.%s%s)" % (
                result, funcname, argrepr, argrepr, attrname, extra)
        if self.rpyfunc:
            res = "%s: %s" % (self.rpyfunc, res)
        if self.debug_mp_str:
            res = self.debug_mp_str + "\n" + res
        return res
