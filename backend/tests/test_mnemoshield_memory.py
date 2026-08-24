from app.mnemoshield.memory_module import AgentMemoryModule

def test_memory_module_scoring_and_consolidation():
    mem = AgentMemoryModule()
    
    # Add a high importance memory
    high_entry = mem.add_entry("Crucial refinery valve safety override threshold set to 8.5 bar.", category="conclusion", importance=5.0)
    
    # Add a low importance memory
    low_entry = mem.add_entry("Routine check: Weather temperature sunny at 28C.", category="action", importance=1.0)
    
    # Verify importance & composite scores
    assert high_entry.importance == 5.0
    assert low_entry.importance == 1.0
    assert high_entry.composite_score() > low_entry.composite_score()

    # Trigger consolidation
    res = mem.consolidate_memory(threshold_score=2.0)
    assert res["purged_count"] >= 1
    assert low_entry.entry_id in res["purged_ids"]
    assert high_entry.entry_id not in res["purged_ids"]

def test_operator_manual_purge():
    mem = AgentMemoryModule()
    entry = mem.add_entry("Stale operator note regarding pump P-101 vibration.", category="action", importance=2.0)
    
    assert entry.entry_id in mem.entries
    purged = mem.purge_entry(entry.entry_id)
    assert purged is True
    assert entry.entry_id not in mem.entries
