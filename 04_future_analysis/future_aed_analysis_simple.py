"""
川崎市AED最適配置分析 - 将来人口推計版（シンプル）
- 2025年〜2070年の全10時点の人口を平等に合計
- リスク加重人口の合計が大きい順に優先度を決定
"""

import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
plt.rcParams['font.family'] = 'Hiragino Sans'

# ========================================
# 設定
# ========================================
DATA_DIR = '../kawasakishi_data'
AED_FILE = '../01_aed_data/kawasaki_aed_merged.csv'

# 年齢別リスク重み（心停止発生率に基づく）
RISK_WEIGHTS = {
    '0〜4歳': 0.04, '5〜9歳': 0.02, '10〜14歳': 0.04, '15〜19歳': 0.11,
    '20〜24歳': 0.18, '25〜29歳': 0.27, '30〜34歳': 0.40, '35〜39歳': 0.62,
    '40〜44歳': 1.00, '45〜49歳': 1.60, '50〜54歳': 2.51, '55〜59歳': 3.78,
    '60〜64歳': 5.60, '65〜69歳': 8.44, '70〜74歳': 12.44, '75〜79歳': 17.78,
    '80〜84歳': 24.44, '85〜89歳': 31.11, '90〜94歳': 35.56, '95〜99歳': 35.56,
    '100歳以上': 35.56
}

# 分析対象年（全10時点）
TARGET_YEARS = ['R7', 'R12', 'R17', 'R22', 'R27', 'R32', 'R37', 'R42', 'R47', 'R52']


def haversine_distance(lat1, lon1, lat2, lon2):
    """2点間の距離を計算（km）"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def load_population_data(year_code):
    """指定年のデータを読み込み"""
    file_path = f"{DATA_DIR}/町丁別将来人口推計({year_code}).csv"
    df = pd.read_csv(file_path, encoding='shift_jis')
    return df


def main():
    print("=" * 70)
    print("🔮 川崎市AED最適配置分析 - 将来人口推計版（シンプル）")
    print("=" * 70)
    print("2025年〜2070年の全10時点を平等に合計して分析")
    
    # AEDデータ読み込み
    print("\n📂 AEDデータ読み込み中...")
    df_aed = pd.read_csv(AED_FILE)
    print(f"  AED数: {len(df_aed)}")
    
    # ========================================
    # 全年次のデータを合計
    # ========================================
    print("\n📂 人口推計データ読み込み中...")
    
    all_data = []
    for year_code in TARGET_YEARS:
        print(f"  {year_code}...", end=" ")
        df = load_population_data(year_code)
        df['リスク重み'] = df['年齢5歳階級'].map(RISK_WEIGHTS)
        df['リスク加重人口'] = df['将来推計人口'] * df['リスク重み']
        all_data.append(df)
        print("OK")
    
    # 全年次を結合
    df_all = pd.concat(all_data, ignore_index=True)
    
    # ========================================
    # 町丁ごとに全年次を合計
    # ========================================
    print("\n📊 町丁ごとに全年次を合計...")
    
    # 町丁ごとに合計（全10時点 × 男女 = 20回分を合計）
    chocho = df_all.groupby(['町丁コード', '行政区', '町丁名', 'X_CODE', 'Y_CODE']).agg({
        '将来推計人口': 'sum',
        'リスク加重人口': 'sum'
    }).reset_index()
    
    chocho.columns = ['町丁コード', '区', '町丁名', '経度', '緯度', '総人口_累計', 'リスク加重人口_累計']
    
    print(f"  町丁数: {len(chocho)}")
    
    # ========================================
    # 各町丁の最寄りAED距離を計算
    # ========================================
    print("\n🗺️  最寄りAED距離を計算中...")
    
    distances = []
    aed_counts = []
    
    for i, row in chocho.iterrows():
        if pd.isna(row['緯度']) or pd.isna(row['経度']):
            distances.append(np.nan)
            aed_counts.append(0)
            continue
        
        min_dist = float('inf')
        count_500m = 0
        
        for _, aed in df_aed.iterrows():
            if pd.isna(aed['latitude']) or pd.isna(aed['longitude']):
                continue
            
            dist = haversine_distance(row['緯度'], row['経度'], aed['latitude'], aed['longitude'])
            if dist < min_dist:
                min_dist = dist
            if dist <= 0.5:
                count_500m += 1
        
        distances.append(min_dist if min_dist != float('inf') else np.nan)
        aed_counts.append(count_500m)
        
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(chocho)} 完了...")
    
    chocho['最寄りAED距離_km'] = distances
    chocho['500m以内AED数'] = aed_counts
    
    # ========================================
    # カバー率計算
    # ========================================
    total_risk_pop = chocho['リスク加重人口_累計'].sum()
    covered = chocho[chocho['500m以内AED数'] > 0]
    covered_risk_pop = covered['リスク加重人口_累計'].sum()
    coverage_rate = covered_risk_pop / total_risk_pop * 100
    
    print(f"\n📊 カバー状況")
    print(f"  総リスク加重人口（累計）: {total_risk_pop:,.0f}")
    print(f"  カバー済み: {covered_risk_pop:,.0f} ({coverage_rate:.1f}%)")
    print(f"  カバー外: {total_risk_pop - covered_risk_pop:,.0f} ({100-coverage_rate:.1f}%)")
    
    # ========================================
    # 空白地帯をリスク加重人口順にソート
    # ========================================
    print("\n" + "=" * 70)
    print("🎯 AED設置推奨場所 TOP10（リスク加重人口累計順）")
    print("=" * 70)
    
    blank = chocho[chocho['500m以内AED数'] == 0].copy()
    blank = blank.sort_values('リスク加重人口_累計', ascending=False)
    
    print(f"\nAED空白地帯: {len(blank)}町丁")
    print("\n【推奨場所 TOP10】")
    print("-" * 70)
    
    recommendations = []
    for rank, (_, row) in enumerate(blank.head(10).iterrows(), 1):
        print(f"\n{rank}位: {row['区']} {row['町丁名']}")
        print(f"   リスク加重人口（累計）: {row['リスク加重人口_累計']:,.0f}")
        print(f"   総人口（累計）: {row['総人口_累計']:,.0f}")
        print(f"   最寄りAED: {row['最寄りAED距離_km']:.2f}km")
        print(f"   座標: ({row['緯度']:.6f}, {row['経度']:.6f})")
        
        recommendations.append({
            '順位': rank,
            '区': row['区'],
            '町丁名': row['町丁名'],
            'リスク加重人口_累計': int(row['リスク加重人口_累計']),
            '総人口_累計': int(row['総人口_累計']),
            '最寄りAED距離_km': round(row['最寄りAED距離_km'], 2),
            '緯度': row['緯度'],
            '経度': row['経度']
        })
    
    # 結果保存
    df_rec = pd.DataFrame(recommendations)
    df_rec.to_csv('future_aed_recommendations.csv', index=False, encoding='utf-8-sig')
    print(f"\n💾 推奨場所リスト保存: future_aed_recommendations.csv")
    
    # 全空白地帯リスト
    blank_out = blank[['区', '町丁名', '総人口_累計', 'リスク加重人口_累計', '最寄りAED距離_km', '緯度', '経度']]
    blank_out.to_csv('future_blank_areas.csv', index=False, encoding='utf-8-sig')
    print(f"💾 全空白地帯リスト保存: future_blank_areas.csv")
    
    # 全町丁データ
    chocho.to_csv('chocho_analysis_all_years.csv', index=False, encoding='utf-8-sig')
    
    print("\n✅ 分析完了!")
    
    return recommendations


if __name__ == '__main__':
    main()

