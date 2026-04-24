"""提供一个非常小的辅助函数：把数据写入 data.json，方便后续用 XMind 或其它工具导入。

注意：原项目尝试直接使用 XMind 库，但仓库中未提供正确的依赖或用法。为保证可运行性，这里仅生成 JSON 输出文件。
"""

import json
from typing import Any, Mapping


def write_data_json(data: Mapping[str, Any], path: str = 'data.json') -> str:
	"""把给定数据字典序列化为 JSON 并写入文件，返回写入路径。"""
	try:
		# 保障所有值可序列化
		serializable = {k: (v if isinstance(v, (str, int, float, bool, list, dict, type(None))) else str(v)) for k, v in data.items()}
	except Exception:
		serializable = {k: str(v) for k, v in data.items()}
	with open(path, 'w', encoding='utf-8') as f:
		json.dump(serializable, f, ensure_ascii=False, indent=2)
	return path


if __name__ == '__main__':
	print('Xmind helper: 运行该模块可将字典写为 data.json')