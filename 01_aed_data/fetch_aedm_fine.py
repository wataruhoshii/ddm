"""
aedm.jp（全国AEDマップ）から川崎市のAEDデータを取得するスクリプト
グリッド間隔を狭めた詳細版
"""

import json
import time
import requests
import csv
from typing import Set, List, Dict

# 川崎市の緯度経度範囲
KAWASAKI_BOUNDS = {
    'sw_lat': 35.495,
    'sw_lng': 139.461,
    'ne_lat': 35.640,
    'ne_lng': 139.790
}

def fetch_aedm_session():
    """aedm.jpからセッションとCSRFトークンを取得"""
    session = requests.Session()
    
    # まずトップページにアクセスしてセッションを確立
    try:
        response = session.get('https://aedm.jp/', timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"セッション取得エラー: {e}")
        return None
    
    return session

def fetch_aeds_at_location(session, lat: float, lng: float, zoom: int = 15) -> List[Dict]:
    """指定した緯度経度周辺のAEDデータを取得"""
    
    # aedm.jpのAPIエンドポイント
    url = "https://aedm.jp/api/aed/get"
    
    # 検索範囲を計算（zoom 15 で約1km四方）
    delta = 0.015  # 約1.5km
    
    params = {
        'swlat': lat - delta,
        'swlng': lng - delta,
        'nelat': lat + delta,
        'nelng': lng + delta,
        'zoom': zoom
    }
    
    try:
        response = session.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                return data['data']
            return []
        else:
            return []
    except Exception as e:
        print(f"\n  エラー at ({lat:.4f}, {lng:.4f}): {e}")
        return []

def fetch_kawasaki_aeds_fine() -> List[Dict]:
    """川崎市全体のAEDデータを細かいグリッドで取得"""
    print("🔍 aedm.jpから川崎市のAEDデータを取得中（細かいグリッド版）...")
    
    session = fetch_aedm_session()
    if not session:
        print("❌ セッション取得に失敗しました")
        return []
    
    print("✅ セッション確立")
    
    all_aeds = {}
    seen_ids: Set[str] = set()
    
    # グリッドを作成（0.01度間隔 ≒ 約1km）- 以前の半分
    lat_step = 0.01
    lng_step = 0.0125
    
    # 総ポイント数を計算
    total_points = 0
    temp_lat = KAWASAKI_BOUNDS['sw_lat']
    while temp_lat <= KAWASAKI_BOUNDS['ne_lat']:
        temp_lng = KAWASAKI_BOUNDS['sw_lng']
        while temp_lng <= KAWASAKI_BOUNDS['ne_lng']:
            total_points += 1
            temp_lng += lng_step
        temp_lat += lat_step
    
    print(f"📍 検索ポイント数: {total_points}（約{total_points * 0.35 / 60:.1f}分予想）")
    
    current_point = 0
    lat = KAWASAKI_BOUNDS['sw_lat']
    
    start_time = time.time()
    
    while lat <= KAWASAKI_BOUNDS['ne_lat']:
        lng = KAWASAKI_BOUNDS['sw_lng']
        while lng <= KAWASAKI_BOUNDS['ne_lng']:
            current_point += 1
            
            elapsed = time.time() - start_time
            if current_point > 1:
                eta = (elapsed / current_point) * (total_points - current_point)
                eta_min = int(eta // 60)
                eta_sec = int(eta % 60)
                print(f"\r  進捗: {current_point}/{total_points} ({len(seen_ids)}件取得済) ETA: {eta_min}分{eta_sec}秒    ", end="", flush=True)
            else:
                print(f"\r  進捗: {current_point}/{total_points} ({len(seen_ids)}件取得済)", end="", flush=True)
            
            aeds = fetch_aeds_at_location(session, lat, lng)
            
            for aed in aeds:
                aed_id = str(aed.get('id', ''))
                if aed_id and aed_id not in seen_ids:
                    # 川崎市のデータのみ抽出
                    address = aed.get('address', '')
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
    if not aeds:
        print("保存するデータがありません")
        return
    
    fieldnames = ['id', 'name', 'address', 'latitude', 'longitude', 'area', 'time_weekday', 
                  'time_saturday', 'time_sunday', 'time_holiday', 'source']
    
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for aed in aeds:
            row = {
                'id': aed.get('id'),
                'name': aed.get('name'),
                'address': aed.get('address'),
                'latitude': aed.get('lat'),
                'longitude': aed.get('lng'),
                'area': aed.get('area', ''),
                'time_weekday': aed.get('time_weekday', ''),
                'time_saturday': aed.get('time_saturday', ''),
                'time_sunday': aed.get('time_sunday', ''),
                'time_holiday': aed.get('time_holiday', ''),
                'source': 'aedm.jp'
            }
            writer.writerow(row)
    
    print(f"📄 CSV保存: {filename}")

def analyze_data(aeds: List[Dict]):
    """データの概要を分析"""
    print("\n" + "=" * 60)
    print("📊 aedm.jp（川崎市）データ概要")
    print("=" * 60)
    
    print(f"\n📍 総件数: {len(aeds)}件")
    
    # 区別
    wards = {}
    for aed in aeds:
        addr = aed.get('address', '')
        for ward in ['川崎区', '幸区', '中原区', '高津区', '宮前区', '多摩区', '麻生区']:
            if ward in addr:
                wards[ward] = wards.get(ward, 0) + 1
                break
    
    print("\n🏘️ 区別:")
    for ward in ['川崎区', '幸区', '中原区', '高津区', '宮前区', '多摩区', '麻生区']:
        count = wards.get(ward, 0)
        print(f"   {ward}: {count}件")
    
    # いなげやを検索
    print("\n🔍 「いなげや」を含むAED:")
    inageya_count = 0
    for aed in aeds:
        name = aed.get('name', '')
        if 'いなげや' in name or 'イナゲヤ' in name:
            inageya_count += 1
            print(f"   - {name}: {aed.get('address', '')}")
    if inageya_count == 0:
        print("   見つかりませんでした")

def main():
    print("\n🏥 aedm.jp データ取得ツール（細かいグリッド版）🏥\n")
    
    # データ取得
    aeds = fetch_kawasaki_aeds_fine()
    
    if not aeds:
        print("❌ データが取得できませんでした")
        return
    
    # 分析
    analyze_data(aeds)
    
    # 保存
    save_to_csv(aeds, 'kawasaki_aed_aedm_fine.csv')
    
    # JSON保存
    with open('kawasaki_aed_aedm_fine.json', 'w', encoding='utf-8') as f:
        json.dump(aeds, f, ensure_ascii=False, indent=2)
    print(f"📋 JSON保存: kawasaki_aed_aedm_fine.json")
    
    print("\n✅ 完了!")

if __name__ == "__main__":
    main()
