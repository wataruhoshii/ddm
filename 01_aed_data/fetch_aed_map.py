"""
全国AEDマップから川崎市のAEDデータを取得するスクリプト
API: https://www.qqzaidanmap.jp/api/aed/search_by_location
"""

import json
import time
import requests
from typing import Set, List, Dict

# 川崎市の緯度経度範囲
# 南西: 35.495, 139.461
# 北東: 35.637, 139.785

KAWASAKI_BOUNDS = {
    'sw_lat': 35.495,
    'sw_lng': 139.461,
    'ne_lat': 35.640,
    'ne_lng': 139.790
}

def fetch_aeds_at_location(lat: float, lng: float) -> List[Dict]:
    """指定した緯度経度周辺のAEDデータを取得"""
    url = f"https://www.qqzaidanmap.jp/api/aed/search_by_location?latitude={lat}&longitude={lng}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('aeds', [])
    except Exception as e:
        print(f"  エラー at ({lat}, {lng}): {e}")
        return []

def fetch_kawasaki_aeds() -> List[Dict]:
    """川崎市全体のAEDデータを取得"""
    print("🔍 全国AEDマップから川崎市のAEDデータを取得中...")
    
    all_aeds = {}
    seen_ids: Set[int] = set()
    
    # グリッドを作成（0.02度間隔 ≒ 約2km）
    lat_step = 0.02
    lng_step = 0.025
    
    lat = KAWASAKI_BOUNDS['sw_lat']
    total_points = 0
    
    # 総ポイント数を計算
    temp_lat = lat
    while temp_lat <= KAWASAKI_BOUNDS['ne_lat']:
        temp_lng = KAWASAKI_BOUNDS['sw_lng']
        while temp_lng <= KAWASAKI_BOUNDS['ne_lng']:
            total_points += 1
            temp_lng += lng_step
        temp_lat += lat_step
    
    print(f"📍 検索ポイント数: {total_points}")
    
    current_point = 0
    while lat <= KAWASAKI_BOUNDS['ne_lat']:
        lng = KAWASAKI_BOUNDS['sw_lng']
        while lng <= KAWASAKI_BOUNDS['ne_lng']:
            current_point += 1
            print(f"\r  進捗: {current_point}/{total_points} ({len(seen_ids)}件取得済)", end="", flush=True)
            
            aeds = fetch_aeds_at_location(lat, lng)
            
            for aed in aeds:
                aed_id = aed.get('id')
                if aed_id and aed_id not in seen_ids:
                    # 川崎市のデータのみ抽出
                    address = aed.get('install_address', '')
                    if '川崎市' in address:
                        seen_ids.add(aed_id)
                        all_aeds[aed_id] = aed
            
            lng += lng_step
            time.sleep(0.3)  # API負荷軽減
        lat += lat_step
    
    print(f"\n✅ 取得完了: {len(all_aeds)}件")
    return list(all_aeds.values())

def save_to_csv(aeds: List[Dict], filename: str):
    """CSVファイルとして保存"""
    import csv
    
    if not aeds:
        print("保存するデータがありません")
        return
    
    fieldnames = [
        'id', 'register_number', 'install_location_name', 'install_address',
        'install_address_detail', 'install_type_name', 'install_date',
        'available_time', 'open_days', 'use_everyday', 'everyone_allow',
        'rank', 'latitude', 'longitude', 'updated_at', 'note'
    ]
    
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for aed in aeds:
            row = {
                'id': aed.get('id'),
                'register_number': aed.get('register_number'),
                'install_location_name': aed.get('install_location_name'),
                'install_address': aed.get('install_address'),
                'install_address_detail': aed.get('install_address_detail'),
                'install_type_name': aed.get('install_type_name'),
                'install_date': aed.get('install_date'),
                'available_time': aed.get('available_time'),
                'open_days': aed.get('open_days'),
                'use_everyday': aed.get('use_everyday'),
                'everyone_allow': aed.get('everyone_allow'),
                'rank': aed.get('rank'),
                'latitude': aed.get('location', {}).get('latitude'),
                'longitude': aed.get('location', {}).get('longitude'),
                'updated_at': aed.get('updated_at'),
                'note': aed.get('note')
            }
            writer.writerow(row)
    
    print(f"📄 CSV保存: {filename}")

def save_to_geojson(aeds: List[Dict], filename: str):
    """GeoJSONファイルとして保存"""
    features = []
    
    for aed in aeds:
        location = aed.get('location', {})
        lat = location.get('latitude')
        lng = location.get('longitude')
        
        if lat and lng:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "properties": {
                    "id": aed.get('id'),
                    "name": aed.get('install_location_name'),
                    "address": aed.get('install_address'),
                    "address_detail": aed.get('install_address_detail'),
                    "type": aed.get('install_type_name'),
                    "available_time": aed.get('available_time'),
                    "open_days": aed.get('open_days'),
                    "everyone_allow": aed.get('everyone_allow'),
                    "rank": aed.get('rank')
                }
            }
            features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    
    print(f"🗺️ GeoJSON保存: {filename}")

def analyze_data(aeds: List[Dict]):
    """データの概要を分析"""
    print("\n" + "=" * 60)
    print("📊 全国AEDマップ（川崎市）データ概要")
    print("=" * 60)
    
    print(f"\n📍 総件数: {len(aeds)}件")
    
    # 施設タイプ別
    types = {}
    for aed in aeds:
        t = aed.get('install_type_name', '不明')
        types[t] = types.get(t, 0) + 1
    
    print("\n🏢 施設タイプ別:")
    for t, count in sorted(types.items(), key=lambda x: -x[1])[:10]:
        print(f"   {t}: {count}件")
    
    # 区別
    wards = {}
    for aed in aeds:
        addr = aed.get('install_address', '')
        for ward in ['川崎区', '幸区', '中原区', '高津区', '宮前区', '多摩区', '麻生区']:
            if ward in addr:
                wards[ward] = wards.get(ward, 0) + 1
                break
    
    print("\n🏘️ 区別:")
    for ward, count in sorted(wards.items(), key=lambda x: -x[1]):
        print(f"   {ward}: {count}件")
    
    # ランク別
    ranks = {}
    for aed in aeds:
        r = aed.get('rank', '不明')
        ranks[r] = ranks.get(r, 0) + 1
    
    print("\n⭐ ランク別（A=いつでも使える）:")
    for r, count in sorted(ranks.items()):
        print(f"   ランク{r}: {count}件")

def main():
    print("\n🏥 全国AEDマップ データ取得ツール 🏥\n")
    
    # データ取得
    aeds = fetch_kawasaki_aeds()
    
    if not aeds:
        print("❌ データが取得できませんでした")
        return
    
    # 分析
    analyze_data(aeds)
    
    # 保存
    save_to_csv(aeds, 'kawasaki_aed_national_map.csv')
    save_to_geojson(aeds, 'kawasaki_aed_national_map.geojson')
    
    # JSON生の保存
    with open('kawasaki_aed_national_map.json', 'w', encoding='utf-8') as f:
        json.dump(aeds, f, ensure_ascii=False, indent=2)
    print(f"📋 JSON保存: kawasaki_aed_national_map.json")
    
    print("\n✅ 完了!")

if __name__ == "__main__":
    main()

