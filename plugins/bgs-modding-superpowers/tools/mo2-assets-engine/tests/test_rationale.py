from mo2_assets_engine.rationale import (
    BucketRationale,
    rationale_for_bucket,
)
from mo2_assets_engine.types import ConflictBucket


def test_each_bucket_has_a_rationale() -> None:
    for bucket in ConflictBucket:
        rationale = rationale_for_bucket(bucket)
        assert isinstance(rationale, BucketRationale)
        assert rationale.short
        assert rationale.kb_record_ids


def test_loose_overwrites_archive_cites_loose_over_archive_record() -> None:
    rationale = rationale_for_bucket(ConflictBucket.LOOSE_OVERWRITES_ARCHIVE)
    assert "archive-precedence.loose-over-archive.v1" in rationale.kb_record_ids


def test_archive_overwrites_archive_cites_plugin_order_record() -> None:
    rationale = rationale_for_bucket(ConflictBucket.ARCHIVE_OVERWRITES_ARCHIVE)
    assert "archive-precedence.plugin-order-is-not-asset-order.v1" in rationale.kb_record_ids


def test_no_conflict_has_empty_short_but_still_yields_kb_id() -> None:
    rationale = rationale_for_bucket(ConflictBucket.NO_CONFLICT)
    assert rationale.short  # not empty — explains "no overlap"
