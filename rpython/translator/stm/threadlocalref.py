from rpython.rtyper.lltypesystem import lltype, llmemory
from rpython.translator.unsimplify import varoftype
from rpython.flowspace.model import SpaceOperation, Constant

#
# Note: all this slightly messy code is to have 'stm_threadlocalref_flush'
# which zeroes *all* thread-locals variables accessed with
# stm_threadlocalref_{get,set}.
#

def transform_tlref(graphs):
    ids = set()
    #
    for graph in graphs:
        for block in graph.iterblocks():
            for i in range(len(block.operations)):
                op = block.operations[i]
                if (op.opname == 'stm_threadlocalref_set' or
                    op.opname == 'stm_threadlocalref_get'):
                    ids.add(op.args[0].value)
    #
    ids = sorted(ids)
    ARRAY = lltype.FixedSizeArray(llmemory.Address, len(ids))
    S = lltype.Struct('THREADLOCALREF', ('ptr', ARRAY),
                      hints={'stm_thread_local': True})
    ll_threadlocalref = lltype.malloc(S, immortal=True)
    c_threadlocalref = Constant(ll_threadlocalref, lltype.Ptr(S))
    c_fieldname = Constant('ptr', lltype.Void)
    c_null = Constant(llmemory.NULL, llmemory.Address)
    #
    for graph in graphs:
        for block in graph.iterblocks():
            for i in range(len(block.operations)-1, -1, -1):
                op = block.operations[i]
                if op.opname == 'stm_threadlocalref_set':
                    v_array = varoftype(lltype.Ptr(ARRAY))
                    ops = [
                        SpaceOperation('getfield', [c_threadlocalref,
                                                    c_fieldname],
                                       v_array),
                        SpaceOperation('setarrayitem', [v_array,
                                                        op.args[0],
                                                        op.args[1]],
                                       op.result)]
                    block.operations[i:i+1] = ops
                elif op.opname == 'stm_threadlocalref_get':
                    v_array = varoftype(lltype.Ptr(ARRAY))
                    ops = [
                        SpaceOperation('getfield', [c_threadlocalref,
                                                    c_fieldname],
                                       v_array),
                        SpaceOperation('getarrayitem', [v_array,
                                                        op.args[0]],
                                       op.result)]
                    block.operations[i:i+1] = ops
                elif op.opname == 'stm_threadlocalref_addr':
                    v_array = varoftype(lltype.Ptr(ARRAY))
                    ops = [
                        SpaceOperation('getfield', [c_threadlocalref,
                                                    c_fieldname],
                                       v_array),
                        SpaceOperation('direct_ptradd', [v_array,
                                                         op.args[0]],
                                       op.result)]
                    block.operations[i:i+1] = ops
                elif op.opname == 'stm_threadlocalref_count':
                    c_count = Constant(len(ids), lltype.Signed)
                    op = SpaceOperation('same_as', [c_count], op.result)
                    block.operations[i] = op
