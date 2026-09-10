"""Native credential storage only; never fall back to a plaintext backend."""

import sys


class PasswordStorageError(OSError):
    """A sanitized error suitable for display without leaking backend details."""


class PasswordVault:
    SERVICE = "SuperconformalIndex.N2Database.MySQL"

    def __init__(self):
        self._backend = None

    def _get_backend(self):
        if self._backend is None:
            try:
                # Explicit native backends bypass keyring's configurable backend
                # discovery, including keyrings.alt and plaintext file stores.
                if sys.platform.startswith("linux"):
                    from keyring.backends.SecretService import Keyring
                elif sys.platform == "darwin":
                    from keyring.backends.macOS import Keyring
                elif sys.platform == "win32":
                    from keyring.backends.Windows import WinVaultKeyring as Keyring
                else:
                    raise PasswordStorageError("No native password vault is supported on this platform.")
                self._backend = Keyring()
            except ImportError:
                raise PasswordStorageError(
                    "Secure password storage requires the keyring package. "
                    "Install gui/requirements.txt with the Python interpreter running this app."
                ) from None
        return self._backend

    def _call(self, method, *args):
        try:
            return getattr(self._get_backend(), method)(self.SERVICE, *args)
        except PasswordStorageError:
            raise
        except Exception:
            # Some backend exceptions may contain request data. Do not display
            # or chain them into logs/tracebacks containing the password.
            raise PasswordStorageError(
                "Cannot access the system password vault. Unlock your desktop keyring "
                "and try again. On Linux, a running Secret Service (such as GNOME "
                "Keyring) is required. The password was not saved in plaintext."
            ) from None

    def get(self, credential_id: str) -> str:
        password = self._call("get_password", credential_id)
        if password is None:
            raise PasswordStorageError(
                "The saved password is missing from the system vault. Restore its "
                "keyring entry, or remove mysql/password_id from the settings file "
                "to enter a new password."
            )
        return password

    def set(self, credential_id: str, password: str) -> None:
        self._call("set_password", credential_id, password)
        if self.get(credential_id) != password:
            raise PasswordStorageError("The system vault did not confirm the saved password.")

    def delete(self, credential_id: str) -> None:
        self._call("delete_password", credential_id)
