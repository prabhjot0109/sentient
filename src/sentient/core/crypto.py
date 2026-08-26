"""Vault primitives: encrypt with the current key, decrypt with any key we still hold.

**The problem this solves.** `SENTIENT_SECRET_KEY` had no rotation story, and
changing it did not error -- it silently stopped every stored credential from
decrypting. `services/runtime.py:_stored_key` catches that and falls back to the
environment key, which is right for one corrupt row and wrong for a rotation:
every user's vaulted key quietly stops being used and the env key answers in its
place. Nobody sees an error; the bill just moves. **A silent invalidation is
worse than a loud one**, and the cure is to make rotation never reach that path.

`MultiFernet` decrypts with any key in the list and encrypts with the first, so
holding the previous key for one deploy makes rotation a no-downtime, three-step
operation. See README, "Rotating the vault key".
"""

from __future__ import annotations

from collections.abc import Sequence

from cryptography.fernet import Fernet, MultiFernet


def _multi(secret: str, previous: Sequence[str] = ()) -> MultiFernet:
    """Primary first -- MultiFernet encrypts with `keys[0]` and tries all of them
    when decrypting, so the order here is what makes new writes use the new key."""
    return MultiFernet([Fernet(secret.encode()), *(Fernet(key.encode()) for key in previous)])


def encrypt_key(raw: str, secret: str) -> str:
    return Fernet(secret.encode()).encrypt(raw.encode()).decode()


def decrypt_key(token: str, secret: str, previous: Sequence[str] = ()) -> str:
    """Decrypt with the current key, or any key in `previous`.

    Raises `InvalidToken` when none of them fit. It deliberately does not return
    None: callers that want to degrade decide that for themselves and log it, and
    a primitive that answers "no key" the same way it answers "no credential"
    would make those two indistinguishable at the one place they differ.
    """
    return _multi(secret, previous).decrypt(token.encode()).decode()


def rotate_token(token: str, secret: str, previous: Sequence[str] = ()) -> str:
    """Re-encrypt one stored token under the current key.

    `MultiFernet.rotate` decrypts then re-encrypts; it never nests, so running a
    rotation twice is harmless -- which matters, because operators re-run
    commands. The output is not byte-identical on a second pass (Fernet stamps a
    fresh IV and timestamp) but the plaintext and the key used are.
    """
    return _multi(secret, previous).rotate(token.encode()).decode()


def key_hint(raw: str) -> str:
    return "…" + raw[-4:]


def crypto_available(settings: object) -> bool:
    return bool(getattr(settings, "sentient_secret_key", None))
