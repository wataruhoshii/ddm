"""
一様分布モデルによるAED推奨マップを作成（300mカバー範囲）
"""
import pandas as pd
import folium

# データ読み込み
df_rec = pd.read_csv('uniform_model_recommendations.csv')
df_results = pd.read_csv('uniform_model_results.csv')
df_aed = pd.read_csv('../01_aed_data/kawasaki_aed_merged.csv')

# 座標情報をマッチング
df_pop = pd.read_csv('chocho_analysis_all_years.csv')
df_pop_coords = df_pop.groupby(['区', '町丁名']).agg({'緯度': 'first', '経度': 'first'}).reset_index()

df_rec = df_rec.merge(df_pop_coords, on=['区', '町丁名'], how='left')

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

# 推奨場所を番号付きで表示（TOP10のみ）
for idx, rec in df_rec.head(10).iterrows():
    if pd.isna(rec['緯度']) or pd.isna(rec['経度']):
        continue
    
    # 300mカバー範囲
    folium.Circle(
        location=[rec['緯度'], rec['経度']],
        radius=300,
        color='#2e7d32',
        fill=True,
        fillOpacity=0.2,
        weight=2
    ).add_to(m)
    
    # カバー率に応じた色
    coverage = rec['カバー率']
    if coverage < 30:
        color = '#c53030'  # 赤（低カバー率）
        badge = '🔴'
    elif coverage < 60:
        color = '#dd6b20'  # オレンジ
        badge = '🟠'
    else:
        color = '#38a169'  # 緑
        badge = '🟢'
    
    # ポップアップ
    rank = idx + 1
    popup_text = f"""
    <div style="font-family: sans-serif; min-width: 220px;">
        <h4 style="margin: 0 0 8px 0; color: #2d3748;">
            {badge} 推奨 {rank}位: {rec['区']} {rec['町丁名']}
        </h4>
        <table style="width: 100%; font-size: 12px;">
            <tr><td>カバー率</td><td style="color: {color};"><b>{rec['カバー率']}%</b></td></tr>
            <tr><td>カバー外リスク加重人口</td><td><b>{int(rec['カバー外リスク加重人口']):,}</b></td></tr>
            <tr><td>リスク加重人口（累計）</td><td>{int(rec['リスク加重人口_累計']):,}</td></tr>
            <tr><td>総人口（累計）</td><td>{int(rec['総人口_累計']):,}</td></tr>
            <tr><td>最寄りAED</td><td>{rec['最寄りAED距離_m']}m</td></tr>
        </table>
        <p style="font-size: 11px; color: #666; margin-top: 8px;">
            ※一様分布モデル（50mグリッド）による分析<br>
            ※カバー範囲: 300m
        </p>
    </div>
    """
    
    folium.Marker(
        location=[rec['緯度'], rec['経度']],
        popup=folium.Popup(popup_text, max_width=280),
        icon=folium.DivIcon(
            html=f'<div style="font-size: 14pt; color: white; background-color: {color}; border-radius: 50%; width: 28px; height: 28px; text-align: center; line-height: 28px; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">{rank}</div>'
        )
    ).add_to(m)

# 凡例
legend_html = '''
<div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
            background-color: white; padding: 15px; border-radius: 8px;
            border: 2px solid #e2e8f0; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);">
    <b style="font-size: 14px;">🎯 AED設置推奨地域 TOP10</b><br>
    <span style="color: #666; font-size: 11px;">一様分布モデル（300mカバー）</span><br><br>
    <b>現在のカバー率</b><br>
    🔴 30%未満（最優先）<br>
    🟠 30〜60%（要対応）<br>
    🟢 60%以上（部分的未カバー）<br><br>
    🟢 円: 新規カバー範囲(300m)<br>
    ⚫ 点: 既存AED
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

m.save('uniform_model_map.html')
print("✅ マップ保存: uniform_model_map.html")

