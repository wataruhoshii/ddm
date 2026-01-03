# 川崎市AED最適配置分析プロジェクト

川崎市のAED設置状況を分析し、人口分布（特に高齢者）に基づいた最適配置を検討するプロジェクトです。

## 📁 フォルダ構成

```
DDM8/
├── 01_aed_data/          # AEDデータの取得・整理
├── 02_population_data/   # 人口データの取得
├── 03_analysis/          # データ分析・最適化
└── README.md
```

## 🔄 分析フロー

### Step 1: AEDデータ取得 (`01_aed_data/`)

3つのソースからAEDデータを収集・統合:

| ソース | 件数 | 内容 |
|--------|------|------|
| 川崎市オープンデータ | 617件 | 公共施設のAED |
| 全国AEDマップ | 667件 | 民間施設含む |
| セブン-イレブン | 208件 | コンビニAED |

**統合後: 936件**（重複除去済み）

### Step 2: 人口データ取得 (`02_population_data/`)

e-Stat API（政府統計ポータル）から取得:
- 年齢5歳階級別人口
- 区別の高齢化率

### Step 3: 分析 (`03_analysis/`)

AEDと人口データを組み合わせて分析:
- 区別AED密度
- 高齢者人口あたりAED数
- AED不足リスクスコア

## 📊 主な分析結果

### AED不足リスクが高い区 TOP3

| 順位 | 区 | リスクスコア | 高齢化率 | 人口/AED |
|------|------|------------|---------|----------|
| 1 | 宮前区 | 92.3 | 18.0% | 2,361人/台 |
| 2 | 麻生区 | 74.2 | 19.8% | 1,807人/台 |
| 3 | 幸区 | 54.7 | 18.1% | 1,694人/台 |

## 🛠️ 使用方法

### 必要なライブラリ

```bash
pip install pandas requests matplotlib openpyxl
```

### 実行順序

```bash
# 1. AEDデータ取得・統合
cd 01_aed_data
python fetch_aed_map.py      # 全国AEDマップからデータ取得
python merge_aed_data.py     # 3ソースを統合

# 2. 人口データ取得
cd ../02_population_data
python fetch_population.py   # e-Statから人口データ取得

# 3. 分析実行
cd ../03_analysis
python aed_optimization.py   # 最適配置分析
```

## 📄 データソース

- **川崎市オープンデータ**: https://www.city.kawasaki.jp/350/page/0000099784.html
- **全国AEDマップ**: https://www.qqzaidanmap.jp/
- **e-Stat（政府統計）**: https://www.e-stat.go.jp/

## 📅 データ時点

- AEDデータ: 2025年10月時点
- 人口データ: 令和2年（2020年）国勢調査

