"""courses の targetCompany ごとに受講ユーザのダミーデータを生成するスクリプト。

出力: dataset/users/<slugified_company>.json  (各ファイルは配列)

レコード構造:
    {
        "userName": "姓 名",           # ユーザ氏名 (日本語)
        "companyName": "...",          # courses の targetCompany と一致
        "departmentName": "人事部" など # 値は日本語 / フィールド名は英語
        "jobTitle": "課長" など         # 値は日本語 / フィールド名は英語
    }

要件:
- 会社ごとに約30名 (デフォルト 30, 環境変数 USERS_PER_COMPANY で変更可)
- id フィールドは付与しない (Cosmos 側で自動付与想定)

実行例:
    python dataset/generate_users.py

"""
from __future__ import annotations
import json
import os
import random
import re
from pathlib import Path
from typing import List, Dict

COURSES_DIR = Path("dataset") / "courses"
OUTPUT_DIR = Path("dataset") / "users"
DEFAULT_COUNT = int(os.getenv("USERS_PER_COMPANY", "30"))

# サンプルの苗字と名前 (適当に拡張可能)
LAST_NAMES = [
    "佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤",
    "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水"
]
FIRST_NAMES = [
    "太郎", "花子", "健一", "真由美", "亮", "愛", "翔", "美咲", "直樹", "彩香",
    "裕介", "麻衣", "啓介", "夏美", "拓也", "美穂", "智也", "里奈", "悠斗", "和葉"
]

DEPARTMENTS = [
    "人事部", "情報システム部", "経営企画部", "財務部", "経理部",
    "営業部", "マーケティング部", "カスタマーサポート部", "研究開発部", "品質保証部",
    "オペレーション部", "法務部", "調達部", "生産管理部", "データ分析室"
]

JOB_TITLES = [
    "一般職", "主任", "係長", "課長", "次長",
    "部長", "シニアスペシャリスト", "リードエンジニア", "アナリスト", "スペシャリスト"
]


def slugify_company(name: str) -> str:
    # 便宜的に株式会社等の接尾辞を除去し英数・ハイフンのみ残す
    base = re.sub(r"株式会社|有限会社", "", name)
    # 全角スペース等を半角スペースへ
    base = re.sub(r"\s+", " ", base).strip()
    # ASCII 化: 漢字はそのままでは残るので Unicode コードポイントを16進で繋ぐ方式でも良いが
    # ここでは簡易に漢字を落としてフィルタ (ファイル名衝突があれば調整)
    ascii_part = ''.join(ch for ch in base if ord(ch) < 128)
    if not ascii_part:
        # すべて非ASCII の場合はコードポイント下位4桁で構築
        ascii_part = ''.join(f"{ord(ch):x}" for ch in base)[:24]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_part).strip('-').lower() or "company"
    return slug


def load_companies() -> List[str]:
    companies = []
    for fp in COURSES_DIR.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        comp = data.get("targetCompany")
        if comp and comp not in companies:
            companies.append(comp)
    return companies


def generate_user_records(company: str, count: int) -> List[Dict[str, str]]:
    # 会社ごとにシードを固定して再現性を確保
    rnd = random.Random(hash(company) & 0xFFFFFFFF)
    records: List[Dict[str, str]] = []
    for _ in range(count):
        last = rnd.choice(LAST_NAMES)
        first = rnd.choice(FIRST_NAMES)
        user_name = f"{last} {first}"  # スペース区切り
        dept = rnd.choice(DEPARTMENTS)
        title = rnd.choice(JOB_TITLES)
        records.append({
            "userName": user_name,
            "companyName": company,
            "departmentName": dept,
            "jobTitle": title,
        })
    return records


def main():
    if not COURSES_DIR.exists():
        raise SystemExit(f"courses ディレクトリが見つかりません: {COURSES_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    companies = load_companies()
    if not companies:
        raise SystemExit("targetCompany が見つかりませんでした")

    for company in companies:
        recs = generate_user_records(company, DEFAULT_COUNT)
        slug = slugify_company(company)
        out_file = OUTPUT_DIR / f"{slug}.json"
        with out_file.open("w", encoding="utf-8") as f:
            json.dump(recs, f, ensure_ascii=False, indent=2)
        print(f"Generated {len(recs)} users for {company} -> {out_file}")

    print("DONE")


if __name__ == "__main__":
    main()
