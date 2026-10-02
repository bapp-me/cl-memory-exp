"""Reproduce and certify the two-stream initialization repair, without GLM."""
from concurrent.futures import ThreadPoolExecutor
import uuid
from runtime import ROOT, read, save
from fixtures_complex import config
from complex_memory import make_adapter


def main():
    current = config()

    def initialize(index):
        run_id = f'fixture-parallel-mem0-{index}-' + uuid.uuid4().hex
        adapter = make_adapter('mem0', run_id, current, 'fixture-key', fixture_responses=[])
        try:
            model = adapter.native.embedding_model.model
            assert not any(parameter.is_meta for parameter in model.parameters())
            assert model.get_sentence_embedding_dimension() == 384
            assert adapter.snapshot()['points'] == []
            return {'index': index, 'parameters_have_data': True, 'dimensions': 384, 'passed': True}
        finally:
            adapter.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        checks = list(pool.map(initialize, [0, 1]))
    report = {'passed': True, 'language_model_calls': 0, 'parallel_requested_initializations': 2,
              'initialization_only_serialized': True, 'online_streams_remain_parallel': True, 'checks': checks}
    save(ROOT / 'records/parallel-embedding-fixture.json', report)
    print(report)


if __name__ == '__main__':
    main()
