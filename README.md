## Civic Reach

簡易な説明と、アプリを起動するための最低限の手順のみを記載しています。

### 必要環境
- **Python**: 3.10 以上を推奨
- **API キー**: Google Gemini (`GEMINI_API_KEY`)

### セットアップ
1. **依存関係のインストール**
   ```bash
   pip install -r requirements.txt
   ```
2. **環境変数の設定 (.env)**
   ```bash
   echo "GEMINI_API_KEY=あなたの_API_キー" > .env
   ```

### 起動方法
```bash
streamlit run app.py --server.headless true
```


