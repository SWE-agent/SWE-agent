# Multi-Agent System Improvements - Quick Reference

## 改进概览

三个主要问题及其解决方案：

### 1. Agent-Coordinator交互问题 ✅

**问题**: 信息传递不清晰，导致信息丢失或冗余

**解决方案**:
- 实现结构化的handoff文档（6个section）
- 文件位置: `sweagent/agent/mas/coordinator.py:274-425`
- 关键改进: `_extract_rca_findings()` 方法重写

**结构化Handoff格式**:
```
1. PROBLEMATIC FILES
2. ROOT CAUSE
3. ERRORS ENCOUNTERED
4. REPRODUCTION
5. FINAL ANALYSIS
6. EXIT STATUS
```

### 2. 历史记录问题 ✅

**问题**: 多个Agent共享history导致混乱和丢失，输出在/tmp不持久

**解决方案**:
- 每个Agent的history独立保存到`global_context`
- Patch Agent启动时重置history
- 输出目录改为 `trajectories/marrs_{timestamp}/`
- 自动生成workflow摘要文件
- 文件位置:
  - `coordinator.py:80-86` (时间戳目录)
  - `coordinator.py:271-280` (RCA保存)
  - `coordinator.py:468` (Patch重置)
  - `coordinator.py:496-503` (Patch保存)
  - `coordinator.py:594-681` (摘要生成)

**新的目录结构**:
```
trajectories/
└── marrs_20241204_125030/          # 自动生成时间戳
    ├── rca/
    │   └── default/
    │       └── default_rca.traj     # RCA轨迹
    ├── patch/
    │   └── default/
    │       └── default_patch.traj   # Patch轨迹
    ├── workflow_summary_default.json   # 完整历史数据
    └── workflow_summary_default.txt    # 人类可读摘要
```

**关键改进**:
- ✅ 不再使用/tmp，输出持久化
- ✅ 时间戳目录便于追踪和比较
- ✅ 完整的workflow摘要包含两个Agent的所有历史
- ✅ 同时提供JSON（机器可读）和TXT（人类可读）格式

### 3. RCA Agent效率问题 ✅

**问题**: 无效尝试太多，效率低下

**解决方案**:
- 升级模型: `gpt-3.5-turbo-0613` → `gpt-4o-mini`
- 增加cost limit: `2.0` → `4.0`
- 添加系统化调查策略（6步骤）
- 添加结构化提交格式
- 文件位置: `config/agents/rca_agent.yaml`

**6步调查策略**:
1. UNDERSTAND THE ISSUE (2-3 actions)
2. LOCATE RELEVANT CODE (3-5 actions)
3. EXAMINE CODE (3-5 actions)
4. CREATE REPRODUCTION (2-3 actions)
5. ANALYZE ROOT CAUSE (1-2 actions)
6. SUBMIT STRUCTURED FINDINGS

**目标**: 15-20个actions完成分析（之前可能需要50+）

## 修改的文件

### 核心文件
1. **sweagent/agent/mas/coordinator.py**
   - ✅ 结构化handoff提取
   - ✅ History独立保存和重置
   - ✅ 时间戳输出目录
   - ✅ Workflow摘要生成

2. **config/agents/rca_agent.yaml**
   - ✅ 模型升级到gpt-4o-mini
   - ✅ Cost limit提升到4.0
   - ✅ 系统化调查策略
   - ✅ 结构化提交格式

3. **config/agents/patch_agent.yaml**
   - ✅ 模型升级到gpt-4o-mini
   - ✅ 实现策略优化
   - ✅ 强调信任RCA结果

4. **tools/run_mas.py**
   - ✅ 默认输出目录改为None（自动生成时间戳）

## 运行测试

```bash
# 基本测试（自动创建时间戳目录）
python tools/run_mas.py \
  --repo /path/to/test/repo \
  --issue_text "Bug description here"

# 输出会在: trajectories/marrs_YYYYMMDD_HHMMSS/

# 指定输出目录
python tools/run_mas.py \
  --repo /path/to/test/repo \
  --issue_text "Bug description" \
  --output_dir my_custom_dir

# 检查最新输出
ls -lt trajectories/ | head -5

# 查看workflow摘要
cat trajectories/marrs_*/workflow_summary_default.txt

# 查看RCA轨迹
cat trajectories/marrs_*/rca/default/default_rca.traj

# 查看Patch轨迹
cat trajectories/marrs_*/patch/default/default_patch.traj

# 分析完整历史（需要jq）
jq '.histories' trajectories/marrs_*/workflow_summary_default.json
```

## 验证改进

### 检查点1: 结构化Handoff
```bash
# 在coordinator日志中应该看到:
# "1. PROBLEMATIC FILES:"
# "2. ROOT CAUSE:"
# "3. ERRORS ENCOUNTERED:"
# etc.
```

### 检查点2: History独立性
```bash
# 查看workflow摘要
cat trajectories/marrs_*/workflow_summary_default.txt

# RCA trajectory只包含RCA的消息
grep '"agent": "rca"' trajectories/marrs_*/rca/default/*.traj

# Patch trajectory只包含Patch的消息
grep '"agent": "patch"' trajectories/marrs_*/patch/default/*.traj

# 检查workflow摘要中的历史条目数
jq '.agents.rca.history_entries' trajectories/marrs_*/workflow_summary_default.json
jq '.agents.patch.history_entries' trajectories/marrs_*/workflow_summary_default.json
```

### 检查点3: RCA效率
- RCA应该在15-25个actions内完成
- 提交应该遵循结构化格式
- 应该看到系统化的步骤进展

## 预期效果

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| RCA actions | 40-60+ | 15-25 |
| Patch actions | 20-30 | 8-15 |
| 总actions | 60-90+ | 25-40 |
| RCA信息完整性 | 60-70% | 90-95% |
| History独立性 | 无 | 100% |

## 不需要LangChain的原因

虽然考虑过使用LangChain，但最终决定不使用，原因：

1. **架构简单明确**: Star topology已经很清晰，不需要复杂框架
2. **直接控制**: 对handoff格式需要精确控制
3. **依赖最小化**: 避免引入大型框架依赖
4. **性能考虑**: 直接实现更高效
5. **学习曲线**: 团队不需要学习新框架

当前的直接实现方式完全满足需求。

## 下一步

如果效果仍然不理想，可以考虑：

1. **动态策略调整**: 监控进度，自动调整搜索策略
2. **RCA结果验证**: Coordinator验证RCA输出的完整性
3. **增强模型**: 考虑使用GPT-4（而非4o-mini）
4. **工具优化**: 添加专门的代码分析工具

## 故障排除

### 如果找不到输出文件：
```bash
# 列出最近的运行
ls -lt trajectories/

# 查找最新的workflow摘要
find trajectories -name "workflow_summary_*.txt" -type f -mtime -1
```

### 如果RCA仍然低效：
- 检查是否正确加载了新的配置文件
- 确认模型已升级到gpt-4o-mini
- 查看系统提示是否正确传递

### 如果History仍然混乱：
- 确认line 468的history重置代码是否执行
- 检查workflow_summary文件中的history_entries数量
- 使用jq验证历史独立性：
  ```bash
  jq '.histories.rca_history[].agent' trajectories/marrs_*/workflow_summary_default.json | sort -u
  # 应该只输出: "rca"
  ```

### 如果Handoff信息不完整：
- 检查RCA Agent是否遵循了结构化格式提交
- 查看workflow_summary_default.txt中的RCA FINDINGS部分
- 确认trajectory正确保存

## 新增功能详解

### Workflow摘要文件

每次运行完成后，会生成两个摘要文件：

1. **workflow_summary_{request_id}.json** - 包含完整数据：
   - 运行元数据（时间戳、目录等）
   - 两个Agent的统计信息
   - 完整的RCA和Patch历史
   - RCA findings预览

2. **workflow_summary_{request_id}.txt** - 人类可读格式：
   - 清晰的章节划分
   - Agent统计信息
   - RCA findings完整内容
   - 轨迹文件位置

### 时间戳目录

- 格式: `marrs_YYYYMMDD_HHMMSS`
- 例如: `marrs_20241204_125030`
- 便于按时间排序和查找
- 避免多次运行的文件冲突

## 联系和支持

详细技术文档:
- `docs/MAS_IMPROVEMENTS_SUMMARY.md` - 完整改进说明
- `docs/HISTORY_TRACKING_SOLUTION.md` - 历史记录解决方案详解
- `docs/multi_agent_architecture.md` - 架构文档
