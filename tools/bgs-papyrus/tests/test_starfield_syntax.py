from bgs_papyrus.starfield_syntax import fix


def test_unvalidated_guard_block_is_marked_not_rewritten():
    src = "Guard myGuard\n  Foo()\nEndGuard\n"

    out = fix(src)

    assert "UNVERIFIED sf-syntax" in out
    assert "EndLockGuard" not in out


def test_validated_guard_block_is_rewritten():
    src = "Guard myGuard\n  Foo()\nEndGuard\n"

    out = fix(src, validated={"lock_guard_block": True})

    assert "LockGuard" in out and "EndLockGuard" in out
    assert "sf-syntax-fix applied" in out


def test_idempotent():
    src = "Guard g\nEndGuard\n"

    once = fix(src)
    twice = fix(once)

    assert once == twice
