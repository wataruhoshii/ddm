# 01_aed_data - AEDデータ取得・整理

川崎市のAED設置場所データを収集・統合するフォルダです。

## 📁 ファイル構成

### スクリプト

| ファイル | 説明 |
|----------|------|
| `fetch_aed_map.py` | 全国AEDマップAPIからデータ取得 |
| `merge_aed_data.py` | 3ソースのデータを統合 |
| `analyze_aed.py` | 基本的な分析・可視化 |

### データファイル（入力）

| ファイル | 説明 |
|----------|------|
| `kawasaki_aed.csv` | 川崎市オープンデータ（元ファイル・Shift-JIS） |
| `kawasaki_aed_utf8.csv` | 川崎市オープンデータ（UTF-8変換済） |
| `kawasaki_711_aed.xlsx` | セブン-イレブン設置店舗リスト |

### データファイル（出力）

| ファイル | 説明 |
|----------|------|
| `kawasaki_aed_national_map.csv` | 全国AEDマップから取得したデータ |
| `kawasaki_aed_national_map.geojson` | 同上（GeoJSON形式） |
| `kawasaki_aed_merged.csv` | **統合済みデータ（最終版）** |
| `kawasaki_aed_merged.geojson` | 同上（GeoJSON形式） |
| `kawasaki_aed_analysis.png` | 分析グラフ |

## 🔄 データフロー

```
川崎市オープンデータ (617件)
        ↓
全国AEDマップ (667件)      → merge_aed_data.py → kawasaki_aed_merged.csv (936件)
        ↓
セブン-イレブン (208件)
```

## 📊 統合データの内訳

| ソース | 採用件数 |
|--------|----------|
| 川崎市オープンデータ | 532件 |
| 全国AEDマップ | 314件 |
| セブン-イレブン | 90件 |
| **合計** | **936件** |

## 🛠️ 使用方法

```bash
# 全国AEDマップからデータ取得（約1分）
python fetch_aed_map.py

# 3ソースを統合（セブン-イレブンの住所→座標変換で約1分）
python merge_aed_data.py

# 基本分析
python analyze_aed.py
```


