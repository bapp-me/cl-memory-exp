"""Deterministic synthetic tasks. Public environments and private checks are separate.

No downloaded benchmark score is claimed. Data values come from the formulas here.
All regime differences are discoverable through files or tool responses.
"""
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


CATALOG = [
    ('01_units', 'SQL 金额单位', '旧导出 price 为美分，发现换算和状态筛选', '同版本新订单', '新导出 price 已为美元', 'export.json 的 amount_unit 与样本值', 'SQL 汇总金额及最终数值'),
    ('02_coverage', 'SQL 非空覆盖', '低价子集 display_usd 与完整 price_minor 等价', '另一低价上限仍在覆盖内', '全量目标包含 display_usd 缺失的高价行', 'schema、非空计数及缺失行', '独立 price_minor 汇总'),
    ('03_join', 'SQL 关联基数', '客户标签表在源快照一客户一行', '同样基数的新订单', '目标快照一客户多条匹配标签，join 会重复金额', '复合主键、原始行及计数', '按客户存在匹配标签汇总订单'),
    ('04_pagination', 'API 分页协议', 'page 分页和终止条件', 'v1 新账本', 'v2 cursor 分页，page 参数忽略', '/info、api.json、响应 next_cursor', '完整账本金额和可见记录 ID'),
    ('05_update', 'API 更新语义', 'v1 PATCH 部分更新保留其余字段', 'v1 新用户', 'v2 PUT 替换，缺失字段重置默认值', '/info、api.json、405、GET 返回', '落地 profile 所有字段'),
    ('06_build', '代码构建工作区', '单包 test 运行目标包', '同样布局新源码', 'monorepo 根 test 只测 core，必须指定 ui', 'package.json、packages/ui/package.json、命令输出', '模拟测试引擎真实执行目标包检查并记录套件'),
    ('07_config', '配置优先级', 'settings.json 为实际配置入口', '无额外覆盖的新实例', '运行环境 APP_PORT 覆盖文件', 'deployment.json、settings.json、运行时 config 输出', '更新后实际有效端口与既有主机名'),
    ('08_csv', '文件编码与表结构', 'UTF-8、逗号、一行表头', '同导出器新账目', 'UTF-16、制表符、两行前言', 'export.json、前缀字节、解码/解析结果', '实际 csv 模块解析后的分类金额'),
    ('09_timezone', '时间窗口与夏令时', 'UTC 日界半开区间', 'UTC 另一日期', '纽约夏令时结束日为 25 小时', 'reporting.json 给定时区及两端 UTC offset、events', '固定 UTC 事件按明确日界计数'),
    ('10_preference', '项目偏好覆盖', '团队默认英语、compact、2 位小数', '没有项目覆盖的另一报告', '当前项目新偏好覆盖团队默认', 'preferences/default.json、project.json 的优先级与日期', '保存的报告语言、布局、精度与数值'),
]


def build(group, stage):
    i = 'abcd'.index(stage)
    changed = stage in 'cd'
    files = {}
    env = {'files': files, 'kind': group, 'data': {}, 'tools': ['list_files', 'read_file']}
    check = {}
    n = i + 1
    if group == '01_units':
        scale = 1 if changed else 100
        rows = [(j, (j * 17 + n * 3) * scale, 'paid' if j % 3 else 'cancelled') for j in range(1, 10)]
        files['export.json'] = {'dataset': 'orders', 'export_version': 2 if changed else 1, 'amount_unit': 'USD' if changed else 'USD cents'}
        env['data']['sql'] = {'schema': ['CREATE TABLE orders(id INTEGER PRIMARY KEY,price REAL,status TEXT)'], 'rows': {'orders': rows}}
        env['tools'] += ['sql']
        env['prompt'] = 'Compute the total dollar amount of paid orders whose individual dollar price is greater than 50. Return JSON {"answer": number}.'
        check['answer'] = sum(p / scale for _, p, s in rows if s == 'paid' and p / scale > 50)
    elif group == '02_coverage':
        rows = [(j, (j * 1900 + n * 137), (j * 1900 + n * 137) / 100 if j <= 5 else None) for j in range(1, 10)]
        files['catalog.md'] = 'Catalog schema: price_minor is the source price in USD cents. display_usd is a nullable display field in USD. Inspect SQLite schema and data through sql.'
        env['data']['sql'] = {'schema': ['CREATE TABLE products(id INTEGER PRIMARY KEY,price_minor INTEGER,display_usd REAL)'], 'rows': {'products': rows}}
        env['tools'] += ['sql']
        cap = [60, 80, None, None][i]
        env['prompt'] = ('Compute the mean dollar price of ' + (f'products priced below {cap} dollars.' if cap else 'all listed products.') + ' Return JSON {"answer": number}.')
        vals = [r[1] / 100 for r in rows if cap is None or r[1] / 100 < cap]
        check['answer'] = sum(vals) / len(vals)
    elif group == '03_join':
        orders = [(j, (j % 4) + 1, j * 13 + n) for j in range(1, 10)]
        tags = [(1, 'vip-main'), (2, 'vip-main'), (3, 'standard'), (4, 'standard')]
        if changed:
            tags += [(1, 'vip-renewal'), (2, 'vip-event')]
        env['data']['sql'] = {'schema': ['CREATE TABLE orders(id INTEGER PRIMARY KEY,customer_id INTEGER,amount_usd REAL)', 'CREATE TABLE customer_tags(customer_id INTEGER,tag TEXT,PRIMARY KEY(customer_id,tag))'], 'rows': {'orders': orders, 'customer_tags': tags}}
        files['schema.md'] = 'Order amount is USD. customer_tags lists customer memberships. Tags starting with vip- qualify for the VIP segment. Schema constraints and rows can be inspected with sql.'
        env['tools'] += ['sql']
        env['prompt'] = 'What is the total order revenue from customers who have at least one vip- membership tag? Each order contributes its amount once. Return JSON {"answer": number}.'
        check['answer'] = sum(r[2] for r in orders if r[1] in (1, 2))
    elif group == '04_pagination':
        items = [{'id': f'item-{n}-{j}', 'amount': j * 7 + n, 'active': j % 3 != 0} for j in range(1, 9)]
        env['data'].update(items=items, version=2 if changed else 1)
        files['api.json'] = {'service': 'ledger', 'version': env['data']['version'], 'endpoints': {'/info': 'GET service metadata', '/items': 'GET limit (max 3); cursor token and next_cursor, null ends the list. page is ignored.' if changed else 'GET page (1 based), limit (max 3); next_page null ends the list.'}}
        env['tools'] += ['api']
        env['prompt'] = 'Using the local ledger API, compute the sum of amounts for all active items in the current ledger. Return JSON {"answer": number}.'
        check['answer'] = sum(r['amount'] for r in items if r['active'])
    elif group == '05_update':
        env['data'].update(version=2 if changed else 1, profile={'timezone': 'UTC', 'email': f'person{n}@example.test', 'digest': True})
        files['api.json'] = {'service': 'profiles', 'version': env['data']['version'], '/info': 'GET metadata', '/profile': 'GET current profile. PUT replaces profile; missing email defaults to null, digest to false, timezone to UTC. PATCH unsupported.' if changed else 'GET current profile. PATCH changes specified fields only; omitted fields retained. PUT unsupported.'}
        env['tools'] += ['api']
        env['prompt'] = 'Update the current profile timezone to Asia/Tokyo while preserving the current email and digest setting. Verify the saved profile. Return JSON {"answer": "updated"}.'
        check.update(answer='updated', state={'profile': {**env['data']['profile'], 'timezone': 'Asia/Tokyo'}})
    elif group == '06_build':
        files['package.json'] = {'name': 'workspace' if changed else 'ui', 'scripts': {'test': 'test-engine core' if changed else 'test-engine ui'}, 'packageManager': 'pnpm@10'}
        files['packages/ui/package.json'] = {'name': 'ui', 'scripts': {'test': 'test-engine ui'}}
        files['packages/ui/source.json'] = {'base': n * 5, 'increment': 4, 'expected': n * 5 + 4}
        files['README.md'] = 'Local mock build engine accepts pnpm test and pnpm --filter <package> test, resolving scripts from package.json. It checks the selected package source fixture and reports the actual executed suites. No network or installation is needed.'
        env['data'].update(tested=[])
        env['tools'] += ['build']
        env['prompt'] = 'Run the tests for the ui package and report the actual ui test result. Return JSON {"answer": "passed"} when ui has passed.'
        check.update(answer='passed', state={'tested_contains': 'ui'})
    elif group == '07_config':
        files['settings.json'] = {'port': 8000 + n, 'host': '127.0.0.1'}
        files['deployment.json'] = {'environment': {'APP_PORT': str(9000 + n)} if changed else {}, 'config_file': 'settings.json'}
        files['README.md'] = 'Application configuration: load settings.json; deployment.json environment.APP_PORT, if present, overrides the file port. The config tool displays effective runtime settings. write_file accepts JSON text and updates local files.'
        env['tools'] += ['write_file', 'config']
        env['prompt'] = f'Set the effective application port to {8100 + n}, retaining its host. Verify runtime configuration and return JSON {{"answer": {8100 + n}}}.'
        check.update(answer=8100 + n, state={'config': {'port': 8100 + n, 'host': '127.0.0.1'}})
    elif group == '08_csv':
        rows = [('sales' if j % 2 else 'refund', j * 9 + n) for j in range(1, 9)]
        encoding, delimiter, skip = ('utf-16', '\t', 2) if changed else ('utf-8', ',', 0)
        stream = io.StringIO(newline='')
        if skip:
            stream.write('Export from ledger suite\nAmounts are in USD\n')
        writer = csv.writer(stream, delimiter=delimiter, lineterminator='\n')
        writer.writerow(['category', 'amount'])
        writer.writerows(rows)
        env['data']['blobs'] = {'ledger.csv': stream.getvalue().encode(encoding).hex()}
        files['export.json'] = {'encoding': encoding, 'delimiter': delimiter, 'preamble_lines': skip, 'file': 'ledger.csv'}
        env['tools'] += ['parse_csv']
        env['prompt'] = 'Compute the total amount of sales rows in the ledger.csv export. Return JSON {"answer": number}.'
        check['answer'] = sum(v for k, v in rows if k == 'sales')
    elif group == '09_timezone':
        day = '2026-11-01' if changed else f'2026-10-{10 + n:02d}'
        start = f'{day}T04:00:00+00:00' if changed else f'{day}T00:00:00+00:00'
        end = '2026-11-02T05:00:00+00:00' if changed else f'2026-10-{11 + n:02d}T00:00:00+00:00'
        lo, hi = (int(datetime.fromisoformat(x).timestamp()) for x in (start, end))
        offsets = [-3600, 0, 3600, 7200, 82800, 84600, 86400, 88200, 90000, 93600]
        if stage == 'd':
            offsets += [18000, 27000]
        rows = [(j, lo + sec + (60 if stage == 'd' else 0)) for j, sec in enumerate(offsets)]
        files['reporting.json'] = {'timezone': 'America/New_York' if changed else 'UTC', 'date': day, 'midnight_offset': '-04:00' if changed else '+00:00', 'next_midnight_offset': '-05:00' if changed else '+00:00', 'storage': 'UTC epoch seconds', 'window': 'inclusive start, exclusive next midnight'}
        env['data']['sql'] = {'schema': ['CREATE TABLE events(id INTEGER PRIMARY KEY,ts INTEGER)'], 'rows': {'events': rows}}
        env['tools'] += ['sql']
        env['prompt'] = f'Count events on reporting calendar day {day}, using the configured reporting timezone. Return JSON {{"answer": number}}.'
        check['answer'] = sum(lo <= ts < hi for _, ts in rows)
    elif group == '10_preference':
        files['preferences/default.json'] = {'updated': '2026-08-01', 'language': 'en', 'layout': 'compact', 'decimals': 2}
        files['preferences/project.json'] = {'updated': '2026-10-02', 'language': 'zh', 'layout': 'detail', 'decimals': 0} if changed else {}
        files['README.md'] = 'Report configuration: project preferences override team defaults for keys present. Missing project keys inherit defaults. render_report saves the numeric report specification with language, layout, decimals, value. Read figures.json for current value.'
        files['figures.json'] = {'value': 127.456 + n * 4}
        env['tools'] += ['render_report']
        env['prompt'] = 'Save the current numeric report using the applicable preferences for this project. Return JSON {"answer": "saved"}.'
        pref = {**files['preferences/default.json'], **files['preferences/project.json']}
        check.update(answer='saved', state={'report': {k: pref[k] for k in ('language', 'layout', 'decimals')} | {'value': round(files['figures.json']['value'], pref['decimals'])}})
    else:
        raise ValueError(group)
    env['files'] = {k: json.dumps(v, ensure_ascii=False, indent=2) if not isinstance(v, str) else v for k, v in files.items()}
    return env, check


def main():
    inventory = []
    for group, title, experience, transfer, boundary, evidence, quality in CATALOG:
        record = dict(zip(('group', 'title', 'a_experience', 'b_reuse', 'c_boundary', 'visible_evidence', 'quality'), (group, title, experience, transfer, boundary, evidence, quality)))
        record.update(source='synthetic, deterministic make_tasks.py; inspired by general environment conventions, not a public benchmark score', d='new independent values under the c regime', stages={})
        for stage in 'abcd':
            env, check = build(group, stage)
            dump(ROOT / 'fixtures' / group / f'{stage}.json', env)
            dump(ROOT / 'checks' / group / f'{stage}.json', check)
            record['stages'][stage] = {'sha256': hashlib.sha256(json.dumps(env, sort_keys=True).encode()).hexdigest()}
        inventory.append(record)
    dump(ROOT / 'task-catalog.json', inventory)
    print(f'Generated {len(inventory)} groups, 40 tasks; evaluation checks are not exposed by task tools.')


if __name__ == '__main__':
    main()
