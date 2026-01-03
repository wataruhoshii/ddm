"""
川崎市AED設置場所データの分析スクリプト
データソース: 川崎市オープンデータ
https://www.city.kawasaki.jp/350/page/0000099784.html
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from collections import Counter
import re

# 日本語フォント設定
matplotlib.rcParams['font.family'] = ['Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'Arial Unicode MS', 'sans-serif']

def load_data():
    """CSVデータを読み込む"""
    df = pd.read_csv('kawasaki_aed_utf8.csv', encoding='utf-8')
    # 空のカラムを削除
    df = df.dropna(axis=1, how='all')
    return df

def basic_stats(df):
    """基本統計情報を表示"""
    print("=" * 60)
    print("📊 川崎市AED設置施設データ 基本統計")
    print("=" * 60)
    print(f"\n📍 総設置数: {len(df)} 件")
    print(f"\n📋 カラム一覧:")
    for col in df.columns:
        print(f"   - {col}")
    
    print(f"\n🔢 データ型:")
    print(df.dtypes)

def analyze_availability(df):
    """24時間利用可能かどうかの分析"""
    print("\n" + "=" * 60)
    print("⏰ 24時間365日利用可能性分析")
    print("=" * 60)
    
    availability = df['24時間365日利用可能か'].value_counts()
    print("\n利用可能性の分布:")
    for status, count in availability.items():
        percentage = count / len(df) * 100
        print(f"   {status}: {count}件 ({percentage:.1f}%)")
    
    return availability

def analyze_by_ward(df):
    """区ごとの設置数を分析"""
    print("\n" + "=" * 60)
    print("🏘️ 区別AED設置数分析")
    print("=" * 60)
    
    # 住所から区を抽出
    def extract_ward(address):
        if pd.isna(address):
            return "不明"
        wards = ['川崎区', '幸区', '中原区', '高津区', '宮前区', '多摩区', '麻生区']
        for ward in wards:
            if ward in str(address):
                return ward
        return "不明"
    
    df['区'] = df['住所'].apply(extract_ward)
    ward_counts = df['区'].value_counts()
    
    print("\n区別設置数:")
    for ward, count in ward_counts.items():
        percentage = count / len(df) * 100
        bar = "█" * int(percentage / 2)
        print(f"   {ward}: {count:>4}件 ({percentage:>5.1f}%) {bar}")
    
    return ward_counts

def analyze_location_types(df):
    """設置場所タイプの分析"""
    print("\n" + "=" * 60)
    print("🏢 設置場所タイプ分析")
    print("=" * 60)
    
    # キーワードで分類
    categories = {
        '市役所・行政': ['市役所', '区役所', '出張所', '事務所'],
        '学校・教育': ['学校', '小学', '中学', '高校', '大学', '教育'],
        '福祉施設': ['福祉', '介護', '老人', '高齢', '障害'],
        '文化・スポーツ': ['体育館', 'スポーツ', 'プール', '文化', '図書館', '美術館', '博物館'],
        '病院・医療': ['病院', '医療', 'クリニック', '診療'],
        '公園・緑地': ['公園', '緑地'],
        'その他公共施設': ['センター', 'ホール', '会館'],
    }
    
    def categorize(location):
        if pd.isna(location):
            return 'その他'
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in str(location):
                    return category
        return 'その他'
    
    df['施設カテゴリ'] = df['設置場所'].apply(categorize)
    category_counts = df['施設カテゴリ'].value_counts()
    
    print("\n施設カテゴリ別設置数:")
    for category, count in category_counts.items():
        percentage = count / len(df) * 100
        print(f"   {category}: {count}件 ({percentage:.1f}%)")
    
    return category_counts

def analyze_coordinates(df):
    """緯度経度の分析"""
    print("\n" + "=" * 60)
    print("🗺️ 位置情報分析")
    print("=" * 60)
    
    # 緯度経度の範囲
    lat_min, lat_max = df['緯度'].min(), df['緯度'].max()
    lon_min, lon_max = df['経度'].min(), df['経度'].max()
    
    print(f"\n緯度の範囲: {lat_min:.6f} ～ {lat_max:.6f}")
    print(f"経度の範囲: {lon_min:.6f} ～ {lon_max:.6f}")
    print(f"緯度の平均: {df['緯度'].mean():.6f}")
    print(f"経度の平均: {df['経度'].mean():.6f}")

def create_visualizations(df, ward_counts, availability):
    """可視化グラフを作成"""
    print("\n" + "=" * 60)
    print("📈 グラフを生成中...")
    print("=" * 60)
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    
    # 1. 区別設置数の棒グラフ
    ax1 = axes[0, 0]
    colors = plt.cm.Set3(range(len(ward_counts)))
    ward_counts.plot(kind='bar', ax=ax1, color=colors)
    ax1.set_title('区別AED設置数', fontsize=14, fontweight='bold')
    ax1.set_xlabel('区')
    ax1.set_ylabel('設置数')
    ax1.tick_params(axis='x', rotation=45)
    for i, v in enumerate(ward_counts.values):
        ax1.text(i, v + 5, str(v), ha='center', fontsize=10)
    
    # 2. 24時間利用可能性の円グラフ
    ax2 = axes[0, 1]
    colors2 = ['#2ecc71', '#e74c3c']
    availability.plot(kind='pie', ax=ax2, autopct='%1.1f%%', colors=colors2)
    ax2.set_title('24時間365日利用可能か', fontsize=14, fontweight='bold')
    ax2.set_ylabel('')
    
    # 3. 施設カテゴリ別（横棒グラフ）
    ax3 = axes[1, 0]
    category_counts = df['施設カテゴリ'].value_counts()
    category_counts.plot(kind='barh', ax=ax3, color=plt.cm.Paired(range(len(category_counts))))
    ax3.set_title('施設カテゴリ別設置数', fontsize=14, fontweight='bold')
    ax3.set_xlabel('設置数')
    
    # 4. 位置情報の散布図
    ax4 = axes[1, 1]
    scatter = ax4.scatter(df['経度'], df['緯度'], 
                          c=df['区'].astype('category').cat.codes, 
                          alpha=0.6, s=20, cmap='tab10')
    ax4.set_title('AED設置位置マップ', fontsize=14, fontweight='bold')
    ax4.set_xlabel('経度')
    ax4.set_ylabel('緯度')
    
    plt.tight_layout()
    plt.savefig('kawasaki_aed_analysis.png', dpi=150, bbox_inches='tight')
    print("✅ グラフを kawasaki_aed_analysis.png に保存しました")
    
    return fig

def export_geojson(df):
    """GeoJSON形式でエクスポート"""
    import json
    
    features = []
    for _, row in df.iterrows():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row['経度'], row['緯度']]
            },
            "properties": {
                "台帳番号": int(row['台帳番号']) if pd.notna(row['台帳番号']) else None,
                "設置場所": row['設置場所'],
                "設置位置": row['設置位置'],
                "住所": row['住所'],
                "24時間利用可能": row['24時間365日利用可能か'],
                "利用開始時間": row['利用開始時間'],
                "利用終了時間": row['利用終了時間'],
            }
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open('kawasaki_aed.geojson', 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    
    print("✅ GeoJSONを kawasaki_aed.geojson に保存しました")

def main():
    print("\n🏥 川崎市AED設置場所データ分析ツール 🏥\n")
    
    # データ読み込み
    df = load_data()
    
    # 基本統計
    basic_stats(df)
    
    # 各種分析
    availability = analyze_availability(df)
    ward_counts = analyze_by_ward(df)
    analyze_location_types(df)
    analyze_coordinates(df)
    
    # 可視化
    try:
        create_visualizations(df, ward_counts, availability)
    except Exception as e:
        print(f"⚠️ グラフ生成でエラー: {e}")
    
    # GeoJSONエクスポート
    export_geojson(df)
    
    print("\n" + "=" * 60)
    print("✅ 分析完了！")
    print("=" * 60)
    print("\n生成されたファイル:")
    print("  📄 kawasaki_aed_utf8.csv - UTF-8変換済みCSV")
    print("  🗺️ kawasaki_aed.geojson - GeoJSON形式（地図アプリ用）")
    print("  📊 kawasaki_aed_analysis.png - 分析グラフ")

if __name__ == "__main__":
    main()

