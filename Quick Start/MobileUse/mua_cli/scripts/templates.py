"""
示例任务模板 - 给 0 基础用户"拿来即用"的现成任务

用法 (CLI 中):
  在"请描述任务"提示处直接输入模板序号 (如 2), 即可使用对应示例;
  也可以基于示例改写, 或完全自己描述。

模板分三类, 企业应用场景刻意放在前面:
  - 通用场景: 看桌面, 零成本试手 (环境自检);
  - 企业应用场景: 客户沟通 / 销售 CRM / 考勤 / 财务开票 / 供应链库存 / 电商订单 / OA 审批,
    覆盖不同业务职能线, 最能直观展示"AI 替你干活"的效果;
  - 生活场景: 刷抖音 / 找餐厅 / 查天气, 让第一次使用的人一眼就懂"我能让它做什么"。

提示词刻意写得口语化、具体, 拿到就能演示。
"""

TASK_TEMPLATES = [
    # ---- 通用: 先试手, 零成本 (环境自检) ----
    {
        "name": "看看桌面",
        "prompt": "查看云手机桌面上有什么文件或文件夹，列出所有内容，并简要说明每项是什么",
        "scene": "通用",
    },
    # ---- 企业应用: 覆盖不同业务线, 最能体现"AI 替你干活" ----
    {
        "name": "企业微信回客户消息",
        "prompt": "打开企业微信，查看未读消息，把最新一条客户消息回复：收到，今天下班前给你反馈",
        "scene": "企业应用",
        "apps": ["企业微信"],
    },
    {
        "name": "CRM 录入客户",
        "prompt": "打开 CRM 系统，在「新增客户」页面录入客户：公司名称华信科技，联系人张经理，电话 13800138000，然后保存并告诉我结果",
        "scene": "企业应用",
        "apps": ["CRM 系统"],
    },
    {
        "name": "钉钉考勤打卡",
        "prompt": "打开钉钉，点击「考勤打卡」，完成上班打卡，并告诉我打卡结果",
        "scene": "企业应用",
        "apps": ["钉钉"],
    },
    {
        "name": "开票系统查统计",
        "prompt": "打开开票系统，查询本月已开出的发票，统计总金额和发票数量，用一句话告诉我",
        "scene": "企业应用",
        "apps": ["开票系统"],
    },
    {
        "name": "进销存查库存",
        "prompt": "打开进销存系统，查询「A4 复印纸」的当前库存数量，如果少于 100 箱就提醒我该补货了",
        "scene": "企业应用",
        "apps": ["进销存系统"],
    },
    {
        "name": "电商后台发货",
        "prompt": "打开电商后台，查看最新的 3 笔待发货订单，把第一笔标记为已发货",
        "scene": "企业应用",
        "apps": ["电商后台"],
    },
    {
        "name": "OA 审批",
        "prompt": "打开 OA 系统，查看待审批事项，把其中的请假申请全部通过，并告诉我处理结果",
        "scene": "企业应用",
        "apps": ["OA 系统"],
    },
    # ---- 生活: 生活化场景, 让新手一眼就懂 ----
    {
        "name": "打开微信发消息",
        "prompt": "打开微信，给「文件传输助手」发一条消息：你好，这条消息来自云端手机",
        "scene": "生活",
        "apps": ["微信"],
    },
    {
        "name": "打开抖音搜美食",
        "prompt": "打开抖音，搜索「美食」，看看有哪些热门视频，简单介绍前三个",
        "scene": "生活",
        "apps": ["抖音"],
    },
    {
        "name": "看看附近有什么吃的",
        "prompt": "打开地图应用，搜索我附近的餐厅，列出距离最近的 3 家以及它们的评分",
        "scene": "生活",
        "apps": ["地图"],
    },
    {
        "name": "查一下今天天气",
        "prompt": "打开浏览器，查询今天北京的天气，告诉我温度和适不适合出门",
        "scene": "生活",
    },
]


def resolve_template(choice: str):
    """把用户的输入解析为任务提示词

    输入为 1~N 的序号时返回对应模板的提示词, 否则原样返回。
    (配合"输入序号用示例"的引导, 0 基础用户无需理解即可上手)

    Args:
        choice: 用户在"请描述任务"处输入的内容

    Returns:
        (提示词, 模板名或 None)
    """
    choice = (choice or "").strip()
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(TASK_TEMPLATES):
            tpl = TASK_TEMPLATES[idx - 1]
            return tpl["prompt"], tpl["name"]
    return choice, None


def format_template_menu(max_items: int | None = None) -> str:
    """生成模板菜单文本 (按场景分组, 用于任务输入前的引导)

    Args:
        max_items: 最多展示前几个模板 (None 表示全部)

    Returns:
        多行文本, 如 "  通用  1) 看看桌面 ..."
    """
    lines = ["第一次不知道说什么？直接输入序号，用现成的例子："]
    items = TASK_TEMPLATES if max_items is None else TASK_TEMPLATES[:max_items]

    # 按场景分组, 保持模板原有顺序与序号
    groups: dict[str, list] = {}
    order: list[str] = []
    for i, tpl in enumerate(items, start=1):
        scene = tpl.get("scene", "通用")
        if scene not in groups:
            groups[scene] = []
            order.append(scene)
        groups[scene].append((i, tpl))

    for scene in order:
        cells = []
        for i, tpl in groups[scene]:
            mark = "*" if tpl.get("apps") else ""
            cells.append(f"{i}) {tpl['name']}{mark}")
        lines.append(f"  {scene}  " + "  ".join(cells))

    if any(t.get("apps") for t in items):
        lines.append("  带 * 的示例需要云手机上已安装对应 App（可在 MUA 控制台「发布 App」安装）")
    return "\n".join(lines)
