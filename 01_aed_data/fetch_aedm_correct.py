"""
aedm.jp（全国AEDマップ）から川崎市のAEDデータを取得するスクリプト
正しいAPIパラメータ（lat/lng）を使用
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

def fetch_aeds_at_location(session, lat: float, lng: float, headers: dict) -> List[Dict]:
    """指定した緯度経度周辺のAEDデータを取得"""
    url = "https://aedm.jp/api/aed/get"
    params = {'lat': lat, 'lng': lng}
    
    try:
        response = session.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get('aed', [])
        return []
    except Exception as e:
        print(f"\n  エラー at ({lat:.4f}, {lng:.4f}): {e}")
        return []

def fetch_kawasaki_aeds() -> List[Dict]:
    """川崎市全体のAEDデータを取得"""
    print("🔍 aedm.jpから川崎市のAEDデータを取得中...")
    print("   （正しいAPIパラメータ lat/lng を使用）")
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    # セッション確立
    session.get('https://aedm.jp/', headers=headers, timeout=30)
    print("✅ セッション確立")
    
    all_aeds = {}
    seen_ids: Set[int] = set()
    
    # グリッドを作成（約1km間隔）
    # APIは約5km範囲を返すので、余裕を持った間隔
    lat_step = 0.015  # 約1.7km
    lng_step = 0.02   # 約2km
    
    # 総ポイント数を計算
    total_points = 0
    temp_lat = KAWASAKI_BOUNDS['sw_lat']
    while temp_lat <= KAWASAKI_BOUNDS['ne_lat']:
        temp_lng = KAWASAKI_BOUNDS['sw_lng']
        while temp_lng <= KAWASAKI_BOUNDS['ne_lng']:
            total_points += 1
            temp_lng += lng_step
        temp_lat += lat_step
    
    print(f"📍 検索ポイント数: {total_points}")
    
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
                print(f"\r  進捗: {current_point}/{total_points}", end="", flush=True)
            
            aeds = fetch_aeds_at_location(session, lat, lng, headers)
            
            for aed in aeds:
                aed_id = aed.get('id')
                if aed_id and aed_id not in seen_ids:
                    # 川崎市のデータのみ抽出
                    address = aed.get('adr') or ''
                    if '川崎市' in address or '川崎' in address:
                        seen_ids.add(aed_id)
                        all_aeds[aed_id] = aed
            
            lng += lng_step
            time.sleep(0.3)
        lat += lat_step
    
    print(f"\n✅ 取得完了: {len(all_aeds)}件")
    return list(all_aeds.values())

def save_to_csv(aeds: List[Dict], filename: str):
    """CSVファイルとして保存"""
    if not aeds:
        print("保存するデータがありません")
        return
    
    fieldnames = ['id', 'name', 'address', 'lat', 'lng', 'source', 'able', 'tel']
    
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for aed in aeds:
            row = {
                'id': aed.get('id'),
                'name': aed.get('name'),
                'address': aed.get('adr'),
                'lat': aed.get('lat'),
                'lng': aed.get('lng'),
                'source': aed.get('src', ''),
                'able': aed.get('able', ''),
                'tel': aed.get('tel', '')
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
        addr = aed.get('adr', '')
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
            print(f"   - {name}: {aed.get('adr', '')}")
    if inageya_count == 0:
        print("   見つかりませんでした")
    
    # ソース別
    sources = {}
    for aed in aeds:
        src = aed.get('src', '不明')
        sources[src] = sources.get(src, 0) + 1
    
    print("\n📝 データソース別:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1])[:10]:
        print(f"   {src}: {count}件")

def main():
    print("\n🏥 aedm.jp データ取得ツール（正しいパラメータ版）🏥\n")
    
    # データ取得
    aeds = fetch_kawasaki_aeds()
    
    if not aeds:
        print("❌ データが取得できませんでした")
        return
    
    # 分析
    analyze_data(aeds)
    
    # 保存
    save_to_csv(aeds, 'kawasaki_aed_aedm_v2.csv')
    
    # JSON保存
    with open('kawasaki_aed_aedm_v2.json', 'w', encoding='utf-8') as f:
        json.dump(aeds, f, ensure_ascii=False, indent=2)
    print(f"📋 JSON保存: kawasaki_aed_aedm_v2.json")
    
    print("\n✅ 完了!")

if __name__ == "__main__":
    main()
