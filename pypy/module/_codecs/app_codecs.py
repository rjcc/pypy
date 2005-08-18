# Note:
# This *is* now explicitly RPython.
# Please make sure not to break this.

"""

   _codecs -- Provides access to the codec registry and the builtin
              codecs.

   This module should never be imported directly. The standard library
   module "codecs" wraps this builtin module for use within Python.

   The codec registry is accessible via:

     register(search_function) -> None

     lookup(encoding) -> (encoder, decoder, stream_reader, stream_writer)

   The builtin Unicode codecs use the following interface:

     <encoding>_encode(Unicode_object[,errors='strict']) -> 
         (string object, bytes consumed)

     <encoding>_decode(char_buffer_obj[,errors='strict']) -> 
        (Unicode object, bytes consumed)

   <encoding>_encode() interfaces also accept non-Unicode object as
   input. The objects are then converted to Unicode using
   PyUnicode_FromObject() prior to applying the conversion.

   These <encoding>s are available: utf_8, unicode_escape,
   raw_unicode_escape, unicode_internal, latin_1, ascii (7-bit),
   mbcs (on win32).


Written by Marc-Andre Lemburg (mal@lemburg.com).

Copyright (c) Corporation for National Research Initiatives.

"""
#from unicodecodec import *

import sys
#/* --- Registry ----------------------------------------------------------- */
codec_search_path = []
codec_search_cache = {}
codec_error_registry = {}
codec_need_encodings = [True]

def codec_register( search_function ):
    """register(search_function)
    
    Register a codec search function. Search functions are expected to take
    one argument, the encoding name in all lower case letters, and return
    a tuple of functions (encoder, decoder, stream_reader, stream_writer).
    """

    if callable(search_function):
        codec_search_path.append(search_function)

register = codec_register

def codec_lookup(encoding):
    """lookup(encoding) -> (encoder, decoder, stream_reader, stream_writer)
    Looks up a codec tuple in the Python codec registry and returns
    a tuple of functions.
    """
    
    result = codec_search_cache.get(encoding,None)
    if not result:
        if codec_need_encodings:
            import encodings
            if len(codec_search_path) == 0:
                raise LookupError("no codec search functions registered: can't find encoding")
            del codec_need_encodings[:]
        if not isinstance(encoding,str):
            raise TypeError("Encoding must be a string")
        for search in codec_search_path:
            result=search(encoding)
            if result :
                if not( type(result) == tuple and len(result) == 4):
                    raise TypeError("codec search functions must return 4-tuples")
                else:
                    codec_search_cache[encoding] = result 
                    return result
        if not result:
            raise LookupError( "unknown encoding: %s" % encoding)
    return result
    

lookup = codec_lookup

def encode(v, encoding='defaultencoding',errors='strict'):
    """encode(obj, [encoding[,errors]]) -> object
    
    Encodes obj using the codec registered for encoding. encoding defaults
    to the default encoding. errors may be given to set a different error
    handling scheme. Default is 'strict' meaning that encoding errors raise
    a ValueError. Other possible values are 'ignore', 'replace' and
    'xmlcharrefreplace' as well as any other name registered with
    codecs.register_error that can handle ValueErrors.
    """
    if isinstance(encoding,str):
        encoder = lookup(encoding)[0]
        if encoder and isinstance(errors,str):
            res = encoder(v,errors)
            return res[0]
        else:
            raise TypeError("Errors must be a string")
    else:
        raise TypeError("Encoding must be a string")

def decode(obj,encoding='defaultencoding',errors='strict'):
    """decode(obj, [encoding[,errors]]) -> object

    Decodes obj using the codec registered for encoding. encoding defaults
    to the default encoding. errors may be given to set a different error
    handling scheme. Default is 'strict' meaning that encoding errors raise
    a ValueError. Other possible values are 'ignore' and 'replace'
    as well as any other name registerd with codecs.register_error that is
    able to handle ValueErrors.
    """
    if isinstance(encoding,str):
        decoder = lookup(encoding)[1]
        if decoder and isinstance(errors,str):
            res = decoder(obj,errors)
            if not isinstance(res,tuple) or len(res) != 2:
                raise TypeError("encoder must return a tuple (object,integer)")
            return res[0]
        else:
            raise TypeError("Errors must be a string")
    else:
        raise TypeError("Encoding must be a string")

def latin_1_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeLatin1(obj,len(obj),errors)
    res = ''.join(res)
    return res, len(res)
# XXX MBCS codec might involve ctypes ?
def mbcs_decode():
    """None
    """
    pass

def readbuffer_encode( obj,errors='strict'):
    """None
    """
    res = str(obj)
    return res,len(res)

def escape_encode( obj,errors='strict'):
    """None
    """
    s = repr(obj)
    v = s[1:-1]
    return v,len(v)

def utf_8_decode( data,errors='strict',final=None):
    """None
    """
    res = PyUnicode_DecodeUTF8Stateful(data, len(data), errors, final)
    res = u''.join(res)
    return res,len(res)

def raw_unicode_escape_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeRawUnicodeEscape(data, len(data), errors)
    res = u''.join(res)
    return res,len(res)

def utf_7_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeUTF7(data,len(data),errors)
    res = u''.join(res)
    return res,len(res)

def unicode_escape_encode( obj,errors='strict'):
    """None
    """
    res = unicodeescape_string(obj,len(obj),0)
    res = ''.join(res)
    return res, len(res)

def latin_1_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeLatin1(data,len(data),errors)
    res = u''.join(res)
    return res, len(res)

def utf_16_decode( data,errors='strict',final=None):
    """None
    """
    res = PyUnicode_DecodeUTF16Stateful(data,len(data),errors)
    res = ''.join(res)
    return res, len(res)

def unicode_escape_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeUnicodeEscape(data,len(data),errors)
    res = u''.join(res)
    return res, len(res)


def ascii_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeASCII(data,len(data),errors)
    res = u''.join(res)
    return res, len(res)

def charmap_encode(obj,errors='strict',mapping='latin-1'):
    """None
    """

    res = PyUnicode_EncodeCharmap(obj,len(obj),mapping,errors)
    res = ''.join(res)
    return res, len(res)

if sys.maxunicode == 65535:
    unicode_bytes = 2
else:
    unicode_bytes = 4

def unicode_internal_encode( obj,errors='strict'):
    """None
    """
    if type(obj) == unicode:
        p = []
        t = [ord(x) for x in obj]
        for i in t:
            bytes = []
            for j in xrange(unicode_bytes):
                bytes += chr(i%256)
                i >>= 8
            if sys.byteorder == "big":
                bytes.reverse()
            p += bytes
        res = ''.join(p)
        return res, len(res)
    else:
        res = "You can do better than this" # XXX make this right
        return res,len(res)

def unicode_internal_decode( unistr,errors='strict'):
    """None
    """
    if type(unistr) == unicode:
        return unistr,len(unistr)
    else:
        p=[]
        i=0
        if sys.byteorder == "big":
            start = unicode_bytes - 1
            stop = -1
            step = -1
        else:
            start = 0
            stop = unicode_bytes
            step = 1
        while i < len(unistr)-unicode_bytes+1:
            t = 0
            h = 0
            for j in range(start, stop, step):
                t += ord(unistr[i+j])<<(h*8)
                h += 1
            i += unicode_bytes
            p += unichr(t)
        res = u''.join(p)
        return res, len(res)

def utf_16_ex_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeUTF16Stateful(data,len(data),errors,'native')
    res = ''.join(res)
    return res, len(res)
# XXX escape_decode Check if this is right
def escape_decode(data,errors='strict'):
    """None
    """
    l = len(data)
    i = 0
    res = []
    while i<l:
        
        if data[i] == '\\':
            i += 1
            if data[i] == '\\':
                res += '\\'
            if data[i] == 'n':
                res += '\n'
            if data[i] == 't':
                res += '\t'
            if data[i] == 'r':
                res += '\r'
            if data[i] == 'b':
                res += '\b'
            if data[i] == '\'':
                res += '\''
            if data[i] == '\"':
                res += '\"'
            if data[i] == 'f':
                res += '\f'
            if data[i] == 'a':
                res += '\a'
            if data[i] == 'v':
                res += '\v'
            if data[i] == '0':
                octal = data[i+1:i+3]
                res += chr(int(octal,8))
                i += 2
            if data[i] == 'x':
                hexa = data[i+1:i+3]
                res += chr(int(hexa,16))
                i += 2
            if data[i] == 'u':
                res += data[i-1:i+5]
                i += 4
            if data[i] == 'U':
                res += data[i-1:i+9]
                i += 8
            if data[i] == 'N':
                raise NotImplementedError
        else:
            res += data[i]
        i += 1
    res = ''.join(res)    
    return res,len(res)

def charbuffer_encode( obj,errors='strict'):
    """None
    """
    res = str(obj)
    res = ''.join(res)
    return res, len(res)

def charmap_decode( data,errors='strict',mapping=None):
    """None
    """
    res = PyUnicode_DecodeCharmap(data, len(data), mapping, errors)
    res = ''.join(res)
    return res, len(res)


def utf_7_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeUTF7(obj,len(obj),0,0,errors)
    res = ''.join(res)
    return res, len(res)

def mbcs_encode( obj,errors='strict'):
    """None
    """
    pass
##    return (PyUnicode_EncodeMBCS(
##			       (obj), 
##			       len(obj),
##			       errors),
##		    len(obj))
    

def ascii_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeASCII(obj,len(obj),errors)
    res = ''.join(res)
    return res, len(res)

def utf_16_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeUTF16(obj,len(obj),errors)
    res = ''.join(res)
    return res, len(res)

def raw_unicode_escape_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeRawUnicodeEscape(obj,len(obj))
    res = ''.join(res)
    return res, len(res)

def utf_8_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeUTF8(obj,len(obj),errors)
    res = ''.join(res)
    return res, len(res)

def utf_16_le_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeUTF16(obj,len(obj),errors,'little')
    res = ''.join(res)
    return res, len(res)

def utf_16_be_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeUTF16(obj,len(obj),errors,'big')
    res = ''.join(res)
    return res, len(res)

def utf_16_le_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeUTF16Stateful(data,len(data),errors,'little')
    res = ''.join(res)
    return res, len(res)

def utf_16_be_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeUTF16Stateful(data,len(data),errors,'big')
    res = ''.join(res)
    return res, len(res)

def strict_errors(exc):
    if isinstance(exc,Exception):
        raise exc
    else:
        raise TypeError("codec must pass exception instance")
    
def ignore_errors(exc):
    if isinstance(exc,(UnicodeEncodeError,UnicodeDecodeError,UnicodeTranslateError)):
        return u'',exc.end
    else:
        raise TypeError("don't know how to handle %.400s in error callback"%exc)

Py_UNICODE_REPLACEMENT_CHARACTER = u"\ufffd"

def replace_errors(exc):
    if isinstance(exc,UnicodeEncodeError):
        return u'?'*(exc.end-exc.start),exc.end
    elif isinstance(exc,(UnicodeTranslateError,UnicodeDecodeError)):
        return Py_UNICODE_REPLACEMENT_CHARACTER*(exc.end-exc.start),exc.end
    else:
        raise TypeError("don't know how to handle %.400s in error callback"%exc)

def xmlcharrefreplace_errors(exc):
    if isinstance(exc,UnicodeEncodeError):
        res = []
        for ch in exc.object[exc.start:exc.end]:
            res += '&#'
            res += str(ord(ch))
            res += ';'
        return u''.join(res),exc.end
    else:
        raise TypeError("don't know how to handle %.400s in error callback"%type(exc))
    
def backslashreplace_errors(exc):
    if isinstance(exc,UnicodeEncodeError):
        p=[]
        for c in exc.object[exc.start:exc.end]:
            p.append('\\')
            oc = ord(c)
            if (oc >= 0x00010000):
                p.append('U')
                p.append("%.8x" % ord(c))
            elif (oc >= 0x100):
                p.append('u')
                p.append("%.4x" % ord(c))
            else:
                p.append('x')
                p.append("%.2x" % ord(c))
        return u''.join(p),exc.end
    else:
        raise TypeError("don't know how to handle %.400s in error callback"%type(exc))


#  ----------------------------------------------------------------------

##import sys
##""" Python implementation of CPythons builtin unicode codecs.
##
##    Generally the functions in this module take a list of characters an returns 
##    a list of characters.
##    
##    For use in the PyPy project"""


## indicate whether a UTF-7 character is special i.e. cannot be directly
##       encoded:
##	   0 - not special
##	   1 - special
##	   2 - whitespace (optional)
##	   3 - RFC2152 Set O (optional)
    
utf7_special = [
    1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 2, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 3, 3, 3, 3, 3, 3, 0, 0, 0, 3, 1, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 0,
    3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 1, 3, 3, 3,
    3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 1, 1,
]
unicode_latin1=[None]*256


def lookup_error(errors):
    """lookup_error(errors) -> handler

    Return the error handler for the specified error handling name
    or raise a LookupError, if no handler exists under this name.
    """
    
    try:
        err_handler = codec_error_registry[errors]
    except KeyError:
        raise LookupError("unknown error handler name %s"%errors)
    return err_handler

def register_error(errors, handler):
    """register_error(errors, handler)

    Register the specified error handler under the name
    errors. handler must be a callable object, that
    will be called with an exception instance containing
    information about the location of the encoding/decoding
    error and must return a (replacement, new position) tuple.
    """
    if callable(handler):
        codec_error_registry[errors] = handler
    else:
        raise TypeError("handler must be callable")

register_error("strict",strict_errors)
register_error("ignore",ignore_errors)
register_error("replace",replace_errors)
register_error("xmlcharrefreplace",xmlcharrefreplace_errors)
register_error("backslashreplace",backslashreplace_errors)
    
def SPECIAL(c, encodeO, encodeWS):
    c = ord(c)
    return (c>127 or utf7_special[c] == 1) or \
            (encodeWS and (utf7_special[(c)] == 2)) or \
            (encodeO and (utf7_special[(c)] == 3))
def B64(n):
    return ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"[(n) & 0x3f])
def B64CHAR(c):
    return (c.isalnum() or (c) == '+' or (c) == '/')
def UB64(c):
    if (c) == '+' :
        return 62 
    elif (c) == '/':
        return 63 
    elif (c) >= 'a':
        return ord(c) - 71 
    elif (c) >= 'A':
        return ord(c) - 65 
    else: 
        return ord(c) + 4

def ENCODE( ch, bits) :
    charvalue = 0
    out = []
##    for c in ch:
##        charvalue <<= 16
##        charvalue += ord(c)
    while (bits >= 6):
        out +=  B64(ch >> (bits-6))
        bits -= 6 
    return out,bits


def PyUnicode_DecodeUTF7(s, size, errors):

    starts = s
    errmsg = ""
    inShift = 0
    bitsleft = 0
    charsleft = 0
    surrogate = 0
    p = []
    errorHandler = None
    exc = None

    if (size == 0):
        return unicode('')
    i = 0
    while i < size:
        
        ch = s[i]
        if (inShift):
            if ((ch == '-') or not B64CHAR(ch)):
                inShift = 0
                i += 1
                
                while (bitsleft >= 16):
                    outCh =  ((charsleft) >> (bitsleft-16)) & 0xffff
                    bitsleft -= 16
                    
                    if (surrogate):
                        ##            We have already generated an error for the high surrogate
                        ##            so let's not bother seeing if the low surrogate is correct or not 
                        surrogate = 0
                    elif (0xDC00 <= (outCh) and (outCh) <= 0xDFFF):
            ##             This is a surrogate pair. Unfortunately we can't represent 
            ##               it in a 16-bit character 
                        surrogate = 1
                        msg = "code pairs are not supported"
                        out,x = unicode_call_errorhandler(errors,'utf-7',msg,s,i-1,i)
                        p += out
                        bitsleft = 0
                        break
                    else:
                        p +=  unichr(outCh )
                        #p += out
                if (bitsleft >= 6):
##                    /* The shift sequence has a partial character in it. If
##                       bitsleft < 6 then we could just classify it as padding
##                       but that is not the case here */
                    msg = "partial character in shift sequence"
                    out,x = unicode_call_errorhandler(errors,'utf-7',msg,s,i-1,i)
                    
##                /* According to RFC2152 the remaining bits should be zero. We
##                   choose to signal an error/insert a replacement character
##                   here so indicate the potential of a misencoded character. */

##                /* On x86, a << b == a << (b%32) so make sure that bitsleft != 0 */
##                if (bitsleft and (charsleft << (sizeof(charsleft) * 8 - bitsleft))):
##                    raise UnicodeDecodeError, "non-zero padding bits in shift sequence"
                if (ch == '-') :
                    if ((i < size) and (s[i] == '-')) :
                        p +=  '-'
                        inShift = 1
                    
                elif SPECIAL(ch,0,0) :
                    raise  UnicodeDecodeError,"unexpected special character"
	                
                else:  
                    p +=  ch 
            else:
                charsleft = (charsleft << 6) | UB64(ch)
                bitsleft += 6
                i+=1
##                /* p, charsleft, bitsleft, surrogate = */ DECODE(p, charsleft, bitsleft, surrogate);
        elif ( ch == '+' ):
            startinpos = i
            i+=1
            if (i<size and s[i] == '-'):
                i+=1
                p +=  '+'
            else:
                inShift = 1
                bitsleft = 0
                
        elif (SPECIAL(ch,0,0)):
            i+=1
            raise UnicodeDecodeError,"unexpected special character"
        else:
            p +=  ch 
            i+=1

    if (inShift) :
        #XXX This aint right
        endinpos = size
        raise UnicodeDecodeError, "unterminated shift sequence"
        
    return p

def PyUnicode_EncodeUTF7(s, size, encodeSetO, encodeWhiteSpace, errors):

#    /* It might be possible to tighten this worst case */
    inShift = False
    i = 0
    bitsleft = 0
    charsleft = 0
    out = []
    for ch in s:
        if (not inShift) :
            if (ch == '+'):
                out +=  '+'
                out +=  '-'
            elif (SPECIAL(ch, encodeSetO, encodeWhiteSpace)):
                charsleft = ord(ch)
                bitsleft = 16
                out += '+'
                p, bitsleft = ENCODE( charsleft, bitsleft)
                out += p
                inShift = bitsleft > 0
            else:
                out += chr(ord(ch))
        else:
            if (not SPECIAL(ch, encodeSetO, encodeWhiteSpace)):
                out += B64((charsleft) << (6-bitsleft))
                charsleft = 0
                bitsleft = 0
##                /* Characters not in the BASE64 set implicitly unshift the sequence
##                   so no '-' is required, except if the character is itself a '-' */
                if (B64CHAR(ch) or ch == '-'):
                    out += '-'
                inShift = False
                out += chr(ord(ch))
            else:
                bitsleft += 16
                charsleft = (((charsleft) << 16) | ord(ch))
                p, bitsleft =  ENCODE(charsleft, bitsleft)
                out += p
##                /* If the next character is special then we dont' need to terminate
##                   the shift sequence. If the next character is not a BASE64 character
##                   or '-' then the shift sequence will be terminated implicitly and we
##                   don't have to insert a '-'. */

                if (bitsleft == 0):
                    if (i + 1 < size):
                        ch2 = s[i+1]

                        if (SPECIAL(ch2, encodeSetO, encodeWhiteSpace)):
                            pass
                        elif (B64CHAR(ch2) or ch2 == '-'):
                            out +=  '-'
                            inShift = False
                        else:
                            inShift = False
                    else:
                        out +=  '-'
                        inShift = False
        i+=1
            
    if (bitsleft):
        out += B64(charsleft << (6-bitsleft) ) 
        out +=  '-'

    return out

unicode_empty=u''

##def PyUnicode_Decode(s,size,encoding,errors):
##
##    if (encoding == None):
##        encoding = PyUnicode_GetDefaultEncoding()
##
####    /* Shortcuts for common default encodings */
##    decoder = encodings.get(encoding,None)
##    if decoder:
##        return decoder(s,encoding,errors)
####    /* Decode via the codec registry */
##    buf = buffer(s)
##    result = PyCodec_Decode(buf, encoding, errors)
##    if (not isinstance(result,unicode)):
##        raise UnicodeDecodeError, "decoder did not return an unicode object (type=%.400s)"%type(result)
##    return result

def unicodeescape_string(s, size, quotes):

    p = []
    if (quotes) :
        p += 'u'
        if (s.find('\'')!=-1 and s.find('"')==-1):
            p += '"' 
        else:
            p += '\''
    pos = 0
    while (pos < size):
        ch = s[pos]
        #/* Escape quotes */
        if (quotes and (ch == p[1] or ch == '\\')):
            p += '\\'
            p += ch
            pos += 1
            continue

#ifdef Py_UNICODE_WIDE
        #/* Map 21-bit characters to '\U00xxxxxx' */
        elif (ord(ch) >= 0x10000):
            p += '\\'
            p += 'U'
            p += '%08x'%ord(ch)
            pos += 1
            continue        
#endif
	#/* Map UTF-16 surrogate pairs to Unicode \UXXXXXXXX escapes */
        elif (ord(ch) >= 0xD800 and ord(ch) < 0xDC00):
            pos += 1
            ch2 = s[pos]
	    
            if (ord(ch2) >= 0xDC00 and ord(ch2) <= 0xDFFF):
                ucs = (((ord(ch) & 0x03FF) << 10) | (ord(ch2) & 0x03FF)) + 0x00010000
                p += '\\'
                p += 'U'
                p += '%08x'%ucs
                pos += 1
                continue
	   
	    #/* Fall through: isolated surrogates are copied as-is */
	    pos -= 1
	    
        #/* Map 16-bit characters to '\uxxxx' */
        if (ord(ch) >= 256):
            p += '\\'
            p += 'u'
            p += '%04x'%ord(ch)
            
        #/* Map special whitespace to '\t', \n', '\r' */
        elif (ch == '\t'):
            p += '\\'
            p += 't'
        
        elif (ch == '\n'):
            p += '\\'
            p += 'n'

        elif (ch == '\r'):
            p += '\\'
            p += 'r'

        #/* Map non-printable US ASCII to '\xhh' */
        elif (ch < ' ' or ch >= 0x7F) :
            p += '\\'
            p += 'x'
            p += '%02x'%ord(ch)
        #/* Copy everything else as-is */
        else:
            p += chr(ord(ch))
        pos += 1
    if (quotes):
        p += p[1]
    return p

def PyUnicode_DecodeASCII(s, size, errors):

#    /* ASCII is equivalent to the first 128 ordinals in Unicode. */
    if (size == 1 and ord(s) < 128) :
        return [unichr(ord(s))]
    if (size == 0):
        return [u''] #unicode('')
    p = []
    pos = 0
    while pos < len(s):
        c = s[pos]
        if ord(c) < 128:
            p += unichr(ord(c))
            pos += 1
        else:
            
            res = unicode_call_errorhandler(
                    errors, "ascii", "ordinal not in range(128)",
                    s,  pos, pos+1)
            p += [unichr(ord(x)) for x in res[0]]
            pos = res[1]
    return p

def PyUnicode_EncodeASCII(p,size,errors):

    return unicode_encode_ucs1(p, size, errors, 128)

def PyUnicode_AsASCIIString(unistr):

    if not type(unistr) == unicode:
        raise TypeError
    return PyUnicode_EncodeASCII(unicode(unistr),
				 len(unicode),
				None)

def PyUnicode_DecodeUTF16Stateful(s,size,errors,byteorder='native',consumed=None):

    bo = 0       #/* assume native ordering by default */
    errmsg = ""

    if sys.byteorder == 'little':
        ihi = 1
        ilo = 0
    else:
        ihi = 0
        ilo = 1
    
    if (size == 0):
        return [u'']

    #/* Unpack UTF-16 encoded data */

##    /* Check for BOM marks (U+FEFF) in the input and adjust current
##       byte order setting accordingly. In native mode, the leading BOM
##       mark is skipped, in all other modes, it is copied to the output
##       stream as-is (giving a ZWNBSP character). */
    q = 0
    p = []
    if byteorder == 'native':
        if (size >= 2):
            bom = (ord(s[ihi]) << 8) | ord(s[ilo])
#ifdef BYTEORDER_IS_LITTLE_ENDIAN
            if sys.byteorder == 'little':
        	    if (bom == 0xFEFF):
        	        q += 2
        	        bo = -1
        	    elif bom == 0xFFFE:
        	        q += 2
        	        bo = 1
            else:
        	    if bom == 0xFEFF:
        	        q += 2
        	        bo = 1
        	    elif bom == 0xFFFE:
        	        q += 2
        	        bo = -1
    elif byteorder == 'little':
        bo = -1
    else:
        bo = 1
        
    if (bo == -1):
        #/* force LE */
        ihi = 1
        ilo = 0

    elif (bo == 1):
        #/* force BE */
        ihi = 0
        ilo = 1

    while (q < len(s)):
    
    	#/* remaining bytes at the end? (size should be even) */
    	if (len(s)-q<2):
    	    if (consumed):
                break
    	    errmsg = "truncated data"
    	    startinpos = q
    	    endinpos = len(s)
    	    unicode_call_errorhandler()
##    	    /* The remaining input chars are ignored if the callback
##    	       chooses to skip the input */
    
    	ch = (ord(s[q+ihi]) << 8) | ord(s[q+ilo])
    	q += 2
    
    	if (ch < 0xD800 or ch > 0xDFFF):
    	   p += unichr(ch)
    	   continue
    
	#/* UTF-16 code pair: */
        if (q >= len(s)):
            errmsg = "unexpected end of data"
            startinpos = q-2
            endinpos = len(s)
            unicode_call_errorhandler

    	if (0xD800 <= ch and ch <= 0xDBFF):
            ch2 = (ord(s[q+ihi]) << 8) | ord(s[q+ilo])
            q += 2
            if (0xDC00 <= ch2 and ch2 <= 0xDFFF):
    #ifndef Py_UNICODE_WIDE
                if sys.maxunicode < 65536:
                    p += unichr(ch)
                    p += unichr(ch2)
                else:
                    p += unichr((((ch & 0x3FF)<<10) | (ch2 & 0x3FF)) + 0x10000)
    #endif
                continue

            else:
    	        errmsg = "illegal UTF-16 surrogate"
                startinpos = q-4
                endinpos = startinpos+2
                unicode_call_errorhandler
    	   
	errmsg = "illegal encoding"
	startinpos = q-2
	endinpos = startinpos+2
	unicode_call_errorhandler
	
    return p

# moved out of local scope, especially because it didn't
# have any nested variables.

def STORECHAR(CH, byteorder):
    hi = chr(((CH) >> 8) & 0xff)
    lo = chr((CH) & 0xff)
    if byteorder == 'little':
        return [lo, hi]
    else:
        return [hi, lo]

def PyUnicode_EncodeUTF16(s, size, errors, byteorder='little'):

#    /* Offsets from p for storing byte pairs in the right order. */

        
    p = []
    bom = sys.byteorder
    if (byteorder == 'native'):
        
        bom = sys.byteorder
        p += STORECHAR(0xFEFF,bom)
        
    if (size == 0):
        return ""

    if (byteorder == 'little' ):
        bom = 'little'
    elif (byteorder == 'big'):
        bom = 'big'


    for c in s:
        ch = ord(c)
        ch2 = 0
        if (ch >= 0x10000) :
            ch2 = 0xDC00 | ((ch-0x10000) & 0x3FF)
            ch  = 0xD800 | ((ch-0x10000) >> 10)

        p += STORECHAR(ch,bom)
        if (ch2):
            p +=STORECHAR(ch2,bom)

    return p


def PyUnicode_DecodeMBCS(s, size, errors):
    pass

def PyUnicode_EncodeMBCS(p, size, errors):
    pass
####    /* If there are no characters, bail now! */
##    if (size==0)
##	    return ""
##    from ctypes import *
##    WideCharToMultiByte = windll.kernel32.WideCharToMultiByte
####    /* First get the size of the result */
##    mbcssize = WideCharToMultiByte(CP_ACP, 0, p, size, s, 0, None, None);
##    if (mbcssize==0)
##        raise UnicodeEncodeError, "Windows cannot decode the string %s" %p
### More error handling required (check windows errors and such)
##    
###    /* Do the conversion */
####    s = ' '*mbcssize
####    if (0 == WideCharToMultiByte(CP_ACP, 0, p, size, s, mbcssize, NULL, NULL)):
####        raise UnicodeEncodeError, "Windows cannot decode the string %s" %p
##    return s
def unicode_call_errorhandler(errors,  encoding, 
                reason, input, startinpos, endinpos,decode=True):
    
    errorHandler = lookup_error(errors)
    if decode:
        exceptionObject = UnicodeDecodeError(encoding, input, startinpos, endinpos, reason)
    else:
        exceptionObject = UnicodeEncodeError(encoding, input, startinpos, endinpos, reason)
    res = errorHandler(exceptionObject)
    if isinstance(res,tuple) and isinstance(res[0],unicode) and isinstance(res[1],int):
        newpos = res[1]
        if (newpos<0):
            newpos = len(input)+newpos
        if newpos<0 or newpos>len(input):
            raise IndexError( "position %d from error handler out of bounds" % newpos)
        return res[0],newpos
    else:
        raise TypeError("encoding error handler must return (unicode, int) tuple")

def PyUnicode_DecodeUTF8(s, size, errors):

    return PyUnicode_DecodeUTF8Stateful(s, size, errors, None)

##    /* Map UTF-8 encoded prefix byte to sequence length.  zero means
##       illegal prefix.  see RFC 2279 for details */
utf8_code_length = [
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 0, 0
]

def PyUnicode_DecodeUTF8Stateful(s,size,errors,consumed):
    
    if (size == 0):
        if (consumed):
            consumed = 0
        return u''
    
    p = []
    pos = 0
    while pos < size:
        ch = s[pos]
        if ord(ch) < 0x80:
            p += ch
            pos += 1
            continue
        
        n = utf8_code_length[ord(ch)]
        startinpos =  pos 
        if (startinpos + n > size):
            if (consumed):
                break
            else:
                errmsg = "unexpected end of data"
                endinpos = size 
                res = unicode_call_errorhandler(
                                    errors, "utf8", errmsg,
                                    s,  startinpos, endinpos)
                p += res[0]
                pos = res[1]
        if n == 0:
            errmsg = "unexpected code byte"
            endinpos = startinpos+1
            res = unicode_call_errorhandler(
                                    errors, "utf8", errmsg,
                                    s,  startinpos, endinpos)
            p += res[0]
            pos = res[1]
        elif n == 1:
            errmsg = "internal error"
            endinpos = startinpos+1
            res = unicode_call_errorhandler(
                                    errors, "utf8", errmsg,
                                    s,  startinpos, endinpos)
            p += res[0]
            pos = res[1]
        elif n == 2:
            if ((ord(s[pos+1]) & 0xc0) != 0x80):
                errmsg = "invalid data"
                endinpos = startinpos+2
                res = unicode_call_errorhandler(
                                    errors, "utf8", errmsg,
                                    s,  startinpos, endinpos)
                p += res[0]
                pos = res[1]
            else:
                c = ((ord(s[pos]) & 0x1f) << 6) + (ord(s[pos+1]) & 0x3f)
                if c<0x80:
                    errmsg = "illegal encoding"
                    endinpos = startinpos+2
                    res = unicode_call_errorhandler(
                                            errors, "utf8", errmsg,
                                            s,  startinpos, endinpos)
                    p += res[0]
                    pos = res[1]
                else:
                    p += unichr(c)
                    pos += n
                    #break
        elif n == 3:
            if ((ord(s[pos+1]) & 0xc0) != 0x80 or
                    (ord(s[pos+2]) & 0xc0) != 0x80):
                errmsg = "invalid data"
                endinpos = startinpos+3
                res = unicode_call_errorhandler(
                                            errors, "utf8", errmsg,
                                            s,  startinpos, endinpos)
                p += res[0]
                pos = res[1]
            else:
                c = ((ord(s[pos]) & 0x0f) << 12) + \
                        ((ord(s[pos+1]) & 0x3f) << 6) +\
                        (ord(s[pos+2]) & 0x3f)       
                        
##		/* Note: UTF-8 encodings of surrogates are considered
##		   legal UTF-8 sequences;
##
##		   XXX For wide builds (UCS-4) we should probably try
##		       to recombine the surrogates into a single code
##		       unit.
##		*/
                if c < 0x0800:
                    errmsg = "illegal encoding"
                    endinpos = startinpos+3
                    res = unicode_call_errorhandler(
                                        errors, "utf8", errmsg,
                                        s,  startinpos, endinpos)
                    p += res[0]
                    pos = res[1]
                else:
                    p += unichr(c)
                    pos += n
        elif n == 4:
##        case 4:
            if ((ord(s[pos+1]) & 0xc0) != 0x80 or
                (ord(s[pos+2]) & 0xc0) != 0x80 or
                (ord(s[pos+3]) & 0xc0) != 0x80):
                
                errmsg = "invalid data"
                startinpos = pos
                endinpos = startinpos+4
                res = unicode_call_errorhandler(
                            errors, "utf8", errmsg,
                            s,  startinpos, endinpos)
                p += res[0]
                pos = res[1]
            else:
                c = ((ord(s[pos+0]) & 0x7) << 18) + ((ord(s[pos+1]) & 0x3f) << 12) +\
                     ((ord(s[pos+2]) & 0x3f) << 6) + (ord(s[pos+3]) & 0x3f)
                #/* validate and convert to UTF-16 */
                if ((c < 0x10000) or (c > 0x10ffff)):
                    #/* minimum value allowed for 4 byte encoding */
                    #/* maximum value allowed for UTF-16 */
	   
                    errmsg = "illegal encoding"
                    startinpos = pos
                    endinpos = startinpos+4
                    res = unicode_call_errorhandler(
                                            errors, "utf8", errmsg,
                                            s,  startinpos, endinpos)
                    p += res[0]
                    pos = res[1]
                else:
#ifdef Py_UNICODE_WIDE
                    if c<sys.maxunicode:
                        p += unichr(c)
                        pos += n
                    else:
##                /*  compute and append the two surrogates: */
##                /*  translate from 10000..10FFFF to 0..FFFF */
                        c -= 0x10000
            #/*  high surrogate = top 10 bits added to D800 */
                        p += unichr(0xD800 + (c >> 10))
            #/*  low surrogate = bottom 10 bits added to DC00 */
                        p += unichr(0xDC00 + (c & 0x03FF))
                        pos += n
        else:
##        default:
##            /* Other sizes are only needed for UCS-4 */
            errmsg = "unsupported Unicode code range"
    	    startinpos = pos
    	    endinpos = startinpos+n
    	    res = unicode_call_errorhandler(
                     errors, "utf8", errmsg,
                     s,  startinpos, endinpos)
            p += res[0]
            pos = res[1]
            
	#continue

    if (consumed):
        consumed = pos
    return p

def PyUnicode_EncodeUTF8(s,size,errors):

    #assert(s != None)
    assert(size >= 0)
    p = []
    i = 0
    while i<size:
        ch = s[i]
        i+=1
        if (ord(ch) < 0x80):
##         /* Encode ASCII */
            p += chr(ord(ch))
        elif (ord(ch) < 0x0800) :
##            /* Encode Latin-1 */
            p += chr((0xc0 | (ord(ch) >> 6)))
            p += chr((0x80 | (ord(ch) & 0x3f)))
        else:
##            /* Encode UCS2 Unicode ordinals */
            if (ord(ch) < 0x10000):
##                /* Special case: check for high surrogate */
                if (0xD800 <=ord(ch) and ord(ch) <= 0xDBFF and i != size) :
                    ch2 = s[i]
##                    /* Check for low surrogate and combine the two to
##                       form a UCS4 value */
                    if (0xDC00 <= ord(ch2) and ord(ch2) <= 0xDFFF) :
                        ch3 = ((ord(ch) - 0xD800) << 10 | (ord(ch2) - 0xDC00)) + 0x10000
                        i+=1
                        p.extend(encodeUCS4(ch3))
                        continue
##                    /* Fall through: handles isolated high surrogates */
                p += (chr((0xe0 | (ord(ch) >> 12))))
                p += (chr((0x80 | ((ord(ch) >> 6) & 0x3f))))
                p += (chr((0x80 | (ord(ch) & 0x3f))))
                continue
    return p

def encodeUCS4(ch):
##      /* Encode UCS4 Unicode ordinals */
    p=[]
    p +=  (chr((0xf0 | (ch >> 18))))
    p +=  (chr((0x80 | ((ch >> 12) & 0x3f))))
    p +=  (chr((0x80 | ((ch >> 6) & 0x3f))))
    p +=  (chr((0x80 | (ch & 0x3f))))
    return p

#/* --- Latin-1 Codec ------------------------------------------------------ */

def PyUnicode_DecodeLatin1(s, size, errors):
    #/* Latin-1 is equivalent to the first 256 ordinals in Unicode. */
##    if (size == 1):
##        return [PyUnicode_FromUnicode(s, 1)]
    pos = 0
    p = []
    while (pos < size):
        p += unichr(ord(s[pos]))
        pos += 1
    return p

def unicode_encode_ucs1(p,size,errors,limit):
    
    if limit == 256:
        reason = "ordinal not in range(256)"
        encoding = "latin-1"
    else:
        reason = "ordinal not in range(128)"
        encoding = "ascii"
    
    if (size == 0):
        return ['']
    res = []
    pos=0
    while pos < len(p):
    #for ch in p:
        ch = p[pos]
        
        if ord(ch) < limit:
            res += chr(ord(ch))
            pos += 1
        else:
            #/* startpos for collecting unencodable chars */
            collstart = pos 
            collend = pos+1 
            while collend < len(p) and ord(p[collend]) >= limit:
                collend += 1
            x = unicode_call_errorhandler(errors,encoding,reason,p,collstart,collend,False)
            res += str(x[0])
            pos = x[1]
    
    return res

def PyUnicode_EncodeLatin1(p,size,errors):
    res=unicode_encode_ucs1(p, size, errors, 256)
    return res

hexdigits = [hex(i)[-1] for i in range(16)]+[hex(i)[-1].upper() for i in range(10,16)]
def hexescape(s,pos,digits,message,errors):
    chr = 0
    p = []
    if (pos+digits>len(s)):
        message = "end of string in escape sequence"
        x = unicode_call_errorhandler(errors,"unicodeescape",message,s,pos-2,len(s))
        p += x[0]
        pos = x[1]
    else:
        try:
            chr = int(s[pos:pos+digits],16)
        except ValueError:
            endinpos = pos
            while s[endinpos] in hexdigits: 
                endinpos +=1
            x = unicode_call_errorhandler(errors,"unicodeescape",message,s,pos-2,
                        endinpos+1)
            p += x[0]
            pos = x[1]
        #/* when we get here, chr is a 32-bit unicode character */
        else:
            if chr <= sys.maxunicode:
                p += [unichr(chr)]
                pos += digits
            
            elif (chr <= 0x10ffff):
                chr -= 0x10000L
                p += unichr(0xD800 + (chr >> 10))
                p += unichr(0xDC00 +  (chr & 0x03FF))
                pos += digits
            else:
                message = "illegal Unicode character"
                x = unicode_call_errorhandler(errors,"unicodeescape",message,s,pos-2,
                        pos+1)
                p += x[0]
                pos = x[1]
    res = p
    return res,pos

def PyUnicode_DecodeUnicodeEscape(s, size, errors):

    if (size == 0):
        return u''
    
    p = []
    pos = 0
    while (pos < size): 
##        /* Non-escape characters are interpreted as Unicode ordinals */
        if (s[pos] != '\\') :
            p += s[pos]
            pos += 1
            continue
##        /* \ - Escapes */
        else:
            pos +=1
            if pos>=len(s):
                errmessage = "\\ at end of string"
                unicode_call_errorhandler(errors,"unicodeescape",errmessage,s,pos-1,size)
            ch = s[pos]
            pos += 1
    ##        /* \x escapes */
            #if ch == '\n': break;
            if ch == '\\': p += '\\'
            elif ch == '\'': p += '\''
            elif ch == '\"': p += '\"' 
            elif ch == 'b': p += '\b' 
            elif ch == 'f': p += '\014' #/* FF */
            elif ch == 't': p += '\t' 
            elif ch == 'n': p += '\n'
            elif ch == 'r': 
                p += '\r' 
                
            elif ch == 'v': p += '\013' #break; /* VT */
            elif ch == 'a': p += '\007' # break; /* BEL, not classic C */
    
    ##        /* \OOO (octal) escapes */
            elif ch in [ '0','1', '2', '3','4', '5', '6','7']:
                x = ord(ch) - ord('0')
                ch = s[pos]
                if ('0' <= ch and ch <= '7'):
                    x = (x<<3) + ord(ch) - ord('0')
                    ch = s[pos+1]
                    if ('0' <= ch and ch <= '7'):
                        x = (x<<3) + ord(ch) - ord('0')
                        pos += 2
    
                p += unichr(x)
    ##        /* hex escapes */
    ##        /* \xXX */
            elif ch == 'x':
                digits = 2
                message = "truncated \\xXX escape"
                x = hexescape(s,pos,digits,message,errors)
                p += x[0]
                pos = x[1]
    
         #   /* \uXXXX */
            elif ch == 'u':
                digits = 4
                message = "truncated \\uXXXX escape"
                x = hexescape(s,pos,digits,message,errors)
                p += x[0]
                pos = x[1]
    
          #  /* \UXXXXXXXX */
            elif ch == 'U':
                digits = 8
                message = "truncated \\UXXXXXXXX escape"
                x = hexescape(s,pos,digits,message,errors)
                p += x[0]
                pos = x[1]
##        /* \N{name} */
            elif ch == 'N':
                message = "malformed \\N character escape"
                #pos += 1
                try:
                    import unicodedata
                except ImportError:
                    message = "\\N escapes not supported (can't load unicodedata module)"
                    unicode_call_errorhandler(errors,"unicodeescape",message,s,pos-1,size)
                if (s[pos] == '{'):
                    look = pos+1
                    #/* look for the closing brace */
                    while (s[look] != '}' and look < size):
                        look += 1
                    if (look > pos+1 and look < size and s[look] == '}'):
                        #/* found a name.  look it up in the unicode database */
                        message = "unknown Unicode character name"
                        look += 1
                        try:
                            chr = unicodedata.lookup(s[pos:look])
                            #x = hexescape(chr,pos+1,8,message,errors)
                        except KeyError:
                            x=unicode_call_errorhandler(errors,"unicodeescape",message,s,pos-1,look)
                        else:
                            x = hexescape(s,pos+1,look-pos,message,errors)
                        p += x[0]
                        pos = x[1]
            else:
                if (pos > size):
                    message = "\\ at end of string"
                    handler = lookup_error(errors)
                    x = handler(UnicodeDecodeError("unicodeescape",s,pos,
                                size,message))
                    p += x[0]
                    pos = x[1]
                else:
                    p += '\\'
                    p += s[pos]
    return p

def PyUnicode_EncodeRawUnicodeEscape(s,size):
    
    if (size == 0):
        return ''

    p = []
    for ch in s:
#	/* Map 32-bit characters to '\Uxxxxxxxx' */
        if (ord(ch) >= 0x10000):
            p += '\\'
            p += 'U'
            p += '%08x'%(ord(ch))
        elif (ord(ch) >= 256) :
#	/* Map 16-bit characters to '\uxxxx' */
            p += '\\'
            p += 'u'
            p += '%04x'%(ord(ch))
#	/* Copy everything else as-is */
        else:
            p += chr(ord(ch))
    
    #p += '\0'
    return p

def charmapencode_output(c,mapping):

    rep = mapping[c]
    if isinstance(rep,int) or isinstance(rep, long):
        if rep<256:
            return chr(rep)
        else:
            raise TypeError("character mapping must be in range(256)")
    elif isinstance(rep,str):
        return rep
    elif rep == None:
        raise KeyError("character maps to <undefined>")
    else:
        raise TypeError("character mapping must return integer, None or str")

def PyUnicode_EncodeCharmap(p,size,mapping='latin-1',errors='strict'):

##    /* the following variable is used for caching string comparisons
##     * -1=not initialized, 0=unknown, 1=strict, 2=replace,
##     * 3=ignore, 4=xmlcharrefreplace */

#    /* Default to Latin-1 */
    if mapping == 'latin-1':
        return PyUnicode_EncodeLatin1(p, size, errors)
    if (size == 0):
        return ''
    inpos = 0
    res = []
    while (inpos<size):
	#/* try to encode it */
        try:
            x = charmapencode_output(ord(p[inpos]),mapping)
            res += [x]
        except KeyError:
            x = unicode_call_errorhandler(errors,"charmap",
            "character maps to <undefined>",p,inpos,inpos+1,False)
            try:
                res += [charmapencode_output(ord(y),mapping) for y in x[0]]
            except KeyError:
                raise UnicodeEncodeError("charmap",p,inpos,inpos+1,
                                        "character maps to <undefined>")
##        except TypeError,err:
##            x = unicode_call_errorhandler(errors,"charmap",
##            err,p,inpos,inpos+1,False)
##            try:
##                res += [charmapencode_output(ord(y),mapping) for y in x[0]]
##            except KeyError:
##                raise UnicodeEncodeError("charmap",p,inpos,inpos+1,
##                                        "character maps to <undefined>")
##    
	    #/* done with this character => adjust input position */
        inpos+=1
    return res

def PyUnicode_DecodeCharmap(s, size, mapping, errors):

##    /* Default to Latin-1 */
    if (mapping == None):
        return PyUnicode_DecodeLatin1(s, size, errors)

    if (size == 0):
        return u''
    p = []
    inpos = 0
    while (inpos< len(s)):
	
	#/* Get mapping (char ordinal -> integer, Unicode char or None) */
        ch = s[inpos]
        try:
            x = mapping[ord(ch)]
            if isinstance(x,int):
                if x<65536:
                    p += unichr(x)
                else:
                    raise TypeError("character mapping must be in range(65536)")
            elif isinstance(x,unicode):
                p += x
            elif not x:
                raise KeyError
            else:
                raise TypeError
        except KeyError:
            x = unicode_call_errorhandler(errors,"charmap",
                "character maps to <undefined>",s,inpos,inpos+1)
            p += x[0]
##        except TypeError:
##            x = unicode_call_errorhandler(errors,"charmap",
##                "character mapping must return integer, None or unicode",
##                s,inpos,inpos+1)
##            p += x[0]
        inpos +=1
    return p

def PyUnicode_DecodeRawUnicodeEscape(s, size,errors):

    if (size == 0):
        return u''
    pos = 0
    p = []
    while (pos < len(s)):
        ch = s[pos]
    #/* Non-escape characters are interpreted as Unicode ordinals */
        if (ch != '\\'):
            p += unichr(ord(ch))
            pos += 1
            continue        
        startinpos = pos
        #pos += 1
##	/* \u-escapes are only interpreted iff the number of leading
##	   backslashes is odd */
        bs = pos
        while pos < size:
            if (s[pos] != '\\'):
                break
            p += unichr(ord(s[pos]))
            pos += 1
    
        if (((pos - bs) & 1) == 0 or
            pos >= size or
            (s[pos] != 'u' and s[pos] != 'U')) :
            p += s[pos]
            pos += 1
            continue
        
        p.pop(-1)
        if s[pos] == 'u':
            count = 4 
        else: 
            count = 8
        pos += 1

	#/* \uXXXX with 4 hex digits, \Uxxxxxxxx with 8 */

        i = 0
        x = 0
        try:
            x = int(s[pos:pos+count],16)
        except ValueError:
            res = unicode_call_errorhandler(
                    errors, "rawunicodeescape", "truncated \\uXXXX",
                    s, size, pos, pos+count)
            p += res[0]
            pos = res[1]
        else:
    #ifndef Py_UNICODE_WIDE
            if sys.maxunicode > 0xffff:
                if (x > 0x10000):
                    res = unicode_call_errorhandler(
                        errors, "rawunicodeescape", "\\Uxxxxxxxx out of range",
                        s, size, pos, pos+1)
                    pos = i = res[1]
                    p += res[0]
                    i += 1
                else:
                    p += unichr(x)
                    pos += count
            else:
                if (x > 0x10000):
                    res = unicode_call_errorhandler(
                        errors, "rawunicodeescape", "\\Uxxxxxxxx out of range",
                        s, size, pos, pos+1)
                    pos = i = res[1]
                    p += res[0]

    #endif
                else:
                    p += unichr(x)
                    pos += count

    return p
