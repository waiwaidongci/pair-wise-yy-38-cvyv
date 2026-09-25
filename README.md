# 水库防汛调度与操作确认

根据库位、入库流量、下游警戒和施工限制生成复核授权的泄洪指令。

## 模块结构

- `app.py`：参数解析、依赖组装和HTTP服务启动。
- `src/domain.py`：数据结构、错误、状态和基础校验。
- `src/rules.py`：状态机、角色矩阵、优先级、期限和关闭不变量。
- `src/repository.py`：SQLite建表、事务、版本控制和审计链。
- `src/service.py`：权限检查、用例编排、并发控制和审计。
- `src/http_api.py`：JSON路由和统一错误响应。
- `src/audit.py`：UTC时间和SHA-256审计事件。
- `static/index.html`：最小演示页。
- `tests/`：完整流程、规则和失败测试。

## 初始化与启动

```bash
python3 app.py --db ./data.db --port 8315
```

默认端口为`8315`，首次启动自动建库。使用`X-Actor`和`X-Role`请求头传递身份。

## 主要接口

- `GET /health`
- `GET /api/items`
- `POST /api/items`
- `GET /api/items/{id}`
- `POST /api/items/{id}/records`
- `POST /api/items/{id}/records/{record_id}/close`，按记录类型限定关闭角色
- `POST /api/items/{id}/transition`，必须提交`expected_version`
- `GET /api/audit`

允许角色：duty_officer, chief_engineer, dispatcher, viewer。库位超过汛限或入库流量上升时提升紧迫度。

流转中接入复核与现场反馈：

- 送审（`draft→checked`）必须提交`reviewer`（复核人）和`opinion`（复核意见），自动生成复核记录。
- 复核记录关闭后（duty_officer）才能送总工授权（`checked→authorized`）。
- 执行（`authorized→executed`）必须提交`contact`（现场联系人）和`discharge`（泄量），自动生成现场反馈记录。
- 反馈记录未关闭（dispatcher 关闭）不能归档（`executed→closed`）。
- 归档后列表和详情通过`reviewer`、`last_feedback_by`展示复核人和最后反馈人。

## 测试

```bash
python3 -m unittest discover -s tests -v
```
