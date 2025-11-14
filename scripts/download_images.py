#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_images.py
依照 bgg_data.json / manual.csv 合併結果
→ 批次下載封面圖片到 site/assets/img/

命名方式：
  <bgg_id>-<md5>.jpg

規則：
  - 若 image_override 存在 → 優先使用
  - 若已有檔案 → 不再下載（安全）
  - 全程 https，BGG URL 自動修正
"""

import json, pathlib, hashlib, requests, time, csv

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_MANUAL = ROOT / "data" / "manual.csv"
DATA_BGG = ROOT / "data" / "bgg_data.json"
IMG_DIR = ROOT / "site" / "assets" / "img"

IMG_DIR.mkdir(parents=True, exist_ok=True)

UA = {
    "User-Agent": "GameGuideImageBot/2.0 (https://github.com/TELIFUJ)"
}

def log(msg):
    print(f"[img] {msg}")

def md5(s: str):
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:8]


def fix_url(url: str):
    """全部變 https://"""
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return url.replace("http://", "https://")
    return url


# -------------------------------------------------------------
# 讀 manual.csv → key: bgg_id, val: image_override
# -------------------------------------------------------------
def load_manual_override():
    override = {}
    if not DATA_MANUAL.exists():
        return override

    with DATA_MANUAL.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bid = row.get("bgg_id")
            img = row.get("image_override")
            if bid and img:
                override[str(int(float(bid)))] = img.strip()
    return override


# -------------------------------------------------------------
# 主流程
# -------------------------------------------------------------
def main():
    if not DATA_BGG.exists():
        log("找不到 bgg_data.json")
        return

    manual = load_manual_override()
    log(f"手動 override: {len(manual)} 筆")

    rows = json.loads(DATA_BGG.read_text("utf-8"))
    log(f"BGG rows: {len(rows)}")

    for idx, g in enumerate(rows, start=1):
        bid = str(g.get("bgg_id"))
        if not bid:
            continue

        # 來源圖片
        if bid in manual:
            src = manual[bid]
            log(f"[{idx}] {bid} 來自 override")
        else:
            src = g.get("image") or g.get("thumbnail") or ""
            src = fix_url(src)

        if not src:
            log(f"[{idx}] {bid} 無圖片 URL，跳過")
            continue

        # 檔名: <bgg_id>-<md5>.jpg
        fn = f"{bid}-{md5(src)}.jpg"
        out = IMG_DIR / fn

        if out.exists():
            log(f"[{idx}] {fn} 已存在，跳過")
            continue

        # 下載
        try:
            log(f"[{idx}] downloading {src}")
            r = requests.get(src, headers=UA, timeout=20)
            if r.status_code == 200:
                out.write_bytes(r.content)
                time.sleep(0.5)
            else:
                log(f"  HTTP {r.status_code} → 失敗")
        except Exception as e:
            log(f"  ERR: {e}")

    log("全部圖片處理完成")


if __name__ == "__main__":
    main()
