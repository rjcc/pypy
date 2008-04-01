from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython.ootypesystem import ootype

class Memo(object):
    _annspecialcase_ = 'specialize:ctr_location'

    def __init__(self):
        self.boxes = {}
        self.containers = {}

def enter_block_memo():
    return Memo()

def freeze_memo():
    return Memo()

def exactmatch_memo(rgenop, force_merge=False):
    memo = Memo()
    memo.rgenop = rgenop
    memo.partialdatamatch = {}
    memo.forget_nonzeroness = {}
    memo.force_merge=force_merge
    return memo

def copy_memo():
    return Memo()

def unfreeze_memo():
    return Memo()

def make_vrti_memo():
    return Memo()

class DontMerge(Exception):
    pass

class LLTypeMixin(object):
    _mixin_ = True

    def _revealconst(self, gv):
        return gv.revealconst(llmemory.Address)

class OOTypeMixin(object):
    _mixin_ = True

    def _revealconst(self, gv):
        return gv.revealconst(ootype.Object)


class RedBox(object):
    _attrs_ = ['genvar', 'most_recent_frozen']
    most_recent_frozen = None

    def __init__(self, genvar=None):
        self.genvar = genvar    # None or a genvar

    def __repr__(self):
        if not self.genvar:
            return '<dummy>'
        else:
            return '<%r>' % (self.genvar,)

    def is_constant(self):
        return bool(self.genvar) and self.genvar.is_const
    
    def getkind(self):
        assert self.genvar is not None
        return self.genvar.getkind()

    def getgenvar(self, jitstate):
        return self.genvar

    def setgenvar(self, newgenvar):
        assert not self.is_constant()
        self.genvar = newgenvar

    def learn_boolvalue(self, jitstate, boolval):
        return True

    def enter_block(self, incoming, memo):
        memo = memo.boxes
        if not self.is_constant() and self not in memo:
            incoming.append(self)
            memo[self] = None

    def freeze(self, memo):
        memo = memo.boxes
        try:
            return memo[self]
        except KeyError:
            assert self.genvar is not None
            result = self.most_recent_frozen
            if result is None:
                result = self.getfrozen(self.genvar)
                self.most_recent_frozen = result
            else:
                # sanity-check the most_recent_frozen object
                if self.genvar.is_const:
                    assert isinstance(result, FrozenConst)
                else:
                    assert isinstance(result, FrozenVar)
            memo[self] = result
            return result

    def forcevar(self, jitstate, memo, forget_nonzeroness):
        if self.is_constant():
            # cannot mutate constant boxes in-place
            builder = jitstate.curbuilder
            box = self.copy(memo)
            box.genvar = builder.genop_same_as(self.genvar)
            return box
        else:
            return self

    def replace(self, memo):
        memo = memo.boxes
        return memo.setdefault(self, self)

    def see_promote(self):
        if self.most_recent_frozen is not None:
            self.most_recent_frozen.will_be_promoted = True
            self.most_recent_frozen = None


def ll_redboxcls(TYPE):
    assert TYPE is not lltype.Void, "cannot make red boxes of voids"
    return ll_redboxbuilder(TYPE)

def redboxbuilder_void(gv_value): return None
def redboxbuilder_int(gv_value): return IntRedBox(gv_value)
def redboxbuilder_dbl(gv_value): return DoubleRedBox(gv_value)
def redboxbuilder_ptr(gv_value): return PtrRedBox(gv_value)
def redboxbuilder_inst(gv_value): return InstanceRedBox(gv_value)
def redboxbuilder_bool(gv_value): return BoolRedBox(gv_value)

def ll_redboxbuilder(TYPE):
    if TYPE is lltype.Void:
        return redboxbuilder_void
    elif isinstance(TYPE, lltype.Ptr):
        return redboxbuilder_ptr
    elif TYPE is lltype.Float:
        return redboxbuilder_dbl
    elif isinstance(TYPE, ootype.OOType):
        return redboxbuilder_inst
    elif TYPE == lltype.Bool:
        return redboxbuilder_bool
    else:
        assert isinstance(TYPE, lltype.Primitive)
        # XXX what about long longs?
        return redboxbuilder_int

def ll_fromvalue(jitstate, value):
    "Make a constant RedBox from a low-level value."
    gv = ll_gv_fromvalue(jitstate, value)
    T = lltype.typeOf(value)
    cls = ll_redboxcls(T)
    return cls(gv)

def redbox_from_prebuilt_value(RGenOp, value):
    T = lltype.typeOf(value)
    gv = RGenOp.constPrebuiltGlobal(value)
    cls = ll_redboxcls(T)
    return cls(gv)

def ll_gv_fromvalue(jitstate, value):
    rgenop = jitstate.curbuilder.rgenop
    gv = rgenop.genconst(value)
    return gv

def ll_getvalue(box, T):
    "Return the content of a known-to-be-constant RedBox."
    return box.genvar.revealconst(T)


class IntRedBox(RedBox):
    "A red box that contains a constant integer-like value."

    def learn_boolvalue(self, jitstate, boolval):
        if self.is_constant():
            return self.genvar.revealconst(lltype.Bool) == boolval
        else:
            self.setgenvar(ll_gv_fromvalue(jitstate, boolval))
            return True

    def copy(self, memo):
        memo = memo.boxes
        try:
            return memo[self]
        except KeyError:
            result = memo[self] = IntRedBox(self.genvar)
            return result

    @staticmethod
    def getfrozen(gv_value):
        if gv_value.is_const:
            return FrozenIntConst(gv_value)
        else:
            return FrozenIntVar()


class BoolRedBox(RedBox):
    # XXX make true and false singletons?

    def __init__(self, genvar):
        RedBox.__init__(self, genvar)
        self.iftrue = []

    def learn_boolvalue(self, jitstate, boolval):
        if self.is_constant():
            return self.genvar.revealconst(lltype.Bool) == boolval
        else:
            self.setgenvar(ll_gv_fromvalue(jitstate, boolval))
            result = True
            for effect in self.iftrue:
                result = effect.learn_boolvalue(jitstate, boolval) and result
            self.iftrue = []
            return result
            
    def copy(self, memo):
        memoboxes = memo.boxes
        try:
            return memoboxes[self]
        except KeyError:
            result = memoboxes[self] = BoolRedBox(self.genvar)
            result.iftrue = [effect.copy(memo) for effect in self.iftrue]
            return result

    @staticmethod
    def getfrozen(gv_value):
        if gv_value.is_const:
            return FrozenBoolConst(gv_value)
        else:
            return FrozenBoolVar()


class DoubleRedBox(RedBox):
    "A red box that contains a constant double-precision floating point value."

    def copy(self, memo):
        memo = memo.boxes
        try:
            return memo[self]
        except KeyError:
            result = memo[self] = DoubleRedBox(self.genvar)
            return result

    @staticmethod
    def getfrozen(gv_value):
        if gv_value.is_const:
            return FrozenDoubleConst(gv_value)
        else:
            return FrozenDoubleVar()


class AbstractPtrRedBox(RedBox):
    """
    Base class for PtrRedBox (lltype) and InstanceRedBox (ootype)
    """

    content = None   # or an AbstractContainer

    def __init__(self, genvar=None, known_nonzero=False):
        self.genvar = genvar    # None or a genvar
        if genvar is not None and genvar.is_const:
            known_nonzero = bool(self._revealconst(genvar))
        self.known_nonzero = known_nonzero

    def setgenvar(self, newgenvar):
        RedBox.setgenvar(self, newgenvar)
        self.known_nonzero = (newgenvar.is_const and
                              bool(self._revealconst(newgenvar)))

    def setgenvar_hint(self, newgenvar, known_nonzero):
        RedBox.setgenvar(self, newgenvar)
        self.known_nonzero = known_nonzero

    def learn_nonzeroness(self, jitstate, nonzeroness):
        ok = True
        if nonzeroness:
            if self.is_constant():
                ok = self.known_nonzero   # not ok if constant zero
            else:
                self.known_nonzero = True
        else:
            if self.known_nonzero:
                ok = False
            elif not self.is_constant():
                assert self.genvar is not None
                kind = self.genvar.getkind()
                gv_null = jitstate.curbuilder.rgenop.genzeroconst(kind)
                self.setgenvar_hint(gv_null, known_nonzero=False)
        return ok

    learn_boolvalue = learn_nonzeroness

    def __repr__(self):
        if not self.genvar and self.content is not None:
            return '<virtual %s>' % (self.content,)
        else:
            return RedBox.__repr__(self)

    def copy(self, memo):
        boxmemo = memo.boxes
        try:
            result = boxmemo[self]
        except KeyError:
            result = self.__class__(self.genvar, self.known_nonzero)
            boxmemo[self] = result
            if self.content:
                result.content = self.content.copy(memo)
        assert isinstance(result, AbstractPtrRedBox)
        return result

    def replace(self, memo):
        boxmemo = memo.boxes
        try:
            result = boxmemo[self]
        except KeyError:
            boxmemo[self] = self
            if self.content:
                self.content.replace(memo)
            result = self
        assert isinstance(result, AbstractPtrRedBox)
        return result

    def freeze(self, memo):
        boxmemo = memo.boxes
        try:
            return boxmemo[self]
        except KeyError:
            content = self.content
            if content is None:
                assert self.genvar is not None
                result = self.most_recent_frozen
                if result is None:
                    if self.genvar.is_const:
                        result = self.FrozenPtrConst(self.genvar)
                    else:
                        result = self.FrozenPtrVar(self.known_nonzero)
                    self.most_recent_frozen = result
                else:
                    # sanity-check the most_recent_frozen object
                    if self.genvar.is_const:
                        assert isinstance(result, self.FrozenPtrConst)
                    else:
                        assert isinstance(result, self.FrozenPtrVar)
                return result
            self.most_recent_frozen = None   # for now
            if not self.genvar:
                from pypy.jit.timeshifter import rcontainer
                assert isinstance(content, rcontainer.VirtualContainer)
                result = self.FrozenPtrVirtual()
                # store the result in the memo before content.freeze(),
                # for recursive data structures
                boxmemo[self] = result
                result.fz_content = content.freeze(memo)
            else:
                # if self.content is not None, it's a PartialDataStruct
                from pypy.jit.timeshifter import rcontainer
                assert isinstance(content, rcontainer.PartialDataStruct)
                result = self.FrozenPtrVarWithPartialData(known_nonzero=True)
                # store the result in the memo before content.freeze(),
                # for recursive data structures
                boxmemo[self] = result
                result.fz_partialcontent = content.partialfreeze(memo)
            return result

    def getgenvar(self, jitstate):
        if not self.genvar:
            content = self.content
            from pypy.jit.timeshifter import rcontainer
            if isinstance(content, rcontainer.VirtualizableStruct):
                return content.getgenvar(jitstate)
            assert isinstance(content, rcontainer.VirtualContainer)
            content.force_runtime_container(jitstate)
            assert self.genvar
        return self.genvar

    def forcevar(self, jitstate, memo, forget_nonzeroness):
        from pypy.jit.timeshifter import rcontainer
        # xxx
        assert not isinstance(self.content, rcontainer.VirtualizableStruct)
        if self.is_constant():
            # cannot mutate constant boxes in-place
            builder = jitstate.curbuilder
            box = self.copy(memo)
            box.genvar = builder.genop_same_as(self.genvar)
        else:
            # force virtual containers
            self.getgenvar(jitstate)
            box = self

        if forget_nonzeroness:
            box.known_nonzero = False
        return box

    def enter_block(self, incoming, memo):
        if self.genvar:
            RedBox.enter_block(self, incoming, memo)
        if self.content:
            self.content.enter_block(incoming, memo)

    def op_getfield(self, jitstate, fielddesc):
        self.learn_nonzeroness(jitstate, True)
        if self.content is not None:
            box = self.content.op_getfield(jitstate, fielddesc)
            if box is not None:
                return box
        gv_ptr = self.getgenvar(jitstate)
        box = fielddesc.generate_get(jitstate, gv_ptr)
        if fielddesc.immutable:
            self.remember_field(fielddesc, box)
        fz = self.most_recent_frozen
        if fz is not None:
            newfz = fz.get_ghost_child(fielddesc, box.genvar)
            box.most_recent_frozen = newfz
        return box

    def op_setfield(self, jitstate, fielddesc, valuebox):
        self.learn_nonzeroness(jitstate, True)
        gv_ptr = self.genvar
        if gv_ptr:
            fielddesc.generate_set(jitstate, gv_ptr,
                                   valuebox.getgenvar(jitstate))
        else:
            assert self.content is not None
            self.content.op_setfield(jitstate, fielddesc, valuebox)

    def getfield_dont_generate_code(self, rgenop, fielddesc):
        if self.content is not None:
            return self.content.getfield_dont_generate_code(rgenop, fielddesc)
        elif self.genvar.is_const:
            # this raises if something's wrong, never returns None right
            try:
                gv_result = fielddesc.perform_getfield(rgenop, self.genvar)
            except rcontainer.SegfaultException:
                return None
            return fielddesc.redboxcls(gv_result)
        else:
            return None

    def remember_field(self, fielddesc, box):
        if self.genvar.is_const:
            return      # no point in remembering field then
        if self.content is None:
            from pypy.jit.timeshifter import rcontainer
            self.content = rcontainer.PartialDataStruct()
        self.content.remember_field(fielddesc, box)


class PtrRedBox(AbstractPtrRedBox, LLTypeMixin):

    def op_getsubstruct(self, jitstate, fielddesc):
        self.learn_nonzeroness(jitstate, True)
        gv_ptr = self.genvar
        if gv_ptr:
            return fielddesc.generate_getsubstruct(jitstate, gv_ptr)
        else:
            assert self.content is not None
            return self.content.op_getsubstruct(jitstate, fielddesc)

    @staticmethod
    def getfrozen(gv_value):
        if gv_value.is_const:
            return FrozenPtrConst(gv_value)
        else:
            return FrozenPtrVar(known_nonzero=False)


class InstanceRedBox(AbstractPtrRedBox, OOTypeMixin):

    @staticmethod
    def getfrozen(gv_value):
        if gv_value.is_const:
            return FrozenInstanceConst(gv_value)
        else:
            return FrozenInstanceVar()


# ____________________________________________________________

class FrozenValue(object):
    """An abstract value frozen in a saved state.
    """
    _attrs_ = ['will_be_promoted']
    will_be_promoted = False

    def is_constant_equal(self, box):
        return False

    def is_constant_nullptr(self):
        return False

    def check_future_promotions(self, box, memo):
        if (self.will_be_promoted and box.is_constant()
            and not self.is_constant_equal(box)):
            raise DontMerge


class FrozenConst(FrozenValue):

    def exactmatch(self, box, outgoingvarboxes, memo):
        if self.is_constant_equal(box):
            return True
        else:
            if self.will_be_promoted and box.is_constant():
                raise DontMerge
            outgoingvarboxes.append(box)
            return False


class FrozenVar(FrozenValue):

    def exactmatch(self, box, outgoingvarboxes, memo):
        if self.will_be_promoted and box.is_constant():
            raise DontMerge
        memo = memo.boxes
        if self not in memo:
            memo[self] = box
            outgoingvarboxes.append(box)
            return True
        elif memo[self] is box:
            return True
        else:
            outgoingvarboxes.append(box)
            return False


class FrozenIntConst(FrozenConst):

    def __init__(self, gv_const):
        self.gv_const = gv_const

    def is_constant_equal(self, box):
        return (box.is_constant() and
                self.gv_const.revealconst(lltype.Signed) ==
                box.genvar.revealconst(lltype.Signed))

    def unfreeze(self, incomingvarboxes, memo):
        # XXX could return directly the original IntRedBox
        return IntRedBox(self.gv_const)


class FrozenIntVar(FrozenVar):

    def unfreeze(self, incomingvarboxes, memo):
        memo = memo.boxes
        if self not in memo:
            newbox = IntRedBox(None)
            incomingvarboxes.append(newbox)
            memo[self] = newbox
            return newbox
        else:
            return memo[self]


class FrozenBoolConst(FrozenConst):

    def __init__(self, gv_const):
        self.gv_const = gv_const

    def is_constant_equal(self, box):
        return (box.is_constant() and
                self.gv_const.revealconst(lltype.Bool) ==
                box.genvar.revealconst(lltype.Bool))

    def unfreeze(self, incomingvarboxes, memo):
        return BoolRedBox(self.gv_const)


class FrozenBoolVar(FrozenVar):

    def unfreeze(self, incomingvarboxes, memo):
        memo = memo.boxes
        if self not in memo:
            newbox = BoolRedBox(None)
            incomingvarboxes.append(newbox)
            memo[self] = newbox
            return newbox
        else:
            return memo[self]

class FrozenDoubleConst(FrozenConst):

    def __init__(self, gv_const):
        self.gv_const = gv_const

    def is_constant_equal(self, box):
        return (box.is_constant() and
                self.gv_const.revealconst(lltype.Float) ==
                box.genvar.revealconst(lltype.Float))

    def unfreeze(self, incomingvarboxes, memo):
        return DoubleRedBox(self.gv_const)


class FrozenDoubleVar(FrozenVar):

    def unfreeze(self, incomingvarboxes, memo):
        memo = memo.boxes
        if self not in memo:
            newbox = DoubleRedBox(None)
            incomingvarboxes.append(newbox)
            memo[self] = newbox
            return newbox
        else:
            return memo[self]


class FrozenPtrMixin(object):
    _mixin_ = True
    ghost_children = None

    def get_ghost_child(self, fielddesc, gv_value):
        # ghost children of a constant immutable FrozenPtrConst
        # are only used to track future promotions; they have no
        # other effect on exactmatch().
        if self.ghost_children is None:
            self.ghost_children = {}
        else:
            try:
                return self.ghost_children[fielddesc]
            except KeyError:
                pass
        newfz = fielddesc.getfrozen(gv_value)
        self.ghost_children[fielddesc] = newfz
        return newfz

    def check_future_promotions(self, box, memo):
        FrozenValue.check_future_promotions(self, box, memo)
        if self.ghost_children is not None:
            for fielddesc, fz_child in self.ghost_children.items():
                box_child = box.getfield_dont_generate_code(memo.rgenop, 
                                                            fielddesc)
                if box_child is not None:
                    fz_child.check_future_promotions(box_child, memo)


class FrozenAbstractPtrConst(FrozenPtrMixin, FrozenConst):

    def __init__(self, gv_const):
        FrozenConst.__init__(self)
        self.gv_const = gv_const

    def is_constant_equal(self, box):
        return (box.is_constant() and
                self._revealconst(self.gv_const) ==
                self._revealconst(box.genvar))

    def is_constant_nullptr(self):
        return not self._revealconst(self.gv_const)

    def exactmatch(self, box, outgoingvarboxes, memo):
        assert isinstance(box, AbstractPtrRedBox)
        memo.partialdatamatch[box] = None     # could do better
        if self.is_constant_nullptr():
            memo.forget_nonzeroness[box] = None
        match = FrozenConst.exactmatch(self, box, outgoingvarboxes, memo)
        if not match:
            self.check_future_promotions(box, memo)
        #if not memo.force_merge and not match:
        #    from pypy.jit.timeshifter.rcontainer import VirtualContainer
        #    if isinstance(box.content, VirtualContainer):
        #        raise DontMerge   # XXX recursive data structures?
        return match

    def unfreeze(self, incomingvarboxes, memo):
        return self.PtrRedBox(self.gv_const)


class FrozenPtrConst(FrozenAbstractPtrConst, LLTypeMixin):
    PtrRedBox = PtrRedBox

class FrozenInstanceConst(FrozenAbstractPtrConst, OOTypeMixin):
    PtrRedBox = InstanceRedBox


class AbstractFrozenPtrVar(FrozenPtrMixin, FrozenVar):

    def __init__(self, known_nonzero):
        FrozenVar.__init__(self)
        self.known_nonzero = known_nonzero

    def exactmatch(self, box, outgoingvarboxes, memo):
        from pypy.jit.timeshifter.rcontainer import VirtualContainer
        assert isinstance(box, AbstractPtrRedBox)
        memo.partialdatamatch[box] = None
        if not self.known_nonzero:
            memo.forget_nonzeroness[box] = None
        match = FrozenVar.exactmatch(self, box, outgoingvarboxes, memo)
        if self.known_nonzero and not box.known_nonzero:
            match = False
        self.check_future_promotions(box, memo)
        return match

    def unfreeze(self, incomingvarboxes, memo):
        memo = memo.boxes
        if self not in memo:
            newbox = self.PtrRedBox(None, self.known_nonzero)
            incomingvarboxes.append(newbox)
            memo[self] = newbox
            return newbox
        else:
            return memo[self]

class FrozenPtrVar(AbstractFrozenPtrVar, LLTypeMixin):
    PtrRedBox = PtrRedBox

class FrozenInstanceVar(AbstractFrozenPtrVar, OOTypeMixin):
    PtrRedBox = InstanceRedBox


class FrozenPtrVarWithPartialData(FrozenPtrVar):

    def exactmatch(self, box, outgoingvarboxes, memo):
        if self.fz_partialcontent is None:
            return FrozenPtrVar.exactmatch(self, box, outgoingvarboxes, memo)
        assert isinstance(box, PtrRedBox)
        partialdatamatch = self.fz_partialcontent.match(box,
                                                        memo.partialdatamatch)
        # skip the parent's exactmatch()!
        exact = FrozenVar.exactmatch(self, box, outgoingvarboxes, memo)
        match = exact and partialdatamatch
        if not memo.force_merge and not match:
            from pypy.jit.timeshifter.rcontainer import VirtualContainer
            if isinstance(box.content, VirtualContainer):
                raise DontMerge   # XXX recursive data structures?
        return match


class FrozenPtrVirtual(FrozenValue):

    def exactmatch(self, box, outgoingvarboxes, memo):
        assert isinstance(box, PtrRedBox)
        if box.genvar:
            raise DontMerge
        else:
            assert box.content is not None
            match = self.fz_content.exactmatch(box.content, outgoingvarboxes,
                                              memo)
        return match
    
    def unfreeze(self, incomingvarboxes, memo):
        return self.fz_content.unfreeze(incomingvarboxes, memo)


##class FrozenPtrVarWithData(FrozenValue):

##    def exactmatch(self, box, outgoingvarboxes, memo):
##        memo = memo.boxes
##        if self not in memo:
##            memo[self] = box
##            outgoingvarboxes.append(box)
##            return True
##        elif memo[self] is box:
##            return True
##        else:
##            outgoingvarboxes.append(box)
##            return False

PtrRedBox.FrozenPtrVirtual = FrozenPtrVirtual
PtrRedBox.FrozenPtrConst = FrozenPtrConst
PtrRedBox.FrozenPtrVar = FrozenPtrVar
PtrRedBox.FrozenPtrVarWithPartialData = FrozenPtrVarWithPartialData

InstanceRedBox.FrozenPtrVirtual = None
InstanceRedBox.FrozenPtrConst = FrozenInstanceConst
InstanceRedBox.FrozenPtrVar = FrozenInstanceVar
InstanceRedBox.FrozenPtrVarWithPartialData = None
