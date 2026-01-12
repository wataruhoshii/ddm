"""
川崎市AED最適配置分析（町丁レベル・空間分析）
- 町丁別人口データとAEDデータを組み合わせ
- 各町丁からAEDまでの距離を計算
- AED空白地帯・高リスク地域を特定
"""

import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import matplotlib.pyplot as plt
import matplotlib
import re

# 日本語フォント設定
matplotlib.rcParams['font.family'] = ['Hiragino Sans', 'Arial Unicode MS', 'sans-serif']

def haversine_distance(lat1, lon1, lat2, lon2):
    """2点間の距離を計算（km）"""
    R = 6371  # 地球の半径（km）
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def extract_chocho_from_address(address, ward):
    """住所から町丁名を抽出"""
    if pd.isna(address):
        return None
    
    addr = str(address)
    # 区名を削除
    addr = re.sub(r'^神奈川県川崎市', '', addr)
    addr = re.sub(r'^(川崎区|幸区|中原区|高津区|宮前区|多摩区|麻生区)', '', addr)
    
    # 丁目付きの町名を抽出
    match = re.match(r'([^0-9０-９]+[0-9０-９]*丁目)', addr)
    if match:
        chocho = match.group(1)
        # 数字を全角に統一
        chocho = chocho.replace('1', '１').replace('2', '２').replace('3', '３')
        chocho = chocho.replace('4', '４').replace('5', '５').replace('6', '６')
        chocho = chocho.replace('7', '７').replace('8', '８').replace('9', '９').replace('0', '０')
        return chocho
    
    # 丁目なしの町名
    match = re.match(r'([^0-9０-９\-ー]+)', addr)
    if match:
        return match.group(1).strip()
    
    return None

def main():
    print("=" * 70)
    print("🏥 川崎市AED最適配置分析（町丁レベル・空間分析）")
    print("=" * 70)
    
    # ========================================
    # データ読み込み
    # ========================================
    print("\n📂 データ読み込み中...")
    
    # 人口データ（ロング形式）
    df_pop = pd.read_csv('../02_population_data/kawasaki_chocho_age_processed.csv')
    
    # 町丁ごとの集計データを作成
    df_chocho = df_pop.groupby(['町丁コード', '区', '町丁名', '緯度', '経度']).agg({
        '総人口': 'first',
        '高齢化率': 'first',
        '後期高齢化率': 'first'
    }).reset_index()
    
    # 高齢者人口を計算（65歳以上）
    df_elderly = df_pop[df_pop['年齢5歳階級'].isin(['65〜69歳', '70〜74歳', '75〜79歳', '80〜84歳', '85〜89歳', '90〜94歳', '95歳以上'])]
    elderly_by_chocho = df_elderly.groupby('町丁コード')['人口'].sum().reset_index()
    elderly_by_chocho.columns = ['町丁コード', '高齢者人口']
    df_chocho = df_chocho.merge(elderly_by_chocho, on='町丁コード', how='left')
    
    print(f"  町丁数: {len(df_chocho)}")
    print(f"  総人口: {df_chocho['総人口'].sum():,}")
    
    # AEDデータ
    df_aed = pd.read_csv('../01_aed_data/kawasaki_aed_merged.csv')
    print(f"  AED数: {len(df_aed)}")
    
    # ========================================
    # 各町丁から最寄りAEDまでの距離を計算
    # ========================================
    print("\n📏 各町丁から最寄りAEDまでの距離を計算中...")
    
    nearest_distances = []
    nearest_aed_names = []
    aed_count_500m = []  # 500m以内のAED数
    aed_count_1km = []   # 1km以内のAED数
    
    for i, row in df_chocho.iterrows():
        if pd.isna(row['緯度']) or pd.isna(row['経度']):
            nearest_distances.append(None)
            nearest_aed_names.append(None)
            aed_count_500m.append(0)
            aed_count_1km.append(0)
            continue
        
        # 全AEDまでの距離を計算
        distances = []
        for j, aed in df_aed.iterrows():
            if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
                d = haversine_distance(row['緯度'], row['経度'], aed['latitude'], aed['longitude'])
                distances.append((d, aed['name']))
        
        if distances:
            distances.sort(key=lambda x: x[0])
            nearest_distances.append(distances[0][0])
            nearest_aed_names.append(distances[0][1])
            aed_count_500m.append(sum(1 for d, _ in distances if d <= 0.5))
            aed_count_1km.append(sum(1 for d, _ in distances if d <= 1.0))
        else:
            nearest_distances.append(None)
            nearest_aed_names.append(None)
            aed_count_500m.append(0)
            aed_count_1km.append(0)
        
        if (i + 1) % 100 == 0:
            print(f"  進捗: {i+1}/{len(df_chocho)}")
    
    df_chocho['最寄りAED距離_km'] = nearest_distances
    df_chocho['最寄りAED名'] = nearest_aed_names
    df_chocho['500m以内AED数'] = aed_count_500m
    df_chocho['1km以内AED数'] = aed_count_1km
    
    # ========================================
    # リスクスコア計算
    # ========================================
    print("\n📊 リスクスコア計算中...")
    
    # 人口0の町丁を除外
    df_valid = df_chocho[df_chocho['総人口'] > 0].copy()
    
    # 各指標を正規化（0-100）
    df_valid['高齢化率_norm'] = (df_valid['高齢化率'] - df_valid['高齢化率'].min()) / (df_valid['高齢化率'].max() - df_valid['高齢化率'].min()) * 100
    df_valid['距離_norm'] = (df_valid['最寄りAED距離_km'] - df_valid['最寄りAED距離_km'].min()) / (df_valid['最寄りAED距離_km'].max() - df_valid['最寄りAED距離_km'].min()) * 100
    
    # 人口密度を考慮（人口が多いほどAEDの必要性が高い）
    df_valid['人口_norm'] = (df_valid['総人口'] - df_valid['総人口'].min()) / (df_valid['総人口'].max() - df_valid['総人口'].min()) * 100
    
    # リスクスコア = 高齢化率 × 0.3 + 距離 × 0.4 + 人口規模 × 0.3
    df_valid['リスクスコア'] = (
        df_valid['高齢化率_norm'] * 0.3 +
        df_valid['距離_norm'] * 0.4 +
        df_valid['人口_norm'] * 0.3
    )
    
    # ========================================
    # 結果出力
    # ========================================
    print("\n" + "=" * 70)
    print("📈 分析結果")
    print("=" * 70)
    
    # AED空白地帯（500m以内にAEDがない）
    no_aed_500m = df_valid[df_valid['500m以内AED数'] == 0]
    print(f"\n【AED空白地帯（500m以内にAEDなし）】")
    print(f"  該当町丁数: {len(no_aed_500m)} / {len(df_valid)} ({len(no_aed_500m)/len(df_valid)*100:.1f}%)")
    print(f"  影響人口: {no_aed_500m['総人口'].sum():,} 人")
    print(f"  影響高齢者: {no_aed_500m['高齢者人口'].sum():,} 人")
    
    # 区別統計
    print(f"\n【区別 AED空白地帯】")
    ward_stats = no_aed_500m.groupby('区').agg({
        '町丁コード': 'count',
        '総人口': 'sum',
        '高齢者人口': 'sum'
    }).rename(columns={'町丁コード': '空白町丁数'})
    ward_stats = ward_stats.sort_values('高齢者人口', ascending=False)
    print(ward_stats.to_string())
    
    # リスクスコア上位
    print(f"\n【リスクスコア上位20町丁】")
    top_risk = df_valid.nlargest(20, 'リスクスコア')[['区', '町丁名', '総人口', '高齢者人口', '高齢化率', '最寄りAED距離_km', '500m以内AED数', 'リスクスコア']]
    top_risk['最寄りAED距離_km'] = top_risk['最寄りAED距離_km'].round(2)
    top_risk['リスクスコア'] = top_risk['リスクスコア'].round(1)
    print(top_risk.to_string(index=False))
    
    # 高齢者が多くAEDが遠い地域
    print(f"\n【高齢者1000人以上 & 最寄りAED 500m以上】")
    high_risk_elderly = df_valid[(df_valid['高齢者人口'] >= 1000) & (df_valid['最寄りAED距離_km'] >= 0.5)]
    high_risk_elderly = high_risk_elderly.sort_values('高齢者人口', ascending=False)
    if len(high_risk_elderly) > 0:
        print(high_risk_elderly[['区', '町丁名', '総人口', '高齢者人口', '高齢化率', '最寄りAED距離_km']].head(15).to_string(index=False))
    else:
        print("  該当なし")
    
    # ========================================
    # 結果保存
    # ========================================
    output_file = 'aed_chocho_analysis_result.csv'
    df_valid.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n💾 結果保存: {output_file}")
    
    # ========================================
    # 可視化
    # ========================================
    print("\n📊 グラフ作成中...")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    
    # 1. 区別AED空白地帯の人口
    ax1 = axes[0, 0]
    ward_order = ['川崎区', '幸区', '中原区', '高津区', '宮前区', '多摩区', '麻生区']
    ward_stats_ordered = ward_stats.reindex(ward_order).fillna(0)
    bars = ax1.bar(ward_stats_ordered.index, ward_stats_ordered['高齢者人口'], color='coral')
    ax1.set_title('区別 AED空白地帯（500m圏外）の高齢者人口', fontsize=12, fontweight='bold')
    ax1.set_ylabel('高齢者人口（人）')
    ax1.tick_params(axis='x', rotation=45)
    for bar, val in zip(bars, ward_stats_ordered['高齢者人口']):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 100, f'{int(val):,}', ha='center', va='bottom', fontsize=9)
    
    # 2. 最寄りAED距離の分布
    ax2 = axes[0, 1]
    distances = df_valid['最寄りAED距離_km'].dropna()
    ax2.hist(distances, bins=30, color='steelblue', edgecolor='white', alpha=0.8)
    ax2.axvline(x=0.5, color='red', linestyle='--', label='500m')
    ax2.axvline(x=1.0, color='orange', linestyle='--', label='1km')
    ax2.set_title('最寄りAEDまでの距離分布', fontsize=12, fontweight='bold')
    ax2.set_xlabel('距離（km）')
    ax2.set_ylabel('町丁数')
    ax2.legend()
    
    # 3. 高齢化率 vs 最寄りAED距離
    ax3 = axes[1, 0]
    scatter = ax3.scatter(df_valid['高齢化率'], df_valid['最寄りAED距離_km'], 
                          c=df_valid['総人口'], cmap='YlOrRd', alpha=0.6, s=20)
    ax3.axhline(y=0.5, color='red', linestyle='--', alpha=0.5)
    ax3.set_title('高齢化率 vs 最寄りAED距離（色：人口）', fontsize=12, fontweight='bold')
    ax3.set_xlabel('高齢化率（%）')
    ax3.set_ylabel('最寄りAED距離（km）')
    plt.colorbar(scatter, ax=ax3, label='総人口')
    
    # 4. リスクスコア上位10
    ax4 = axes[1, 1]
    top10 = df_valid.nlargest(10, 'リスクスコア')
    y_pos = range(len(top10))
    bars = ax4.barh(y_pos, top10['リスクスコア'], color='crimson', alpha=0.8)
    ax4.set_yticks(y_pos)
    ax4.set_yticklabels([f"{row['区']} {row['町丁名']}" for _, row in top10.iterrows()], fontsize=9)
    ax4.set_title('リスクスコア上位10町丁', fontsize=12, fontweight='bold')
    ax4.set_xlabel('リスクスコア')
    ax4.invert_yaxis()
    
    plt.tight_layout()
    plt.savefig('aed_chocho_analysis.png', dpi=150, bbox_inches='tight')
    print("📊 グラフ保存: aed_chocho_analysis.png")
    
    print("\n✅ 分析完了!")

if __name__ == '__main__':
    main()



