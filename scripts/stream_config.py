"""
配信タイプ別設定
"""

STREAM_CONFIGS = {
    "morning_market": {
        "title_template": "{date} 朝の市況サマリー｜イリスのIR分析",
        "description": "平日朝の市況サマリー配信",
        "duration_minutes": 10,
        "segment_delay": 6,  # セグメント間の待機秒数
        "comment_interaction_minutes": 5,  # コメント対応時間
        "chars_per_second": 5,  # 日本語発話速度（文字/秒）
        "privacy_status": "public",
        "tags": ["IR分析", "株式投資", "市況", "イリス", "AIVTuber", "朝の市況"],
        "category_id": "22",  # People & Blogs
    },
    "ir_analysis": {
        "title_template": "{company_name} IR分析｜イリスのIR分析",
        "description": "新規IR発表の分析配信",
        "duration_minutes": 15,
        "segment_delay": 8,
        "comment_interaction_minutes": 10,
        "chars_per_second": 5,
        "privacy_status": "public",
        "tags": ["IR分析", "決算", "株式投資", "企業分析", "イリス", "AIVTuber"],
        "category_id": "22",
    },
    "weekly_summary": {
        "title_template": "{date} 週間マーケットまとめ｜イリスのIR分析",
        "description": "日曜日の週間マーケットまとめ配信",
        "duration_minutes": 25,
        "segment_delay": 8,
        "comment_interaction_minutes": 10,
        "chars_per_second": 5,
        "privacy_status": "public",
        "tags": ["IR分析", "週間まとめ", "株式投資", "マーケット", "イリス", "AIVTuber"],
        "category_id": "22",
    },
    "trading_challenge": {
        "title_template": "Day{day_number} クオンツAIトレーディング実況｜イリス",
        "description": "AIに10万円を渡して日本株を自動運用。ML予測+PCA+テクニカル指標のクオンツ戦略で毎日実況します。",
        "duration_minutes": 12,
        "segment_delay": 7,
        "comment_interaction_minutes": 8,
        "chars_per_second": 5,
        "privacy_status": "public",
        "tags": ["AIトレーディング", "クオンツ", "株式投資", "日本株", "イリス", "AIVTuber", "自動売買"],
        "category_id": "22",
    },
}

# aituber-kit API endpoint
AITUBER_KIT_URL = "http://localhost:3000"
AITUBER_KIT_MESSAGE_API = f"{AITUBER_KIT_URL}/api/messages"
