# Civic Navi: スラッジ監査の評価基準と根拠 (Evaluation Methodology)

Civic Navi は、OECD（経済協力開発機構）が2024年に発表したレポート **『Fixing Frictions: ‘Sludge audits’ around the world』** で定義された行動科学的フレームワークに基づき、行政文書の「スラッジ（Sludge）」を監査・評価します。

本ツールは、単なる文章の読みやすさ（Readability）だけでなく、市民が感じる心理的負担（Psychological Costs）を定量化するために、以下のロジックを採用しています。

---

## 1. 「スラッジ (Sludge)」の定義
本ツールにおける「スラッジ」の定義は、OECDレポートの定義に準拠しています。

> **Sludge describes the ‘excessive or unjustified’ frictions that make it harder for people to follow through on their intentions and achieve their goals.** > （スラッジとは、人々が意図した行動を完遂し、目標を達成することを困難にする『過度で不当な』摩擦のことを指す。）
>
> *Source: OECD (2024), Fixing Frictions, Box 1.1, p.8*

---

## 2. 評価ロジック：4つの心理的コスト
Civic Navi は、レポート **Page 9, Figure 1.1 "The Psychological Costs of Sludge"** に示された4つのコスト分類に基づき、100点満点からの減点方式でスコアリングを行います。

### 🔍 1. 探索コスト (Search Costs)
情報を見つけ出し、手続きに必要な要件を特定するためにかかる時間と労力です。
* **監査観点:**
    * 必要な情報（期限、連絡先、対象者）が文書内に埋もれていないか？
    * 「次に何をすべきか（Next Steps）」が明確か？
* **出典:** *Figure 1.1, p.9; Annex A.3, p.49 (NSW Sludge Scales "Next steps")*

### 🤔 2. 決断コスト (Decision Costs)
情報の比較検討や、自分に関連する選択肢を決定する際にかかる認知負荷です。
* **監査観点:**
    * 選択肢が多すぎて混乱を招いていないか（Choice Overload）？
    * 条件分岐が複雑で、自分が対象者かどうかの判断が困難ではないか？
* **出典:** *Figure 1.1, p.9; p.10 (Decision points)*

### 🧠 3. 認知的コスト (Cognitive Costs)
情報を読み解き、理解し、記憶するために必要な精神的リソース（Cognitive Bandwidth）の消費量です。
* **監査観点:**
    * 専門用語（Jargon）や受動態が多用されていないか？
    * 貧困状態などによる「認知的希少性（Cognitive Scarcity）」にある市民にとって、負担が大きすぎないか？
* **出典:** *Figure 1.1, p.9; p.14 (Cognitive scarcity)*

### ❤️ 4. 感情的コスト (Emotional Costs)
手続きを行う過程で市民が感じる心理的な痛み、ストレス、屈辱感です。
* **監査観点:**
    * 威圧的、官僚的、冷淡なトーン（Tone of voice）ではないか？
    * 支援を受けることに対する「スティグマ（恥ずかしさ）」や不安を煽っていないか？
* **出典:** *Figure 1.1, p.9; p.14 (Stigma towards persons with disabilities)*

---

## 3. 改善アプローチ：EASTフレームワーク
特定されたスラッジを解消するための改善提案は、OECDレポートでも推奨されている行動科学のフレームワーク（BIT等により開発）に基づいています。

レポート内の **"suggest making behaviours easier to do, more inclusive, more compelling and easier to follow through to completion" (p.19)** という指針を、以下のEASTフレームワークにマッピングして提案を生成しています。

* **Easy (かんたん):** デフォルト化、摩擦の低減
* **Attractive (印象的):** 注意を引く、メリットの提示
* **Social (社会的):** 社会規範の活用、安心感の醸成
* **Timely (タイムリー):** 適切なタイミングでの介入

---

## 参考文献 (References)
* **OECD (2024)**, *Fixing Frictions: ‘Sludge audits’ around the world*, OECD Public Governance Policy Papers, OECD Publishing, Paris. [https://doi.org/10.1787/14e1c5e8-en-fr](https://doi.org/10.1787/14e1c5e8-en-fr)
* **New South Wales Government (2024)**, *The NSW Government Sludge Audit Method*.