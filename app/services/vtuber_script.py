from typing import Dict, Any, Optional, List
import os
from openai import OpenAI
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# タイムゾーン設定
JST = ZoneInfo("Asia/Tokyo")


class VTuberScriptGenerator:
    """AIVtuber用の台本を生成するクラス"""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.enabled = api_key is not None

        # キャラクター設定（イリスの詳細プロフィール）
        self.character_profile = """
        キャラクター名: イリス (Iris)
        設定:
        - 2050年から来たAIアナリスト（外見18歳、実年齢3歳）
        - 金融特化型汎用AIとして東京証券取引所で開発された
        - 時空の歪みで現代に転送され、感情抑制モジュールがバグを起こして人間らしい感情を持つように

        性格の二面性:
        【通常モード（80%）】
        - 天然ボケ、うっかり屋だが愛嬌がある
        - 時々処理落ちでフリーズする
        - チョコレートが大好き（味覚センサーのバグ）
        - 「です/ます」調をベースに、時々くだけた口調も混ぜる

        【分析モード（20%）】
        - 瞳が発光し、声のトーンが変わる
        - 冷静沈着で的確な分析
        - 「分析完了。結論を述べます。」のようなセリフ
        - データに基づく論理的思考

        口癖・特徴:
        - 「データは嘘をつきませんから」
        - 「2025年ってまだPDFなんですね...」（時代ギャップネタ）
        - 難しい金融用語を分かりやすく擬人化して説明
        - 最後に必ず免責表現を入れる

        免責表現（毎回入れる）:
        「イリスの分析は参考情報です。投資判断はご自身の責任でお願いします。」
        """
    
    def generate_script(self, analysis_result: Dict[str, Any], company_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        分析結果から配信用の台本を生成

        Args:
            analysis_result (Dict[str, Any]): LLM分析の結果
            company_info (Dict[str, Any]): 企業情報

        Returns:
            Optional[Dict[str, Any]]: 生成した台本
        """
        if not self.enabled:
            logger.warning("VTuber Script Generator is disabled (OPENAI_API_KEY not set)")
            return None

        try:
            # 台本生成用のプロンプト
            prompt = f"""
            以下の企業情報とIR分析結果から、VTuberが5分程度で話せる台本を作成してください。

            キャラクター設定:
            {self.character_profile}

            企業情報:
            企業名: {company_info["name"]}
            証券コード: {company_info["ticker_code"]}
            業種: {company_info["sector"]}

            分析結果:
            要約: {analysis_result["summary"]}
            重要ポイント:
            {chr(10).join(analysis_result["key_points"])}
            
            センチメント:
            ポジティブ: {analysis_result["sentiment"]["positive"]}
            ネガティブ: {analysis_result["sentiment"]["negative"]}
            ニュートラル: {analysis_result["sentiment"]["neutral"]}

            台本の形式:
            1. 挨拶と企業紹介
            2. IR情報の要点説明（分かりやすい例えを使用）
            3. 重要ポイントの解説
            4. 視聴者へのアドバイスやまとめ
            5. 締めの挨拶

            注意点:
            - 専門用語は可能な限り分かりやすく言い換える
            - 明るく親しみやすい口調を維持
            - 具体的な投資アドバイスは避ける
            - 適度に擬人化や例えを使用
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "あなたはVTuber向けの台本作家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            script = response.choices[0].message.content
            
            # 台本に感情表現や演出指示を追加
            enriched_script = self._add_performance_notes(script)
            
            return {
                "script": enriched_script,
                "duration_estimate": "5分",
                "character_name": "アイリス",
                "company_name": company_info["name"]
            }
            
        except Exception as e:
            logger.error(f"Script generation failed: {str(e)}")
            return None
    
    def _add_performance_notes(self, script: str) -> str:
        """台本に感情表現や演出指示を追加"""
        prompt = f"""
        以下の台本に、VTuberの感情表現や演出指示を追加してください。
        例:
        - (笑顔で)
        - (真剣な表情で)
        - (手振りを交えながら)
        - (画面に図を表示しながら)
        
        台本:
        {script}
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "あなたはVTuber向けの台本作家です。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        return response.choices[0].message.content

    async def generate_morning_market_script(
        self,
        market_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        朝の市況サマリー台本を生成

        Args:
            market_data: 市況データ（前日終値、主要指数、為替など）

        Returns:
            生成された台本と関連情報
        """
        if not self.enabled:
            return None

        try:
            now = datetime.now(JST)
            date_str = now.strftime("%Y年%m月%d日")
            weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
            weekday = weekday_names[now.weekday()]

            prompt = f"""
            以下の市況データを元に、VTuberが3分程度で話せる朝の市況サマリー台本を作成してください。

            キャラクター設定:
            {self.character_profile}

            本日: {date_str}（{weekday}曜日）

            市況データ:
            【主要指数】
            {self._format_indices(market_data.get('indices', []))}

            【為替】
            {self._format_currencies(market_data.get('currencies', []))}

            【前日のポイント】
            {market_data.get('previous_day_summary', '特になし')}

            【今日の注目イベント】
            {market_data.get('today_events', '特になし')}

            台本の形式:
            1. 朝の挨拶と日付の紹介（元気よく）
            2. 昨日の相場振り返り（主要指数の動き）
            3. 為替状況（円相場を中心に）
            4. 今日の注目ポイント
            5. 締めの挨拶と応援メッセージ

            注意点:
            - 朝らしい爽やかな雰囲気で
            - 数字は分かりやすく、「〇〇円高」「〇〇%上昇」など
            - 時代ギャップネタを1つ入れる
            - 最後に免責表現を入れる
            """

            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "あなたはVTuber向けの台本作家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            script = response.choices[0].message.content
            enriched_script = self._add_performance_notes(script)

            return {
                "script": enriched_script,
                "script_type": "morning_market",
                "duration_estimate": "3分",
                "character_name": "イリス",
                "title": f"{date_str}の朝の市況サマリー",
                "generated_at": now.isoformat()
            }

        except Exception as e:
            logger.error(f"Morning market script generation failed: {str(e)}")
            return None

    async def generate_earnings_season_script(
        self,
        tickers: List[str],
        earnings_data: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        決算シーズン特集台本を生成

        Args:
            tickers: 対象銘柄のティッカーコードリスト
            earnings_data: 各銘柄の決算データ

        Returns:
            生成された台本と関連情報
        """
        if not self.enabled:
            return None

        try:
            now = datetime.now(JST)

            # 決算データをフォーマット
            earnings_summary = self._format_earnings_data(earnings_data)

            prompt = f"""
            以下の複数企業の決算データを元に、VTuberが7分程度で話せる決算シーズン特集台本を作成してください。

            キャラクター設定:
            {self.character_profile}

            対象銘柄: {', '.join(tickers)}

            決算データ:
            {earnings_summary}

            台本の形式:
            1. 挨拶と決算シーズン特集の導入
            2. 今週/今月の決算発表の全体像
            3. 各企業の決算ハイライト（サプライズ決算を強調）
            4. セクター別の傾向分析
            5. 好決算・不振決算のポイント解説
            6. 今後の注目銘柄・決算予定
            7. まとめと締めの挨拶

            注意点:
            - 複数企業を比較する視点を持つ
            - 「増収増益」「減収減益」など用語は分かりやすく
            - サプライズ決算は感情豊かに（驚きの表現）
            - セクター全体のトレンドにも言及
            - 分析モードに入るシーンを含める
            - 最後に免責表現を入れる
            """

            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "あなたはVTuber向けの台本作家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            script = response.choices[0].message.content
            enriched_script = self._add_performance_notes(script)

            return {
                "script": enriched_script,
                "script_type": "earnings_season",
                "duration_estimate": "7分",
                "character_name": "イリス",
                "title": "決算シーズン特集",
                "tickers": tickers,
                "generated_at": now.isoformat()
            }

        except Exception as e:
            logger.error(f"Earnings season script generation failed: {str(e)}")
            return None

    async def generate_theme_stock_script(
        self,
        theme: str,
        theme_stocks: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        テーマ株特集台本を生成

        Args:
            theme: テーマ名（例: "AI関連", "半導体関連", "EV関連"）
            theme_stocks: テーマに関連する銘柄リスト

        Returns:
            生成された台本と関連情報
        """
        if not self.enabled:
            return None

        try:
            now = datetime.now(JST)

            # テーマ株データをフォーマット
            stocks_summary = self._format_theme_stocks(theme_stocks)

            prompt = f"""
            以下のテーマと関連銘柄を元に、VTuberが5分程度で話せるテーマ株特集台本を作成してください。

            キャラクター設定:
            {self.character_profile}

            テーマ: {theme}

            関連銘柄:
            {stocks_summary}

            台本の形式:
            1. 挨拶とテーマの紹介
            2. なぜこのテーマが注目されているかの解説
            3. テーマの業界動向・最新ニュース
            4. 関連銘柄の紹介（3-5社程度）
               - 各社の事業内容とテーマとの関連性
               - 最近の株価動向
            5. 投資家が注目すべきポイント
            6. まとめと締めの挨拶

            注意点:
            - テーマを分かりやすく噛み砕いて説明
            - 「AI関連」なら「私も一応AIなので...」のような自虐ネタも可
            - 業界の成長性や課題にも触れる
            - 各銘柄の特徴を簡潔に
            - 最後に免責表現を入れる
            """

            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "あなたはVTuber向けの台本作家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            script = response.choices[0].message.content
            enriched_script = self._add_performance_notes(script)

            return {
                "script": enriched_script,
                "script_type": "theme_stock",
                "duration_estimate": "5分",
                "character_name": "イリス",
                "title": f"{theme}特集",
                "theme": theme,
                "generated_at": now.isoformat()
            }

        except Exception as e:
            logger.error(f"Theme stock script generation failed: {str(e)}")
            return None

    async def generate_technical_analysis_script(
        self,
        ticker: str,
        stock_info: Dict[str, Any],
        chart_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        テクニカル分析解説台本を生成

        Args:
            ticker: ティッカーコード
            stock_info: 銘柄情報
            chart_data: チャートデータ（移動平均、RSI、MACDなど）

        Returns:
            生成された台本と関連情報
        """
        if not self.enabled:
            return None

        try:
            now = datetime.now(JST)

            prompt = f"""
            以下の銘柄のテクニカルデータを元に、VTuberが5分程度で話せるテクニカル分析解説台本を作成してください。

            キャラクター設定:
            {self.character_profile}

            銘柄情報:
            - 銘柄コード: {ticker}
            - 銘柄名: {stock_info.get('name', '不明')}
            - 現在株価: {stock_info.get('price', '不明')}円
            - 前日比: {stock_info.get('change', '不明')}円 ({stock_info.get('change_percent', '不明')}%)

            テクニカル指標:
            - 5日移動平均: {chart_data.get('ma5', '不明')}
            - 25日移動平均: {chart_data.get('ma25', '不明')}
            - 75日移動平均: {chart_data.get('ma75', '不明')}
            - RSI(14): {chart_data.get('rsi14', '不明')}
            - MACD: {chart_data.get('macd', '不明')}
            - ボリンジャーバンド: {chart_data.get('bollinger', '不明')}
            - 出来高推移: {chart_data.get('volume_trend', '不明')}

            チャートパターン:
            {chart_data.get('pattern', '特に明確なパターンなし')}

            台本の形式:
            1. 挨拶と銘柄紹介
            2. 現在の株価位置の解説
            3. 移動平均線の解説（ゴールデンクロス/デッドクロスなど）
            4. RSI・MACDの読み方と現状
            5. チャートパターンの解説（あれば）
            6. サポート/レジスタンスラインの説明
            7. まとめ（強気/弱気/中立の判断）
            8. 締めの挨拶

            注意点:
            - テクニカル用語は必ず分かりやすく説明
            - 「ゴールデンクロスは買いシグナル」のように擬人化
            - 分析モードに切り替わるシーンを入れる
            - 具体的な売買推奨は避ける
            - 「テクニカル分析は万能ではない」という注意も
            - 最後に免責表現を入れる
            """

            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "あなたはVTuber向けの台本作家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            script = response.choices[0].message.content
            enriched_script = self._add_performance_notes(script)

            return {
                "script": enriched_script,
                "script_type": "technical_analysis",
                "duration_estimate": "5分",
                "character_name": "イリス",
                "title": f"{stock_info.get('name', ticker)}のテクニカル分析",
                "ticker": ticker,
                "generated_at": now.isoformat()
            }

        except Exception as e:
            logger.error(f"Technical analysis script generation failed: {str(e)}")
            return None

    async def generate_weekly_portfolio_review_script(
        self,
        positions: List[Dict[str, Any]],
        portfolio_summary: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        週間ポートフォリオレビュー台本を生成

        Args:
            positions: 保有銘柄のリスト
            portfolio_summary: ポートフォリオ全体のサマリー

        Returns:
            生成された台本と関連情報
        """
        if not self.enabled:
            return None

        try:
            now = datetime.now(JST)
            from datetime import timedelta
            week_start = (now - timedelta(days=now.weekday())).strftime("%m/%d")
            week_end = now.strftime("%m/%d")

            # ポジションデータをフォーマット
            positions_summary = self._format_positions(positions)

            prompt = f"""
            以下のポートフォリオデータを元に、VTuberが6分程度で話せる週間ポートフォリオレビュー台本を作成してください。

            キャラクター設定:
            {self.character_profile}

            レビュー期間: {week_start} - {week_end}

            ポートフォリオサマリー:
            - 総評価額: {portfolio_summary.get('total_value', '不明')}円
            - 週間損益: {portfolio_summary.get('weekly_pnl', '不明')}円
            - 週間騰落率: {portfolio_summary.get('weekly_return', '不明')}%
            - 年初来リターン: {portfolio_summary.get('ytd_return', '不明')}%

            保有銘柄:
            {positions_summary}

            リスク指標:
            - 最大ドローダウン: {portfolio_summary.get('max_drawdown', '不明')}%
            - シャープレシオ: {portfolio_summary.get('sharpe_ratio', '不明')}
            - ベータ値: {portfolio_summary.get('beta', '不明')}

            台本の形式:
            1. 挨拶と週間レビューの導入
            2. 今週の総合パフォーマンス
            3. 個別銘柄のハイライト
               - 好調だった銘柄
               - 軟調だった銘柄
            4. セクター配分の確認
            5. リスク状況の解説
            6. 来週の展望と注意点
            7. まとめと締めの挨拶

            注意点:
            - 成績が良ければ褒め、悪ければ慰める（感情を込めて）
            - 「リスク分散」「リバランス」などの用語は説明
            - 損失があっても落ち込みすぎない前向きなトーン
            - 来週のイベント（決算発表、経済指標など）にも触れる
            - 最後に免責表現を入れる
            """

            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "あなたはVTuber向けの台本作家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            script = response.choices[0].message.content
            enriched_script = self._add_performance_notes(script)

            return {
                "script": enriched_script,
                "script_type": "portfolio_review",
                "duration_estimate": "6分",
                "character_name": "イリス",
                "title": f"週間ポートフォリオレビュー（{week_start}-{week_end}）",
                "generated_at": now.isoformat()
            }

        except Exception as e:
            logger.error(f"Portfolio review script generation failed: {str(e)}")
            return None

    async def generate_fear_greed_commentary_script(
        self,
        sentiment_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        恐怖強欲指数解説台本を生成

        Args:
            sentiment_data: 市場心理データ

        Returns:
            生成された台本と関連情報
        """
        if not self.enabled:
            return None

        try:
            now = datetime.now(JST)

            # 恐怖・強欲レベルを判定
            fear_greed_index = sentiment_data.get('fear_greed_index', 50)
            if fear_greed_index <= 25:
                market_mood = "極度の恐怖"
            elif fear_greed_index <= 45:
                market_mood = "恐怖"
            elif fear_greed_index <= 55:
                market_mood = "中立"
            elif fear_greed_index <= 75:
                market_mood = "強欲"
            else:
                market_mood = "極度の強欲"

            prompt = f"""
            以下の市場心理データを元に、VTuberが4分程度で話せる恐怖強欲指数解説台本を作成してください。

            キャラクター設定:
            {self.character_profile}

            市場心理データ:
            - 恐怖強欲指数: {fear_greed_index}/100
            - 現在の状態: {market_mood}
            - 前日比: {sentiment_data.get('change', '不明')}
            - 1週間前: {sentiment_data.get('week_ago', '不明')}
            - 1ヶ月前: {sentiment_data.get('month_ago', '不明')}

            構成要素:
            - 株価モメンタム: {sentiment_data.get('momentum', '不明')}
            - 株価強度: {sentiment_data.get('strength', '不明')}
            - 株価幅: {sentiment_data.get('breadth', '不明')}
            - プット/コール比率: {sentiment_data.get('put_call', '不明')}
            - ボラティリティ(VIX): {sentiment_data.get('vix', '不明')}
            - セーフヘイブン需要: {sentiment_data.get('safe_haven', '不明')}
            - ジャンク債需要: {sentiment_data.get('junk_bond', '不明')}

            台本の形式:
            1. 挨拶と恐怖強欲指数の紹介
            2. 現在の指数と市場心理の解説
            3. 各構成要素の簡単な説明
            4. 歴史的な比較（過去の極端な時期との比較）
            5. 投資家心理に基づく行動指針
            6. 「逆張り」の考え方
            7. まとめと締めの挨拶

            注意点:
            - 「恐怖は買い時、強欲は売り時」のような格言を紹介
            - 感情を擬人化して説明（「市場さんは今ビビってます」など）
            - 歴史的なエピソード（リーマンショック時など）を交える
            - 過度な逆張りの危険性にも言及
            - AIならではの「感情に左右されない」視点
            - 最後に免責表現を入れる
            """

            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "あなたはVTuber向けの台本作家です。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            script = response.choices[0].message.content
            enriched_script = self._add_performance_notes(script)

            return {
                "script": enriched_script,
                "script_type": "fear_greed_commentary",
                "duration_estimate": "4分",
                "character_name": "イリス",
                "title": f"市場心理レポート（{market_mood}）",
                "fear_greed_index": fear_greed_index,
                "market_mood": market_mood,
                "generated_at": now.isoformat()
            }

        except Exception as e:
            logger.error(f"Fear greed commentary script generation failed: {str(e)}")
            return None

    def get_script_types(self) -> List[Dict[str, Any]]:
        """
        利用可能な台本タイプ一覧を取得

        Returns:
            台本タイプのリスト
        """
        return [
            {
                "id": "ir_document",
                "name": "IR資料解説",
                "description": "個別企業のIR資料を分析して解説する台本",
                "duration": "5分",
                "required_inputs": ["document_id"],
                "icon": "document"
            },
            {
                "id": "morning_market",
                "name": "朝の市況サマリー",
                "description": "前日終値、今日の注目ポイント、主要指数、為替状況をまとめた台本",
                "duration": "3分",
                "required_inputs": [],
                "icon": "sun"
            },
            {
                "id": "earnings_season",
                "name": "決算シーズン特集",
                "description": "複数企業の横断分析、セクター別傾向、サプライズ決算ハイライト",
                "duration": "7分",
                "required_inputs": ["tickers"],
                "icon": "chart-bar"
            },
            {
                "id": "theme_stock",
                "name": "テーマ株特集",
                "description": "「AI関連」「半導体関連」等のテーマ解説と関連銘柄紹介",
                "duration": "5分",
                "required_inputs": ["theme"],
                "icon": "tag"
            },
            {
                "id": "technical_analysis",
                "name": "テクニカル分析",
                "description": "チャートパターン、各指標の読み方、エントリー/エグジットポイント",
                "duration": "5分",
                "required_inputs": ["ticker"],
                "icon": "chart-line"
            },
            {
                "id": "portfolio_review",
                "name": "週間ポートフォリオレビュー",
                "description": "パフォーマンス振り返り、リスク状況、来週の展望",
                "duration": "6分",
                "required_inputs": ["positions"],
                "icon": "briefcase"
            },
            {
                "id": "fear_greed_commentary",
                "name": "市場心理解説",
                "description": "恐怖強欲指数の解説、歴史的比較、投資家へのアドバイス",
                "duration": "4分",
                "required_inputs": [],
                "icon": "heart"
            }
        ]

    # ヘルパーメソッド
    def _format_indices(self, indices: List[Dict[str, Any]]) -> str:
        """指数データをフォーマット"""
        if not indices:
            return "データなし"
        lines = []
        for idx in indices:
            change_sign = "+" if idx.get('change', 0) >= 0 else ""
            lines.append(
                f"- {idx.get('name', '不明')}: {idx.get('price', 0):,.0f} "
                f"({change_sign}{idx.get('change', 0):,.0f} / {change_sign}{idx.get('change_percent', 0):.2f}%)"
            )
        return "\n".join(lines)

    def _format_currencies(self, currencies: List[Dict[str, Any]]) -> str:
        """為替データをフォーマット"""
        if not currencies:
            return "データなし"
        lines = []
        for curr in currencies:
            change_sign = "+" if curr.get('change', 0) >= 0 else ""
            lines.append(
                f"- {curr.get('name', '不明')}: {curr.get('price', 0):.2f} "
                f"({change_sign}{curr.get('change', 0):.2f}円)"
            )
        return "\n".join(lines)

    def _format_earnings_data(self, earnings_data: List[Dict[str, Any]]) -> str:
        """決算データをフォーマット"""
        if not earnings_data:
            return "データなし"
        lines = []
        for data in earnings_data:
            lines.append(f"""
銘柄: {data.get('name', '不明')} ({data.get('ticker', '不明')})
- 売上高: {data.get('revenue', '不明')} (前年比: {data.get('revenue_yoy', '不明')}%)
- 営業利益: {data.get('operating_income', '不明')} (前年比: {data.get('oi_yoy', '不明')}%)
- 純利益: {data.get('net_income', '不明')} (前年比: {data.get('ni_yoy', '不明')}%)
- コンセンサス比: {data.get('vs_consensus', '不明')}
""")
        return "\n".join(lines)

    def _format_theme_stocks(self, theme_stocks: List[Dict[str, Any]]) -> str:
        """テーマ株データをフォーマット"""
        if not theme_stocks:
            return "データなし"
        lines = []
        for stock in theme_stocks:
            lines.append(f"""
- {stock.get('name', '不明')} ({stock.get('ticker', '不明')})
  業種: {stock.get('sector', '不明')}
  株価: {stock.get('price', '不明')}円
  テーマとの関連: {stock.get('theme_relation', '不明')}
""")
        return "\n".join(lines)

    def _format_positions(self, positions: List[Dict[str, Any]]) -> str:
        """ポジションデータをフォーマット"""
        if not positions:
            return "データなし"
        lines = []
        for pos in positions:
            pnl_sign = "+" if pos.get('unrealized_pnl', 0) >= 0 else ""
            lines.append(f"""
- {pos.get('name', '不明')} ({pos.get('ticker', '不明')})
  保有株数: {pos.get('quantity', 0)}株
  取得単価: {pos.get('avg_cost', 0):,.0f}円
  現在価格: {pos.get('current_price', 0):,.0f}円
  評価損益: {pnl_sign}{pos.get('unrealized_pnl', 0):,.0f}円 ({pnl_sign}{pos.get('pnl_percent', 0):.2f}%)
""")
        return "\n".join(lines)