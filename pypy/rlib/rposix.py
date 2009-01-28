import os, sys
from pypy.rpython.lltypesystem.rffi import CConstant, CExternVariable, INT
from pypy.rpython.lltypesystem import lltype, ll2ctypes, rffi
from pypy.translator.tool.cbuild import ExternalCompilationInfo
from pypy.rlib.rarithmetic import intmask

class CConstantErrno(CConstant):
    # these accessors are used when calling get_errno() or set_errno()
    # on top of CPython
    def __getitem__(self, index):
        assert index == 0
        try:
            return ll2ctypes.TLS.errno
        except AttributeError:
            raise ValueError("no C function call occurred so far, "
                             "errno is undefined")
    def __setitem__(self, index, value):
        assert index == 0
        ll2ctypes.TLS.errno = value

errno_eci = ExternalCompilationInfo(
    includes=['errno.h']
)

_get_errno, _set_errno = CExternVariable(INT, 'errno', errno_eci,
                                         CConstantErrno, sandboxsafe=True,
                                         _nowrapper=True)
# the default wrapper for set_errno is not suitable for use in critical places
# like around GIL handling logic, so we provide our own wrappers.

def get_errno():
    return intmask(_get_errno())

def set_errno(errno):
    _set_errno(rffi.cast(INT, errno))


def closerange(fd_low, fd_high):
    # this behaves like os.closerange() from Python 2.6.
    for fd in xrange(fd_low, fd_high):
        try:
            os.close(fd)
        except OSError:
            pass

# An implementation of ftruncate for Windows
if sys.platform == 'win32':
    from pypy.rlib import rwin32

    eci = ExternalCompilationInfo()
    _get_osfhandle = rffi.llexternal('_get_osfhandle', [rffi.INT], rffi.LONG,
                                     compilation_info=eci)
    SetEndOfFile = rffi.llexternal('SetEndOfFile', [rffi.LONG], rwin32.BOOL,
                                   compilation_info=eci)

    def ftruncate(fd, size):
        # move to the position to be truncated
        os.lseek(fd, size, 0)
        # Truncate.  Note that this may grow the file!
        handle = _get_osfhandle(fd)
        if handle == -1:
            raise IOError(get_errno(), "Invalid file handle")
        if not SetEndOfFile(handle):
            raise IOError("Could not truncate file")
        return size
