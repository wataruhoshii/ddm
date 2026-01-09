"""
グリッドレベル推奨地点のマップを作成
"""
import pandas as pd
import folium

# データ読み込み（グルーピング済みデータを使用）
df_rec = pd.read_csv('grid_level_recommendations_grouped.csv')
df_aed = pd.read_csv('../01_aed_data/kawasaki_aed_merged.csv')

# TOP20
df_top = df_rec.head(20)

# マップ作成（登戸付近を中心に）
center_lat = df_top['緯度'].mean()
center_lon = df_top['経度'].mean()
m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles='cartodbpositron')

# 既存AEDを薄く表示
for _, aed in df_aed.iterrows():
    if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
        folium.CircleMarker(
            location=[aed['latitude'], aed['longitude']],
            radius=4,
            color='gray',
            fill=True,
            fillOpacity=0.4,
            weight=1
        ).add_to(m)

# 推奨地点を番号付きで表示
max_risk = df_top['新規カバーリスク加重人口'].max()

for idx, row in df_top.iterrows():
    rank = idx + 1
    risk = row['新規カバーリスク加重人口']
    
    # 300mカバー範囲
    folium.Circle(
        location=[row['緯度'], row['経度']],
        radius=300,
        color='#2e7d32',
        fill=True,
        fillOpacity=0.15,
        weight=1
    ).add_to(m)
    
    # 色（効果の大きさで）
    ratio = risk / max_risk
    if ratio >= 0.9:
        color = '#c53030'  # 赤（最高効果）
    elif ratio >= 0.7:
        color = '#dd6b20'  # オレンジ
    else:
        color = '#38a169'  # 緑
    
    # ポップアップ
    popup_text = f"""
    <div style="font-family: sans-serif; min-width: 220px;">
        <h4 style="margin: 0 0 8px 0; color: #2d3748;">
            🎯 推奨 {rank}位: {row['区']} {row['町丁名']}
        </h4>
        <table style="width: 100%; font-size: 12px;">
            <tr><td>新規カバー人口</td><td><b style="color: {color};">{risk:,}</b></td></tr>
            <tr><td>座標</td><td>({row['緯度']:.6f}, {row['経度']:.6f})</td></tr>
        </table>
        <p style="font-size: 11px; color: #666; margin-top: 8px;">
            ※この地点にAEDを1台設置した場合の効果<br>
            ※カバー範囲: 300m
        </p>
    </div>
    """
    
    folium.Marker(
        location=[row['緯度'], row['経度']],
        popup=folium.Popup(popup_text, max_width=280),
        icon=folium.DivIcon(
            html=f'<div style="font-size: 12pt; color: white; background-color: {color}; border-radius: 50%; width: 26px; height: 26px; text-align: center; line-height: 26px; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">{rank}</div>'
        )
    ).add_to(m)

# 凡例
legend_html = '''
<div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
            background-color: white; padding: 15px; border-radius: 8px;
            border: 2px solid #e2e8f0; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);">
    <b style="font-size: 14px;">🎯 グリッドレベル推奨地点 TOP20</b><br>
    <span style="color: #666; font-size: 11px;">1台設置時の新規カバー効果</span><br><br>
    <b>効果レベル</b><br>
    🔴 90%以上（最高効果）<br>
    🟠 70〜90%<br>
    🟢 70%未満<br><br>
    🟢 円: カバー範囲(300m)<br>
    ⚫ 点: 既存AED
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

# 全体表示用のマップも作成
m_full = folium.Map(location=[35.57, 139.55], zoom_start=11, tiles='cartodbpositron')

# 既存AED
for _, aed in df_aed.iterrows():
    if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
        folium.CircleMarker(
            location=[aed['latitude'], aed['longitude']],
            radius=3,
            color='gray',
            fill=True,
            fillOpacity=0.3
        ).add_to(m_full)

# 推奨地点（全体マップ）
for idx, row in df_top.iterrows():
    rank = idx + 1
    risk = row['新規カバーリスク加重人口']
    ratio = risk / max_risk
    
    if ratio >= 0.9:
        color = '#c53030'
    elif ratio >= 0.7:
        color = '#dd6b20'
    else:
        color = '#38a169'
    
    folium.Circle(
        location=[row['緯度'], row['経度']],
        radius=300,
        color='#2e7d32',
        fill=True,
        fillOpacity=0.2,
        weight=2
    ).add_to(m_full)
    
    popup_text = f"""
    <div style="font-family: sans-serif;">
        <b>{rank}位: {row['区']} {row['町丁名']}</b><br>
        新規カバー: {risk:,}
    </div>
    """
    
    folium.Marker(
        location=[row['緯度'], row['経度']],
        popup=folium.Popup(popup_text, max_width=200),
        icon=folium.DivIcon(
            html=f'<div style="font-size: 12pt; color: white; background-color: {color}; border-radius: 50%; width: 26px; height: 26px; text-align: center; line-height: 26px; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">{rank}</div>'
        )
    ).add_to(m_full)

m_full.get_root().html.add_child(folium.Element(legend_html))

# 保存
m.save('grid_level_map_detail.html')
m_full.save('grid_level_map.html')

print("✅ マップ保存:")
print("  - grid_level_map.html (全体表示)")
print("  - grid_level_map_detail.html (詳細表示)")

