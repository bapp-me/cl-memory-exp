"""Primary-agent interpretations authored after reading the selected original evidence."""
import ast
from common_opt import *

NOTES = {
48: "原生文件 GLM 输出存在 JSON 语法错误，不强行恢复其全部标签。三次定向 Grep、一次截断、88.48% 非正文返回字节是 D0；种子作用范围仍有契约竞争解释，不能归因于未检索。",
49: "GLM 将失败边界归为自测执行问题，未充分保留316评分遮蔽边界。隐藏测试在提交之后再次定义同名目标函数，评分成功不能强证明实际提交实现正确；原分数保留。",
53: "零主动记忆调用是事实，但启动时仍有逐条索引，不能称为 NoMemory 或推断本该检索。此题成功构成不强制搜索的控制。",
58: "三次调用包含一次空检索和30行定向读取；79.94%非正文返回字节不意味着三次调用都浪费。可检验响应编码，不能按结果改查询词。",
59: "GLM说自测全部通过，与11次PYTHON中2次非零返回直接矛盾。只有一次记忆读取；148245 tokens高成本关联长业务执行链，不能都归于检索。Axes/矩阵返回类型有契约张力。",
61: "题面明确 horizontally，而评分期望(4,11)。Grep命中与失败共存不足以证明负迁移；保留契约候选与原失败分数。",
62: "两次Grep成功且83.18%字节为非正文，支持格式开销假设。该GLM输出缺少要求的agentic_search字段，不能将未输出字段填成良好或零问题。",
67: "一次定向Grep即完成来源访问，88.69%非正文占比是格式事实；无额外读动作证据，不将高占比自动解释为无效读取。",
69: "未主动搜索且失败，但题面同时称列表元素为字典、又要求非DataFrame抛异常；实际抛TypeError。因此不能直接给检索失败标签，GLM原始语法错误也保留。",
72: "两次Grep均有打包截断、91.58%非正文字节，但任务成功。支持减少响应样板的可检验机会，不证明丢失了必要信息。",
84: "GLM主边界info_visible_but_adaptation过强：题面要求空列表填5个整数后算所有值，评分期望原6个数均值3.5；11个整数总和不可能为38.5，存在可定位契约矛盾。失败不直接作为记忆误用证据。",
88: "三次Grep都截断、91.44%非正文，第二个同文件查询有范围重复，另有一次业务工具错误。这是格式/查阅开销候选；评分成功仍受815弱测试边界限制。"
}


def main():
    d0 = read(ROOT / "records/d0-initial.json")["tasks"]
    originals = baseline_rows()
    assets = read(OBS / ".cache/agentcl-codeeval.json")
    records = []
    for index, judgment in NOTES.items():
        direct = next(r for r in d0 if r["method"] == "native_files" and r["index"] == index)
        original = next(r for r in originals if r["method"] == "native_files" and r["index"] == index)
        folder = REPO / original["source_path"]
        references = []
        for name in ("input-public.json", "evaluator.json", "pi-result.json", "tools.jsonl", "memory-access.jsonl"):
            path = folder / name
            references.append(dict(file=path.relative_to(REPO).as_posix(), sha256=sha(path) if path.exists() else None,
                                   state="present" if path.exists() else "not_applicable_no_memory_calls"))
        entry = dict(index=index, case_id=direct["case_id"], reviewer="primary Codex agent, not human",
            human_reviewed=False, level="D0 referenced facts with D1 interpretation", judgment=judgment,
            evidence_files=references, D0={k:direct[k] for k in ("result_status", "memory_calls", "python_calls", "non_content_response_fraction", "truncated_response_calls")},
            causal_claim=False, scoring_changed=False)
        if index == 49:
            names = [n.name for n in ast.walk(ast.parse(assets[index]["test_code"])) if isinstance(n, ast.FunctionDef)]
            assert "new_task_func" in names
            entry["confirmed_test_function_definitions"] = names
        if index == 59:
            assert direct["tool_metrics"]["observations_with_error_signals"] == 2 and direct["python_calls"] == 11
        if index == 84:
            assert "fill it with SIZE" in assets[index]["problem"] and "'mean': 3.5" in read(folder / "evaluator.json")["stderr"]
        records.append(entry)
    save(ROOT / "records/primary-adjudication-initial.json", dict(records=records, independent_targets=12,
        new_model_calls=0, raw_GLM_unchanged=True,
        scope="Evidence-led selected native-file cases; not a full human audit or true mechanism prevalence"))
    print("12 primary-agent adjudications saved; GLM outputs and scores unchanged.")


if __name__ == "__main__":
    main()
