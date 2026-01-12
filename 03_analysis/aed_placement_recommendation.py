"""
川崎市AED最適配置推奨スクリプト
- AED設置優先順位の算出
- 設置場所の具体的な推奨
- カバー率改善シミュレーション
"""

import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import folium

def haversine_distance(lat1, lon1, lat2, lon2):
    """2点間の距離を計算（km）"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def calculate_coverage_improvement(new_lat, new_lon, df_chocho, current_coverage):
    """新しいAEDを設置した場合のカバー率改善を計算"""
    new_coverage = 0
    for _, row in df_chocho.iterrows():
        if pd.isna(row['緯度']) or row['総人口'] == 0:
            continue
        
        # 現在カバーされていない地域
        if row['500m以内AED数'] == 0:
            distance = haversine_distance(new_lat, new_lon, row['緯度'], row['経度'])
            if distance <= 0.5:
                new_coverage += row['総人口']
    
    return new_coverage

def main():
    print("=" * 70)
    print("🎯 川崎市AED最適配置推奨分析")
    print("=" * 70)
    
    # ========================================
    # データ読み込み
    # ========================================
    print("\n📂 データ読み込み中...")
    
    df_pop = pd.read_csv('../02_population_data/kawasaki_chocho_age_processed.csv')
    
    # 町丁ごとの集計
    df_chocho = df_pop.groupby(['町丁コード', '区', '町丁名', '緯度', '経度']).agg({
        '総人口': 'first',
        '高齢化率': 'first'
    }).reset_index()
    
    # 高齢者人口
    df_elderly = df_pop[df_pop['年齢5歳階級'].isin(['65〜69歳', '70〜74歳', '75〜79歳', '80〜84歳', '85〜89歳', '90〜94歳', '95歳以上'])]
    elderly_by_chocho = df_elderly.groupby('町丁コード')['人口'].sum().reset_index()
    elderly_by_chocho.columns = ['町丁コード', '高齢者人口']
    df_chocho = df_chocho.merge(elderly_by_chocho, on='町丁コード', how='left')
    
    # 後期高齢者人口（75歳以上）
    df_late_elderly = df_pop[df_pop['年齢5歳階級'].isin(['75〜79歳', '80〜84歳', '85〜89歳', '90〜94歳', '95歳以上'])]
    late_elderly = df_late_elderly.groupby('町丁コード')['人口'].sum().reset_index()
    late_elderly.columns = ['町丁コード', '後期高齢者人口']
    df_chocho = df_chocho.merge(late_elderly, on='町丁コード', how='left')
    
    # 分析結果をマージ
    df_result = pd.read_csv('aed_chocho_analysis_result.csv')
    df_chocho = df_chocho.merge(
        df_result[['町丁コード', '最寄りAED距離_km', '500m以内AED数', 'リスクスコア']],
        on='町丁コード', how='left'
    )
    
    df_aed = pd.read_csv('../01_aed_data/kawasaki_aed_merged.csv')
    
    print(f"  町丁数: {len(df_chocho)}")
    print(f"  現在のAED数: {len(df_aed)}")
    
    # ========================================
    # 現状の分析
    # ========================================
    print("\n" + "=" * 70)
    print("📊 現状分析")
    print("=" * 70)
    
    total_pop = df_chocho['総人口'].sum()
    covered_pop = df_chocho[df_chocho['500m以内AED数'] > 0]['総人口'].sum()
    coverage_rate = covered_pop / total_pop * 100
    
    total_elderly = df_chocho['高齢者人口'].sum()
    covered_elderly = df_chocho[df_chocho['500m以内AED数'] > 0]['高齢者人口'].sum()
    elderly_coverage = covered_elderly / total_elderly * 100
    
    print(f"\n【人口カバー率】")
    print(f"  総人口: {total_pop:,}人")
    print(f"  500m以内にAEDあり: {covered_pop:,}人 ({coverage_rate:.1f}%)")
    print(f"  カバー外: {total_pop - covered_pop:,}人 ({100-coverage_rate:.1f}%)")
    
    print(f"\n【高齢者カバー率】")
    print(f"  高齢者人口: {total_elderly:,}人")
    print(f"  500m以内にAEDあり: {covered_elderly:,}人 ({elderly_coverage:.1f}%)")
    print(f"  カバー外: {total_elderly - covered_elderly:,}人")
    
    # ========================================
    # AED設置優先度スコア計算
    # ========================================
    print("\n" + "=" * 70)
    print("🎯 AED設置優先順位算出")
    print("=" * 70)
    
    # 空白地帯のみを対象
    df_blank = df_chocho[(df_chocho['500m以内AED数'] == 0) & (df_chocho['総人口'] > 0)].copy()
    
    print(f"\nAED空白地帯: {len(df_blank)}町丁")
    
    # 優先度スコア計算
    # = 高齢者人口 × 0.4 + 後期高齢者人口 × 0.3 + 総人口 × 0.2 + 距離 × 0.1
    df_blank['高齢者_norm'] = (df_blank['高齢者人口'] / df_blank['高齢者人口'].max()) * 100
    df_blank['後期高齢者_norm'] = (df_blank['後期高齢者人口'] / df_blank['後期高齢者人口'].max()) * 100
    df_blank['人口_norm'] = (df_blank['総人口'] / df_blank['総人口'].max()) * 100
    df_blank['距離_norm'] = (df_blank['最寄りAED距離_km'] / df_blank['最寄りAED距離_km'].max()) * 100
    
    df_blank['設置優先度'] = (
        df_blank['高齢者_norm'] * 0.4 +
        df_blank['後期高齢者_norm'] * 0.3 +
        df_blank['人口_norm'] * 0.2 +
        df_blank['距離_norm'] * 0.1
    )
    
    # 優先順位でソート
    df_priority = df_blank.sort_values('設置優先度', ascending=False)
    
    # ========================================
    # TOP10推奨場所
    # ========================================
    print("\n【AED設置推奨場所 TOP10】")
    print("-" * 70)
    
    recommendations = []
    for rank, (_, row) in enumerate(df_priority.head(10).iterrows(), 1):
        print(f"\n{rank}位: {row['区']} {row['町丁名']}")
        print(f"   優先度スコア: {row['設置優先度']:.1f}")
        print(f"   総人口: {int(row['総人口']):,}人")
        print(f"   高齢者: {int(row['高齢者人口']):,}人 ({row['高齢化率']:.1f}%)")
        print(f"   後期高齢者(75+): {int(row['後期高齢者人口']):,}人")
        print(f"   最寄りAED: {row['最寄りAED距離_km']:.2f}km")
        print(f"   座標: ({row['緯度']:.6f}, {row['経度']:.6f})")
        
        recommendations.append({
            '順位': rank,
            '区': row['区'],
            '町丁名': row['町丁名'],
            '優先度スコア': round(row['設置優先度'], 1),
            '総人口': int(row['総人口']),
            '高齢者人口': int(row['高齢者人口']),
            '後期高齢者人口': int(row['後期高齢者人口']),
            '高齢化率': round(row['高齢化率'], 1),
            '最寄りAED距離_km': round(row['最寄りAED距離_km'], 2),
            '緯度': row['緯度'],
            '経度': row['経度']
        })
    
    # ========================================
    # カバー率改善シミュレーション
    # ========================================
    print("\n" + "=" * 70)
    print("📈 カバー率改善シミュレーション")
    print("=" * 70)
    
    print("\nTOP10の場所にAEDを設置した場合の効果:")
    print("-" * 70)
    
    cumulative_new_coverage = 0
    for i, rec in enumerate(recommendations):
        # この場所にAEDを置いた場合、新たにカバーされる人口を計算
        new_coverage = calculate_coverage_improvement(
            rec['緯度'], rec['経度'], df_chocho, None
        )
        cumulative_new_coverage += new_coverage
        
        new_coverage_rate = (covered_pop + cumulative_new_coverage) / total_pop * 100
        
        print(f"{i+1}. {rec['区']} {rec['町丁名']}")
        print(f"   新規カバー人口: +{new_coverage:,}人")
        print(f"   累計カバー率: {new_coverage_rate:.1f}% (+{new_coverage_rate - coverage_rate:.1f}%)")
    
    # ========================================
    # 結果保存
    # ========================================
    df_recommendations = pd.DataFrame(recommendations)
    df_recommendations.to_csv('aed_placement_recommendations.csv', index=False, encoding='utf-8-sig')
    print(f"\n💾 推奨場所リスト保存: aed_placement_recommendations.csv")
    
    # 全空白地帯の優先度リスト
    df_priority_all = df_priority[['区', '町丁名', '総人口', '高齢者人口', '後期高齢者人口', 
                                    '高齢化率', '最寄りAED距離_km', '設置優先度', '緯度', '経度']]
    df_priority_all.to_csv('aed_blank_areas_priority.csv', index=False, encoding='utf-8-sig')
    print(f"💾 全空白地帯優先度リスト保存: aed_blank_areas_priority.csv")
    
    # ========================================
    # 推奨場所マップ作成
    # ========================================
    print("\n🗺️  推奨場所マップ作成中...")
    
    center_lat = df_chocho['緯度'].mean()
    center_lon = df_chocho['経度'].mean()
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='cartodbpositron')
    
    # 既存AEDを薄く表示
    for _, aed in df_aed.iterrows():
        if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
            folium.CircleMarker(
                location=[aed['latitude'], aed['longitude']],
                radius=3,
                color='gray',
                fill=True,
                fillOpacity=0.3
            ).add_to(m)
    
    # 推奨場所を番号付きで表示
    for rec in recommendations:
        # 500mカバー範囲
        folium.Circle(
            location=[rec['緯度'], rec['経度']],
            radius=500,
            color='green',
            fill=True,
            fillOpacity=0.2,
            weight=2
        ).add_to(m)
        
        # マーカー
        popup_text = f"""
        <b>推奨 {rec['順位']}位: {rec['区']} {rec['町丁名']}</b><br>
        優先度: {rec['優先度スコア']}<br>
        総人口: {rec['総人口']:,}人<br>
        高齢者: {rec['高齢者人口']:,}人<br>
        後期高齢者: {rec['後期高齢者人口']:,}人<br>
        最寄りAED: {rec['最寄りAED距離_km']}km
        """
        
        folium.Marker(
            location=[rec['緯度'], rec['経度']],
            popup=folium.Popup(popup_text, max_width=250),
            icon=folium.DivIcon(
                html=f'<div style="font-size: 14pt; color: white; background-color: red; border-radius: 50%; width: 28px; height: 28px; text-align: center; line-height: 28px; font-weight: bold;">{rec["順位"]}</div>'
            )
        ).add_to(m)
    
    # 凡例
    legend_html = '''
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid gray; font-size: 12px;">
        <b>AED設置推奨場所</b><br>
        🔴 数字: 優先順位<br>
        🟢 円: 新規カバー範囲(500m)<br>
        ⚫ 点: 既存AED
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    m.save('aed_placement_recommendation_map.html')
    print("💾 推奨場所マップ保存: aed_placement_recommendation_map.html")
    
    # ========================================
    # サマリー
    # ========================================
    print("\n" + "=" * 70)
    print("📋 分析サマリー")
    print("=" * 70)
    print(f"\n現状:")
    print(f"  AED数: {len(df_aed)}台")
    print(f"  人口カバー率: {coverage_rate:.1f}%")
    print(f"  高齢者カバー率: {elderly_coverage:.1f}%")
    print(f"\nTOP10推奨場所にAED設置後:")
    final_coverage = (covered_pop + cumulative_new_coverage) / total_pop * 100
    print(f"  予測人口カバー率: {final_coverage:.1f}% (+{final_coverage - coverage_rate:.1f}%)")
    print(f"  新規カバー人口: {cumulative_new_coverage:,}人")
    
    print("\n✅ 分析完了!")

if __name__ == '__main__':
    main()



