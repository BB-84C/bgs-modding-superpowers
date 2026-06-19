from bgs_papyrus.starfield_syntax import VALIDATED, fix


def test_unvalidated_guard_block_is_marked_not_rewritten():
    src = (
        "Guard myGuard ;*** WARNING: Experimental syntax, may be incorrect: Guard\n"
        "  Foo()\n"
        "EndGuard ;*** WARNING: Experimental syntax, may be incorrect: EndGuard\n"
    )

    out = fix(src, validated={"lock_guard_block": False})

    assert "UNVERIFIED sf-syntax" in out
    assert "EndLockGuard" not in out


def test_validated_guard_block_is_rewritten():
    src = (
        "Guard myGuard ;*** WARNING: Experimental syntax, may be incorrect: Guard\n"
        "  Foo()\n"
        "EndGuard ;*** WARNING: Experimental syntax, may be incorrect: EndGuard\n"
    )

    out = fix(src, validated={"lock_guard_block": True})

    assert "LockGuard" in out and "EndLockGuard" in out
    assert "sf-syntax-fix applied" in out


def test_idempotent():
    src = (
        "Guard g ;*** WARNING: Experimental syntax, may be incorrect: Guard\n"
        "EndGuard ;*** WARNING: Experimental syntax, may be incorrect: EndGuard\n"
    )

    once = fix(src)
    twice = fix(once)

    assert once == twice


def test_empirically_validated_starfield_lock_guard_mapping_rewrites_by_default():
    src = (
        "  Guard UpdatePowerGuard ;*** WARNING: Experimental syntax, may be incorrect: Guard  ; #DEBUG_LINE_NO:36\n"
        "    Foo()\n"
        "  EndGuard ;*** WARNING: Experimental syntax, may be incorrect: EndGuard \n"
    )

    out = fix(src)

    assert VALIDATED["lock_guard_block"] is True
    assert "UNVERIFIED sf-syntax: lock_guard_block" not in out
    assert "  LockGuard UpdatePowerGuard ;*** WARNING: Experimental syntax, may be incorrect: Guard  ; #DEBUG_LINE_NO:36" in out
    assert "  EndLockGuard" in out


def test_empirically_validated_starfield_try_lock_guard_mapping_rewrites_by_default():
    src = (
        "\tTryGuard TaskMasterRestoreGuard ;*** WARNING: Experimental syntax, may be incorrect: TryGuard  ; #DEBUG_LINE_NO:155\n"
        "\t\tFoo()\n"
        "\tEndGuard ;*** WARNING: Experimental syntax, may be incorrect: EndGuard \n"
    )

    out = fix(src)

    assert VALIDATED["try_lock_guard_block"] is True
    assert "UNVERIFIED sf-syntax: try_lock_guard_block" not in out
    assert "\tTryLockGuard TaskMasterRestoreGuard ;*** WARNING: Experimental syntax, may be incorrect: TryGuard  ; #DEBUG_LINE_NO:155" in out
    assert "\tEndTryLockGuard" in out


def test_guard_declaration_is_not_rewritten_when_guard_block_is_fixed():
    src = (
        "Guard UpdatePowerGuard\n"
        "Function UpdatePowerState()\n"
        "  Guard UpdatePowerGuard ;*** WARNING: Experimental syntax, may be incorrect: Guard  ; #DEBUG_LINE_NO:36\n"
        "    Foo()\n"
        "  EndGuard ;*** WARNING: Experimental syntax, may be incorrect: EndGuard \n"
        "EndFunction\n"
    )

    out = fix(src)

    assert "Guard UpdatePowerGuard\nFunction" in out
    assert "LockGuard UpdatePowerGuard\nFunction" not in out
    assert "  LockGuard UpdatePowerGuard" in out
    assert "  EndLockGuard" in out


def test_guard_declaration_adds_protects_function_logic_when_block_has_no_guarded_members():
    src = (
        ";*** WARNING: Guard declaration syntax is EXPERIMENTAL, subject to change\n"
        "Guard UpdatePowerGuard\n"
        "Function UpdatePowerState()\n"
        "  Guard UpdatePowerGuard ;*** WARNING: Experimental syntax, may be incorrect: Guard\n"
        "    Foo()\n"
        "  EndGuard ;*** WARNING: Experimental syntax, may be incorrect: EndGuard\n"
        "EndFunction\n"
    )

    out = fix(src)

    assert "Guard UpdatePowerGuard ProtectsFunctionLogic" in out


def test_guard_declaration_keeps_plain_guard_when_members_require_it():
    src = (
        ";*** WARNING: Guard declaration syntax is EXPERIMENTAL, subject to change\n"
        "Guard CoraGuardCount\n"
        "Int CoraStartingBookCount RequiresGuard(CoraGuardCount)\n"
        "Function CheckCountAndOpenMenu()\n"
        "  Guard CoraGuardCount ;*** WARNING: Experimental syntax, may be incorrect: Guard\n"
        "    CoraStartingBookCount = 1\n"
        "  EndGuard ;*** WARNING: Experimental syntax, may be incorrect: EndGuard\n"
        "EndFunction\n"
    )

    out = fix(src)

    assert "Guard CoraGuardCount\n" in out
    assert "Guard CoraGuardCount ProtectsFunctionLogic" not in out


def test_unmodeled_guard_related_construct_gets_general_unverified_marker():
    src = "ScriptName Example\nFunction F() RequiresGuard(Foo)\nEndFunction\n"

    out = fix(src)

    assert "UNVERIFIED sf-syntax: unmodeled guard-related construct(s) present" in out


def test_fully_modeled_guard_rewrite_does_not_get_general_unverified_marker():
    src = (
        "Guard myGuard ;*** WARNING: Experimental syntax, may be incorrect: Guard\n"
        "  Foo()\n"
        "EndGuard ;*** WARNING: Experimental syntax, may be incorrect: EndGuard\n"
    )

    out = fix(src)

    assert "LockGuard" in out and "EndLockGuard" in out
    assert "unmodeled guard-related construct(s) present" not in out
