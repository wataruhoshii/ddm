"""
将来予測を含むAED推奨マップを作成
"""
import pandas as pd
import folium

# データ読み込み
df_rec = pd.read_csv('future_aed_recommendations.csv')
df_aed = pd.read_csv('../01_aed_data/kawasaki_aed_merged.csv')

# マップ作成
center_lat = 35.57
center_lon = 139.55
m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='cartodbpositron')

# 既存AEDを薄く表示
for _, aed in df_aed.iterrows():
    if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
        folium.CircleMarker(
            location=[aed['latitude'], aed['longitude']],
            radius=3,
            color='gray',
            fill=True,
            fillOpacity=0.3
        ).add_to(m)

# 推奨場所を番号付きで表示
for _, rec in df_rec.iterrows():
    # 500mカバー範囲
    folium.Circle(
        location=[rec['緯度'], rec['経度']],
        radius=500,
        color='green',
        fill=True,
        fillOpacity=0.2,
        weight=2
    ).add_to(m)
    
    # リスク増加率に応じた色
    change_rate = rec['リスク加重変化率']
    if change_rate >= 70:
        color = '#c53030'  # 赤（急増）
        badge = '🔴'
    elif change_rate >= 40:
        color = '#dd6b20'  # オレンジ
        badge = '🟠'
    else:
        color = '#38a169'  # 緑
        badge = '🟢'
    
    # ポップアップ
    popup_text = f"""
    <div style="font-family: sans-serif; min-width: 200px;">
        <h4 style="margin: 0 0 8px 0; color: #2d3748;">
            {badge} 推奨 {int(rec['順位'])}位: {rec['区']} {rec['町丁名']}
        </h4>
        <table style="width: 100%; font-size: 12px;">
            <tr><td>将来重視スコア</td><td><b>{rec['将来重視スコア']}</b></td></tr>
            <tr><td>2025年リスク加重人口</td><td>{rec['リスク加重_2025']:,}</td></tr>
            <tr><td>2045年リスク加重人口</td><td>{rec['リスク加重_2045']:,}</td></tr>
            <tr><td>変化率</td><td style="color: {color};"><b>+{rec['リスク加重変化率']:.0f}%</b></td></tr>
            <tr><td>最寄りAED</td><td>{rec['最寄りAED距離_km']}km</td></tr>
        </table>
    </div>
    """
    
    folium.Marker(
        location=[rec['緯度'], rec['経度']],
        popup=folium.Popup(popup_text, max_width=250),
        icon=folium.DivIcon(
            html=f'<div style="font-size: 14pt; color: white; background-color: {color}; border-radius: 50%; width: 28px; height: 28px; text-align: center; line-height: 28px; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">{int(rec["順位"])}</div>'
        )
    ).add_to(m)

# 凡例
legend_html = '''
<div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
            background-color: white; padding: 15px; border-radius: 8px;
            border: 2px solid #e2e8f0; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);">
    <b style="font-size: 14px;">🔮 将来重視AED設置推奨</b><br><br>
    <b>リスク増加率（2025→2045）</b><br>
    🔴 70%以上（急増地域）<br>
    🟠 40〜70%（増加地域）<br>
    🟢 40%未満（安定地域）<br><br>
    🟢 円: 新規カバー範囲(500m)<br>
    ⚫ 点: 既存AED
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

m.save('future_aed_recommendation_map.html')
print("✅ マップ保存: future_aed_recommendation_map.html")


