"""
川崎市AEDデータ統合スクリプト
4つのデータソースを統合：
1. 川崎市オープンデータ（公共施設）
2. 全国AEDマップ（qqzaidanmap）
3. セブン-イレブン設置店舗リスト
4. aedm.jp（全国AEDマップ - 一般投稿含む）
"""

import pandas as pd
import json
import re
from typing import Dict, List, Tuple
import time
import requests

def load_kawasaki_opendata() -> pd.DataFrame:
    """川崎市オープンデータを読み込み"""
    print("📄 川崎市オープンデータを読み込み中...")
    df = pd.read_csv('kawasaki_aed_utf8.csv')
    df = df.dropna(axis=1, how='all')
    
    # 統一フォーマットに変換
    result = pd.DataFrame({
        'id': df['台帳番号'].apply(lambda x: f"kawasaki_{x}"),
        'source': '川崎市オープンデータ',
        'name': df['設置場所'],
        'address': df['住所'],
        'address_detail': df['設置位置'],
        'facility_type': '公共施設',
        'available_24h': df['24時間365日利用可能か'].apply(lambda x: '365日24時間使用可' in str(x)),
        'available_time': df.apply(lambda r: f"{r['利用開始時間']} - {r['利用終了時間']}" if pd.notna(r['利用開始時間']) else '', axis=1),
        'latitude': df['緯度'],
        'longitude': df['経度'],
        'everyone_allow': df['使用対象者の範囲'].apply(lambda x: '外部' in str(x)),
        'note': df['使用可能日・使用可能時間帯の補足']
    })
    
    print(f"  → {len(result)}件")
    return result

def load_national_map() -> pd.DataFrame:
    """全国AEDマップデータを読み込み"""
    print("📄 全国AEDマップデータを読み込み中...")
    df = pd.read_csv('kawasaki_aed_national_map.csv')
    
    result = pd.DataFrame({
        'id': df['id'].apply(lambda x: f"national_{x}"),
        'source': '全国AEDマップ',
        'name': df['install_location_name'],
        'address': df['install_address'].apply(lambda x: str(x).replace('川崎市', '') if pd.notna(x) else ''),
        'address_detail': df['install_address_detail'],
        'facility_type': df['install_type_name'],
        'available_24h': df['use_everyday'],
        'available_time': df['available_time'],
        'latitude': df['latitude'],
        'longitude': df['longitude'],
        'everyone_allow': df['everyone_allow'].apply(lambda x: x == '認める'),
        'note': df['note']
    })
    
    print(f"  → {len(result)}件")
    return result

def geocode_address(address: str) -> Tuple[float, float]:
    """住所から緯度経度を取得（国土地理院API使用）"""
    try:
        # 住所を正規化
        full_address = f"神奈川県川崎市{address}" if not address.startswith('神奈川') else address
        
        url = "https://msearch.gsi.go.jp/address-search/AddressSearch"
        params = {'q': full_address}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data and len(data) > 0:
            coords = data[0].get('geometry', {}).get('coordinates', [])
            if len(coords) == 2:
                return coords[1], coords[0]  # lat, lng
    except Exception as e:
        pass
    
    return None, None

def load_seven_eleven() -> pd.DataFrame:
    """セブン-イレブンデータを読み込み（ジオコーディング付き）"""
    print("📄 セブン-イレブンデータを読み込み中...")
    df = pd.read_excel('kawasaki_711_aed.xlsx')
    
    print("  🌐 住所から緯度経度を取得中（少々お待ちください）...")
    
    latitudes = []
    longitudes = []
    
    for i, row in df.iterrows():
        address = row['住所']
        lat, lng = geocode_address(address)
        latitudes.append(lat)
        longitudes.append(lng)
        
        if (i + 1) % 20 == 0:
            print(f"    進捗: {i + 1}/{len(df)}")
        
        time.sleep(0.2)  # API負荷軽減
    
    result = pd.DataFrame({
        'id': df['No'].apply(lambda x: f"seven_{x}"),
        'source': 'セブン-イレブン（川崎市協定）',
        'name': df['店名'],
        'address': df['住所'],
        'address_detail': '店舗内',
        'facility_type': '商業施設（コンビニ）',
        'available_24h': True,  # 24時間営業
        'available_time': '24時間',
        'latitude': latitudes,
        'longitude': longitudes,
        'everyone_allow': True,
        'note': '川崎市・セブン-イレブン協定（2025年10月〜）'
    })
    
    # 座標取得成功率
    success = result['latitude'].notna().sum()
    print(f"  → {len(result)}件（座標取得成功: {success}件）")
    
    return result

def load_aedm() -> pd.DataFrame:
    """aedm.jp（全国AEDマップ）データを読み込み"""
    print("📄 aedm.jp データを読み込み中...")
    df = pd.read_csv('kawasaki_aed_aedm_v2.csv')
    
    result = pd.DataFrame({
        'id': df['id'].apply(lambda x: f"aedm_{x}"),
        'source': 'aedm.jp',
        'name': df['name'],
        'address': df['address'].apply(lambda x: str(x).replace('川崎市', '').replace('神奈川県川崎市', '') if pd.notna(x) else ''),
        'address_detail': '',
        'facility_type': '',
        'available_24h': False,
        'available_time': df['able'],
        'latitude': df['lat'],
        'longitude': df['lng'],
        'everyone_allow': True,
        'note': df['source']  # aedm内のソース情報
    })
    
    print(f"  → {len(result)}件")
    return result

def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """重複を除去（座標ベースで判定）"""
    print("\n🔍 重複チェック中...")
    
    # 重複マーキング（優先順位: 川崎市 > 全国AED(qqzaidan) > セブン > aedm.jp）
    source_priority = {
        '川崎市オープンデータ': 1,
        '全国AEDマップ': 2,
        'セブン-イレブン（川崎市協定）': 3,
        'aedm.jp': 4
    }
    df['_priority'] = df['source'].map(source_priority).fillna(5)
    
    # ソートして重複除去
    df = df.sort_values('_priority')
    
    # 座標を小数点5桁で丸めて重複判定
    df['_lat_round'] = df['latitude'].round(5)
    df['_lng_round'] = df['longitude'].round(5)
    
    before = len(df)
    df = df.drop_duplicates(subset=['_lat_round', '_lng_round'], keep='first')
    
    # 一時カラム削除
    df = df.drop(columns=['_priority', '_lat_round', '_lng_round'])
    
    removed = before - len(df)
    print(f"  → 重複除去: {removed}件")
    
    return df

def extract_ward(address: str) -> str:
    """住所から区を抽出"""
    wards = ['川崎区', '幸区', '中原区', '高津区', '宮前区', '多摩区', '麻生区']
    for ward in wards:
        if ward in str(address):
            return ward
    return '不明'

def analyze_merged_data(df: pd.DataFrame):
    """統合データの分析"""
    print("\n" + "=" * 60)
    print("📊 統合データ分析")
    print("=" * 60)
    
    print(f"\n📍 総件数: {len(df)}件")
    
    # ソース別
    print("\n📦 データソース別:")
    for source, count in df['source'].value_counts().items():
        print(f"   {source}: {count}件")
    
    # 区別
    df['ward'] = df['address'].apply(extract_ward)
    print("\n🏘️ 区別:")
    for ward, count in df['ward'].value_counts().items():
        print(f"   {ward}: {count}件")
    
    # 24時間利用可能
    available_24h = df['available_24h'].sum()
    print(f"\n⏰ 24時間利用可能: {available_24h}件 ({available_24h/len(df)*100:.1f}%)")
    
    # 座標あり
    has_coords = df[['latitude', 'longitude']].notna().all(axis=1).sum()
    print(f"🗺️ 座標情報あり: {has_coords}件 ({has_coords/len(df)*100:.1f}%)")

def save_merged_data(df: pd.DataFrame):
    """統合データを保存"""
    print("\n💾 データを保存中...")
    
    # CSV
    df.to_csv('kawasaki_aed_merged.csv', index=False, encoding='utf-8')
    print("  📄 kawasaki_aed_merged.csv")
    
    # GeoJSON
    features = []
    for _, row in df.iterrows():
        if pd.notna(row['latitude']) and pd.notna(row['longitude']):
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row['longitude'], row['latitude']]
                },
                "properties": {
                    "id": row['id'],
                    "source": row['source'],
                    "name": row['name'],
                    "address": row['address'],
                    "address_detail": row['address_detail'],
                    "facility_type": row['facility_type'],
                    "available_24h": bool(row['available_24h']),
                    "available_time": row['available_time'],
                    "everyone_allow": bool(row['everyone_allow']),
                    "note": row['note'] if pd.notna(row['note']) else ''
                }
            }
            features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open('kawasaki_aed_merged.geojson', 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print("  🗺️ kawasaki_aed_merged.geojson")

def main():
    print("\n" + "=" * 60)
    print("🏥 川崎市AEDデータ統合ツール 🏥")
    print("=" * 60)
    
    # データ読み込み
    df_kawasaki = load_kawasaki_opendata()
    df_national = load_national_map()
    df_seven = load_seven_eleven()
    df_aedm = load_aedm()
    
    # 統合
    print("\n🔗 データを統合中...")
    df_merged = pd.concat([df_kawasaki, df_national, df_seven, df_aedm], ignore_index=True)
    print(f"  → 統合前: {len(df_merged)}件")
    
    # 重複除去
    df_merged = remove_duplicates(df_merged)
    print(f"  → 統合後: {len(df_merged)}件")
    
    # 分析
    analyze_merged_data(df_merged)
    
    # 保存
    save_merged_data(df_merged)
    
    print("\n" + "=" * 60)
    print("✅ 統合完了!")
    print("=" * 60)

if __name__ == "__main__":
    main()

