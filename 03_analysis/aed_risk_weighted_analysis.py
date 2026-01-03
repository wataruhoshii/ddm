"""
川崎市AED最適配置分析（年齢別心停止リスク重み付け版）
- 疫学データに基づく年齢別リスク重み
- リスク加重人口での評価
"""

import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import folium

# 年齢別心停止リスク重み（40-44歳 = 1.0 基準）
# 院外心停止の疫学データに基づく推定
AGE_RISK_WEIGHTS = {
    '0〜4歳': 0.044,
    '5〜9歳': 0.022,
    '10〜14歳': 0.044,
    '15〜19歳': 0.111,
    '20〜24歳': 0.178,
    '25〜29歳': 0.267,
    '30〜34歳': 0.400,
    '35〜39歳': 0.622,
    '40〜44歳': 1.000,
    '45〜49歳': 1.556,
    '50〜54歳': 2.222,
    '55〜59歳': 3.111,
    '60〜64歳': 4.222,
    '65〜69歳': 5.778,
    '70〜74歳': 7.778,
    '75〜79歳': 10.000,
    '80〜84歳': 12.222,
    '85〜89歳': 14.444,
    '90〜94歳': 15.556,
    '95歳以上': 16.667
}

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def main():
    print("=" * 70)
    print("🎯 川崎市AED分析（年齢別心停止リスク重み付け版）")
    print("=" * 70)
    
    # ========================================
    # データ読み込み
    # ========================================
    print("\n📂 データ読み込み中...")
    
    df_pop = pd.read_csv('../02_population_data/kawasaki_chocho_age_processed.csv')
    df_aed = pd.read_csv('../01_aed_data/kawasaki_aed_merged.csv')
    
    # ========================================
    # リスク加重人口の計算
    # ========================================
    print("\n📊 リスク加重人口を計算中...")
    
    # 年齢階級ごとにリスク重みを適用
    df_pop['リスク重み'] = df_pop['年齢5歳階級'].map(AGE_RISK_WEIGHTS)
    df_pop['リスク加重人口'] = df_pop['人口'] * df_pop['リスク重み']
    
    # 町丁ごとに集計
    df_chocho = df_pop.groupby(['町丁コード', '区', '町丁名', '緯度', '経度']).agg({
        '総人口': 'first',
        '人口': 'sum',  # 確認用
        'リスク加重人口': 'sum'
    }).reset_index()
    
    # 高齢者関連も計算
    df_elderly = df_pop[df_pop['年齢5歳階級'].isin(['65〜69歳', '70〜74歳', '75〜79歳', '80〜84歳', '85〜89歳', '90〜94歳', '95歳以上'])]
    elderly_by_chocho = df_elderly.groupby('町丁コード').agg({
        '人口': 'sum',
        'リスク加重人口': 'sum'
    }).reset_index()
    elderly_by_chocho.columns = ['町丁コード', '高齢者人口', '高齢者リスク加重人口']
    df_chocho = df_chocho.merge(elderly_by_chocho, on='町丁コード', how='left')
    
    # リスク加重高齢化率
    df_chocho['リスク加重高齢化率'] = df_chocho['高齢者リスク加重人口'] / df_chocho['リスク加重人口'] * 100
    
    print(f"  町丁数: {len(df_chocho)}")
    print(f"  総人口: {df_chocho['総人口'].sum():,}")
    print(f"  リスク加重人口合計: {df_chocho['リスク加重人口'].sum():,.0f}")
    
    # ========================================
    # 最寄りAED距離を計算
    # ========================================
    print("\n📏 最寄りAED距離を計算中...")
    
    nearest_distances = []
    aed_count_500m = []
    
    for i, row in df_chocho.iterrows():
        if pd.isna(row['緯度']) or pd.isna(row['経度']):
            nearest_distances.append(None)
            aed_count_500m.append(0)
            continue
        
        distances = []
        for _, aed in df_aed.iterrows():
            if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
                d = haversine_distance(row['緯度'], row['経度'], aed['latitude'], aed['longitude'])
                distances.append(d)
        
        if distances:
            nearest_distances.append(min(distances))
            aed_count_500m.append(sum(1 for d in distances if d <= 0.5))
        else:
            nearest_distances.append(None)
            aed_count_500m.append(0)
        
        if (i + 1) % 100 == 0:
            print(f"  進捗: {i+1}/{len(df_chocho)}")
    
    df_chocho['最寄りAED距離_km'] = nearest_distances
    df_chocho['500m以内AED数'] = aed_count_500m
    
    # ========================================
    # リスク加重スコアの計算
    # ========================================
    print("\n📊 リスク加重スコア計算中...")
    
    df_valid = df_chocho[df_chocho['総人口'] > 0].copy()
    
    # 正規化（0-100）
    df_valid['リスク加重人口_norm'] = (df_valid['リスク加重人口'] / df_valid['リスク加重人口'].max()) * 100
    df_valid['距離_norm'] = (df_valid['最寄りAED距離_km'] / df_valid['最寄りAED距離_km'].max()) * 100
    
    # リスク加重スコア = リスク加重人口 × 0.6 + 距離 × 0.4
    df_valid['リスク加重スコア'] = (
        df_valid['リスク加重人口_norm'] * 0.6 +
        df_valid['距離_norm'] * 0.4
    )
    
    # ========================================
    # 結果出力
    # ========================================
    print("\n" + "=" * 70)
    print("📈 分析結果（リスク加重版）")
    print("=" * 70)
    
    # 全体統計
    total_risk_pop = df_valid['リスク加重人口'].sum()
    covered_risk_pop = df_valid[df_valid['500m以内AED数'] > 0]['リスク加重人口'].sum()
    risk_coverage = covered_risk_pop / total_risk_pop * 100
    
    print(f"\n【リスク加重人口カバー率】")
    print(f"  リスク加重人口合計: {total_risk_pop:,.0f}")
    print(f"  500m以内にAEDあり: {covered_risk_pop:,.0f} ({risk_coverage:.1f}%)")
    print(f"  カバー外: {total_risk_pop - covered_risk_pop:,.0f} ({100-risk_coverage:.1f}%)")
    
    # 従来の人口ベースとの比較
    total_pop = df_valid['総人口'].sum()
    covered_pop = df_valid[df_valid['500m以内AED数'] > 0]['総人口'].sum()
    pop_coverage = covered_pop / total_pop * 100
    
    print(f"\n【比較: 単純人口 vs リスク加重人口】")
    print(f"  単純人口カバー率: {pop_coverage:.1f}%")
    print(f"  リスク加重カバー率: {risk_coverage:.1f}%")
    print(f"  差: {risk_coverage - pop_coverage:+.1f}%")
    
    # 空白地帯
    blank_areas = df_valid[df_valid['500m以内AED数'] == 0]
    print(f"\n【AED空白地帯（500m圏外）】")
    print(f"  町丁数: {len(blank_areas)}")
    print(f"  リスク加重人口: {blank_areas['リスク加重人口'].sum():,.0f}")
    
    # リスク加重スコア上位
    print(f"\n【リスク加重スコア上位15町丁（AED設置推奨）】")
    print("-" * 70)
    top_risk = df_valid.nlargest(15, 'リスク加重スコア')[
        ['区', '町丁名', '総人口', 'リスク加重人口', '高齢者人口', '最寄りAED距離_km', '500m以内AED数', 'リスク加重スコア']
    ].copy()
    top_risk['リスク加重人口'] = top_risk['リスク加重人口'].round(0).astype(int)
    top_risk['最寄りAED距離_km'] = top_risk['最寄りAED距離_km'].round(2)
    top_risk['リスク加重スコア'] = top_risk['リスク加重スコア'].round(1)
    print(top_risk.to_string(index=False))
    
    # 空白地帯のリスク加重人口上位
    print(f"\n【AED空白地帯のリスク加重人口上位10】")
    print("-" * 70)
    top_blank = blank_areas.nlargest(10, 'リスク加重人口')[
        ['区', '町丁名', '総人口', 'リスク加重人口', '高齢者人口', '最寄りAED距離_km']
    ].copy()
    top_blank['リスク加重人口'] = top_blank['リスク加重人口'].round(0).astype(int)
    top_blank['最寄りAED距離_km'] = top_blank['最寄りAED距離_km'].round(2)
    print(top_blank.to_string(index=False))
    
    # ========================================
    # 年齢別リスク寄与度
    # ========================================
    print(f"\n【年齢別リスク寄与度（全市）】")
    print("-" * 70)
    
    age_contribution = df_pop.groupby('年齢5歳階級').agg({
        '人口': 'sum',
        'リスク加重人口': 'sum'
    }).reset_index()
    age_contribution['リスク寄与率(%)'] = age_contribution['リスク加重人口'] / age_contribution['リスク加重人口'].sum() * 100
    age_contribution['人口構成比(%)'] = age_contribution['人口'] / age_contribution['人口'].sum() * 100
    
    # 年齢順にソート
    age_order = list(AGE_RISK_WEIGHTS.keys())
    age_contribution['順序'] = age_contribution['年齢5歳階級'].map({v: i for i, v in enumerate(age_order)})
    age_contribution = age_contribution.sort_values('順序')
    
    print(age_contribution[['年齢5歳階級', '人口', '人口構成比(%)', 'リスク加重人口', 'リスク寄与率(%)']].to_string(index=False))
    
    # ========================================
    # 結果保存
    # ========================================
    df_valid.to_csv('aed_risk_weighted_analysis_result.csv', index=False, encoding='utf-8-sig')
    print(f"\n💾 結果保存: aed_risk_weighted_analysis_result.csv")
    
    # ========================================
    # 推奨場所（リスク加重版）
    # ========================================
    print("\n" + "=" * 70)
    print("🎯 AED設置推奨場所（リスク加重版）TOP10")
    print("=" * 70)
    
    # 空白地帯のみ
    df_blank = df_valid[df_valid['500m以内AED数'] == 0].copy()
    df_priority = df_blank.nlargest(10, 'リスク加重人口')
    
    recommendations = []
    for rank, (_, row) in enumerate(df_priority.iterrows(), 1):
        print(f"\n{rank}位: {row['区']} {row['町丁名']}")
        print(f"   リスク加重人口: {row['リスク加重人口']:,.0f}")
        print(f"   総人口: {int(row['総人口']):,}人")
        print(f"   高齢者: {int(row['高齢者人口']):,}人")
        print(f"   最寄りAED: {row['最寄りAED距離_km']:.2f}km")
        
        recommendations.append({
            '順位': rank,
            '区': row['区'],
            '町丁名': row['町丁名'],
            'リスク加重人口': int(row['リスク加重人口']),
            '総人口': int(row['総人口']),
            '高齢者人口': int(row['高齢者人口']),
            '最寄りAED距離_km': round(row['最寄りAED距離_km'], 2),
            '緯度': row['緯度'],
            '経度': row['経度']
        })
    
    df_rec = pd.DataFrame(recommendations)
    df_rec.to_csv('aed_placement_recommendations_risk_weighted.csv', index=False, encoding='utf-8-sig')
    print(f"\n💾 推奨場所保存: aed_placement_recommendations_risk_weighted.csv")
    
    print("\n✅ 分析完了!")

if __name__ == '__main__':
    main()

