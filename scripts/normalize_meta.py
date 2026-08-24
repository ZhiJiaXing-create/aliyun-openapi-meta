#!/usr/bin/env python3
"""
将 aliyun-openapi-meta 从分散的多目录结构合并为单一 metadatas/ 目录。

Before:
  metadatas/{product}/{api}.json              — 结构数据 (无 description, 无 deprecated)
  descriptions/{locale}/{product}/{api}.json  — deprecated + 参数描述
  en-US/{product}/{api}.json                  — 老结构 (description 内联)
  zh-CN/{product}/{api}.json                  — 老结构 (description 内联)

After:
  metadatas/{product}/{api}.json              — 完整合并数据 (含 {zh, en} 描述)
  products/{locale}/products.json             — 不变

执行后删除 en-US/, zh-CN/, descriptions/ 目录。
"""

import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def merge_parameters(zh_params, en_params):
    """Merge zh and en parameter descriptions into {zh, en} objects."""
    en_map = {}
    if en_params:
        for p in en_params:
            en_map[p.get("name", "")] = p.get("description", "")

    result = []
    for p in zh_params or []:
        name = p.get("name", "")
        zh_desc = (p.get("description", "") or "").strip()
        en_desc = (en_map.get(name, "") or "").strip()

        merged = {}
        if zh_desc:
            merged["zh"] = zh_desc
        if en_desc:
            merged["en"] = en_desc

        result.append((name, merged))

    # Also add en-only params not in zh
    zh_names = {p.get("name", "") for p in (zh_params or [])}
    for p in en_params or []:
        name = p.get("name", "")
        if name not in zh_names:
            en_desc = (p.get("description", "") or "").strip()
            if en_desc:
                result.append((name, {"en": en_desc}))

    return dict(result)


def main():
    metadatas_dir = REPO_ROOT / "metadatas"
    desc_dir = REPO_ROOT / "descriptions"
    zh_dir = REPO_ROOT / "zh-CN"
    en_dir = REPO_ROOT / "en-US"

    api_count = 0
    param_count = 0
    deprecated_count = 0

    for product_dir in sorted(metadatas_dir.iterdir()):
        if not product_dir.is_dir() or product_dir.name.startswith("."):
            continue
        product = product_dir.name

        for api_file in sorted(product_dir.iterdir()):
            if not api_file.name.endswith(".json") or api_file.name in ("products.json", "version.json"):
                continue

            base_data = load_json(api_file)
            if base_data is None:
                continue

            # Try loading from en-US/zh-CN (old full structure)
            en_data = load_json(en_dir / product / api_file.name)
            zh_data = load_json(zh_dir / product / api_file.name)

            # Try loading from descriptions/ (extracted structure)
            desc_zh = load_json(desc_dir / "zh-CN" / product / api_file.name)
            desc_en = load_json(desc_dir / "en-US" / product / api_file.name)

            # Merge deprecated
            deprecated = None
            for src in [en_data, zh_data, desc_zh, desc_en]:
                if src and "deprecated" in src:
                    deprecated = src["deprecated"]
                    break
            if deprecated is not None:
                base_data["deprecated"] = deprecated
                deprecated_count += 1

            # Collect parameter descriptions
            zh_params = None
            en_params = None

            # Priority: old full structure > descriptions/
            if zh_data and "parameters" in zh_data:
                zh_params = zh_data["parameters"]
            elif desc_zh and "parameters" in desc_zh:
                zh_params = desc_zh["parameters"]

            if en_data and "parameters" in en_data:
                en_params = en_data["parameters"]
            elif desc_en and "parameters" in desc_en:
                en_params = desc_en["parameters"]

            # Build description map
            desc_map = merge_parameters(zh_params, en_params)

            # Merge into base parameters
            if desc_map:
                modified = False
                for param in base_data.get("parameters", []):
                    pname = param.get("name", "")
                    if pname in desc_map and desc_map[pname]:
                        param["description"] = desc_map[pname]
                        modified = True
                        param_count += 1
                if modified:
                    api_count += 1

            # Write back
            api_file.write_text(
                json.dumps(base_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    print(f"Merged descriptions into {api_count} API files, {param_count} parameters")
    print(f"Set deprecated on {deprecated_count} API files")

    # Remove old directories
    for d in [zh_dir, en_dir, desc_dir]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed {d.relative_to(REPO_ROOT)}/")

    # Summary
    print("\n=== After ===")
    for d in ["metadatas", "products"]:
        dp = REPO_ROOT / d
        if dp.exists():
            size = sum(f.stat().st_size for f in dp.rglob("*") if f.is_file())
            print(f"  {d}/: {size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
