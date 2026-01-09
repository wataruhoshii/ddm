"""
グリッドレベルでのAED設置推奨場所分析（高速版）
scipy.spatial.cKDTreeで空間検索を高速化
"""
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import os
from shapely.geometry import shape, Point
import shapefile
from scipy.spatial import cKDTree
import time

# ========================================
# 設定
# ========================================
GRID_SPACING = 50  # グリッド間隔（メートル）
COVER_DISTANCE = 300  # カバー範囲（メートル）
AED_FILE = '../01_aed_data/kawasaki_aed_merged.csv'
ESTATS_DIR = '../estats'

WARD_CODES = {
    '14131': '川崎区', '14132': '幸区', '14133': '中原区',
    '14134': '高津区', '14135': '多摩区', '14136': '宮前区', '14137': '麻生区'
}

# 緯度経度→メートル変換用（川崎市付近）
LAT_TO_M = 111000
LON_TO_M = 111000 * cos(radians(35.55))

def meters_to_degrees(meters, latitude=35.55):
    lat_deg = meters / 111000
    lon_deg = meters / (111000 * cos(radians(latitude)))
    return lat_deg, lon_deg

def generate_grid_points(polygon, spacing_m=50):
    """ポリゴン内にグリッド点を生成"""
    minx, miny, maxx, maxy = polygon.bounds
    center_lat = (miny + maxy) / 2
    lat_spacing, lon_spacing = meters_to_degrees(spacing_m, center_lat)
    
    points = []
    y = miny
    while y <= maxy:
        x = minx
        while x <= maxx:
            p = Point(x, y)
            if polygon.contains(p):
                points.append((y, x))
            x += lon_spacing
        y += lat_spacing
    return points

def load_shapefiles():
    """全区のShapefileを読み込み"""
    all_features = []
    
    for code, ward in WARD_CODES.items():
        shp_path = f'{ESTATS_DIR}/A002005212020DDSWC{code}/r2ka{code}.shp'
        if not os.path.exists(shp_path):
            continue
        
        sf = shapefile.Reader(shp_path, encoding='shift_jis')
        field_names = [f[0] for f in sf.fields[1:]]
        s_name_idx = field_names.index('S_NAME') if 'S_NAME' in field_names else None
        
        for sr in sf.shapeRecords():
            if s_name_idx is not None:
                chocho_name = sr.record[s_name_idx]
                if chocho_name:
                    all_features.append({
                        'ward': ward,
                        'chocho_name': chocho_name,
                        'geometry': shape(sr.shape.__geo_interface__)
                    })
    return all_features

def load_population_data():
    """人口データを読み込み"""
    df = pd.read_csv('chocho_analysis_all_years.csv')
    df_agg = df.groupby(['区', '町丁名']).agg({
        '総人口_累計': 'first',
        'リスク加重人口_累計': 'first'
    }).reset_index()
    return df_agg

def main():
    start_time = time.time()
    
    print("=" * 70)
    print("🎯 グリッドレベルAED設置推奨分析（高速版）")
    print("=" * 70)
    
    # データ読み込み
    print("\n📂 データ読み込み中...")
    
    df_aed = pd.read_csv(AED_FILE)
    aed_coords = df_aed[['latitude', 'longitude']].dropna().values
    print(f"  AED数: {len(aed_coords)}")
    
    # AEDのKDTree（度数単位だが、近傍検索には十分）
    # 緯度経度をメートル換算した座標に変換
    aed_xy = np.column_stack([
        aed_coords[:, 1] * LON_TO_M,  # 経度→X
        aed_coords[:, 0] * LAT_TO_M   # 緯度→Y
    ])
    aed_tree = cKDTree(aed_xy)
    print(f"  AED空間インデックス構築完了")
    
    features = load_shapefiles()
    print(f"  町丁ポリゴン: {len(features)}")
    
    pop_data = load_population_data()
    print(f"  人口データ: {len(pop_data)}件")
    
    # ========================================
    # 全グリッド点を生成
    # ========================================
    print("\n📊 グリッド点生成中...")
    
    all_points = []
    for i, feat in enumerate(features):
        if (i + 1) % 100 == 0:
            print(f"  進捗: {i+1}/{len(features)}")
        
        polygon = feat['geometry']
        ward = feat['ward']
        chocho_name = feat['chocho_name']
        
        grid_points = generate_grid_points(polygon, GRID_SPACING)
        if len(grid_points) == 0:
            centroid = polygon.centroid
            grid_points = [(centroid.y, centroid.x)]
        
        pop_row = pop_data[(pop_data['区'] == ward) & (pop_data['町丁名'] == chocho_name)]
        risk_pop = pop_row['リスク加重人口_累計'].values[0] if not pop_row.empty else 0
        risk_per_point = risk_pop / len(grid_points) if grid_points else 0
        
        for lat, lon in grid_points:
            all_points.append({
                'lat': lat, 'lon': lon,
                'ward': ward, 'chocho': chocho_name,
                'risk': risk_per_point
            })
    
    print(f"  全グリッド点: {len(all_points):,}")
    
    # numpy配列に変換
    points_arr = np.array([[p['lat'], p['lon']] for p in all_points])
    risks_arr = np.array([p['risk'] for p in all_points])
    
    # グリッド点をメートル換算
    points_xy = np.column_stack([
        points_arr[:, 1] * LON_TO_M,
        points_arr[:, 0] * LAT_TO_M
    ])
    
    # ========================================
    # カバー状況を一括判定（KDTreeで高速化）
    # ========================================
    print("\n🔍 カバー状況判定中...")
    
    # 各グリッド点の最寄りAEDまでの距離を一括計算
    distances, _ = aed_tree.query(points_xy)
    is_covered = distances <= COVER_DISTANCE
    
    covered_count = is_covered.sum()
    uncovered_count = len(is_covered) - covered_count
    print(f"  カバー済み: {covered_count:,} ({covered_count/len(is_covered)*100:.1f}%)")
    print(f"  未カバー: {uncovered_count:,}")
    
    # 未カバー点のみ抽出
    uncovered_idx = ~is_covered
    uncovered_xy = points_xy[uncovered_idx]
    uncovered_risks = risks_arr[uncovered_idx]
    uncovered_info = [all_points[i] for i in range(len(all_points)) if uncovered_idx[i]]
    
    print(f"  未カバーのリスク加重人口: {uncovered_risks.sum():,.0f}")
    
    # ========================================
    # 未カバー点のKDTree構築
    # ========================================
    print("\n📍 候補地点の効果計算中...")
    
    if len(uncovered_xy) == 0:
        print("  未カバー点がありません。")
        return
    
    uncovered_tree = cKDTree(uncovered_xy)
    
    # 各未カバー点を候補として、その点にAEDを置いた場合の効果を計算
    # KDTreeのquery_ball_pointで300m以内の点を高速検索
    
    results = []
    total = len(uncovered_xy)
    
    for idx in range(total):
        if (idx + 1) % 2000 == 0:
            elapsed = time.time() - start_time
            remaining = elapsed / (idx + 1) * (total - idx - 1)
            print(f"  進捗: {idx+1}/{total} ({(idx+1)/total*100:.1f}%) - 残り約{remaining:.0f}秒")
        
        # この点の300m以内にある未カバー点を検索
        nearby_indices = uncovered_tree.query_ball_point(uncovered_xy[idx], COVER_DISTANCE)
        new_covered_risk = uncovered_risks[nearby_indices].sum()
        
        info = uncovered_info[idx]
        results.append({
            '緯度': round(info['lat'], 6),
            '経度': round(info['lon'], 6),
            '区': info['ward'],
            '町丁名': info['chocho'],
            '新規カバーリスク加重人口': int(new_covered_risk)
        })
    
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values('新規カバーリスク加重人口', ascending=False)
    
    # ========================================
    # 結果表示
    # ========================================
    print("\n" + "=" * 70)
    print("🏆 AED設置推奨地点 TOP20（グリッドレベル）")
    print("=" * 70)
    
    for rank, (_, row) in enumerate(df_results.head(20).iterrows(), 1):
        print(f"\n{rank}位: {row['区']} {row['町丁名']}")
        print(f"   座標: ({row['緯度']}, {row['経度']})")
        print(f"   新規カバー: {row['新規カバーリスク加重人口']:,}")
    
    df_results.head(100).to_csv('grid_level_recommendations.csv', index=False, encoding='utf-8-sig')
    print(f"\n💾 結果保存: grid_level_recommendations.csv")
    
    elapsed = time.time() - start_time
    print(f"\n⏱️ 総実行時間: {elapsed:.1f}秒")

if __name__ == '__main__':
    main()

