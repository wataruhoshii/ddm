"""
川崎市 町丁の緯度経度取得スクリプト
- Nominatim（OpenStreetMap）でジオコーディング
- 約674件、約11分
"""

import pandas as pd
from geopy.geocoders import Nominatim
import time
import sys

def main():
    print("=" * 60)
    print("🗺️  川崎市 町丁ジオコーディング")
    print("=" * 60)
    
    # データ読み込み
    df = pd.read_csv('kawasaki_chocho_age_processed.csv')
    
    # 町丁ごとにユニークな行を取得
    df_unique = df[['町丁コード', '区', '町丁名']].drop_duplicates().reset_index(drop=True)
    total = len(df_unique)
    print(f"対象町丁数: {total}")
    
    # ジオコーダー設定
    geolocator = Nominatim(user_agent="kawasaki_aed_analysis", timeout=10)
    
    # 結果を格納
    results = []
    success = 0
    failed = 0
    
    print(f"\n🔄 ジオコーディング開始...")
    start_time = time.time()
    
    for i, row in df_unique.iterrows():
        address = f"神奈川県川崎市{row['区']}{row['町丁名']}"
        
        try:
            location = geolocator.geocode(address)
            if location:
                results.append({
                    '町丁コード': row['町丁コード'],
                    '区': row['区'],
                    '町丁名': row['町丁名'],
                    '緯度': location.latitude,
                    '経度': location.longitude
                })
                success += 1
            else:
                # 見つからない場合は区名だけで再試行
                address2 = f"神奈川県川崎市{row['区']}"
                location2 = geolocator.geocode(address2)
                if location2:
                    results.append({
                        '町丁コード': row['町丁コード'],
                        '区': row['区'],
                        '町丁名': row['町丁名'],
                        '緯度': location2.latitude,
                        '経度': location2.longitude
                    })
                    success += 1
                else:
                    results.append({
                        '町丁コード': row['町丁コード'],
                        '区': row['区'],
                        '町丁名': row['町丁名'],
                        '緯度': None,
                        '経度': None
                    })
                    failed += 1
        except Exception as e:
            results.append({
                '町丁コード': row['町丁コード'],
                '区': row['区'],
                '町丁名': row['町丁名'],
                '緯度': None,
                '経度': None
            })
            failed += 1
        
        # 進捗表示
        if (i + 1) % 50 == 0 or (i + 1) == total:
            elapsed = time.time() - start_time
            remaining = (elapsed / (i + 1)) * (total - i - 1)
            print(f"  進捗: {i+1}/{total} ({(i+1)/total*100:.1f}%) - 残り約{remaining/60:.1f}分")
        
        time.sleep(1)  # API制限回避
    
    # 結果をDataFrameに
    df_geo = pd.DataFrame(results)
    
    # 元データとマージ
    df_merged = df.merge(df_geo[['町丁コード', '緯度', '経度']], on='町丁コード', how='left')
    
    # 保存
    df_merged.to_csv('kawasaki_chocho_age_processed.csv', index=False, encoding='utf-8-sig')
    df_geo.to_csv('kawasaki_chocho_geocoded.csv', index=False, encoding='utf-8-sig')
    
    elapsed_total = time.time() - start_time
    print(f"\n" + "=" * 60)
    print(f"✅ 完了!")
    print(f"=" * 60)
    print(f"成功: {success}/{total} ({success/total*100:.1f}%)")
    print(f"失敗: {failed}/{total}")
    print(f"所要時間: {elapsed_total/60:.1f}分")
    print(f"\n保存先:")
    print(f"  - kawasaki_chocho_age_processed.csv (緯度経度追加)")
    print(f"  - kawasaki_chocho_geocoded.csv (町丁座標のみ)")

if __name__ == '__main__':
    main()

