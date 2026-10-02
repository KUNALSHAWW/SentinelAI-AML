"""Hash-chained audit trail: append, verify, and detect every kind of tampering."""

import pytest
from sqlalchemy import text

from sentinelai.db.session import session_scope
from sentinelai.services.audit import GENESIS, audit


async def _append(n):
    async with session_scope() as s:
        for i in range(n):
            await audit.append(s, actor="alice", action="test.event", entity_type="thing", entity_id=str(i), payload={"i": i})


async def test_empty_chain_is_valid(db):
    async with session_scope() as s:
        r = await audit.verify(s)
        head = await audit.head(s)
    assert r["valid"] and r["entries"] == 0 and head["head_hash"] == GENESIS


async def test_chain_links_and_verifies(db):
    await _append(5)
    async with session_scope() as s:
        rows = await audit.entries(s, limit=10)
        r = await audit.verify(s)
    ordered = sorted(rows, key=lambda x: x.seq)
    assert [x.seq for x in ordered] == [1, 2, 3, 4, 5]
    assert ordered[0].prev_hash == GENESIS and all(b.prev_hash == a.hash for a, b in zip(ordered, ordered[1:]))
    assert r["valid"] and r["entries"] == 5 and r["head_hash"] == ordered[-1].hash


async def test_modified_payload_is_detected(db):
    await _append(4)
    async with session_scope() as s:
        await s.execute(text("UPDATE audit_log SET payload = :p WHERE seq = 2"), {"p": '{"i":999}'})
    async with session_scope() as s:
        r = await audit.verify(s)
    assert not r["valid"] and r["first_invalid_seq"] == 2 and "tampered" in r["detail"]


async def test_modified_actor_is_detected(db):
    await _append(3)
    async with session_scope() as s:
        await s.execute(text("UPDATE audit_log SET actor = 'mallory' WHERE seq = 3"))
    async with session_scope() as s:
        assert (await audit.verify(s))["first_invalid_seq"] == 3


async def test_deleted_entry_is_detected(db):
    await _append(5)
    async with session_scope() as s:
        await s.execute(text("DELETE FROM audit_log WHERE seq = 3"))
    async with session_scope() as s:
        r = await audit.verify(s)
    assert not r["valid"] and r["first_invalid_seq"] == 4


async def test_rewritten_history_with_recomputed_hash_still_breaks_the_next_link(db):
    from sentinelai.services.audit import compute_hash
    await _append(4)
    async with session_scope() as s:
        row = (await audit.entries(s, limit=10))[-2]            # seq 2
        forged = compute_hash(row.prev_hash, row.seq, row.timestamp, row.actor, row.action, row.entity_type, row.entity_id, '{"i":42}')
        await s.execute(text("UPDATE audit_log SET payload = :p, hash = :h WHERE seq = 2"), {"p": '{"i":42}', "h": forged})
    async with session_scope() as s:
        r = await audit.verify(s)
    assert not r["valid"] and r["first_invalid_seq"] == 3 and "prev_hash" in r["detail"]


async def test_append_in_same_session_keeps_sequence(db):
    async with session_scope() as s:
        a = await audit.append(s, actor="x", action="a", entity_type="t", entity_id="1")
        b = await audit.append(s, actor="x", action="b", entity_type="t", entity_id="2")
    assert (a.seq, b.seq) == (1, 2) and b.prev_hash == a.hash


async def test_rollback_leaves_no_audit_entry(db):
    with pytest.raises(RuntimeError):
        async with session_scope() as s:
            await audit.append(s, actor="x", action="a", entity_type="t", entity_id="1")
            raise RuntimeError("boom")
    async with session_scope() as s:
        assert (await audit.head(s))["entries"] == 0


async def test_concurrent_writers_never_fork_the_chain(db):
    import asyncio

    async def one(i):
        async with session_scope() as s:
            await audit.append(s, actor="x", action="c", entity_type="t", entity_id=str(i))
    await asyncio.gather(*[one(i) for i in range(12)])
    async with session_scope() as s:
        r = await audit.verify(s)
    assert r["valid"] and r["entries"] == 12
