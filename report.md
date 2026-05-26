# MAGE Memory Persistence 修改报告

## 1. 我做了什么

这次修改只做了 **memory persistence in memory**，没有改组员已经做好的 **agent routing**。

主要改动：

- 新增 `src/mage/debug_memory.py`
  - 用来保存每一轮 debug 的状态。
  - 记录仿真是否通过、mismatch 数量、第一次出错时间、错误类型、修复动作等信息。

- 修改 `src/mage/agent.py`
  - 在 syntax check、simulation、RTL 修复之后记录 checkpoint。
  - 把 memory summary 传给后面的 agent 使用。

- 修改 `src/mage/sim_judge.py`
  - 让 SimJudge 能看到之前的 debug memory。
  - 它判断错误来源时，可以参考前几轮失败记录。

- 修改 `src/mage/rtl_editor.py`
  - 让 RTLEditor 在修改 RTL 时参考 memory。
  - 每次编辑后记录本轮动作和结果，避免下一轮重复犯同样错误。

- 新增 `tests/test_debug_memory.py`
  - 测试 memory 是否能正确记录 mismatch、checkpoint 和 prompt summary。

## 2. 为什么要这样改

原来的 MAGE 每一轮 debug 之间缺少明确的状态保存。

也就是说，模型可能不知道：

- 上一轮哪里错了
- 上一轮改了什么
- 哪一次修改让结果变好或变差
- 第一次 mismatch 出现在什么时间点

加入 memory persistence 后，每一轮都会保存一个状态点。下一轮 debug agent 可以根据历史信息继续修复，而不是每次都重新猜。

简单流程：

```text
仿真失败
  ↓
记录错误状态到 DebugMemory
  ↓
SimJudge 判断错误来源
  ↓
RTLEditor 根据 memory 修改 RTL
  ↓
再次仿真
  ↓
继续记录下一轮状态
```

## 3. 是否修改了 agent routing

没有。

组员的 routing 逻辑仍然保留：

- `SimJudge` 继续判断 `tb_needs_fix`
- `SimJudge` 继续输出 `error_route`
- `RTLEditor` 继续使用原来的 `repair_route`

我的修改只是额外提供 memory context，不改变 routing 决策流程。

## 4. 运行结果

这次运行结果已经写入：

```text
output.txt
```

运行本身没有崩溃：

```text
exit_code=0
```

但是 benchmark 没有通过：

```text
Pass rate: 0/1
```

## 5. 为什么会错误

这次错误不是 memory persistence 造成的，也不是 agent routing 造成的。

主要原因是模型返回格式不符合 MAGE 的 JSON 解析要求。

MAGE 期望模型直接返回纯 JSON，但模型返回了 Markdown 包裹的 JSON，例如：

````text
```json
{ ... }
```
````

于是程序解析失败，日志里出现：

```text
Json Decode Error
drop this response
```

因为模型回复被丢弃，最后没有成功生成 `rtl.sv`，所以后面仿真时报错：

```text
rtl.sv: No such file or directory
```

## 6. 结论

本次完成的是 **in-memory persistence**：

- MAGE 可以在一次 debug run 内保存每轮状态。
- SimJudge 和 RTLEditor 可以看到之前的失败信息。
- 组员的 agent routing 没有被修改。

当前失败原因是 **模型输出 JSON 被 Markdown code block 包住，导致解析失败**。

下一步建议修 JSON parser，让它在解析前自动去掉 ` ```json ` 和 ` ``` ` 这种 Markdown 包装。
