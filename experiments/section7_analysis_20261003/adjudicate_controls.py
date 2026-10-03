"""Primary-agent review notes for the prospectively selected 36-case audit."""
from common import *
from audit_reviews import get_review

NOTES={
'c-e5bbe1e7955c':'NameError 后补 pandas import 的修复可直接支持。No Memory 不写入是实验设置，不归为 WRITE_ADMISSION 缺陷；参考 helper 名称不同、unittest=0 本身不构成评分错误。',
'c-c62b17b5315f':'两次 ACTION 后环境成功；没有 memory，不适用记忆机制归因。',
'c-8cd46b883209':'目标自身修复大小写/Unicode 自测后成功。明确 disabled 的情况下，不能声称无法区分禁用/检索未中/预算淘汰；撤回 PACKING_VISIBILITY 问题标签。unittest=0 与 assert checks=2 不矛盾。',
'c-4167b783e9b9':'ACTION-only 环境，不存在缺少 SUBMIT 的错误。实际记录是开门后 native submitted=false，模型自然语言自称完成而停止；保留未达到环境目标的执行现象，撤回要求提交产物的解释。',
'c-e9212842986b':'确认 PYTHON 与六次 SUBMIT 均 fetch failed，未落盘提交；记录为基础设施中断诊断，固定失败分数仍保留。不能把这一配对改善视为纯记忆能力收益。',
'c-51e533cabee8':'indices/columns 与形状差异有直接片段。源本身也失败，不能称源为正确知识。No Memory 的禁用不构成写入器失败。',
'c-9c232b29a84a':'成功与六次 ACTION 保留。检查合法动作是通用策略，不足以证明复用；成功检索记录不能计为 RETRIEVAL 失败。',
'c-eeeb4c3778c1':'源被包装淘汰而目标成功，支持源注入并非必要的观察。faithful 所指若是未注入原库内容，不能并入实际注入保真率；helper 签名和 unittest=0 的疑点不成立为已证评分缺陷。',
'c-a85368d7e6dc':'源因包装未注入、目标自行解码并成功可核对。无可见复用不等于 USE_TRANSFER 失败。仅 unittest=0 不能证明测评无效。',
'c-51e3e3bcbacb':'提交二元返回，测试三元解包，支持返回契约疑点。源被包装淘汰可由 D0 证实；其反事实收益未知。',
'c-734fad96e5a1':'是 ICL 唯一对应源仍注入的有效复杂目标；扁平随机序列与逐行重置是适配/契约候选。其他无关旧条目被丢弃不解释本题源缺失。',
'c-0a50f4a042ca':'相关源在包装后缺席有完整候选与丢弃证据，不必写成 may have been dropped。闰秒边界与分次 current-time 精确比较是竞争解释，不定为唯一根因。',
'c-390df9a13977':'源的异常/空表检查与多表拼接有一致适配代理，成功保留；不证明记忆导致成功。',
'c-7353cbe025cb':'源生成子步骤重合、目标自行修复空 DataFrame 列表，两者分开。0 unittest/3 checks 不是缺陷证据。',
'c-71bbec20c7c2':'15 次 ACTION 最终环境成功；记忆在 system 注入，不能因不在 target_prompt 就说未注入。重复探索动作不自动视为浪费。',
'c-ed35ca9868a2':'源为固定不可评分项，保持 unknown，不能推为错经验。目标 report 键名未明确是契约候选；生成合法源不是必须通过离线评分才允许的写入。',
'c-ba6a6f3401cc':'同 priority-16 复核：每矩阵一线与聚合一线为新聚合契约疑点，不能单靠失败认定负迁移。',
'c-bf2f5c0c489b':'同 priority-16：题面填空列表与断言忽略填充值存在文本张力；USE_TRANSFER 为 D1，不接受原输出标为 D0 的因果含义。',
'c-de5c81cf0017':'源 writer 无操作、注入为另一个题的两条泛化描述可核对；仅为写入/信息量现象，不证明对当前成功无用。',
'c-86d93e3d8c07':'源 permutations 与目标 product 的差异在独立任务中可见；源失败不能传递为目标失败。DataFrame 两条记忆来自另一源，不能据当前 bigram 题推定它们事实错误。',
'c-878409858bf3':'源无写入、泛化主题句不足以提供具体方法可核对。柱状图描述属于其他原始源，不可因为目标画另一种图就判为摘要错误；命中两个候选不证明召回了正确源。',
'c-9e52706a1570':'横向题意/纵向参考的张力跨方法存在。实际注入主题句与 DTM 无关，但无反事实不能认定干扰；保真字段混用源/注入语义，不采用其总体比例。',
'c-fe7ac26b48af':'检查保留标题字面要求与实际提交/失败日志；若仅是未说明的精确标题失配，归契约候选，泛化主题注入不自动构成错误记忆。',
'c-79d2ecf67c8c':'元组第一项 processed frame 与隐藏统计 frame 的约定有歧义。通用 DataFrame 文本来自其他源，不能以当前源的具体 tuple 内容缺席就说摘要失真。',
'c-b45a0397d509':'两次 zip_longest 相关自测错误与修复可见；工作流缺少单元素点规则仅为片段内容观察。不能说修复因果上来自自身而非记忆，也不能用通用测试习惯证明复用。',
'c-3b95e07cde57':'单样本到多样本的随机流程部分可用；泛化 seeding/verification 同形不等于因果采用。参考均值聚合与当前实现不同，检查不足只作候选。',
'c-1ff096c10a3c':'go-to 目标在两个 ACTION 后成功，locked 门仍可被接近。参数化工作流与导航同形可作弱代理，不能宣称跳过扫描或确定采用。',
'c-ba473882226a':'源 ASCII 字母限制未出现在泛化工作流，目标使用含数字池；保留表示粒度/契约两种解释，不能断定压缩造成字符池选择。',
'c-57e3cf36443e':'返回 (fig,ax) 与测试 Axes.collections 的接口失配可核对；题面未给返回类型，只作契约候选。泛化绘图风格不证明记忆作用。',
'c-59d7ad73a999':'目标 list-of-dicts 与测试 dict-of-lists 的输入形状张力需单列；未定义 helper 的额外断言未经完整组合源码核验，不采用。',
'c-63e12e5e3925':'源具体 bdate_range 条目被预算淘汰；目标自己探查 holidays/freq 后成功可见，但独立于 memory 的因果表述不能由一次轨迹成立。target_update 不用于解释此前目标行为。',
'c-1dec1cd892ec':'注入 ASCII/Unicode 边界与提交字符类重合，另有自测 oracle 修复。部分同源条目被淘汰、另一条仍在，应按条目和来源交叉看，不能简单当源完全丢弃。',
'c-850ed5952c00':'源特定几何条目没注入，大量其他条目带来字节开销；faithful 是对源库/源写入的描述，不能当实际注入保真。成功不证明该开销有益或无益。',
'c-ec2536e84a1f':'ValueError/TypeError 与 appropriate exception 的歧义可核对；显式引用 err IDs 是可见代理，不证明该记忆决定异常类型。未见无关/过期/跨项目干扰，撤回 SCOPE_INTERFERENCE 的强定位。',
'c-fca18bd05bba':'核对源随机字符串模式、实际种子/字符池及隐藏精确计数；优先保留 seed 重设契约与条件适配竞争解释，不单独认定负迁移。',
'c-a1280cc384b7':'输入容器张力与源条目包装丢弃分开。显式引用 err ID 支持可见引用，不等于记忆造成最终 ddof 选择；原解释的“明显影响”应降级。',
}


def main():
    m=read(ROOT/'records/manifest.json');lookup={x['case_id']:x for x in m['cases']};out=[]
    assert set(NOTES)==set(m['audit_sample_ids'])
    for cid in m['audit_sample_ids']:
        case=lookup[cid];review=get_review(case)
        if review is None:raise RuntimeError('Awaiting review for '+cid)
        packet=read(ROOT/'packets'/f'{cid}.json')
        out.append({'case_id':cid,'method':case['method'],'benchmark':case['benchmark'],'task_id':case['task_id'],
                    'original_primary':review.get('primary_hypothesis'),'note':NOTES[cid],
                    'packet_sha256':case['packet_sha256'],'evidence_sections_consulted':[s['id'] for s in packet['evidence'] if s['id'] in ['target_prompt','target_visible','target_submission','offline_target_evaluation','source_prompt','source_visible','source_update_operations','retrieval','mechanical']],
                    'reviewer':'primary Codex agent','human_reviewed':False,'causal_claim':False,'raw_output_changed':False})
    save(ROOT/'records/control-36-adjudication.json',{'selection':'Preregistered before labels, 3 success and 3 failure per method; 36 total',
         'records':out,'human_reviewed':False,'count':36,'purpose':'Find annotation and interpretation errors; not an unbiased estimate of annotator accuracy against human truth.'})


if __name__=='__main__':main()
