"""
グリッドレベル推奨地点のグルーピング
近接する推奨地点をグループ化し、各エリアから代表点のみを選択
"""
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2

# グルーピング距離（この距離以内の点は同一エリアとみなす）
GROUP_DISTANCE = 500  # メートル

def haversine_distance(lat1, lon1, lat2, lon2):
    """2点間の距離（メートル）"""
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))

def main():
    print("=" * 70)
    print("🎯 グリッドレベル推奨地点のグルーピング")
    print("=" * 70)
    print(f"グルーピング距離: {GROUP_DISTANCE}m")
    
    # 元の推奨データを読み込み
    df = pd.read_csv('grid_level_recommendations.csv')
    df = df.sort_values('新規カバーリスク加重人口', ascending=False).reset_index(drop=True)
    
    print(f"元の候補数: {len(df)}")
    
    # グルーピング処理
    # 効果が高い順に選択し、選択した点の近く（500m以内）は除外
    selected = []
    used_indices = set()
    
    for idx, row in df.iterrows():
        if idx in used_indices:
            continue
        
        # この点を選択
        selected.append({
            '順位': len(selected) + 1,
            '緯度': row['緯度'],
            '経度': row['経度'],
            '区': row['区'],
            '町丁名': row['町丁名'],
            '新規カバーリスク加重人口': row['新規カバーリスク加重人口'],
            '元順位': idx + 1
        })
        used_indices.add(idx)
        
        # この点の近くにある点を除外リストに追加
        for other_idx, other_row in df.iterrows():
            if other_idx in used_indices:
                continue
            
            dist = haversine_distance(
                row['緯度'], row['経度'],
                other_row['緯度'], other_row['経度']
            )
            
            if dist <= GROUP_DISTANCE:
                used_indices.add(other_idx)
        
        # TOP20まで選択したら終了
        if len(selected) >= 20:
            break
    
    df_grouped = pd.DataFrame(selected)
    
    # 結果表示
    print("\n" + "=" * 70)
    print("🏆 グルーピング後の推奨地点 TOP20")
    print("=" * 70)
    print(f"（{GROUP_DISTANCE}m以内の点は同一エリアとしてグループ化）\n")
    
    for _, row in df_grouped.iterrows():
        print(f"{int(row['順位'])}位: {row['区']} {row['町丁名']}")
        print(f"   座標: ({row['緯度']}, {row['経度']})")
        print(f"   新規カバー: {row['新規カバーリスク加重人口']:,}")
        print(f"   （元データでの順位: {int(row['元順位'])}位）")
        print()
    
    # 保存
    df_grouped.to_csv('grid_level_recommendations_grouped.csv', index=False, encoding='utf-8-sig')
    print(f"💾 結果保存: grid_level_recommendations_grouped.csv")
    
    return df_grouped

if __name__ == '__main__':
    main()

