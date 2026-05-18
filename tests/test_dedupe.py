from app.services.dedupe import RuntimeDedupe


def test_message_dedupe_only_flags_second_seen() -> None:
    dedupe = RuntimeDedupe()

    assert dedupe.seen_message(-1001, 10) is False
    assert dedupe.seen_message(-1001, 10) is True
    assert dedupe.seen_message(-1001, 11) is False


def test_media_group_finalization_is_single_shot() -> None:
    dedupe = RuntimeDedupe()

    assert dedupe.mark_media_group_finalized(-1001, "abc") is True
    assert dedupe.mark_media_group_finalized(-1001, "abc") is False
    assert dedupe.is_media_group_finalized(-1001, "abc") is True
