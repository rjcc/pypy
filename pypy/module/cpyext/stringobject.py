from pypy.rpython.lltypesystem import rffi, lltype
from pypy.module.cpyext.api import (cpython_api, PyVarObjectFields,
                                    PyStringObject, Py_ssize_t, cpython_struct,
                                    CANNOT_FAIL, build_type_checkers,
                                    PyObjectP)
from pypy.module.cpyext.pyobject import PyObject, make_ref, from_ref


PyString_Check, PyString_CheckExact = build_type_checkers("String", "w_str")

@cpython_api([rffi.CCHARP, Py_ssize_t], PyStringObject, error=lltype.nullptr(PyStringObject.TO))
def PyString_FromStringAndSize(space, char_p, length):
    if char_p:
        s = rffi.charpsize2str(char_p, length)
        ptr = make_ref(space, space.wrap(s))
        return rffi.cast(PyStringObject, ptr)
    else:
        py_str = lltype.malloc(PyStringObject.TO, flavor='raw')
        py_str.c_ob_refcnt = 1
        
        buflen = length + 1
        py_str.c_buffer = lltype.malloc(rffi.CCHARP.TO, buflen, flavor='raw')
        py_str.c_buffer[buflen-1] = '\0'
        py_str.c_size = length
        py_str.c_ob_type = make_ref(space, space.w_str)
        
        return py_str

@cpython_api([rffi.CCHARP], PyObject)
def PyString_FromString(space, char_p):
    s = rffi.charp2str(char_p)
    return space.wrap(s)

@cpython_api([PyObject], rffi.CCHARP, error=0)
def PyString_AsString(space, ref):
    ref_str = rffi.cast(PyStringObject, ref)
    if not ref_str.c_buffer:
        # copy string buffer
        w_str = from_ref(space, ref)
        s = space.str_w(w_str)
        ref_str.c_buffer = rffi.str2charp(s)
    return ref_str.c_buffer

@cpython_api([PyObject], Py_ssize_t, error=-1)
def PyString_Size(space, ref):
    if from_ref(space, ref.c_ob_type) is space.w_str:
        ref = rffi.cast(PyStringObject, ref)
        return ref.c_size
    else:
        w_obj = from_ref(space, ref)
        return space.int_w(space.len(w_obj))

@cpython_api([PyObjectP, Py_ssize_t], rffi.INT_real, error=-1)
def _PyString_Resize(space, w_string, newsize):
    """A way to resize a string object even though it is "immutable". Only use this to
    build up a brand new string object; don't use this if the string may already be
    known in other parts of the code.  It is an error to call this function if the
    refcount on the input string object is not one. Pass the address of an existing
    string object as an lvalue (it may be written into), and the new size desired.
    On success, *string holds the resized string object and 0 is returned;
    the address in *string may differ from its input value.  If the reallocation
    fails, the original string object at *string is deallocated, *string is
    set to NULL, a memory exception is set, and -1 is returned.
    
    This function used an int type for newsize. This might
    require changes in your code for properly supporting 64-bit systems."""
    import pdb
    pdb.set_trace()
