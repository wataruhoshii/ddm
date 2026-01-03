"""
川崎市AED最適配置分析スクリプト
- 人口データ（年齢5歳階級別）とAEDデータを組み合わせて分析
- 高齢者人口に対するAEDカバー率を算出
- AED不足地域を特定
"""

import requests
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from typing import Dict, List, Tuple

# 日本語フォント設定
matplotlib.rcParams['font.family'] = ['Hiragino Sans', 'Arial Unicode MS', 'sans-serif']

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

def fetch_age_population() -> pd.DataFrame:
    """e-Stat APIから年齢5歳階級別人口を取得"""
    print("📊 年齢5歳階級別人口データを取得中...")
    
    params = {
        "appId": API_KEY,
        "statsDataId": "0004019309",
        "cdArea": ",".join(KAWASAKI_AREA_CODES.keys()),
        "limit": 10000
    }
    response = requests.get(f"{BASE_URL}/getStatsData", params=params)
    data = response.json()
    
    stat_data = data.get("GET_STATS_DATA", {}).get("STATISTICAL_DATA", {})
    
    # 分類マップを作成
    class_inf = stat_data.get("CLASS_INF", {}).get("CLASS_OBJ", [])
    class_maps = {}
    for c in class_inf:
        class_id = c.get("@id")
        items = c.get("CLASS", [])
        if isinstance(items, dict):
            items = [items]
        class_maps[class_id] = {item.get("@code"): item.get("@name") for item in items}
    
    # データを取得
    data_inf = stat_data.get("DATA_INF", {}).get("VALUE", [])
    
    rows = []
    for item in data_inf:
        row = {
            "area_code": item.get("@area"),
            "area_name": class_maps.get("area", {}).get(item.get("@area"), ""),
            "age_group": class_maps.get("cat01", {}).get(item.get("@cat01"), ""),
            "nationality": class_maps.get("cat02", {}).get(item.get("@cat02"), ""),
            "gender": class_maps.get("cat03", {}).get(item.get("@cat03"), ""),
            "year": class_maps.get("time", {}).get(item.get("@time"), ""),
            "population": int(item.get("$", 0)) if item.get("$") and item.get("$") != "-" else 0
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    print(f"  → {len(df)}レコード取得")
    return df

def load_aed_data() -> pd.DataFrame:
    """AED統合データを読み込み"""
    print("📍 AEDデータを読み込み中...")
    df = pd.read_csv("../01_aed_data/kawasaki_aed_merged.csv")
    print(f"  → {len(df)}件")
    return df

def analyze_by_ward(pop_df: pd.DataFrame, aed_df: pd.DataFrame) -> pd.DataFrame:
    """区ごとの分析を実施"""
    print("\n🔍 区別分析を実施中...")
    
    # 人口データを整理（国籍総数、総数（男女）のみ）
    pop_filtered = pop_df[
        (pop_df["nationality"] == "国籍総数") &
        (pop_df["gender"] == "総数")
    ].copy()
    
    # 区名を統一
    pop_filtered["ward"] = pop_filtered["area_name"].str.replace("川崎市", "")
    
    results = []
    
    for ward in KAWASAKI_AREA_CODES.values():
        # 人口データ
        ward_pop = pop_filtered[pop_filtered["ward"] == ward]
        
        total_pop = ward_pop[ward_pop["age_group"] == "総数"]["population"].sum()
        
        # 高齢者人口（65歳以上）
        elderly_groups = ["65～69歳", "70～74歳", "75～79歳", "80～84歳", "85歳以上"]
        elderly_pop = ward_pop[ward_pop["age_group"].isin(elderly_groups)]["population"].sum()
        
        # 若年層（0-14歳）
        young_groups = ["0～4歳", "5～9歳", "10～14歳"]
        young_pop = ward_pop[ward_pop["age_group"].isin(young_groups)]["population"].sum()
        
        # AED数
        ward_aed = aed_df[aed_df["address"].str.contains(ward, na=False)]
        aed_count = len(ward_aed)
        aed_24h = ward_aed["available_24h"].sum()
        
        # 指標計算
        pop_per_aed = total_pop / aed_count if aed_count > 0 else float('inf')
        elderly_per_aed = elderly_pop / aed_count if aed_count > 0 else float('inf')
        elderly_ratio = elderly_pop / total_pop * 100 if total_pop > 0 else 0
        
        results.append({
            "区": ward,
            "総人口": total_pop,
            "高齢者人口(65+)": elderly_pop,
            "高齢化率(%)": round(elderly_ratio, 1),
            "若年人口(0-14)": young_pop,
            "AED設置数": aed_count,
            "24時間AED": aed_24h,
            "人口/AED": round(pop_per_aed),
            "高齢者/AED": round(elderly_per_aed),
        })
    
    return pd.DataFrame(results)

def calculate_risk_score(analysis_df: pd.DataFrame) -> pd.DataFrame:
    """AED不足リスクスコアを計算"""
    df = analysis_df.copy()
    
    # 各指標を正規化（0-100）
    df["高齢化率_norm"] = (df["高齢化率(%)"] - df["高齢化率(%)"].min()) / (df["高齢化率(%)"].max() - df["高齢化率(%)"].min()) * 100
    df["人口AED比_norm"] = (df["人口/AED"] - df["人口/AED"].min()) / (df["人口/AED"].max() - df["人口/AED"].min()) * 100
    df["高齢者AED比_norm"] = (df["高齢者/AED"] - df["高齢者/AED"].min()) / (df["高齢者/AED"].max() - df["高齢者/AED"].min()) * 100
    
    # リスクスコア（高いほどAED不足）
    df["リスクスコア"] = (
        df["高齢化率_norm"] * 0.3 +
        df["人口AED比_norm"] * 0.3 +
        df["高齢者AED比_norm"] * 0.4
    ).round(1)
    
    # 推奨追加AED数（高齢者1000人あたり1台を目標）
    target_ratio = 1000  # 高齢者1000人に1台
    df["現在の高齢者/AED"] = df["高齢者/AED"]
    df["推奨追加AED"] = np.maximum(0, (df["高齢者人口(65+)"] / target_ratio - df["AED設置数"])).astype(int)
    
    return df

def visualize_analysis(analysis_df: pd.DataFrame):
    """分析結果を可視化"""
    print("\n📈 グラフを生成中...")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    
    # 1. 区別人口とAED数
    ax1 = axes[0, 0]
    x = np.arange(len(analysis_df))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, analysis_df["総人口"]/1000, width, label="総人口(千人)", color="#3498db")
    bars2 = ax1.bar(x + width/2, analysis_df["高齢者人口(65+)"]/1000, width, label="高齢者(千人)", color="#e74c3c")
    
    ax1_twin = ax1.twinx()
    ax1_twin.plot(x, analysis_df["AED設置数"], "go-", markersize=10, linewidth=2, label="AED数")
    
    ax1.set_xlabel("区")
    ax1.set_ylabel("人口（千人）")
    ax1_twin.set_ylabel("AED設置数")
    ax1.set_xticks(x)
    ax1.set_xticklabels(analysis_df["区"])
    ax1.legend(loc="upper left")
    ax1_twin.legend(loc="upper right")
    ax1.set_title("区別人口とAED設置数", fontsize=14, fontweight="bold")
    
    # 2. 高齢化率とリスクスコア
    ax2 = axes[0, 1]
    colors = plt.cm.RdYlGn_r(analysis_df["リスクスコア"]/100)
    bars = ax2.barh(analysis_df["区"], analysis_df["リスクスコア"], color=colors)
    ax2.set_xlabel("リスクスコア（高いほどAED不足）")
    ax2.set_title("AED不足リスクスコア", fontsize=14, fontweight="bold")
    for i, (score, elderly) in enumerate(zip(analysis_df["リスクスコア"], analysis_df["高齢化率(%)"])):
        ax2.text(score + 1, i, f"高齢化率:{elderly}%", va="center", fontsize=9)
    
    # 3. 人口あたりAED数の比較
    ax3 = axes[1, 0]
    ax3.bar(analysis_df["区"], analysis_df["人口/AED"], color="#9b59b6", alpha=0.7, label="総人口/AED")
    ax3.bar(analysis_df["区"], analysis_df["高齢者/AED"], color="#e67e22", alpha=0.7, label="高齢者/AED")
    ax3.axhline(y=1500, color="red", linestyle="--", label="目標ライン(1500人/台)")
    ax3.set_ylabel("人口/AED")
    ax3.set_title("人口あたりAED設置状況", fontsize=14, fontweight="bold")
    ax3.legend()
    ax3.tick_params(axis="x", rotation=45)
    
    # 4. 推奨追加AED数
    ax4 = axes[1, 1]
    colors4 = ["#e74c3c" if x > 0 else "#2ecc71" for x in analysis_df["推奨追加AED"]]
    ax4.bar(analysis_df["区"], analysis_df["推奨追加AED"], color=colors4)
    ax4.set_ylabel("推奨追加AED数")
    ax4.set_title("推奨AED追加設置数（高齢者1000人に1台目標）", fontsize=14, fontweight="bold")
    ax4.tick_params(axis="x", rotation=45)
    for i, v in enumerate(analysis_df["推奨追加AED"]):
        if v > 0:
            ax4.text(i, v + 0.5, f"+{v}", ha="center", fontsize=10, fontweight="bold")
    
    plt.tight_layout()
    plt.savefig("aed_optimization_analysis.png", dpi=150, bbox_inches="tight")
    print("✅ aed_optimization_analysis.png に保存しました")

def print_recommendations(analysis_df: pd.DataFrame):
    """分析結果と推奨事項を表示"""
    print("\n" + "="*70)
    print("📊 川崎市AED最適配置分析レポート")
    print("="*70)
    
    # 基本統計
    print("\n【区別統計】")
    display_cols = ["区", "総人口", "高齢者人口(65+)", "高齢化率(%)", "AED設置数", "人口/AED", "リスクスコア"]
    print(analysis_df[display_cols].to_string(index=False))
    
    # リスクが高い区
    print("\n【AED不足リスクが高い区 TOP3】")
    high_risk = analysis_df.nlargest(3, "リスクスコア")
    for _, row in high_risk.iterrows():
        print(f"  🔴 {row['区']}: リスクスコア {row['リスクスコア']}")
        print(f"     - 高齢化率: {row['高齢化率(%)']}%")
        print(f"     - 高齢者1人あたりAED: {row['高齢者/AED']}人/台")
        print(f"     - 推奨追加: +{row['推奨追加AED']}台")
    
    # 全体の推奨
    total_additional = analysis_df["推奨追加AED"].sum()
    print(f"\n【全体の推奨】")
    print(f"  📌 川崎市全体で推奨される追加AED数: {total_additional}台")
    print(f"  📌 現在の総AED数: {analysis_df['AED設置数'].sum()}台")
    print(f"  📌 目標達成後の総AED数: {analysis_df['AED設置数'].sum() + total_additional}台")

def main():
    print("\n" + "="*70)
    print("🏥 川崎市AED最適配置分析システム 🏥")
    print("="*70)
    
    # データ取得
    pop_df = fetch_age_population()
    aed_df = load_aed_data()
    
    # 分析
    analysis_df = analyze_by_ward(pop_df, aed_df)
    analysis_df = calculate_risk_score(analysis_df)
    
    # 結果表示
    print_recommendations(analysis_df)
    
    # 可視化
    visualize_analysis(analysis_df)
    
    # CSVに保存
    analysis_df.to_csv("aed_optimization_result.csv", index=False, encoding="utf-8")
    print("\n📄 aed_optimization_result.csv に保存しました")
    
    print("\n" + "="*70)
    print("✅ 分析完了!")
    print("="*70)

if __name__ == "__main__":
    main()

