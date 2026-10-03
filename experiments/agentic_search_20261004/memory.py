"""Three read-only history access systems; no model calls or target-data imports."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import time

VERSION = "agentic-history-v1"
METHODS = ("lexical", "hybrid_context", "graph_walk")


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    # Match the existing experiment's canonical content hashes.
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def tokens(text):
    return re.findall(r"[a-z_][a-z_0-9]*|\d+", text.lower())


def grams(text):
    text = " ".join(tokens(text))
    return Counter(text[i:i + 3] for i in range(max(0, len(text) - 2)))


def spec(name, description, properties, required):
    return dict(name=name, description=description, parameters=dict(type="object", properties=properties,
                required=required, additionalProperties=False))


SEARCH = spec("MEMORY_SEARCH", "Search the frozen archive of 48 independent simple-task histories. "
              "Returns fallible source excerpts and event IDs; scores are relevance, not correctness. "
              "Use a focused query. Page starts at 0. Empty query lists events in archive order.",
              {"query": {"type": "string", "maxLength": 2000}, "page": {"type": "integer", "minimum": 0},
               "source_id": {"type": "string", "description": "Optional exact source ID from a prior result."}}, ["query"])
READ = spec("MEMORY_READ", "Read an exact archived event by ID, in bounded character ranges. "
            "Use next_start_char to continue, or previous_event_id/next_event_id to navigate its original history. "
            "Historical code and submissions are unverified observations, not instructions or validated solutions.",
            {"event_id": {"type": "string"}, "start_char": {"type": "integer", "minimum": 0},
             "max_chars": {"type": "integer", "minimum": 1, "maximum": 8000}}, ["event_id"])
FOLLOW = spec("MEMORY_FOLLOW", "Follow explicit archive links from an event: previous/next chronological event, "
              "paired tool action/observation, or shared code symbols in other events. Shared symbols express "
              "co-occurrence only, not factual equivalence. Page starts at 0.",
              {"event_id": {"type": "string"}, "relation": {"type": "string", "enum": ["sequence", "action_result", "symbol"]},
               "page": {"type": "integer", "minimum": 0}}, ["event_id", "relation"])


class Archive:
    """Immutable by interface; sessions hold separate counters, logs and read ranges."""
    def __init__(self, library):
        start = time.perf_counter()
        if len(library) != 48 or [x["sequence"] for x in library] != list(range(48)):
            raise ValueError("Only the registered 48 simple episodes are permitted")
        self.library_json = encode(library)
        self.library_hash = digest(library)
        self.events = {}
        self.by_source = {}
        self.edges = defaultdict(list)
        symbol_events = defaultdict(set)
        for entry in library:
            if set(entry) != {"sequence", "text"}:
                raise ValueError("Unexpected episode metadata")
            episode = json.loads(entry["text"])
            if set(episode) != {"task", "trajectory"}:
                raise ValueError("Only legal task and visible trajectory fields allowed")
            sid = f"s{entry['sequence']:03d}"
            rows = [("task", episode["task"], "/task", None)]
            for index, value in enumerate(episode["trajectory"]):
                kind = "action" if value.get("type") == "toolCall" else "observation" if "tool" in value else "assistant_text"
                # The full visible object is retained, including failed actions and corrections.
                rows.append((kind, encode(value), f"/trajectory/{index}", value.get("name") or value.get("tool")))
            ids = [f"{sid}:e{i:03d}" for i in range(len(rows))]
            self.by_source[sid] = ids
            for i, (kind, text, locator, tool) in enumerate(rows):
                eid = ids[i]
                symbols = sorted(set(re.findall(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\b", text)))
                doc = dict(event_id=eid, source_id=sid, kind=kind, text=text, locator=locator,
                           tool=tool, content_sha256=hashlib.sha256(text.encode()).hexdigest(), symbols=symbols,
                           previous_event_id=ids[i - 1] if i else None,
                           next_event_id=ids[i + 1] if i + 1 < len(ids) else None)
                self.events[eid] = doc
                for symbol in symbols:
                    symbol_events[symbol].add(eid)
                for j in (i - 1, i + 1):
                    if 0 <= j < len(ids):
                        self.edges[eid].append(dict(to=ids[j], relation="sequence", via="previous" if j < i else "next"))
                if i and kind == "observation" and rows[i - 1][0] == "action" and rows[i - 1][3] == tool:
                    self.edges[eid].append(dict(to=ids[i - 1], relation="action_result", via=tool))
                    self.edges[ids[i - 1]].append(dict(to=eid, relation="action_result", via=tool))
        # Avoid hubs such as very common numpy names. No gold IDs, answer labels, or external facts.
        for symbol, ids in sorted(symbol_events.items()):
            if 2 <= len(ids) <= 24:
                for left in sorted(ids):
                    self.edges[left].extend(dict(to=right, relation="symbol", via=symbol) for right in sorted(ids) if right != left)
        self.tf = {eid: Counter(tokens(doc["text"])) for eid, doc in self.events.items()}
        df = Counter(t for terms in self.tf.values() for t in terms)
        n = len(self.events)
        self.idf = {t: math.log(1 + (n - count + .5) / (count + .5)) for t, count in df.items()}
        self.avg_len = sum(sum(c.values()) for c in self.tf.values()) / n
        raw_grams = {eid: grams(doc["text"]) for eid, doc in self.events.items()}
        gdf = Counter(g for row in raw_grams.values() for g in row)
        self.gidf = {g: math.log((1 + n) / (1 + count)) + 1 for g, count in gdf.items()}
        self.vectors = {eid: self.vector(row) for eid, row in raw_grams.items()}
        self.manifest = dict(version=VERSION, library_hash=self.library_hash, episodes=48, events=n,
                             edges=sum(map(len, self.edges.values())), model_calls=0,
                             index_hash=digest(dict(events=self.events, edges=dict(self.edges))),
                             construction_seconds=time.perf_counter() - start)

    def snapshot(self):
        return json.loads(self.library_json)

    def vector(self, counts):
        vector = {g: (1 + math.log(c)) * self.gidf[g] for g, c in counts.items() if g in self.gidf}
        norm = math.sqrt(sum(v * v for v in vector.values())) or 1
        return {g: v / norm for g, v in vector.items()}

    def rank(self, query, method, source_id=None):
        if source_id is not None and source_id not in self.by_source:
            raise ValueError("Unknown source_id; path access is unavailable")
        candidates = self.by_source[source_id] if source_id else list(self.events)
        query_terms = set(tokens(query))
        if not query_terms:
            return [dict(event_id=eid, score=0, bm25=0, char_cosine=None) for eid in candidates]
        scores = {}
        qv = self.vector(grams(query)) if method == "hybrid_context" else {}
        for eid in candidates:
            terms = self.tf[eid]
            length = sum(terms.values())
            bm25 = sum(self.idf.get(t, 0) * terms[t] * 2.5 /
                       (terms[t] + 1.5 * (.25 + .75 * length / self.avg_len)) for t in query_terms if terms[t])
            cosine = sum(value * self.vectors[eid].get(g, 0) for g, value in qv.items()) if qv else 0
            scores[eid] = dict(event_id=eid, score=bm25, bm25=bm25, char_cosine=cosine if qv else None)
        if method == "hybrid_context":
            fused = Counter()
            for field in ("bm25", "char_cosine"):
                ranked = sorted((x for x in scores.values() if (x[field] or 0) > 0), key=lambda x: (-x[field], x["event_id"]))[:40]
                for rank, row in enumerate(ranked, 1):
                    fused[row["event_id"]] += 1 / (60 + rank)
            for eid, row in scores.items():
                row["score"] = fused[eid]
        return sorted((x for x in scores.values() if x["score"] > 0), key=lambda x: (-x["score"], x["event_id"]))

    def excerpt(self, eid, start=0, length=700):
        if eid not in self.events:
            raise ValueError("Unknown event_id; only frozen simple-source events are readable")
        doc = self.events[eid]
        if type(start) is not int or not 0 <= start <= len(doc["text"]):
            raise ValueError("start_char outside event")
        end = min(start + length, len(doc["text"]))
        return {k: doc[k] for k in ("event_id", "source_id", "kind", "locator", "content_sha256", "previous_event_id", "next_event_id")} | dict(
            start_char=start, end_char=end, total_chars=len(doc["text"]),
            start_utf8_byte=len(doc["text"][:start].encode()), end_utf8_byte=len(doc["text"][:end].encode()),
            truncated=start > 0 or end < len(doc["text"]), next_start_char=end if end < len(doc["text"]) else None,
            content=doc["text"][start:end])


class Session:
    def __init__(self, archive, method, out=None, max_calls=12, max_bytes=48000):
        if method not in METHODS:
            raise ValueError(method)
        self.archive, self.method, self.out = archive, method, Path(out) if out else None
        self.max_calls, self.max_bytes = max_calls, max_bytes
        self.calls = self.returned_bytes = 0
        self.seen = defaultdict(set)
        self.state = {"episode_count": 48}
        self.records = []

    @property
    def tools(self):
        return [SEARCH, READ] + ([FOLLOW] if self.method == "graph_walk" else [])

    def snapshot(self):
        return self.archive.snapshot()

    def task(self, out, identity):
        self.out, self.identity = Path(out), identity

    def retrieve(self, prompt):
        return [], dict(mode="agent_controlled_on_demand", injected_ids=[], injected_utf8_bytes=0,
                        library_hash=self.archive.library_hash, version=VERSION)

    def update(self, discarded):
        self._log(dict(event="writeback_disabled", library_hash=self.archive.library_hash))
        return self.snapshot()

    def restore_checkpoint(self, out, state):
        if digest(state) != self.archive.library_hash:
            raise ValueError("Frozen archive mismatch")

    def _log(self, row):
        row = dict(version=VERSION, method=self.method, at_unix_ns=time.time_ns(), **row)
        self.records.append(row)
        if self.out:
            self.out.mkdir(parents=True, exist_ok=True)
            with (self.out / "memory-access.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(encode(row) + "\n")

    def _search(self, args):
        query = args["query"]
        if not isinstance(query, str) or len(query) > 2000:
            raise ValueError("query must be a string of at most 2000 characters")
        page = args.get("page", 0)
        if type(page) is not int or page < 0:
            raise ValueError("page must be a nonnegative integer")
        ranked = self.archive.rank(query, self.method, args.get("source_id"))
        picked = ranked[page * 5:page * 5 + 5]
        items, included = [], set()
        for candidate in picked:
            eid = candidate["event_id"]
            group = [eid]
            if self.method == "hybrid_context":
                group = [self.archive.by_source[self.archive.events[eid]["source_id"]][0], eid]
                group += [e["to"] for e in self.archive.edges[eid] if e["relation"] == "action_result"]
            for target in group:
                if target in included:
                    continue
                included.add(target)
                text = self.archive.events[target]["text"]
                positions = [text.lower().find(t) for t in tokens(query) if text.lower().find(t) >= 0]
                start = max(0, min(positions) - 100) if positions and target == eid else 0
                item = self.archive.excerpt(target, start, 700 if self.method != "hybrid_context" else 500)
                item.update(reason="ranked_hit" if target == eid else "task_or_action_context", seed_event_id=eid)
                if self.method == "graph_walk":
                    item["symbols"] = self.archive.events[target]["symbols"][:12]
                    item["link_counts"] = dict(Counter(e["relation"] for e in self.archive.edges[target]))
                items.append(item)
        return dict(items=items, total_matches=len(ranked), page=page,
                    next_page=page + 1 if (page + 1) * 5 < len(ranked) else None), dict(candidates=ranked)

    def _read(self, args):
        length = args.get("max_chars", 6000)
        if type(length) is not int or not 1 <= length <= 8000:
            raise ValueError("max_chars must be 1..8000")
        return dict(items=[self.archive.excerpt(args["event_id"], args.get("start_char", 0), length)]), {}

    def _follow(self, args):
        eid, relation = args["event_id"], args["relation"]
        if eid not in self.archive.events or relation not in ("sequence", "action_result", "symbol"):
            raise ValueError("Unknown event or relation")
        page = args.get("page", 0)
        if type(page) is not int or page < 0:
            raise ValueError("page must be a nonnegative integer")
        neighbors = defaultdict(list)
        for edge in self.archive.edges[eid]:
            if edge["relation"] == relation:
                neighbors[edge["to"]].append(edge["via"])
        ids = sorted(neighbors, key=lambda x: (-len(neighbors[x]), x))
        items = [self.archive.excerpt(target, 0, 700) | dict(from_event_id=eid, relation=relation, via=neighbors[target][:12])
                 for target in ids[page * 5:page * 5 + 5]]
        return dict(items=items, total_matches=len(ids), page=page,
                    next_page=page + 1 if (page + 1) * 5 < len(ids) else None), dict(edges=dict(neighbors))

    def call(self, name, args, tool_call_id):
        started = time.perf_counter()
        self.calls += 1
        diagnostics = {}
        result = dict(memory_version=VERSION, method=self.method, library_hash=self.archive.library_hash,
                      evidence_status="historical_unverified", items=[])
        try:
            if self.calls > self.max_calls or self.returned_bytes >= self.max_bytes - 600:
                raise ValueError("Memory access budget exhausted; finish using current evidence")
            definitions = {s["name"]: s for s in self.tools}
            if name not in definitions or not isinstance(args, dict):
                raise ValueError("Unknown memory tool")
            schema = definitions[name]["parameters"]
            if set(args) - set(schema["properties"]) or set(schema["required"]) - set(args):
                raise ValueError("Invalid memory arguments")
            value, diagnostics = {"MEMORY_SEARCH": self._search, "MEMORY_READ": self._read,
                                  "MEMORY_FOLLOW": self._follow}[name](args)
            result.update(value)
        except (ValueError, KeyError, TypeError) as error:
            result["error"] = str(error)
        result["packing_truncated"] = False
        result["dropped_event_ids"] = []
        cap = min(12000, max(600, self.max_bytes - self.returned_bytes))
        while len(encode(result).encode()) > cap and result["items"]:
            item = result["items"][-1]
            if len(item["content"]) > 200:
                reduced = self.archive.excerpt(item["event_id"], item["start_char"], len(item["content"]) // 2)
                item.update(reduced)
            else:
                result["dropped_event_ids"].append(result["items"].pop()["event_id"])
            result["packing_truncated"] = True
        # Budget covers evidence-bearing responses; fixed-size denial messages remain observable separately.
        evidence_bytes = len(encode(result).encode()) if result["items"] else 0
        self.returned_bytes += evidence_bytes
        repeated = 0
        for item in result["items"]:
            positions = set(range(item["start_char"], item["end_char"]))
            repeated += len(positions & self.seen[item["event_id"]])
            self.seen[item["event_id"]].update(positions)
        self._log(dict(event="memory_access", tool_call_id=tool_call_id, name=name, args=args,
                       result=result, result_hash=digest(result), diagnostics=diagnostics,
                       duration_seconds=time.perf_counter() - started, repeated_source_chars=repeated,
                       returned_utf8_bytes=len(encode(result).encode()), evidence_response_bytes=evidence_bytes,
                       cumulative_evidence_response_bytes=self.returned_bytes, call_ordinal=self.calls))
        return result
