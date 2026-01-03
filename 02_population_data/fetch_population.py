"""
e-Stat APIを使用して川崎市の人口データを取得するスクリプト
"""

import requests
import json
import pandas as pd

API_KEY = "6d37106fc8c6b87a1822e7668ef2fe2df0847930"
BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json"

# 川崎市の各区コード
KAWASAKI_AREA_CODES = {
    "14131": "川崎区",
    "14132": "幸区", 
    "14133": "中原区",
    "14134": "高津区",
    "14135": "宮前区",
    "14136": "多摩区",
    "14137": "麻生区"
}

def get_stats_data(stats_data_id: str, area_codes: list, limit: int = 10000) -> dict:
    """e-Stat APIからデータを取得"""
    params = {
        "appId": API_KEY,
        "statsDataId": stats_data_id,
        "cdArea": ",".join(area_codes),
        "limit": limit
    }
    response = requests.get(f"{BASE_URL}/getStatsData", params=params)
    return response.json()

def parse_population_data(data: dict) -> pd.DataFrame:
    """APIレスポンスからデータフレームを作成"""
    stat_data = data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})
    
    # 分類情報を取得
    class_inf = stat_data.get("CLASS_INF", {}).get("CLASS_OBJ", [])
    class_maps = {}
    for c in class_inf:
        class_id = c.get("@id")
        class_items = c.get("CLASS", [])
        if isinstance(class_items, dict):
            class_items = [class_items]
        class_maps[class_id] = {item.get("@code"): item.get("@name") for item in class_items}
    
    # データを取得
    data_inf = stat_data.get("DATA_INF", {}).get("VALUE", [])
    
    rows = []
    for item in data_inf:
        row = {
            "area_code": item.get("@area"),
            "area_name": class_maps.get("area", {}).get(item.get("@area"), ""),
            "age_category": class_maps.get("cat01", {}).get(item.get("@cat01"), ""),
            "gender": class_maps.get("cat02", {}).get(item.get("@cat02"), ""),
            "year": class_maps.get("time", {}).get(item.get("@time"), ""),
            "value": item.get("$")
        }
        rows.append(row)
    
    return pd.DataFrame(rows)

def get_age_population():
    """川崎市の年齢3区分別人口を取得"""
    print("📊 川崎市の年齢別人口データを取得中...")
    
    # 年齢3区分データ (0003448299)
    area_codes = list(KAWASAKI_AREA_CODES.keys())
    data = get_stats_data("0003448299", area_codes)
    
    result = data.get("GET_STATS_DATA", {}).get("RESULT", {})
    if result.get("STATUS") != 0:
        print(f"エラー: {result.get('ERROR_MSG')}")
        return None
    
    df = parse_population_data(data)
    print(f"  → {len(df)}レコード取得")
    
    return df

def get_detailed_age_population():
    """川崎市の年齢5歳階級別人口を取得"""
    print("📊 川崎市の年齢5歳階級別人口データを取得中...")
    
    # 年齢5歳階級データを検索
    search_url = f"{BASE_URL}/getStatsList"
    params = {
        "appId": API_KEY,
        "searchWord": "年齢5歳階級 市区町村 令和2年",
        "surveyYears": "2020",
        "limit": 50
    }
    response = requests.get(search_url, params=params)
    data = response.json()
    
    tables = data.get("GET_STATS_LIST", {}).get("DATALIST_INF", {}).get("TABLE_INF", [])
    if isinstance(tables, dict):
        tables = [tables]
    
    print(f"  → 候補テーブル: {len(tables)}件")
    
    # 適切なテーブルを探す
    for t in tables[:10]:
        title = t.get("TITLE", "")
        if isinstance(title, dict):
            title = title.get("$", "")
        table_id = t.get("@id", "")
        print(f"    {table_id}: {title[:60]}")
    
    return tables

def main():
    print("\n🏥 川崎市人口データ取得ツール 🏥\n")
    
    # 年齢3区分データを取得
    df_age3 = get_age_population()
    
    if df_age3 is not None and len(df_age3) > 0:
        # 令和2年、総数のみ抽出
        df_filtered = df_age3[
            (df_age3["year"].str.contains("令和2年|2020", na=False)) &
            (df_age3["gender"].str.contains("総数|計", na=False))
        ].copy()
        
        print("\n=== 川崎市 区別年齢3区分人口（令和2年）===")
        
        # ピボットテーブル作成
        pivot = df_filtered.pivot_table(
            index="area_name",
            columns="age_category", 
            values="value",
            aggfunc="first"
        )
        print(pivot)
        
        # CSVに保存
        df_filtered.to_csv("kawasaki_population_age3.csv", index=False, encoding="utf-8")
        print("\n📄 kawasaki_population_age3.csv に保存しました")
    
    # 詳細な年齢階級データの候補を表示
    print("\n" + "="*60)
    get_detailed_age_population()

if __name__ == "__main__":
    main()

