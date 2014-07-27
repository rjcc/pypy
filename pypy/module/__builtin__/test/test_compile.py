class AppTestCompile:

    def test_compile(self):
        """Clone of the part of the original test that was failing."""
        import ast

        codestr = '''def f():
        """doc"""
        try:
            assert False
        except AssertionError:
            return (True, f.__doc__)
        else:
            return (False, f.__doc__)
        '''

        def f(): """doc"""
        values = [(-1, __debug__, f.__doc__),
                  (0, True, 'doc'),
                  (1, False, 'doc'),
                  (2, False, None)]

        for optval, debugval, docstring in values:
            # test both direct compilation and compilation via AST
            codeobjs = []
            codeobjs.append(
                    compile(codestr, "<test>", "exec", optimize=optval))
            tree = ast.parse(codestr)
            codeobjs.append(compile(tree, "<test>", "exec", optimize=optval))

            for i, code in enumerate(codeobjs):
                print(optval, debugval, docstring, i)
                ns = {}
                exec(code, ns)
                rv = ns['f']()
                assert rv == (debugval, docstring)

    def test_assert_remove(self):
        """Test removal of the asserts with optimize=1."""
        import ast

        code = """def f():
        assert False
        """
        tree = ast.parse(code)
        for to_compile in [code, tree]:
            compiled = compile(to_compile, "<test>", "exec", optimize=1)
            ns = {}
            exec(compiled, ns)
            ns['f']()

    def test_docstring_remove(self):
        """Test removal of docstrings with optimize=2."""
        import ast
        import marshal

        code = """
'module_doc'

def f():
    'func_doc'

class C:
    'class_doc'
"""
        tree = ast.parse(code)
        for to_compile in [code, tree]:
            compiled = compile(to_compile, "<test>", "exec", optimize=2)

            # check that the docstrings are really gone
            marshalled = str(marshal.dumps(compiled))
            assert 'module_doc' not in marshalled
            assert 'func_doc' not in marshalled
            assert 'class_doc' not in marshalled

            # try to execute the bytecode and see what we get
            ns = {}
            exec(compiled, ns)
            assert '__doc__' not in ns
            assert ns['f'].__doc__ is None
            assert ns['C'].__doc__ is None


# TODO: Check the value of __debug__ inside of the compiled block!
#       According to the documentation, it should follow the optimize flag.
#       However, cpython3.3 behaves the same way as PyPy (__debug__ follows
#       -O, -OO flags of the interpreter).
# TODO: It would also be good to test that with the assert is not removed and
#       is executed when -O flag is set but optimize=0.
