"""Generic native file access changes. No target IDs, gold, or review data are imported."""
import copy
import json

from common_opt import ROOT, size
from native_memory import NativeSession


def compact_result(original):
    """Keep every returned content character and its actionable file/range locator."""
    result = {k: copy.deepcopy(v) for k, v in original.items()
              if k not in ("method", "library_hash", "corpus_hash", "evidence_status", "dropped_items_count")}
    keep = {"path", "start_line", "end_line", "start_char", "end_char", "content",
            "next_line", "next_start_char", "truncated", "match_kind"}
    result["items"] = [{k: v for k, v in item.items() if k in keep} for item in original.get("items", [])]
    return result


class CandidateSession(NativeSession):
    def __init__(self, corpus, variant="compact"):
        if variant != "compact":
            raise ValueError("Candidate not registered")
        self.variant = variant
        super().__init__(corpus, "native_files")

    def call(self, name, args, tool_call_id):
        # The inherited backend, query parameters, rank-free ordering and packing are unchanged.
        destination = self.out
        self.out = None
        try:
            original = super().call(name, args, tool_call_id)
        finally:
            self.out = destination
        compact = compact_result(original)
        assert size(compact) <= size(original)
        assert [i["content"] for i in compact["items"]] == [i["content"] for i in original.get("items", [])]
        if not original.get("error"):
            self.used_bytes -= size(original) - size(compact)
        record = self.records[-1]
        record.update(full_result=original, result=compact, variant=self.variant,
                      full_backend_response_bytes=size(original), returned_utf8_bytes=size(compact),
                      cumulative_memory_bytes_including_startup=self.used_bytes)
        from common_opt import digest
        record["result_hash"] = digest(compact)
        if destination:
            with (destination / "memory-access.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        return compact
