"""
川崎市AED最適配置分析 - 将来人口推計を加味したバージョン
- 2025年〜2070年の人口推計データを使用
- リスク加重人口の将来推移を分析
- 長期的に最適なAED配置を提案
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

# 年齢別リスク重み（東京消防庁「令和5年 救急活動の現況」に基づく）
# 出典: https://www.tfd.metro.tokyo.lg.jp/learning/elib/kyukyukatudojittai/r5.html
RISK_WEIGHTS = {
    '0〜4歳': 0.71, '5〜9歳': 0.16, '10〜14歳': 0.18, '15〜19歳': 0.51,
    '20〜24歳': 0.76, '25〜29歳': 0.43, '30〜34歳': 0.69, '35〜39歳': 0.57,
    '40〜44歳': 1.00, '45〜49歳': 1.12, '50〜54歳': 2.33, '55〜59歳': 2.59,
    '60〜64歳': 4.00, '65〜69歳': 4.35, '70〜74歳': 6.73, '75〜79歳': 11.63,
    '80〜84歳': 19.45, '85〜89歳': 30.78, '90〜94歳': 50.02, '95〜99歳': 72.24,
    '100歳以上': 35.56
}

# 分析対象年
TARGET_YEARS = {
    'R7': 2025, 'R12': 2030, 'R17': 2035, 'R22': 2040, 'R27': 2045,
    'R32': 2050, 'R37': 2055, 'R42': 2060, 'R47': 2065, 'R52': 2070
}


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


def calculate_risk_weighted_population(df):
    """リスク加重人口を計算"""
    df = df.copy()
    df['リスク重み'] = df['年齢5歳階級'].map(RISK_WEIGHTS)
    df['リスク加重人口'] = df['将来推計人口'] * df['リスク重み']
    return df


def analyze_by_chocho(df, df_aed):
    """町丁ごとの分析"""
    # 町丁ごとに集計（男女合計）
    chocho = df.groupby(['町丁コード', '行政区', '町丁名', 'X_CODE', 'Y_CODE']).agg({
        '将来推計人口': 'sum',
        'リスク加重人口': 'sum'
    }).reset_index()
    
    chocho.columns = ['町丁コード', '区', '町丁名', '経度', '緯度', '総人口', 'リスク加重人口']
    
    # 各町丁の最寄りAEDまでの距離と500m以内AED数を計算
    distances = []
    aed_counts = []
    
    for _, row in chocho.iterrows():
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
    
    chocho['最寄りAED距離_km'] = distances
    chocho['500m以内AED数'] = aed_counts
    
    return chocho


def main():
    print("=" * 70)
    print("🔮 川崎市AED最適配置分析 - 将来人口推計版")
    print("=" * 70)
    
    # AEDデータ読み込み
    print("\n📂 AEDデータ読み込み中...")
    df_aed = pd.read_csv(AED_FILE)
    print(f"  AED数: {len(df_aed)}")
    
    # 各年のデータを分析
    results = []
    
    for year_code, year in sorted(TARGET_YEARS.items(), key=lambda x: x[1]):
        print(f"\n📅 {year}年（{year_code}）を分析中...")
        
        # データ読み込み
        df = load_population_data(year_code)
        df = calculate_risk_weighted_population(df)
        
        # 町丁ごとの分析
        chocho = analyze_by_chocho(df, df_aed)
        
        # 統計計算
        total_pop = chocho['総人口'].sum()
        total_risk_pop = chocho['リスク加重人口'].sum()
        
        covered = chocho[chocho['500m以内AED数'] > 0]
        covered_pop = covered['総人口'].sum()
        covered_risk_pop = covered['リスク加重人口'].sum()
        
        coverage_rate = covered_pop / total_pop * 100
        risk_coverage_rate = covered_risk_pop / total_risk_pop * 100
        
        # 高齢者人口（65歳以上）
        elderly_ages = ['65〜69歳', '70〜74歳', '75〜79歳', '80〜84歳', '85〜89歳', '90〜94歳', '95〜99歳', '100歳以上']
        df_elderly = df[df['年齢5歳階級'].isin(elderly_ages)]
        elderly_pop = df_elderly['将来推計人口'].sum()
        elderly_rate = elderly_pop / total_pop * 100
        
        results.append({
            '年': year,
            '総人口': int(total_pop),
            '高齢者人口': int(elderly_pop),
            '高齢化率': round(elderly_rate, 1),
            'リスク加重人口': int(total_risk_pop),
            'カバー率': round(coverage_rate, 1),
            'リスク加重カバー率': round(risk_coverage_rate, 1),
            'カバー外人口': int(total_pop - covered_pop),
            'カバー外リスク加重人口': int(total_risk_pop - covered_risk_pop)
        })
        
        print(f"  総人口: {total_pop:,}人")
        print(f"  高齢化率: {elderly_rate:.1f}%")
        print(f"  カバー率: {coverage_rate:.1f}%")
        print(f"  リスク加重カバー率: {risk_coverage_rate:.1f}%")
        
        # 2025年と2045年のデータを保存
        if year in [2025, 2045]:
            chocho.to_csv(f'chocho_analysis_{year}.csv', index=False, encoding='utf-8-sig')
    
    # 結果をDataFrameに
    df_results = pd.DataFrame(results)
    df_results.to_csv('future_population_analysis.csv', index=False, encoding='utf-8-sig')
    
    # ========================================
    # 将来予測を加味したAED配置優先度
    # ========================================
    print("\n" + "=" * 70)
    print("🎯 将来を見据えたAED配置優先度分析")
    print("=" * 70)
    
    # 2025年と2045年のデータを比較
    df_2025 = load_population_data('R7')
    df_2025 = calculate_risk_weighted_population(df_2025)
    chocho_2025 = analyze_by_chocho(df_2025, df_aed)
    
    df_2045 = load_population_data('R27')
    df_2045 = calculate_risk_weighted_population(df_2045)
    chocho_2045 = analyze_by_chocho(df_2045, df_aed)
    
    # マージしてリスク加重人口の変化を計算
    merged = chocho_2025[['町丁コード', '区', '町丁名', '経度', '緯度', '総人口', 'リスク加重人口', '最寄りAED距離_km', '500m以内AED数']].copy()
    merged.columns = ['町丁コード', '区', '町丁名', '経度', '緯度', '人口_2025', 'リスク加重_2025', '最寄りAED距離_km', '500m以内AED数']
    
    merged = merged.merge(
        chocho_2045[['町丁コード', '総人口', 'リスク加重人口']].rename(
            columns={'総人口': '人口_2045', 'リスク加重人口': 'リスク加重_2045'}
        ),
        on='町丁コード', how='left'
    )
    
    merged['リスク加重変化'] = merged['リスク加重_2045'] - merged['リスク加重_2025']
    merged['リスク加重変化率'] = (merged['リスク加重_2045'] / merged['リスク加重_2025'] - 1) * 100
    
    # 空白地帯のみ
    blank = merged[merged['500m以内AED数'] == 0].copy()
    
    # 将来重視の優先度スコア
    # = 2045年リスク加重人口 × 0.5 + 2025年リスク加重人口 × 0.3 + リスク加重増加分 × 0.2
    blank['将来重視スコア'] = (
        blank['リスク加重_2045'] * 0.5 +
        blank['リスク加重_2025'] * 0.3 +
        blank['リスク加重変化'].clip(lower=0) * 0.2  # 増加分のみ考慮
    )
    
    # 正規化
    max_score = blank['将来重視スコア'].max()
    blank['将来重視スコア_正規化'] = blank['将来重視スコア'] / max_score * 100
    
    # 優先順位でソート
    priority = blank.sort_values('将来重視スコア_正規化', ascending=False)
    
    print("\n【将来を見据えたAED設置推奨場所 TOP10】")
    print("-" * 70)
    
    recommendations = []
    for rank, (_, row) in enumerate(priority.head(10).iterrows(), 1):
        change_str = f"+{row['リスク加重変化率']:.0f}%" if row['リスク加重変化率'] > 0 else f"{row['リスク加重変化率']:.0f}%"
        print(f"\n{rank}位: {row['区']} {row['町丁名']}")
        print(f"   将来重視スコア: {row['将来重視スコア_正規化']:.1f}")
        print(f"   2025年リスク加重人口: {row['リスク加重_2025']:,.0f}")
        print(f"   2045年リスク加重人口: {row['リスク加重_2045']:,.0f} ({change_str})")
        print(f"   最寄りAED: {row['最寄りAED距離_km']:.2f}km")
        
        recommendations.append({
            '順位': rank,
            '区': row['区'],
            '町丁名': row['町丁名'],
            '将来重視スコア': round(row['将来重視スコア_正規化'], 1),
            '人口_2025': int(row['人口_2025']),
            '人口_2045': int(row['人口_2045']),
            'リスク加重_2025': int(row['リスク加重_2025']),
            'リスク加重_2045': int(row['リスク加重_2045']),
            'リスク加重変化率': round(row['リスク加重変化率'], 1),
            '最寄りAED距離_km': round(row['最寄りAED距離_km'], 2),
            '緯度': row['緯度'],
            '経度': row['経度']
        })
    
    df_rec = pd.DataFrame(recommendations)
    df_rec.to_csv('future_aed_recommendations.csv', index=False, encoding='utf-8-sig')
    
    # ========================================
    # グラフ作成
    # ========================================
    print("\n📊 グラフ作成中...")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. 総人口と高齢化率の推移
    ax1 = axes[0, 0]
    ax1_twin = ax1.twinx()
    years = df_results['年']
    ax1.bar(years, df_results['総人口']/10000, color='steelblue', alpha=0.7, label='総人口')
    ax1_twin.plot(years, df_results['高齢化率'], 'ro-', linewidth=2, markersize=8, label='高齢化率')
    ax1.set_xlabel('年')
    ax1.set_ylabel('総人口（万人）', color='steelblue')
    ax1_twin.set_ylabel('高齢化率（%）', color='red')
    ax1.set_title('川崎市の人口と高齢化率の推移')
    ax1.legend(loc='upper left')
    ax1_twin.legend(loc='upper right')
    
    # 2. リスク加重人口の推移
    ax2 = axes[0, 1]
    ax2.plot(years, df_results['リスク加重人口']/10000, 'g^-', linewidth=2, markersize=8)
    ax2.set_xlabel('年')
    ax2.set_ylabel('リスク加重人口（万人）')
    ax2.set_title('心停止リスク加重人口の推移')
    ax2.grid(True, alpha=0.3)
    
    # 3. カバー率の推移（現状AED維持の場合）
    ax3 = axes[1, 0]
    ax3.plot(years, df_results['カバー率'], 'b-', linewidth=2, marker='o', label='シンプルカバー率')
    ax3.plot(years, df_results['リスク加重カバー率'], 'r--', linewidth=2, marker='s', label='リスク加重カバー率')
    ax3.set_xlabel('年')
    ax3.set_ylabel('カバー率（%）')
    ax3.set_title('AEDカバー率の推移（現状維持の場合）')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(90, 100)
    
    # 4. カバー外リスク加重人口の推移
    ax4 = axes[1, 1]
    ax4.bar(years, df_results['カバー外リスク加重人口']/1000, color='coral', alpha=0.8)
    ax4.set_xlabel('年')
    ax4.set_ylabel('カバー外リスク加重人口（千人）')
    ax4.set_title('AED空白地帯のリスク加重人口')
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('future_analysis_charts.png', dpi=150, bbox_inches='tight')
    print("💾 グラフ保存: future_analysis_charts.png")
    
    # ========================================
    # サマリー
    # ========================================
    print("\n" + "=" * 70)
    print("📋 分析サマリー")
    print("=" * 70)
    
    r_2025 = df_results[df_results['年'] == 2025].iloc[0]
    r_2045 = df_results[df_results['年'] == 2045].iloc[0]
    r_2070 = df_results[df_results['年'] == 2070].iloc[0]
    
    print(f"\n【人口推移】")
    print(f"  2025年: {r_2025['総人口']:,}人（高齢化率 {r_2025['高齢化率']}%）")
    print(f"  2045年: {r_2045['総人口']:,}人（高齢化率 {r_2045['高齢化率']}%）")
    print(f"  2070年: {r_2070['総人口']:,}人（高齢化率 {r_2070['高齢化率']}%）")
    
    print(f"\n【リスク加重人口の変化】")
    print(f"  2025年: {r_2025['リスク加重人口']:,}")
    print(f"  2045年: {r_2045['リスク加重人口']:,} ({(r_2045['リスク加重人口']/r_2025['リスク加重人口']-1)*100:+.1f}%)")
    print(f"  2070年: {r_2070['リスク加重人口']:,} ({(r_2070['リスク加重人口']/r_2025['リスク加重人口']-1)*100:+.1f}%)")
    
    print(f"\n【現状AED維持時のカバー率変化】")
    print(f"  2025年: {r_2025['リスク加重カバー率']}%")
    print(f"  2045年: {r_2045['リスク加重カバー率']}%")
    print(f"  2070年: {r_2070['リスク加重カバー率']}%")
    
    print("\n💾 結果保存:")
    print("  - future_population_analysis.csv")
    print("  - future_aed_recommendations.csv")
    print("  - chocho_analysis_2025.csv")
    print("  - chocho_analysis_2045.csv")
    print("  - future_analysis_charts.png")
    
    print("\n✅ 分析完了!")


if __name__ == '__main__':
    main()


