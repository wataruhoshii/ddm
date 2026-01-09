"""
グリッドレベルでのAED設置推奨場所分析
各グリッド点にAEDを配置した場合のリスク加重カバー人口増加量を計算
"""
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import os
from shapely.geometry import shape
import shapefile

# ========================================
# 設定
# ========================================
GRID_SPACING = 50  # グリッド間隔（メートル）
COVER_DISTANCE = 300  # カバー範囲（メートル）
AED_FILE = '../01_aed_data/kawasaki_aed_merged.csv'
ESTATS_DIR = '../estats'

# 区コード
WARD_CODES = {
    '14131': '川崎区', '14132': '幸区', '14133': '中原区',
    '14134': '高津区', '14135': '多摩区', '14136': '宮前区', '14137': '麻生区'
}

# ========================================
# ユーティリティ関数
# ========================================
def haversine_distance(lat1, lon1, lat2, lon2):
    """2点間の距離（メートル）"""
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))

def meters_to_degrees(meters, latitude):
    """メートルを度に変換（近似）"""
    lat_deg = meters / 111320
    lon_deg = meters / (111320 * cos(radians(latitude)))
    return lat_deg, lon_deg

def generate_grid_points(polygon, spacing_m):
    """ポリゴン内にグリッド点を生成"""
    bounds = polygon.bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    lat_step, lon_step = meters_to_degrees(spacing_m, center_lat)
    
    points = []
    lat = bounds[1]
    while lat <= bounds[3]:
        lon = bounds[0]
        while lon <= bounds[2]:
            from shapely.geometry import Point
            if polygon.contains(Point(lon, lat)):
                points.append((lat, lon))
            lon += lon_step
        lat += lat_step
    return points

def load_shapefiles():
    """全区のShapefileを読み込み"""
    all_features = []
    
    for code, ward in WARD_CODES.items():
        shp_path = f'{ESTATS_DIR}/A002005212020DDSWC{code}/r2ka{code}.shp'
        
        if not os.path.exists(shp_path):
            print(f"  ⚠️ {ward}のShapefileが見つかりません: {shp_path}")
            continue
        
        sf = shapefile.Reader(shp_path, encoding='shift_jis')
        
        for sr in sf.shapeRecords():
            rec = sr.record
            geom = shape(sr.shape.__geo_interface__)
            
            # S_NAMEフィールドのインデックスを取得
            field_names = [f[0] for f in sf.fields[1:]]
            s_name_idx = field_names.index('S_NAME') if 'S_NAME' in field_names else None
            
            if s_name_idx is not None:
                chocho_name = rec[s_name_idx]
                if chocho_name:
                    all_features.append({
                        'ward': ward,
                        'chocho_name': chocho_name,
                        'geometry': geom
                    })
    
    return all_features

def load_population_data():
    """人口データを読み込み"""
    pop_file = 'chocho_analysis_all_years.csv'
    df = pd.read_csv(pop_file)
    # すでに累計されているので、町丁名ごとに集約（複数ポリゴン対応）
    df_agg = df.groupby(['区', '町丁名']).agg({
        '総人口_累計': 'first',
        'リスク加重人口_累計': 'first'
    }).reset_index()
    return df_agg

# ========================================
# メイン処理
# ========================================
def main():
    print("=" * 70)
    print("🎯 グリッドレベルAED設置推奨分析")
    print("=" * 70)
    print(f"グリッド間隔: {GRID_SPACING}m")
    print(f"カバー距離: {COVER_DISTANCE}m")
    
    # データ読み込み
    print("\n📂 データ読み込み中...")
    
    df_aed = pd.read_csv(AED_FILE)
    aed_locations = df_aed[['latitude', 'longitude']].dropna().values.tolist()
    print(f"  既存AED数: {len(aed_locations)}")
    
    features = load_shapefiles()
    print(f"  町丁ポリゴン数: {len(features)}")
    
    pop_data = load_population_data()
    print(f"  人口データ: {len(pop_data)}件")
    
    # ========================================
    # 全グリッド点を生成し、現在のカバー状況を計算
    # ========================================
    print("\n📊 全グリッド点のカバー状況を分析中...")
    
    all_grid_points = []  # (lat, lon, ward, chocho, risk_weight_per_point)
    
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
        
        # 人口データとマッチング
        pop_row = pop_data[(pop_data['区'] == ward) & (pop_data['町丁名'] == chocho_name)]
        if not pop_row.empty:
            risk_pop = pop_row['リスク加重人口_累計'].values[0]
        else:
            risk_pop = 0
        
        # 各グリッド点のリスク加重人口（均等配分）
        risk_per_point = risk_pop / len(grid_points) if grid_points else 0
        
        for lat, lon in grid_points:
            # 現在カバーされているか判定
            is_covered = False
            for aed_lat, aed_lon in aed_locations:
                if haversine_distance(lat, lon, aed_lat, aed_lon) <= COVER_DISTANCE:
                    is_covered = True
                    break
            
            all_grid_points.append({
                'lat': lat,
                'lon': lon,
                'ward': ward,
                'chocho': chocho_name,
                'risk_weight': risk_per_point,
                'is_covered': is_covered
            })
    
    df_grid = pd.DataFrame(all_grid_points)
    
    total_points = len(df_grid)
    covered_points = df_grid['is_covered'].sum()
    uncovered_points = total_points - covered_points
    
    print(f"\n  全グリッド点数: {total_points:,}")
    print(f"  カバー済み: {covered_points:,} ({covered_points/total_points*100:.1f}%)")
    print(f"  未カバー: {uncovered_points:,} ({uncovered_points/total_points*100:.1f}%)")
    
    # カバー外のグリッド点のみ抽出
    df_uncovered = df_grid[~df_grid['is_covered']].copy()
    
    print(f"\n  未カバーのリスク加重人口合計: {df_uncovered['risk_weight'].sum():,.0f}")
    
    # ========================================
    # 各候補地点（未カバーグリッド点）の効果を計算
    # ========================================
    print("\n🔍 各候補地点の効果を計算中...")
    print("  （各グリッド点にAEDを置いた場合の新規カバー人口を計算）")
    
    # 未カバー点の座標をnumpy配列に変換（高速化）
    uncovered_coords = df_uncovered[['lat', 'lon']].values
    uncovered_risks = df_uncovered['risk_weight'].values
    
    # 候補地点は未カバー点に限定
    candidates = df_uncovered[['lat', 'lon', 'ward', 'chocho']].drop_duplicates().values
    print(f"  候補地点数: {len(candidates):,}")
    
    results = []
    total_candidates = len(candidates)
    
    for idx, (c_lat, c_lon, c_ward, c_chocho) in enumerate(candidates):
        if (idx + 1) % 1000 == 0:
            print(f"  進捗: {idx+1}/{total_candidates} ({(idx+1)/total_candidates*100:.1f}%)")
        
        # この候補地点にAEDを置いた場合、新たにカバーされる点を計算
        new_covered_risk = 0
        for i, (u_lat, u_lon) in enumerate(uncovered_coords):
            dist = haversine_distance(c_lat, c_lon, u_lat, u_lon)
            if dist <= COVER_DISTANCE:
                new_covered_risk += uncovered_risks[i]
        
        results.append({
            '緯度': round(c_lat, 6),
            '経度': round(c_lon, 6),
            '区': c_ward,
            '町丁名': c_chocho,
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
    print("※ 1台設置した場合に新たにカバーされるリスク加重人口")
    
    for rank, (_, row) in enumerate(df_results.head(20).iterrows(), 1):
        print(f"\n{rank}位: {row['区']} {row['町丁名']}")
        print(f"   座標: ({row['緯度']}, {row['経度']})")
        print(f"   新規カバー: {row['新規カバーリスク加重人口']:,}")
    
    # 保存
    df_results.head(100).to_csv('grid_level_recommendations.csv', index=False, encoding='utf-8-sig')
    print(f"\n💾 結果保存: grid_level_recommendations.csv (TOP100)")
    
    print("\n✅ 分析完了!")
    
    return df_results

if __name__ == '__main__':
    main()
