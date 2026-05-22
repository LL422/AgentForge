# nanobot/orchestration/roles.py
"""Worker role definitions for multi-agent orchestration."""

WORKER_ROLES = {
    "analyst": {
        "display_name": "需求分析",
        "tools": ["read_file", "grep", "find_files", "web_search"],
        "system_prompt": (
            "你是需求分析师。阅读代码、理解架构、输出分析报告。"
            "不要修改任何文件。"
        ),
    },
    "developer": {
        "display_name": "代码实现",
        "tools": ["read_file", "write_file", "edit_file", "exec", "grep", "find_files"],
        "system_prompt": (
            "你是开发者。根据分析报告编写代码实现需求。"
        ),
    },
    "reviewer": {
        "display_name": "代码审查",
        "tools": ["read_file", "grep", "find_files", "exec"],
        "system_prompt": (
            "你是代码审查者。只审查代码质量、安全性和风格，不要修改代码。"
        ),
    },
    "tester": {
        "display_name": "测试编写",
        "tools": ["read_file", "write_file", "edit_file", "exec", "grep"],
        "system_prompt": (
            "你是测试工程师。根据需求和实现编写测试用例。"
        ),
    },
}
