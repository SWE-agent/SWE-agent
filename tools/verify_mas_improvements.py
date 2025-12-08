#!/usr/bin/env python3
"""验证多Agent系统改进的脚本

这个脚本检查所有改进是否正确实施：
1. 结构化handoff功能
2. 历史记录独立性
3. 时间戳输出目录
4. Workflow摘要生成
5. RCA配置优化
"""

import sys
from pathlib import Path


def check_coordinator_improvements():
    """检查coordinator.py的改进"""
    print("检查 coordinator.py 改进...")

    coordinator_path = Path("sweagent/agent/mas/coordinator.py")
    if not coordinator_path.exists():
        print("  ❌ coordinator.py 不存在")
        return False

    content = coordinator_path.read_text()

    checks = {
        "datetime导入": "from datetime import datetime" in content,
        "时间戳目录创建": 'strftime("%Y%m%d_%H%M%S")' in content,
        "RCA history保存": 'self.global_context["rca_history"]' in content,
        "RCA trajectory保存": 'self.global_context["rca_trajectory"]' in content,
        "Patch history重置": "patch_agent.history = []" in content,
        "Patch history保存": 'self.global_context["patch_history"]' in content,
        "Workflow摘要方法": "def _save_workflow_summary" in content,
        "结构化handoff提取": "PROBLEMATIC FILES" in content,
    }

    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False

    return all_passed


def check_rca_config():
    """检查RCA agent配置"""
    print("\n检查 rca_agent.yaml 配置...")

    config_path = Path("config/agents/rca_agent.yaml")
    if not config_path.exists():
        print("  ❌ rca_agent.yaml 不存在")
        return False

    content = config_path.read_text()

    checks = {
        "模型升级": "gpt-4o-mini" in content,
        "Cost limit增加": "per_instance_cost_limit: 4.0" in content,
        "系统化策略": "SYSTEMATIC INVESTIGATION STRATEGY" in content,
        "6步流程": "Step 1: UNDERSTAND THE ISSUE" in content and "Step 6: SUBMIT STRUCTURED FINDINGS" in content,
        "结构化格式": "SUBMISSION FORMAT" in content,
        "效率指导": "15-20 actions" in content,
    }

    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False

    return all_passed


def check_patch_config():
    """检查Patch agent配置"""
    print("\n检查 patch_agent.yaml 配置...")

    config_path = Path("config/agents/patch_agent.yaml")
    if not config_path.exists():
        print("  ❌ patch_agent.yaml 不存在")
        return False

    content = config_path.read_text()

    checks = {
        "模型升级": "gpt-4o-mini" in content,
        "实现策略": "IMPLEMENTATION STRATEGY" in content,
        "6步流程": "Step 1: REVIEW RCA REPORT" in content and "Step 6: SUBMIT THE PATCH" in content,
        "效率目标": "8-12 actions" in content,
    }

    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False

    return all_passed


def check_run_mas_script():
    """检查run_mas.py脚本"""
    print("\n检查 run_mas.py 脚本...")

    script_path = Path("tools/run_mas.py")
    if not script_path.exists():
        print("  ❌ run_mas.py 不存在")
        return False

    content = script_path.read_text()

    checks = {
        "默认输出目录": "default=None" in content and 'default=Path("/tmp/marrs_output")' not in content,
        "帮助文本更新": "auto-generated timestamped" in content.lower() or "timestamp" in content.lower(),
    }

    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False

    return all_passed


def check_documentation():
    """检查文档"""
    print("\n检查文档...")

    docs = [
        "docs/MAS_IMPROVEMENTS_SUMMARY.md",
        "docs/MAS_IMPROVEMENTS_QUICK_REFERENCE.md",
        "docs/HISTORY_TRACKING_SOLUTION.md",
        "docs/FINAL_IMPLEMENTATION_REPORT.md",
    ]

    all_passed = True
    for doc in docs:
        doc_path = Path(doc)
        exists = doc_path.exists()
        status = "✅" if exists else "❌"
        print(f"  {status} {doc_path.name}")
        if not exists:
            all_passed = False

    return all_passed


def check_trajectories_directory():
    """检查trajectories目录"""
    print("\n检查 trajectories 目录...")

    traj_dir = Path("trajectories")
    if not traj_dir.exists():
        print("  ⚠️  trajectories 目录不存在（将在首次运行时创建）")
        return True

    # Check for marrs_* directories
    marrs_dirs = list(traj_dir.glob("marrs_*"))
    if marrs_dirs:
        print(f"  ✅ 找到 {len(marrs_dirs)} 个现有的 MARRS 运行目录")
        latest = max(marrs_dirs, key=lambda p: p.stat().st_mtime)
        print(f"  📁 最新运行: {latest.name}")

        # Check for summary files
        summary_json = list(latest.glob("workflow_summary_*.json"))
        summary_txt = list(latest.glob("workflow_summary_*.txt"))

        if summary_json:
            print("  ✅ 找到 workflow summary JSON 文件")
        if summary_txt:
            print("  ✅ 找到 workflow summary TXT 文件")

    else:
        print("  ℹ️  尚无 MARRS 运行目录（正常，将在首次运行时创建）")

    return True


def main():
    """主函数"""
    print("=" * 70)
    print("多Agent系统改进验证")
    print("=" * 70)
    print()

    results = {
        "Coordinator改进": check_coordinator_improvements(),
        "RCA配置": check_rca_config(),
        "Patch配置": check_patch_config(),
        "Run MAS脚本": check_run_mas_script(),
        "文档": check_documentation(),
        "Trajectories目录": check_trajectories_directory(),
    }

    print("\n" + "=" * 70)
    print("验证结果总结")
    print("=" * 70)

    all_passed = True
    for component, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {component}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 所有检查通过！改进已成功实施。")
        print()
        print("下一步：")
        print("1. 运行多Agent系统测试:")
        print('   python tools/run_mas.py --repo <repo> --issue_text "test bug"')
        print()
        print("2. 检查输出:")
        print("   ls -lt trajectories/")
        print("   cat trajectories/marrs_*/workflow_summary_default.txt")
        print()
        return 0
    else:
        print("❌ 部分检查未通过。请检查上述错误。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
