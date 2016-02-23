from rpython.translator.backendopt import graphanalyze        

# This is not an optimization. It checks for possible releases of the
# GIL in all graphs starting from rgc.no_release_gil.


TRANSACTION_BREAK = set([
    'stm_enter_transactional_zone',
    'stm_leave_transactional_zone',
    'stm_hint_commit_soon',
    'jit_assembler_call',
    'stm_enter_callback_call',
    'stm_leave_callback_call',
    'stm_transaction_break',
    'stm_queue_get',
    'stm_queue_join',
    ])

class GilAnalyzer(graphanalyze.BoolGraphAnalyzer):
    
    def analyze_direct_call(self, graph, seen=None):
        try:
            func = graph.func
        except AttributeError:
            pass
        else:
            if getattr(func, '_gctransformer_hint_close_stack_', False):
                return True
            if getattr(func, '_transaction_break_', False):
                return True
      
        return graphanalyze.BoolGraphAnalyzer.analyze_direct_call(
            self, graph, seen)

    def analyze_external_call(self, op, seen=None):
        # if 'funcobj' releases the GIL, then the GIL-releasing
        # functions themselves will call enter/leave transactional
        # zone. This case is covered above.
        return False

    def analyze_simple_operation(self, op, graphinfo):
        # XXX: includes jit_assembler_call here, but it should probably
        # be handled like indirect_call in the GraphAnalyzer itself
        if op.opname in TRANSACTION_BREAK:
            return True
        return False

def analyze(graphs, translator):
    gilanalyzer = GilAnalyzer(translator)
    for graph in graphs:
        func = getattr(graph, 'func', None)
        if func and getattr(func, '_no_release_gil_', False):
            if gilanalyzer.analyze_direct_call(graph):
                # 'no_release_gil' function can release the gil
                import cStringIO
                err = cStringIO.StringIO()
                import sys
                prev = sys.stdout
                try:
                    sys.stdout = err
                    ca = GilAnalyzer(translator)
                    ca.verbose = True
                    ca.analyze_direct_call(graph)  # print the "traceback" here
                    sys.stdout = prev
                except:
                    sys.stdout = prev
                # ^^^ for the dump of which operation in which graph actually
                # causes it to return True
                raise Exception("'no_release_gil' function can release the GIL:"
                                " %s\n%s" % (func, err.getvalue()))

        
