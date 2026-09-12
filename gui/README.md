# N2SCFTDB GUI

Run from the project root using the existing Sage environment (PyQt6 is installed):

```bash
/home/subo-lee/miniconda3/envs/sage/bin/python -B gui/n2_db.py
```

Alternatively, install the GUI dependencies in a Python environment:

```bash
python -m pip install -r gui/requirements.txt
python gui/n2_db.py
```

The shell itself does not require Sage, FORM, LiE or a
MySQL connection. It also works with `python -m gui.n2_db` from the project root.

Open `n2_db.ui` and `settings.ui` in Qt Creator / Qt Widgets Designer to edit
their layouts. The main window contains only the empty `anomaly` and `index`
tabs. Choose **Settings → Preferences…** (Ctrl+,) for settings; **File → Quit**
(Ctrl+Q) closes the program. Python loads both UI files directly, so no code
generation step is needed.

**OK** saves settings immediately. **Cancel**, Escape and the dialog close
button discard edits. Saved values load on later launches and take precedence
over default values and environment variables. On Linux the settings file is
`~/.config/SuperconformalIndex/n2_db.ini`, or
`$XDG_CONFIG_HOME/SuperconformalIndex/n2_db.ini` when that variable is set.
Other platforms use Qt's generic per-user configuration directory. Persistence
uses [QSettings](https://doc.qt.io/qt-6/qsettings.html) in INI format, with atomic
file replacement and owner-only permissions (0600 on POSIX).

The configuration directory and keyring service retain their original identifiers
for compatibility with saved preferences and passwords. These are storage IDs,
not the current project name. Cache paths inside the previous sibling checkout
are rebased to the current `N2SCFTDB` root when loaded and persisted on the next
settings save. Custom cache paths outside the previous checkout stay as entered.

Passwords are stored in the native system credential vault via
[Python keyring](https://keyring.readthedocs.io/en/latest/): Linux Secret Service
(GNOME Keyring on this machine), macOS Keychain, or Windows Credential Manager.
The INI contains only an opaque `mysql/password_id` reference. No encryption
key or password is stored beside it. Configurable plaintext keyring backends
are bypassed. GNOME Keyring encrypts its password collection using its master
password; use a password-protected keyring. See the
[GNOME security description](https://wiki.gnome.org/Projects/GnomeKeyring/SecurityFAQ).
Encryption protects stored credentials; an unlocked desktop session can access
them through the vault, and the app necessarily holds the password in memory.

The desktop may ask you to unlock your keyring. If secure storage is unavailable,
the GUI reports an error and does not fall back to writing a plaintext password.
An empty saved password requires no vault entry and overrides `N2_DB_PASSWORD`.
Changing or clearing a password removes the previously referenced entry after
the new settings are saved. If cleanup cannot reach the vault, an unused encrypted
entry can remain under the service `SuperconformalIndex.N2Database.MySQL`.

Existing `mysql/password` plaintext settings migrate automatically at startup
or when settings are read: the app saves and reads back the password in the
vault, then atomically replaces the INI without its plaintext key. Failed
migration preserves the original file for retry and displays an error. This
does not erase old filesystem snapshots or backups. Copying only the INI to
another computer does not copy its password; restore the keyring entry or remove
`mysql/password_id` from the INI and enter the password again.

Defaults mirror `index/char_decomposition_cache.py`,
`index/form_expansion_cache.py`, `index/n2_theory_index.py`,
`common/n2_theory_db.py`, and `common/n2_theory_properties.py`:

| Setting | First-run default |
| --- | --- |
| Full superconformal index maximum order | `18` (power of `t`, `INDEX_MAX_ORDER`) |
| Coulomb index maximum dimension | `90` (`C_INDEX_MAX_ORDER`) |
| Character decomposition cache | Project-root `char_decomposition_cache.db` |
| FORM expansion cache | Project-root `form_expansion_cache.db` |
| MySQL database | Empty; the backend requires an explicitly supplied name |
| MySQL host | `N2_DB_HOST`, otherwise `127.0.0.1` |
| MySQL port | `3306` |
| MySQL user | `N2_DB_USER`, otherwise `root` |
| MySQL password | `N2_DB_PASSWORD`, otherwise empty |
| MySQL connection timeout | `10` seconds |
| LiE executable | `lie` (resolved through PATH) |
| FORM executable | `form` (resolved through PATH) |
| LiE / FORM timeout | `600` seconds per invocation |

The **Index truncation** section saves both inclusive cutoffs. Full-index order
is a nonnegative integer; the Coulomb cutoff accepts nonnegative integers or
exact fractions such as `6/5`. Coulomb dimensions are saved as exact strings
(fractions are reduced), without conversion to floating point. Older settings
files use the project defaults for these new fields until saved.
`N2DatabaseWindow.settings` exposes them as `index/full_max_order` and
`index/coulomb_max_dimension`, suitable for the backend's `order` and
`max_dimension` arguments respectively.

Cache paths can select existing files or future files. Relative cache paths
are resolved against the project root when saved. Both cache locations are
explicit settings; changing one does not silently move the other. Executables
accept a command on PATH or an absolute path. Save does not open cache databases,
connect to MySQL, or execute computation tools. The tabs have no computation
actions yet; future actions can read `N2DatabaseWindow.settings`.

To run the GUI regression checks without opening desktop windows:

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  /home/subo-lee/miniconda3/envs/sage/bin/python -B \
  -m unittest discover -s gui -p 'test_*.py' -v
```

These tests use an in-memory credential test double, never your desktop vault.
For an additional real Linux Secret Service check, run:

```bash
/home/subo-lee/miniconda3/envs/sage/bin/python -B gui/check_secret_service.py
```

This opt-in check requires `dbus-run-session` and `gnome-keyring-daemon`. It
creates a private D-Bus session and temporary XDG directories, initializes a
password-protected disposable keyring, and checks migration, a fresh GUI process,
the encrypted keyring file and password removal. It never uses personal
credentials or the normal desktop keyring. Sandboxes that prohibit local sockets
cannot run this integration check.
