# Discollama

Discord bot powered by Ollama - Bring AI conversations directly to your Discord server!

## 概要 (Overview)

DiscollamaはDiscordとOllamaを統合するボットです。Discordサーバー上でOllamaのAIモデルと対話できます。

Discollama is a Discord bot that integrates with Ollama, allowing you to interact with AI models directly from your Discord server.

## 機能 (Features)

- 🤖 DiscordチャンネルでOllamaのAIモデルと会話
- 💬 自然な対話形式でのやり取り
- 🔧 カスタマイズ可能な設定
- 🚀 簡単なセットアップとデプロイ

## 必要要件 (Prerequisites)

- Python 3.8以上
- Discord Bot Token
- Ollama (ローカルまたはリモートでの実行)
- discord.py ライブラリ

## インストール (Installation)

### 1. リポジトリのクローン

```bash
git clone https://github.com/messpy/Discollama.git
cd Discollama
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

必要なパッケージ:
- `discord.py` - Discord API wrapper
- `aiohttp` - Ollama API通信用
- `python-dotenv` - 環境変数管理

### 3. Ollamaのセットアップ

Ollamaをまだインストールしていない場合:

```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# モデルのダウンロード (例: llama2)
ollama pull llama2
```

### 4. Discord Botの作成

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. "New Application"をクリック
3. Bot設定でBotを追加
4. トークンをコピー
5. 必要な権限を設定:
   - Read Messages/View Channels
   - Send Messages
   - Read Message History

### 5. 環境変数の設定

`.env`ファイルを作成:

```env
DISCORD_TOKEN=your_discord_bot_token_here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2
```

## 使い方 (Usage)

### ボットの起動

```bash
python bot.py
```

### Discordでの使用

1. ボットをサーバーに招待
2. チャンネルでボットをメンション: `@Discollama こんにちは！`
3. またはDMで直接メッセージを送信

### コマンド例

```
@Discollama プログラミングについて教えて
@Discollama Pythonでリストを逆順にする方法は？
@Discollama 面白い話をして
```

## 設定 (Configuration)

### config.yaml (オプション)

```yaml
discord:
  prefix: "!"
  activity: "Ollamaで思考中..."

ollama:
  host: "http://localhost:11434"
  model: "llama2"
  temperature: 0.7
  max_tokens: 2048

bot:
  response_timeout: 30
  max_history: 10
```

## トラブルシューティング (Troubleshooting)

### ボットがオンラインにならない
- Discordトークンが正しいか確認
- `.env`ファイルが正しく配置されているか確認

### Ollamaに接続できない
- Ollamaが起動しているか確認: `ollama list`
- `OLLAMA_HOST`の設定が正しいか確認
- ファイアウォール設定を確認

### 応答が遅い
- より軽量なモデルを使用: `ollama pull phi` または `ollama pull tinyllama`
- `max_tokens`を調整
- GPUを使用している場合は設定を確認

## 開発 (Development)

### プロジェクト構造

```
Discollama/
├── bot.py              # メインボットファイル
├── cogs/               # コマンド拡張
├── utils/              # ユーティリティ関数
├── config.yaml         # 設定ファイル
├── requirements.txt    # Python依存関係
└── README.md          # このファイル
```

### 貢献 (Contributing)

プルリクエストを歓迎します！

1. フォークする
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを開く

## ライセンス (License)

このプロジェクトはMITライセンスの下で公開されています。

## リンク (Links)

- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [Ollama](https://ollama.com/)
- [Discord Developer Portal](https://discord.com/developers/applications)

## サポート (Support)

問題が発生した場合は、[Issues](https://github.com/messpy/Discollama/issues)でお知らせください。

---

Made with ❤️ by messpy