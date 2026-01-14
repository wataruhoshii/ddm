"""
川崎市AED最適配置分析 - 一様分布モデル
- 各町丁のポリゴン内に人口が一様に分布していると仮定
- グリッド点を生成してカバー率を計算
"""

import shapefile
from shapely.geometry import shape, Point
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import os

# ========================================
# 設定
# ========================================
ESTATS_DIR = '../estats'
AED_FILE = '../01_aed_data/kawasaki_aed_merged.csv'
POPULATION_DIR = '../kawasakishi_data'
GRID_SPACING = 50  # グリッド間隔（メートル）
COVER_DISTANCE = 300  # カバー範囲（メートル）

# 区コード
# ※ e-Statのシェープファイルでは14135と14136の町丁が入れ替わっているため
#    人口データとマッチングするために区名を入れ替え
WARD_CODES = {
    '14131': '川崎区',
    '14132': '幸区',
    '14133': '中原区',
    '14134': '高津区',
    '14135': '多摩区',  # e-Statでは宮前区コードだが、町丁名は多摩区のもの
    '14136': '宮前区',  # e-Statでは多摩区コードだが、町丁名は宮前区のもの
    '14137': '麻生区',
}

# 年齢別リスク重み（東京消防庁「令和5年 救急活動の現況」に基づく）
# 出典: https://www.tfd.metro.tokyo.lg.jp/learning/elib/kyukyukatudojittai/r5.html
RISK_WEIGHTS = {
    '0〜4歳': 0.71, '5〜9歳': 0.16, '10〜14歳': 0.18, '15〜19歳': 0.51,
    '20〜24歳': 0.76, '25〜29歳': 0.43, '30〜34歳': 0.69, '35〜39歳': 0.57,
    '40〜44歳': 1.00, '45〜49歳': 1.12, '50〜54歳': 2.33, '55〜59歳': 2.59,
    '60〜64歳': 4.00, '65〜69歳': 4.35, '70〜74歳': 6.73, '75〜79歳': 11.63,
    '80〜84歳': 19.45, '85〜89歳': 30.78, '90〜94歳': 50.02, '95〜99歳': 72.24,
    '100歳以上': 72.24
}

TARGET_YEARS = ['R7', 'R12', 'R17', 'R22', 'R27', 'R32', 'R37', 'R42', 'R47', 'R52']


def haversine_distance(lat1, lon1, lat2, lon2):
    """2点間の距離を計算（メートル）"""
    R = 6371000  # 地球の半径（メートル）
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def meters_to_degrees(meters, latitude):
    """メートルを緯度経度の度数に変換（近似）"""
    # 緯度1度 ≈ 111km
    lat_deg = meters / 111000
    # 経度1度 ≈ 111km * cos(緯度)
    lon_deg = meters / (111000 * cos(radians(latitude)))
    return lat_deg, lon_deg


def generate_grid_points(polygon, spacing_m=50):
    """ポリゴン内にグリッド点を生成"""
    minx, miny, maxx, maxy = polygon.bounds
    
    # グリッド間隔を度数に変換
    center_lat = (miny + maxy) / 2
    lat_spacing, lon_spacing = meters_to_degrees(spacing_m, center_lat)
    
    points = []
    y = miny
    while y <= maxy:
        x = minx
        while x <= maxx:
            p = Point(x, y)
            if polygon.contains(p):
                points.append((y, x))  # (緯度, 経度)
            x += lon_spacing
        y += lat_spacing
    
    return points


def load_shapefiles():
    """全区のShapefileを読み込み"""
    all_features = []
    
    for code, ward in WARD_CODES.items():
        shp_path = f'{ESTATS_DIR}/A002005212020DDSWC{code}/r2ka{code}.shp'
        
        if not os.path.exists(shp_path):
            print(f"  ⚠️ {ward}のShapefileが見つかりません")
            continue
        
        sf = shapefile.Reader(shp_path, encoding='shift_jis')
        
        for sr in sf.shapeRecords():
            rec = sr.record
            geom = shape(sr.shape.__geo_interface__)
            
            # S_NAMEフィールドのインデックスを取得
            field_names = [f[0] for f in sf.fields[1:]]
            s_name_idx = field_names.index('S_NAME') if 'S_NAME' in field_names else None
            key_code_idx = field_names.index('KEY_CODE') if 'KEY_CODE' in field_names else None
            
            all_features.append({
                'ward': ward,
                'chocho_name': rec[s_name_idx] if s_name_idx else '',
                'key_code': rec[key_code_idx] if key_code_idx else '',
                'geometry': geom
            })
    
    return all_features


def load_population_data():
    """人口推計データを読み込み（全年次合計）"""
    all_data = []
    
    for year_code in TARGET_YEARS:
        file_path = f"{POPULATION_DIR}/町丁別将来人口推計({year_code}).csv"
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, encoding='shift_jis')
            df['リスク重み'] = df['年齢5歳階級'].map(RISK_WEIGHTS)
            df['リスク加重人口'] = df['将来推計人口'] * df['リスク重み']
            all_data.append(df)
    
    df_all = pd.concat(all_data, ignore_index=True)
    
    # 町丁ごとに合計
    pop_by_chocho = df_all.groupby(['行政区', '町丁名']).agg({
        '将来推計人口': 'sum',
        'リスク加重人口': 'sum'
    }).reset_index()
    
    pop_by_chocho.columns = ['区', '町丁名', '総人口_累計', 'リスク加重人口_累計']
    
    return pop_by_chocho


def main():
    print("=" * 70)
    print("🗺️  川崎市AED最適配置分析 - 一様分布モデル")
    print("=" * 70)
    print(f"グリッド間隔: {GRID_SPACING}m")
    print(f"カバー距離: {COVER_DISTANCE}m")
    
    # ========================================
    # データ読み込み
    # ========================================
    print("\n📂 データ読み込み中...")
    
    # AEDデータ
    df_aed = pd.read_csv(AED_FILE)
    aed_locations = df_aed[['latitude', 'longitude']].dropna().values.tolist()
    print(f"  AED数: {len(aed_locations)}")
    
    # Shapefile
    print("  町丁ポリゴン読み込み中...")
    features = load_shapefiles()
    print(f"  町丁数: {len(features)}")
    
    # 人口データ
    print("  人口データ読み込み中...")
    pop_data = load_population_data()
    print(f"  人口データ: {len(pop_data)}件")
    
    # ========================================
    # 各町丁のカバー率計算
    # ========================================
    print("\n📊 カバー率計算中...")
    print("  （グリッド点生成 → AED距離計算 → カバー率算出）")
    
    results = []
    total = len(features)
    
    for i, feat in enumerate(features):
        if (i + 1) % 50 == 0 or (i + 1) == total:
            print(f"  進捗: {i+1}/{total} ({(i+1)/total*100:.0f}%)")
        
        polygon = feat['geometry']
        ward = feat['ward']
        chocho_name = feat['chocho_name']
        
        # ポリゴンの重心座標を取得
        centroid = polygon.centroid
        centroid_lat = centroid.y
        centroid_lon = centroid.x
        
        # グリッド点生成
        grid_points = generate_grid_points(polygon, GRID_SPACING)
        
        if len(grid_points) == 0:
            # ポリゴンが小さすぎる場合は中心点を使用
            centroid = polygon.centroid
            grid_points = [(centroid.y, centroid.x)]
        
        # 各グリッド点のカバー状況を判定
        covered_count = 0
        min_distance = float('inf')
        
        for lat, lon in grid_points:
            # 最寄りAEDまでの距離
            for aed_lat, aed_lon in aed_locations:
                dist = haversine_distance(lat, lon, aed_lat, aed_lon)
                if dist < min_distance:
                    min_distance = dist
                if dist <= COVER_DISTANCE:
                    covered_count += 1
                    break  # この点はカバーされている
        
        coverage_rate = covered_count / len(grid_points) if grid_points else 0
        
        # 人口データとマッチング
        pop_row = pop_data[(pop_data['区'] == ward) & (pop_data['町丁名'] == chocho_name)]
        
        if not pop_row.empty:
            total_pop = pop_row['総人口_累計'].values[0]
            risk_pop = pop_row['リスク加重人口_累計'].values[0]
        else:
            total_pop = 0
            risk_pop = 0
        
        covered_pop = total_pop * coverage_rate
        covered_risk_pop = risk_pop * coverage_rate
        
        results.append({
            '区': ward,
            '町丁名': chocho_name,
            '緯度': round(centroid_lat, 6),
            '経度': round(centroid_lon, 6),
            'グリッド点数': len(grid_points),
            'カバー率': round(coverage_rate * 100, 1),
            '総人口_累計': int(total_pop),
            'カバー人口_累計': int(covered_pop),
            'リスク加重人口_累計': int(risk_pop),
            'カバーリスク加重人口_累計': int(covered_risk_pop),
            '最寄りAED距離_m': int(min_distance) if min_distance != float('inf') else None
        })
    
    # ========================================
    # 結果集計
    # ========================================
    df_results = pd.DataFrame(results)
    
    print("\n" + "=" * 70)
    print("📊 分析結果")
    print("=" * 70)
    
    total_pop = df_results['総人口_累計'].sum()
    covered_pop = df_results['カバー人口_累計'].sum()
    total_risk = df_results['リスク加重人口_累計'].sum()
    covered_risk = df_results['カバーリスク加重人口_累計'].sum()
    
    print(f"\n【一様分布モデルによるカバー率】")
    print(f"  総人口（累計）: {total_pop:,}")
    print(f"  カバー人口: {covered_pop:,} ({covered_pop/total_pop*100:.1f}%)")
    print(f"  カバー外人口: {total_pop - covered_pop:,} ({(total_pop-covered_pop)/total_pop*100:.1f}%)")
    print(f"\n  リスク加重人口（累計）: {total_risk:,}")
    print(f"  カバーリスク加重人口: {covered_risk:,} ({covered_risk/total_risk*100:.1f}%)")
    print(f"  カバー外リスク加重人口: {total_risk - covered_risk:,}")
    
    # ========================================
    # カバー率が低い町丁（優先設置候補）
    # ========================================
    print("\n" + "=" * 70)
    print("🎯 AED設置推奨地域 TOP10（カバー外リスク加重人口順）")
    print("=" * 70)
    
    df_results['カバー外リスク加重人口'] = df_results['リスク加重人口_累計'] - df_results['カバーリスク加重人口_累計']
    df_priority = df_results.sort_values('カバー外リスク加重人口', ascending=False)
    
    print("\n【推奨場所 TOP10】")
    for rank, (_, row) in enumerate(df_priority.head(10).iterrows(), 1):
        print(f"\n{rank}位: {row['区']} {row['町丁名']}")
        print(f"   カバー率: {row['カバー率']}%")
        print(f"   カバー外リスク加重人口: {row['カバー外リスク加重人口']:,}")
        print(f"   最寄りAED: {row['最寄りAED距離_m']}m")
    
    # ========================================
    # 結果保存
    # ========================================
    df_results.to_csv('uniform_model_results.csv', index=False, encoding='utf-8-sig')
    df_priority.head(20).to_csv('uniform_model_recommendations.csv', index=False, encoding='utf-8-sig')
    
    print(f"\n💾 結果保存:")
    print(f"  - uniform_model_results.csv")
    print(f"  - uniform_model_recommendations.csv")
    
    print("\n✅ 分析完了!")
    
    return df_results


if __name__ == '__main__':
    main()

