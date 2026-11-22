"""Rotating signed attendance tokens (10 s validity) - stdlib hmac vs itsdangerous.

Run:  python tools_tests/token_rotation.py
Proves: a fresh token verifies, a tampered token is rejected, a token older than 10 s is rejected.
"""
import base64
import hashlib
import hmac
import secrets
import time

from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

TTL = 10  # seconds
SIG_LEN = 16  # bytes of truncated HMAC-SHA256
KEY = secrets.token_bytes(32)  # demo key, generated at runtime (real app: env var)


# --- Option A: stdlib hmac -------------------------------------------------
def make_token(payload: str, now: float | None = None) -> str:
    ts = int(now if now is not None else time.time())
    msg = f"{payload}|{ts}".encode()
    sig = hmac.new(KEY, msg, hashlib.sha256).digest()[:SIG_LEN]
    return base64.urlsafe_b64encode(msg + b"|" + sig).decode().rstrip("=")


def verify_token(token: str, now: float | None = None) -> str | None:
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    # The signature is binary and may itself contain b"|": split by its fixed length, not by separator.
    msg, sig = raw[:-SIG_LEN - 1], raw[-SIG_LEN:]
    good = hmac.new(KEY, msg, hashlib.sha256).digest()[:SIG_LEN]
    if not hmac.compare_digest(sig, good):
        return None
    payload, ts = msg.decode().rsplit("|", 1)
    if (now if now is not None else time.time()) - int(ts) > TTL:
        return None
    return payload


# --- Option B: itsdangerous -----------------------------------------------
signer = TimestampSigner(KEY)


def main() -> None:
    t = make_token("session42:sponsor7")
    print("A stdlib  token length:", len(t))
    print("A fresh token valid   :", verify_token(t) == "session42:sponsor7")
    bad = t[:-2] + ("AA" if t[-2:] != "AA" else "BB")
    print("A tampered rejected   :", verify_token(bad) is None)
    old = make_token("session42:sponsor7", now=time.time() - 11)
    print("A 11s-old rejected    :", verify_token(old) is None)

    s = signer.sign("session42:sponsor7").decode()
    print("B itsdangerous length :", len(s))
    print("B fresh valid         :", signer.unsign(s, max_age=TTL).decode() == "session42:sponsor7")
    print("B waiting 11 s (real sleep) ...")
    t0 = time.time()
    time.sleep(11)
    try:
        signer.unsign(s, max_age=TTL)
        print("B expired rejected    : False")
    except SignatureExpired:
        print("B expired rejected    : True (SignatureExpired)")
    print("A real-time expiry    :", verify_token(t) is None, f"(after {time.time() - t0:.1f} s)")
    try:
        signer.unsign(s[:-1] + ("x" if s[-1] != "x" else "y"))
        print("B tampered rejected   : False")
    except BadSignature:
        print("B tampered rejected   : True (BadSignature)")


if __name__ == "__main__":
    main()
