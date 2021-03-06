""" A library providing signature and verification functions for the ECDSA scheme.

Example:
    How to use ``do_ecdsa_sign`` and ``do_ecdsa_verify`` to sign and verify a string:

    >>> from hashlib import sha1
    >>> # Generate a signature / verification key pair.
    >>> G = EcGroup()
    >>> sig_key = G.order().random()
    >>> ver_key = sig_key * G.generator()
    >>> # Hash the (potentially long) message into a short digest.
    >>> digest = sha1(b"Hello World!").digest()
    >>> # Sign and verify signature
    >>> sig = do_ecdsa_sign(G, sig_key, digest)
    >>> do_ecdsa_verify(G, ver_key, sig, digest)
    True

    Fast signatures can be constructed using ``do_ecdsa_setup``:

    >>> from hashlib import sha1
    >>> # Generate a signature / verification key pair.
    >>> G = EcGroup()
    >>> sig_key = G.order().random()
    >>> ver_key = sig_key * G.generator()
    >>> # Hash the (potentially long) message into a short digest.
    >>> digest = sha1(b"Hello World!").digest()
    >>> # Sign and verify signature
    >>> kinv_rp = do_ecdsa_setup(G, sig_key)
    >>> sig = do_ecdsa_sign(G, sig_key, digest, kinv_rp = kinv_rp)
    >>> do_ecdsa_verify(G, ver_key, sig, digest)
    True

"""


from .bindings import _C, _FFI
from .ec import EcGroup, _check
from .bn import Bn, _ctx


def do_ecdsa_setup(G, priv):
    """Compute the parameters kinv and rp to (optionally) speed up ECDSA signing."""

    ec_key = _C.EC_KEY_new()
    _check( _C.EC_KEY_set_group(ec_key, G.ecg) )
    _check( _C.EC_KEY_set_private_key(ec_key, priv.bn) )

    ptr_kinv = _FFI.new("BIGNUM **")
    ptr_rp = _FFI.new("BIGNUM **")

    _check( _C.ECDSA_sign_setup(ec_key, _ctx.bnctx, ptr_kinv, ptr_rp) )

    kinv = Bn()
    _C.BN_copy(kinv.bn, ptr_kinv[0])
    _C.BN_clear_free(ptr_kinv[0])

    rp = Bn()
    _C.BN_copy(rp.bn, ptr_rp[0])
    _C.BN_clear_free(ptr_rp[0])

    return kinv, rp
        


def do_ecdsa_sign(G, priv, data, kinv_rp = None):
    """A quick function to ECDSA sign a hash.

    Args:
        G (EcGroup): the group in which math is done.
        priv (Bn): the secret key.
        data (str): the string to sign.
        kinv_rp (opaque): optional setup parameters.

    Returns:
        Bn, Bn: The (r, s) signature

    """
    ec_key = _C.EC_KEY_new()
    _check( _C.EC_KEY_set_group(ec_key, G.ecg) )
    _check( _C.EC_KEY_set_private_key(ec_key, priv.bn) )
    # _check( _C.EC_KEY_precompute_mult(ec_key, _FFI.NULL) )

    if kinv_rp is None:
        ecdsa_sig = _C.ECDSA_do_sign(data, len(data), ec_key)

    else:
        kinv, rp = kinv_rp
        ecdsa_sig = _C.ECDSA_do_sign_ex(data, len(data), kinv.bn, rp.bn, ec_key)

    r = Bn()
    s = Bn()

    _C.BN_copy(r.bn, ecdsa_sig.r)
    _C.BN_copy(s.bn, ecdsa_sig.s)

    _C.ECDSA_SIG_free(ecdsa_sig)
    _C.EC_KEY_free(ec_key)

    return (r, s)

def do_ecdsa_verify(G, pub, sig, data):
    """A quick function to ECDSA sign a hash.

    Args:
        G (EcGroup): the group in which math is done.
        pub (EcPt): the secret key
        data (str): the string to sign
        sign (Bn, Bn): the (r,s) signature

    Returns:
        bool: A Boolean indicating whether the signature verifies.
    """

    r, s = sig

    ec_key = _C.EC_KEY_new()
    _check( _C.EC_KEY_set_group(ec_key, G.ecg) )
    _check( _C.EC_KEY_set_public_key(ec_key, pub.pt) )
    _check( _C.EC_KEY_precompute_mult(ec_key, _ctx.bnctx) )

    ec_sig = _C.ECDSA_SIG_new()

    _C.BN_copy(ec_sig.r, r.bn)
    _C.BN_copy(ec_sig.s, s.bn)

    try:
        result = int(_C.ECDSA_do_verify(data, len(data), ec_sig, ec_key))
        if result == -1:
            raise Exception("ECDSA Error")

    finally:
        _C.EC_KEY_free(ec_key)
        _C.ECDSA_SIG_free(ec_sig)

    return bool(result)

def test_ecdsa():
    G = EcGroup()
    priv = G.order().random()
    g = G.generator()
    sig = do_ecdsa_sign(G, priv, b"Hello")
    assert do_ecdsa_verify(G, priv * g, sig, b"Hello")

def test_ecdsa_fail():
    G = EcGroup()
    priv = G.order().random()
    g = G.generator()
    sig = do_ecdsa_sign(G, priv, b"Hello")

    assert not do_ecdsa_verify(G, priv * g, sig, b"Hellx")


def test_ecdsa_timing():
    repreats = 1000

    from hashlib import sha1
    import time

    G = EcGroup()
    sig_key = G.order().random()
    ver_key = sig_key * G.generator()
    
    digest = sha1(b"Hello World!").digest()
    
    print 
    t = []

    x = "Sign. plain"
    t0 = time.clock()
    for y in range(repreats):
        sig = do_ecdsa_sign(G, sig_key, digest)
    t += [time.clock() - t0]
    
    print("%s:\t%2.2f/sec" % (x, 1.0/(t[-1] / repreats)) )

    
    x = "Sign. with setup"
    t0 = time.clock()
    kinv_rp = do_ecdsa_setup(G, sig_key)
    for y in range(repreats):
        sig = do_ecdsa_sign(G, sig_key, digest, kinv_rp = kinv_rp)
    t += [time.clock() - t0]
    
    print("%s:\t%2.2f/sec" % (x, 1.0/(t[-1] / repreats)) )


    x = "Verification"
    t0 = time.clock()
    kinv_rp = do_ecdsa_setup(G, sig_key)
    for y in range(repreats):
            do_ecdsa_verify(G, ver_key, sig, digest)
    t += [time.clock() - t0]
    
    print("%s:\t%2.2f/sec" % (x, 1.0/(t[-1] / repreats)) )

