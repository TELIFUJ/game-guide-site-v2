#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_bgg.py
從 bgg_ids.txt 讀取 ID
→ 呼叫 BGG API（含 X-API-Key）
→ 安全 retry、防 rate limit
→ 產生 data/bgg_data.json
"""

import json, time, hashlib, pathlib, requests, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
IDS_FILE = ROOT / "data" / "bgg_ids.txt"
OUT_FILE = ROOT / "data" / "bgg_data.json"

API_URL = "https://api.geekdo.com/xmlapi2/thing?id={}&stats=1"

API_HEADERS = {
    "User-Agent": "GameGuidePipeline/2.0 (https://github.com/TELIFUJ)",
}

API_KEY = pathlib.os.getenv("BGG_API_KEY", "").strip()
if API_KEY:
    API_HEADERS["X-API-Key"] = API_KEY


def log(msg):
    print(f"[fetch_bgg] {msg}")


def safe_get(url):
    """自動 retry、防爆炸"""
    for i in range(5):
        try:
            r = requests.get(url, headers=API_HEADERS, timeout=15)
            if r.status_code == 200:
                return r.text
            log(f"HTTP {r.status_code} retry {i+1}/5")
            time.sleep(2 + i)
        except Exception as e:
            log(f"ERR {e} retry {i+1}/5")
            time.sleep(2 + i)
    return None


def parse_xml_to_dict(xml: str):
    """手動解析 BGG XML，擠出重點欄位"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)

    item = root.find("item")
    if item is None:
        return None

    out = {}
    out["bgg_id"] = int(item.attrib.get("id"))

    # ---------- 名稱 ----------
    name_primary = item.find("./name[@type='primary']")
    out["name"] = name_primary.attrib["value"] if name_primary is not None else ""

    # ---------- 圖片 URL ----------
    def get_and_fix(path):
        node = item.find(path)
        if node is None:
            return None
        url = node.text or ""
        # BGG 有些網址不是 https → 修正
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http://"):
            return url.replace("http://", "https://")
        return url

    out["image"] = get_and_fix("image")
    out["thumbnail"] = get_and_fix("thumbnail")

    # ---------- 數值 ----------
    stats = item.find("statistics/ratings")
    if stats is not None:
        def gv(tag):
            n = stats.find(tag)
            if n is None:
                return None
            try:
                return float(n.text)
            except:
                return None

        out["rating_avg"] = gv("average")
        out["rating_bayes"] = gv("bayesaverage")
        out["users_rated"] = gv("usersrated")

    # ---------- 重量 ----------
    weight = None
    w_node = item.find("statistics/ratings/averageweight")
    if w_node is not None:
        try:
            weight = float(w_node.text)
        except:
            pass
    out["weight"] = weight

    # ---------- 類別 ----------
    cats = []
    mechs = []
    for link in item.findall("link"):
        if link.attrib.get("type") == "boardgamecategory":
            cats.append(link.attrib.get("value"))
        if link.attrib.get("type") == "boardgamemechanic":
            mechs.append(link.attrib.get("value"))

    out["categories"] = cats
    out["mechanisms"] = mechs

    return out


def main():
    if not IDS_FILE.exists():
        log("找不到 data/bgg_ids.txt")
        sys.exit(1)

    ids = []
    with open(IDS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and line.isdigit():
                ids.append(int(line))

    log(f"載入 BGG ID 數量：{len(ids)}")

    rows = []
    for idx, gid in enumerate(ids, start=1):
        log(f"[{idx}/{len(ids)}] Fetch {gid}")

        xml = safe_get(API_URL.format(gid))
        if not xml:
            log(f"ID {gid} 抓取失敗，跳過")
            continue

        try:
            rec = parse_xml_to_dict(xml)
            if rec:
                rows.append(rec)
        except Exception as e:
            log(f"解析失敗 {gid}: {e}")

        time.sleep(1)  # 保護 API
        
    # 寫出結果
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    log(f"完成，共寫入 {len(rows)} 筆 → {OUT_FILE}")


if __name__ == "__main__":
    main()
