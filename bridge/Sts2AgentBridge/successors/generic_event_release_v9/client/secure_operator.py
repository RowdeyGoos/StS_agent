"""Descriptor-bound read lease for the one fixed card-selection operator tree."""
from __future__ import annotations
from pathlib import Path
import os
import stat
import sys
from typing import Callable, Any
import hashlib

CONFIGURATIONS = {"generic": b'{"schema_version":"generic_event_v9_transport_config_v1","enabled":true,"flow_kind":"generic","bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}'}

CONFIG_HASHES = {flow: hashlib.sha256(data).hexdigest() for flow, data in CONFIGURATIONS.items()}

LOWER_HEX = frozenset(b'0123456789abcdef')

class OperatorFailure(Exception):
    pass


def zero(buffer: bytearray) -> None:
    buffer[:] = b'\0' * len(buffer)


def identity(s: os.stat_result) -> tuple[int, ...]:
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _components(home: Path) -> tuple[str, ...]:
    value = str(home)
    if (not home.is_absolute() or value != os.path.normpath(value) or
            len(value.encode('utf-8')) > 1024 or any(c in value for c in '\0\r\n') or
            len(home.parts) < 2 or len(home.parts) > 33 or
            any(p in ('', '.', '..') or len(p.encode('utf-8')) > 255 for p in home.parts[1:])):
        raise OperatorFailure()
    return home.parts[1:]


def _read_exact(fd: int, size: int) -> bytearray:
    data = bytearray(size + 1)
    total = 0
    interruptions = 0
    try:
        while total < len(data):
            view = memoryview(data)[total:]
            try:
                count = os.readv(fd, [view])
            except InterruptedError:
                interruptions += 1
                if interruptions > 8:
                    raise OperatorFailure() from None
                continue
            finally:
                view.release()
            if count == 0:
                break
            if count < 0 or count > len(data) - total:
                raise OperatorFailure()
            total += count
        if total != size:
            raise OperatorFailure()
        del data[-1:]
        return data
    except BaseException:
        zero(data)
        raise


def read_credential(home: Path, uid: int, state: Any,
                    check_acl: Callable[[int], None]) -> bytearray:
    """Private composition API; production obtains all arguments from fixed preflight.

    Tests supply owned synthetic account facts. There is no CLI path override.
    Every descriptor remains owned until all checks complete; cleanup precedes transfer.
    """
    flow_kind = getattr(state, "flow_kind", None)
    if type(flow_kind) is not str or flow_kind not in CONFIGURATIONS or getattr(state, "config_sha256", None) != CONFIG_HASHES[flow_kind]:
        raise OperatorFailure()
    enabled = CONFIGURATIONS[flow_kind]
    parts = _components(home)
    fds: list[tuple[int, int | None, str, os.stat_result, bool, bool, int | None]] = []
    config = bytearray()
    token = bytearray()
    transferred = False

    def validate(entry, stable: bool = True):
        fd, parent, name, before, private, owned, size = entry
        after = os.fstat(fd)
        mode = stat.S_IMODE(after.st_mode)
        if size is None:
            valid = stat.S_ISDIR(after.st_mode) and (mode == 0o700 if private else mode & 0o7022 == 0)
        else:
            valid = stat.S_ISREG(after.st_mode) and mode == 0o600 and after.st_nlink == 1 and after.st_size == size
        if not valid or after.st_uid not in ({uid} if owned else {0, uid}):
            raise OperatorFailure()
        check_acl(fd)
        if stable and identity(after) != identity(before):
            raise OperatorFailure()
        named = os.stat(name, dir_fd=parent, follow_symlinks=False) if parent is not None else os.stat('/', follow_symlinks=False)
        if identity(after) != identity(named):
            raise OperatorFailure()

    def open_entry(name, *, private=False, owned=False, size=None):
        parent = fds[-1][0] if fds else None
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        flags |= os.O_DIRECTORY if size is None else os.O_NONBLOCK
        fd = os.open(name, flags, dir_fd=parent)
        try:
            before = os.fstat(fd)
        except BaseException:
            os.close(fd)
            raise
        entry = (fd, parent, name, before, private, owned, size)
        fds.append(entry)
        validate(entry)
        return entry

    def require_pin(entry, prefix):
        if (entry[3].st_dev, entry[3].st_ino) != (getattr(state, prefix + '_device'), getattr(state, prefix + '_inode')):
            raise OperatorFailure()

    try:
        open_entry('/')
        for index, component in enumerate(parts):
            open_entry(component, owned=index == len(parts) - 1)
        open_entry('Library', owned=True)
        support = open_entry('Application Support', owned=True)
        require_pin(support, 'application_support')
        operator = open_entry('Sts2AgentBridge', private=True, owned=True)
        require_pin(operator, 'operator')
        item = open_entry('generic_event_v9', private=True, owned=True)
        require_pin(item, 'config')
        config_entry = open_entry('config.json', owned=True, size=len(enabled))
        require_pin(config_entry, 'config_file')
        config = _read_exact(config_entry[0], len(enabled))
        if config != enabled:
            raise OperatorFailure()
        for entry in fds:
            validate(entry)
        # Both leaves are relative to the retained card-selection directory, never the config FD.
        parent = item[0]
        fd = os.open('credential.hex', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
        except BaseException:
            os.close(fd)
            raise
        token_entry = (fd, parent, 'credential.hex', before, False, True, 64)
        fds.append(token_entry)
        validate(token_entry)
        require_pin(token_entry, 'credential')
        token = _read_exact(fd, 64)
        if len(token) != 64 or any(value not in LOWER_HEX for value in token):
            raise OperatorFailure()
        for entry in fds:
            validate(entry)
        transferred = True
        return token
    finally:
        control = sys.exc_info()[1]
        control = control if isinstance(control, (KeyboardInterrupt, SystemExit)) else None
        zero(config)
        cleanup_failed = False
        for entry in reversed(fds):
            try:
                os.close(entry[0])
            except BaseException as error:
                cleanup_failed = True
                if control is None and isinstance(error, (KeyboardInterrupt, SystemExit)):
                    control = error
        if not transferred or cleanup_failed:
            zero(token)
        if control is not None:
            raise control
        if cleanup_failed:
            raise OperatorFailure() from None
