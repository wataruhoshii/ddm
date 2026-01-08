"""
川崎市AED空間分析 - インタラクティブマップ
- 町丁別の人口・高齢者分布
- AED設置場所とカバー範囲
- 空白地帯の可視化
"""

import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap, MarkerCluster
import json

def main():
    print("=" * 70)
    print("🗺️  川崎市AED空間分析マップ作成")
    print("=" * 70)
    
    # ========================================
    # データ読み込み
    # ========================================
    print("\n📂 データ読み込み中...")
    
    # 人口データ
    df_pop = pd.read_csv('../02_population_data/kawasaki_chocho_age_processed.csv')
    
    # 町丁ごとの集計
    df_chocho = df_pop.groupby(['町丁コード', '区', '町丁名', '緯度', '経度']).agg({
        '総人口': 'first',
        '高齢化率': 'first'
    }).reset_index()
    
    # 高齢者人口
    df_elderly = df_pop[df_pop['年齢5歳階級'].isin(['65〜69歳', '70〜74歳', '75〜79歳', '80〜84歳', '85〜89歳', '90〜94歳', '95歳以上'])]
    elderly_by_chocho = df_elderly.groupby('町丁コード')['人口'].sum().reset_index()
    elderly_by_chocho.columns = ['町丁コード', '高齢者人口']
    df_chocho = df_chocho.merge(elderly_by_chocho, on='町丁コード', how='left')
    
    # 分析結果
    df_result = pd.read_csv('aed_chocho_analysis_result.csv')
    df_chocho = df_chocho.merge(
        df_result[['町丁コード', '最寄りAED距離_km', '500m以内AED数', 'リスクスコア']],
        on='町丁コード', how='left'
    )
    
    # AEDデータ
    df_aed = pd.read_csv('../01_aed_data/kawasaki_aed_merged.csv')
    
    print(f"  町丁数: {len(df_chocho)}")
    print(f"  AED数: {len(df_aed)}")
    
    # ========================================
    # マップ1: 総合分析マップ
    # ========================================
    print("\n🗺️  総合分析マップ作成中...")
    
    # 川崎市の中心座標
    center_lat = df_chocho['緯度'].mean()
    center_lon = df_chocho['経度'].mean()
    
    m1 = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='cartodbpositron')
    
    # 町丁ごとのマーカー（リスクスコアで色分け）
    for _, row in df_chocho.iterrows():
        if pd.isna(row['緯度']) or row['総人口'] == 0:
            continue
        
        # リスクスコアで色を決定
        risk = row.get('リスクスコア', 0) or 0
        if risk >= 40:
            color = 'red'
        elif risk >= 30:
            color = 'orange'
        elif risk >= 20:
            color = 'yellow'
        else:
            color = 'green'
        
        # 500m以内にAEDがない場合は強調
        if row.get('500m以内AED数', 0) == 0:
            icon = folium.Icon(color=color, icon='exclamation-sign', prefix='glyphicon')
        else:
            icon = folium.Icon(color=color, icon='home', prefix='glyphicon')
        
        popup_text = f"""
        <b>{row['区']} {row['町丁名']}</b><br>
        総人口: {int(row['総人口']):,}人<br>
        高齢者: {int(row.get('高齢者人口', 0)):,}人 ({row['高齢化率']:.1f}%)<br>
        最寄りAED: {row.get('最寄りAED距離_km', 0):.2f}km<br>
        500m以内AED: {int(row.get('500m以内AED数', 0))}台<br>
        リスクスコア: {risk:.1f}
        """
        
        folium.Marker(
            location=[row['緯度'], row['経度']],
            popup=folium.Popup(popup_text, max_width=250),
            icon=icon
        ).add_to(m1)
    
    # AEDマーカー（クラスター）
    aed_cluster = MarkerCluster(name='AED設置場所').add_to(m1)
    for _, aed in df_aed.iterrows():
        if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
            popup_text = f"""
            <b>{aed['name']}</b><br>
            {aed.get('address', '')}<br>
            24時間: {'✅' if aed.get('available_24h') else '❌'}
            """
            folium.Marker(
                location=[aed['latitude'], aed['longitude']],
                popup=folium.Popup(popup_text, max_width=200),
                icon=folium.Icon(color='blue', icon='heart', prefix='glyphicon')
            ).add_to(aed_cluster)
    
    # レイヤーコントロール
    folium.LayerControl().add_to(m1)
    
    # 凡例
    legend_html = '''
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid gray; font-size: 12px;">
        <b>凡例</b><br>
        🔴 高リスク (40+)<br>
        🟠 中リスク (30-40)<br>
        🟡 低リスク (20-30)<br>
        🟢 安全 (20未満)<br>
        ⚠️ AED空白地帯<br>
        💙 AED設置場所
    </div>
    '''
    m1.get_root().html.add_child(folium.Element(legend_html))
    
    m1.save('aed_analysis_map.html')
    print("  💾 保存: aed_analysis_map.html")
    
    # ========================================
    # マップ2: 高齢者人口ヒートマップ
    # ========================================
    print("\n🗺️  高齢者人口ヒートマップ作成中...")
    
    m2 = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='cartodbpositron')
    
    # ヒートマップデータ（高齢者人口で重み付け）
    heat_data = []
    for _, row in df_chocho.iterrows():
        if pd.notna(row['緯度']) and row.get('高齢者人口', 0) > 0:
            # 高齢者人口を重みとして使用
            weight = row['高齢者人口'] / df_chocho['高齢者人口'].max()
            heat_data.append([row['緯度'], row['経度'], weight])
    
    HeatMap(heat_data, radius=20, blur=15, name='高齢者人口密度').add_to(m2)
    
    # AEDを表示
    for _, aed in df_aed.iterrows():
        if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
            folium.CircleMarker(
                location=[aed['latitude'], aed['longitude']],
                radius=3,
                color='blue',
                fill=True,
                popup=aed['name']
            ).add_to(m2)
    
    folium.LayerControl().add_to(m2)
    m2.save('aed_elderly_heatmap.html')
    print("  💾 保存: aed_elderly_heatmap.html")
    
    # ========================================
    # マップ3: AED空白地帯マップ
    # ========================================
    print("\n🗺️  AED空白地帯マップ作成中...")
    
    m3 = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='cartodbpositron')
    
    # AEDの500mカバー範囲を表示
    for _, aed in df_aed.iterrows():
        if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
            folium.Circle(
                location=[aed['latitude'], aed['longitude']],
                radius=500,  # 500m
                color='blue',
                fill=True,
                fillOpacity=0.1,
                weight=1
            ).add_to(m3)
    
    # 空白地帯（500m以内にAEDがない町丁）を強調
    blank_areas = df_chocho[(df_chocho['500m以内AED数'] == 0) & (df_chocho['総人口'] > 0)]
    for _, row in blank_areas.iterrows():
        if pd.notna(row['緯度']):
            # 人口が多いほど大きな円
            radius = max(50, min(300, row['総人口'] / 50))
            
            folium.Circle(
                location=[row['緯度'], row['経度']],
                radius=radius,
                color='red',
                fill=True,
                fillOpacity=0.5,
                popup=f"{row['区']} {row['町丁名']}<br>人口: {int(row['総人口']):,}<br>高齢者: {int(row.get('高齢者人口', 0)):,}"
            ).add_to(m3)
    
    # 凡例
    legend_html2 = '''
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid gray; font-size: 12px;">
        <b>凡例</b><br>
        🔵 AEDカバー範囲(500m)<br>
        🔴 AED空白地帯<br>
        (円の大きさ = 人口)
    </div>
    '''
    m3.get_root().html.add_child(folium.Element(legend_html2))
    
    m3.save('aed_blank_areas_map.html')
    print("  💾 保存: aed_blank_areas_map.html")
    
    # ========================================
    # マップ4: 年齢層別分析マップ
    # ========================================
    print("\n🗺️  年齢層別リスクマップ作成中...")
    
    m4 = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='cartodbpositron')
    
    # 後期高齢者（75歳以上）の人口を計算
    df_late_elderly = df_pop[df_pop['年齢5歳階級'].isin(['75〜79歳', '80〜84歳', '85〜89歳', '90〜94歳', '95歳以上'])]
    late_elderly = df_late_elderly.groupby('町丁コード')['人口'].sum().reset_index()
    late_elderly.columns = ['町丁コード', '後期高齢者人口']
    df_chocho_temp = df_chocho.merge(late_elderly, on='町丁コード', how='left')
    
    # 後期高齢者が多く、AEDが遠い地域を強調
    for _, row in df_chocho_temp.iterrows():
        if pd.isna(row['緯度']) or row['総人口'] == 0:
            continue
        
        late_elderly_pop = row.get('後期高齢者人口', 0) or 0
        distance = row.get('最寄りAED距離_km', 0) or 0
        
        # 後期高齢者100人以上かつAED 300m以上を高リスクとして表示
        if late_elderly_pop >= 100 and distance >= 0.3:
            # リスクに応じた色
            if late_elderly_pop >= 500:
                color = 'darkred'
            elif late_elderly_pop >= 300:
                color = 'red'
            elif late_elderly_pop >= 200:
                color = 'orange'
            else:
                color = 'yellow'
            
            folium.CircleMarker(
                location=[row['緯度'], row['経度']],
                radius=max(5, late_elderly_pop / 100),
                color=color,
                fill=True,
                fillOpacity=0.7,
                popup=f"{row['区']} {row['町丁名']}<br>後期高齢者: {int(late_elderly_pop):,}人<br>最寄りAED: {distance:.2f}km"
            ).add_to(m4)
    
    # AEDを表示
    for _, aed in df_aed.iterrows():
        if pd.notna(aed['latitude']) and pd.notna(aed['longitude']):
            folium.CircleMarker(
                location=[aed['latitude'], aed['longitude']],
                radius=3,
                color='blue',
                fill=True
            ).add_to(m4)
    
    legend_html3 = '''
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid gray; font-size: 12px;">
        <b>後期高齢者(75+) & AED 300m+</b><br>
        🟤 500人以上<br>
        🔴 300-500人<br>
        🟠 200-300人<br>
        🟡 100-200人<br>
        🔵 AED設置場所
    </div>
    '''
    m4.get_root().html.add_child(folium.Element(legend_html3))
    
    m4.save('aed_late_elderly_risk_map.html')
    print("  💾 保存: aed_late_elderly_risk_map.html")
    
    # ========================================
    # 完了
    # ========================================
    print("\n" + "=" * 70)
    print("✅ マップ作成完了！")
    print("=" * 70)
    print("\n生成されたマップ:")
    print("  1. aed_analysis_map.html       - 総合分析マップ")
    print("  2. aed_elderly_heatmap.html    - 高齢者人口ヒートマップ")
    print("  3. aed_blank_areas_map.html    - AED空白地帯マップ")
    print("  4. aed_late_elderly_risk_map.html - 後期高齢者リスクマップ")
    print("\nブラウザで開いて確認してください！")

if __name__ == '__main__':
    main()


