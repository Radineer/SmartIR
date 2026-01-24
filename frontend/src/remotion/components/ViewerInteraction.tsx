import React from "react";
import {
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
  Easing,
} from "remotion";

// インタラクションタイプの定義
export type InteractionType = "comment" | "poll" | "quiz" | "preview" | "cta";

// コメントデータの型
interface CommentData {
  username: string;
  text: string;
  avatar?: string;
}

// 投票オプションの型
interface PollOption {
  label: string;
  value: number; // パーセンテージ
  color?: string;
}

// クイズデータの型
interface QuizData {
  question: string;
  options: { label: string; text: string }[];
  correctIndex: number;
  showAnswer: boolean;
}

// 次回予告データの型
interface PreviewData {
  title: string;
  description?: string;
  thumbnail?: string;
}

// CTAデータの型
interface CTAData {
  mainText: string;
  subText?: string;
  showArrow?: boolean;
}

// ViewerInteractionのプロパティ
interface ViewerInteractionProps {
  interactionType: InteractionType;
  // コメント表示用
  comments?: CommentData[];
  irisResponse?: string;
  // 投票・アンケート用
  pollTitle?: string;
  pollOptions?: PollOption[];
  // クイズ用
  quizData?: QuizData;
  // 次回予告用
  previewData?: PreviewData;
  // CTA用
  ctaData?: CTAData;
  // 共通
  startFrame?: number;
  durationFrames?: number;
}

// バウンスアニメーション用のヘルパー
const bounceIn = (
  frame: number,
  fps: number,
  delay: number = 0
): number => {
  return spring({
    frame: Math.max(0, frame - delay),
    fps,
    config: {
      damping: 8,
      stiffness: 120,
      mass: 0.8,
    },
  });
};

// スライドインアニメーション用のヘルパー
const slideIn = (
  frame: number,
  startFrame: number,
  endFrame: number,
  fromValue: number,
  toValue: number
): number => {
  return interpolate(frame, [startFrame, endFrame], [fromValue, toValue], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
};

// コメント表示コンポーネント
const CommentSection: React.FC<{
  comments: CommentData[];
  irisResponse?: string;
  frame: number;
  fps: number;
}> = ({ comments, irisResponse, frame, fps }) => {
  return (
    <div
      style={{
        position: "absolute",
        top: 80,
        left: 60,
        width: 500,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      {/* セクションタイトル */}
      <div
        style={{
          opacity: interpolate(frame, [0, 15], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          transform: `translateY(${slideIn(frame, 0, 20, -30, 0)}px)`,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 20,
          }}
        >
          <div
            style={{
              width: 8,
              height: 32,
              background: "linear-gradient(180deg, #667eea, #764ba2)",
              borderRadius: 4,
            }}
          />
          <h2
            style={{
              margin: 0,
              fontSize: 28,
              fontWeight: "bold",
              color: "white",
              textShadow: "0 2px 10px rgba(0,0,0,0.5)",
            }}
          >
            視聴者からの質問
          </h2>
        </div>
      </div>

      {/* コメントリスト */}
      {comments.map((comment, index) => {
        const delay = 20 + index * 15;
        const bounce = bounceIn(frame, fps, delay);
        const opacity = interpolate(frame, [delay, delay + 10], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        return (
          <div
            key={index}
            style={{
              opacity,
              transform: `scale(${bounce}) translateX(${slideIn(frame, delay, delay + 20, -50, 0)}px)`,
              background: "rgba(255, 255, 255, 0.1)",
              backdropFilter: "blur(10px)",
              borderRadius: 16,
              padding: 16,
              border: "1px solid rgba(255, 255, 255, 0.15)",
              boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginBottom: 8,
              }}
            >
              {/* アバター */}
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: "50%",
                  background: `linear-gradient(135deg, hsl(${index * 60}, 70%, 60%), hsl(${index * 60 + 40}, 70%, 50%))`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 18,
                  fontWeight: "bold",
                  color: "white",
                }}
              >
                {comment.username.charAt(0)}
              </div>
              <span
                style={{
                  color: "rgba(255, 255, 255, 0.8)",
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                {comment.username}
              </span>
            </div>
            <p
              style={{
                margin: 0,
                color: "white",
                fontSize: 16,
                lineHeight: 1.5,
              }}
            >
              {comment.text}
            </p>
          </div>
        );
      })}

      {/* イリスの回答 */}
      {irisResponse && (
        <div
          style={{
            opacity: interpolate(
              frame,
              [40 + comments.length * 15, 55 + comments.length * 15],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            ),
            transform: `translateY(${slideIn(frame, 40 + comments.length * 15, 60 + comments.length * 15, 30, 0)}px)`,
            marginTop: 16,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
              background: "linear-gradient(135deg, rgba(102, 126, 234, 0.3), rgba(118, 75, 162, 0.3))",
              backdropFilter: "blur(10px)",
              borderRadius: 16,
              padding: 20,
              border: "1px solid rgba(102, 126, 234, 0.4)",
              boxShadow: "0 4px 20px rgba(102, 126, 234, 0.2)",
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "50%",
                background: "linear-gradient(135deg, #667eea, #764ba2)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
                flexShrink: 0,
              }}
            >
              AI
            </div>
            <div>
              <span
                style={{
                  color: "#667eea",
                  fontSize: 14,
                  fontWeight: 600,
                  display: "block",
                  marginBottom: 6,
                }}
              >
                イリス
              </span>
              <p
                style={{
                  margin: 0,
                  color: "white",
                  fontSize: 16,
                  lineHeight: 1.6,
                }}
              >
                {irisResponse}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// 投票・アンケート表示コンポーネント
const PollSection: React.FC<{
  title: string;
  options: PollOption[];
  frame: number;
  fps: number;
}> = ({ title, options, frame, fps }) => {
  const defaultColors = ["#667eea", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6"];

  return (
    <div
      style={{
        position: "absolute",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: 600,
      }}
    >
      {/* タイトル */}
      <div
        style={{
          opacity: interpolate(frame, [0, 15], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          transform: `scale(${bounceIn(frame, fps, 0)})`,
          textAlign: "center",
          marginBottom: 40,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: "bold",
            color: "white",
            textShadow: "0 2px 10px rgba(0,0,0,0.5)",
          }}
        >
          {title}
        </h2>
      </div>

      {/* 投票バー */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 20,
          background: "rgba(255, 255, 255, 0.08)",
          backdropFilter: "blur(20px)",
          borderRadius: 24,
          padding: 32,
          border: "1px solid rgba(255, 255, 255, 0.1)",
          boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
        }}
      >
        {options.map((option, index) => {
          const delay = 15 + index * 12;
          const barProgress = interpolate(
            frame,
            [delay, delay + 40],
            [0, option.value],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          const opacity = interpolate(frame, [delay, delay + 10], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const color = option.color || defaultColors[index % defaultColors.length];

          return (
            <div
              key={index}
              style={{
                opacity,
                transform: `translateX(${slideIn(frame, delay, delay + 15, -30, 0)}px)`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 8,
                }}
              >
                <span
                  style={{
                    color: "white",
                    fontSize: 18,
                    fontWeight: 600,
                  }}
                >
                  {option.label}
                </span>
                <span
                  style={{
                    color: color,
                    fontSize: 18,
                    fontWeight: "bold",
                    fontFamily: "monospace",
                  }}
                >
                  {Math.round(barProgress)}%
                </span>
              </div>
              {/* バー背景 */}
              <div
                style={{
                  width: "100%",
                  height: 24,
                  background: "rgba(255, 255, 255, 0.1)",
                  borderRadius: 12,
                  overflow: "hidden",
                }}
              >
                {/* バー本体 */}
                <div
                  style={{
                    width: `${barProgress}%`,
                    height: "100%",
                    background: `linear-gradient(90deg, ${color}, ${color}dd)`,
                    borderRadius: 12,
                    boxShadow: `0 0 20px ${color}66`,
                    transition: "none",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* 投票数表示 */}
      <div
        style={{
          textAlign: "center",
          marginTop: 20,
          opacity: interpolate(frame, [60, 75], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <span
          style={{
            color: "rgba(255, 255, 255, 0.6)",
            fontSize: 14,
          }}
        >
          {Math.floor(1000 + Math.random() * 500)}票の投票がありました
        </span>
      </div>
    </div>
  );
};

// クイズ演出コンポーネント
const QuizSection: React.FC<{
  data: QuizData;
  frame: number;
  fps: number;
}> = ({ data, frame, fps }) => {
  const showAnswerFrame = 60; // 正解発表までのフレーム

  return (
    <div
      style={{
        position: "absolute",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: 700,
      }}
    >
      {/* 質問 */}
      <div
        style={{
          opacity: interpolate(frame, [0, 15], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          transform: `scale(${bounceIn(frame, fps, 0)})`,
          textAlign: "center",
          marginBottom: 50,
        }}
      >
        <div
          style={{
            display: "inline-block",
            background: "linear-gradient(135deg, rgba(102, 126, 234, 0.4), rgba(118, 75, 162, 0.4))",
            backdropFilter: "blur(10px)",
            borderRadius: 16,
            padding: "16px 32px",
            border: "1px solid rgba(102, 126, 234, 0.5)",
            marginBottom: 20,
          }}
        >
          <span
            style={{
              color: "#667eea",
              fontSize: 16,
              fontWeight: "bold",
              letterSpacing: "0.1em",
            }}
          >
            QUIZ
          </span>
        </div>
        <h2
          style={{
            margin: 0,
            fontSize: 32,
            fontWeight: "bold",
            color: "white",
            textShadow: "0 2px 10px rgba(0,0,0,0.5)",
            lineHeight: 1.4,
          }}
        >
          {data.question}
        </h2>
      </div>

      {/* 選択肢 */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: 30,
        }}
      >
        {data.options.map((option, index) => {
          const delay = 20 + index * 10;
          const isCorrect = index === data.correctIndex;
          const showAnswer = data.showAnswer && frame > showAnswerFrame;
          const bounce = bounceIn(frame, fps, delay);

          // 正解発表時のアニメーション
          const answerScale = showAnswer && isCorrect
            ? 1 + Math.sin(frame * 0.2) * 0.05
            : 1;
          const answerGlow = showAnswer && isCorrect
            ? `0 0 30px rgba(34, 197, 94, 0.6)`
            : "0 4px 20px rgba(0,0,0,0.3)";

          return (
            <div
              key={index}
              style={{
                opacity: interpolate(frame, [delay, delay + 10], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                }),
                transform: `scale(${bounce * answerScale})`,
              }}
            >
              <div
                style={{
                  width: 200,
                  height: 120,
                  background: showAnswer
                    ? isCorrect
                      ? "linear-gradient(135deg, rgba(34, 197, 94, 0.4), rgba(22, 163, 74, 0.4))"
                      : "rgba(255, 255, 255, 0.05)"
                    : "rgba(255, 255, 255, 0.1)",
                  backdropFilter: "blur(10px)",
                  borderRadius: 20,
                  border: showAnswer && isCorrect
                    ? "3px solid #22c55e"
                    : "1px solid rgba(255, 255, 255, 0.15)",
                  boxShadow: answerGlow,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  transition: "none",
                }}
              >
                <span
                  style={{
                    fontSize: 36,
                    fontWeight: "bold",
                    color: showAnswer && isCorrect ? "#22c55e" : "#667eea",
                    marginBottom: 8,
                  }}
                >
                  {option.label}
                </span>
                <span
                  style={{
                    fontSize: 16,
                    color: showAnswer
                      ? isCorrect
                        ? "#22c55e"
                        : "rgba(255, 255, 255, 0.4)"
                      : "white",
                    fontWeight: 500,
                  }}
                >
                  {option.text}
                </span>

                {/* 正解マーク */}
                {showAnswer && isCorrect && (
                  <div
                    style={{
                      position: "absolute",
                      top: -15,
                      right: -15,
                      width: 40,
                      height: 40,
                      background: "#22c55e",
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      boxShadow: "0 4px 15px rgba(34, 197, 94, 0.5)",
                      transform: `scale(${bounceIn(frame, fps, showAnswerFrame)})`,
                    }}
                  >
                    <span style={{ fontSize: 24, color: "white" }}>O</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 正解発表テキスト */}
      {data.showAnswer && frame > showAnswerFrame && (
        <div
          style={{
            textAlign: "center",
            marginTop: 40,
            opacity: interpolate(frame, [showAnswerFrame, showAnswerFrame + 15], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            transform: `scale(${bounceIn(frame, fps, showAnswerFrame)})`,
          }}
        >
          <span
            style={{
              fontSize: 28,
              fontWeight: "bold",
              color: "#22c55e",
              textShadow: "0 0 20px rgba(34, 197, 94, 0.5)",
            }}
          >
            正解は {data.options[data.correctIndex].label}！
          </span>
        </div>
      )}
    </div>
  );
};

// 次回予告コンポーネント
const PreviewSection: React.FC<{
  data: PreviewData;
  frame: number;
  fps: number;
}> = ({ data, frame, fps }) => {
  return (
    <div
      style={{
        position: "absolute",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: 700,
        textAlign: "center",
      }}
    >
      {/* 次回予告タイトル */}
      <div
        style={{
          opacity: interpolate(frame, [0, 15], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          transform: `translateY(${slideIn(frame, 0, 20, -30, 0)}px)`,
          marginBottom: 40,
        }}
      >
        <span
          style={{
            fontSize: 20,
            color: "rgba(255, 255, 255, 0.7)",
            letterSpacing: "0.2em",
            fontWeight: 500,
          }}
        >
          NEXT EPISODE
        </span>
        <h2
          style={{
            margin: "10px 0 0 0",
            fontSize: 28,
            fontWeight: "bold",
            color: "#667eea",
            textShadow: "0 0 20px rgba(102, 126, 234, 0.5)",
          }}
        >
          次回のテーマ
        </h2>
      </div>

      {/* サムネイルプレビュー */}
      <div
        style={{
          opacity: interpolate(frame, [15, 30], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          transform: `scale(${bounceIn(frame, fps, 15)})`,
        }}
      >
        <div
          style={{
            width: "100%",
            aspectRatio: "16/9",
            background: data.thumbnail
              ? `url(${data.thumbnail}) center/cover`
              : `
                linear-gradient(135deg, rgba(102, 126, 234, 0.4), rgba(118, 75, 162, 0.4)),
                linear-gradient(45deg, #1a1a2e, #0f0f1a)
              `,
            borderRadius: 24,
            border: "2px solid rgba(102, 126, 234, 0.5)",
            boxShadow: "0 8px 40px rgba(0,0,0,0.4), 0 0 60px rgba(102, 126, 234, 0.2)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 40,
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* 装飾パターン */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `
                radial-gradient(circle at 20% 30%, rgba(102, 126, 234, 0.3) 0%, transparent 40%),
                radial-gradient(circle at 80% 70%, rgba(118, 75, 162, 0.3) 0%, transparent 40%)
              `,
            }}
          />

          {/* 再生ボタン風アイコン */}
          <div
            style={{
              width: 80,
              height: 80,
              borderRadius: "50%",
              background: "rgba(255, 255, 255, 0.2)",
              backdropFilter: "blur(10px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 24,
              border: "2px solid rgba(255, 255, 255, 0.3)",
              transform: `scale(${1 + Math.sin(frame * 0.1) * 0.05})`,
            }}
          >
            <div
              style={{
                width: 0,
                height: 0,
                borderLeft: "24px solid white",
                borderTop: "14px solid transparent",
                borderBottom: "14px solid transparent",
                marginLeft: 6,
              }}
            />
          </div>

          <h3
            style={{
              margin: 0,
              fontSize: 36,
              fontWeight: "bold",
              color: "white",
              textShadow: "0 2px 20px rgba(0,0,0,0.5)",
              zIndex: 1,
            }}
          >
            {data.title}
          </h3>

          {data.description && (
            <p
              style={{
                margin: "16px 0 0 0",
                fontSize: 18,
                color: "rgba(255, 255, 255, 0.8)",
                zIndex: 1,
              }}
            >
              {data.description}
            </p>
          )}
        </div>
      </div>

      {/* お楽しみに！テキスト */}
      <div
        style={{
          marginTop: 40,
          opacity: interpolate(frame, [45, 60], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          transform: `scale(${bounceIn(frame, fps, 45)})`,
        }}
      >
        <span
          style={{
            fontSize: 32,
            fontWeight: "bold",
            color: "white",
            textShadow: `
              0 0 ${10 + Math.sin(frame * 0.1) * 5}px rgba(102, 126, 234, 0.8),
              0 0 ${20 + Math.sin(frame * 0.1) * 10}px rgba(118, 75, 162, 0.5)
            `,
            letterSpacing: "0.1em",
          }}
        >
          お楽しみに！
        </span>
      </div>
    </div>
  );
};

// CTAコンポーネント
const CTASection: React.FC<{
  data: CTAData;
  frame: number;
  fps: number;
}> = ({ data, frame, fps }) => {
  // 矢印のアニメーション
  const arrowBounce = interpolate(
    Math.sin(frame * 0.15),
    [-1, 1],
    [0, 15]
  );

  return (
    <div
      style={{
        position: "absolute",
        bottom: 120,
        left: "50%",
        transform: "translateX(-50%)",
        textAlign: "center",
      }}
    >
      {/* メインテキスト */}
      <div
        style={{
          opacity: interpolate(frame, [0, 15], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          transform: `scale(${bounceIn(frame, fps, 0)})`,
        }}
      >
        <div
          style={{
            display: "inline-block",
            background: "linear-gradient(135deg, rgba(102, 126, 234, 0.3), rgba(118, 75, 162, 0.3))",
            backdropFilter: "blur(20px)",
            borderRadius: 24,
            padding: "24px 48px",
            border: "2px solid rgba(102, 126, 234, 0.5)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.3), 0 0 40px rgba(102, 126, 234, 0.2)",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 28,
              fontWeight: "bold",
              color: "white",
              textShadow: "0 2px 10px rgba(0,0,0,0.5)",
            }}
          >
            {data.mainText}
          </p>

          {data.subText && (
            <p
              style={{
                margin: "12px 0 0 0",
                fontSize: 18,
                color: "rgba(255, 255, 255, 0.8)",
              }}
            >
              {data.subText}
            </p>
          )}
        </div>
      </div>

      {/* 矢印アニメーション（コメント欄を指す） */}
      {data.showArrow && (
        <div
          style={{
            marginTop: 30,
            opacity: interpolate(frame, [20, 35], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            transform: `translateY(${arrowBounce}px)`,
          }}
        >
          <svg
            width={60}
            height={60}
            viewBox="0 0 60 60"
            style={{
              filter: "drop-shadow(0 4px 10px rgba(102, 126, 234, 0.5))",
            }}
          >
            <defs>
              <linearGradient id="arrowGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#667eea" />
                <stop offset="100%" stopColor="#764ba2" />
              </linearGradient>
            </defs>
            <path
              d="M30 5 L30 45 M15 35 L30 50 L45 35"
              stroke="url(#arrowGradient)"
              strokeWidth={4}
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          </svg>
        </div>
      )}
    </div>
  );
};

// メインコンポーネント
export const ViewerInteraction: React.FC<ViewerInteractionProps> = ({
  interactionType,
  comments = [],
  irisResponse,
  pollTitle = "今週の注目銘柄は？",
  pollOptions = [
    { label: "A. トヨタ自動車", value: 45 },
    { label: "B. ソニーグループ", value: 35 },
    { label: "C. ファーストリテイリング", value: 20 },
  ],
  quizData = {
    question: "この銘柄の決算、良かった？悪かった？",
    options: [
      { label: "A", text: "良かった" },
      { label: "B", text: "悪かった" },
    ],
    correctIndex: 0,
    showAnswer: true,
  },
  previewData = {
    title: "決算解説シリーズ",
    description: "注目企業の最新決算を徹底分析",
  },
  ctaData = {
    mainText: "コメント欄で教えてください！",
    subText: "気になる銘柄があればリクエストを！",
    showArrow: true,
  },
  startFrame = 0,
  durationFrames = 90,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 相対フレーム計算
  const relativeFrame = Math.max(0, frame - startFrame);

  // フェードイン/アウト
  const fadeIn = interpolate(relativeFrame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const fadeOut = interpolate(
    relativeFrame,
    [durationFrames - 15, durationFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const opacity = Math.min(fadeIn, fadeOut);

  // インタラクションタイプに応じたコンテンツをレンダリング
  const renderContent = () => {
    switch (interactionType) {
      case "comment":
        return (
          <CommentSection
            comments={comments.length > 0 ? comments : [
              { username: "株式投資家A", text: "この銘柄の今後の見通しはどうですか？" },
              { username: "初心者トレーダー", text: "PERの見方がよく分かりません..." },
            ]}
            irisResponse={irisResponse || "良い質問ですね！詳しく解説していきましょう。"}
            frame={relativeFrame}
            fps={fps}
          />
        );

      case "poll":
        return (
          <PollSection
            title={pollTitle}
            options={pollOptions}
            frame={relativeFrame}
            fps={fps}
          />
        );

      case "quiz":
        return (
          <QuizSection
            data={quizData}
            frame={relativeFrame}
            fps={fps}
          />
        );

      case "preview":
        return (
          <PreviewSection
            data={previewData}
            frame={relativeFrame}
            fps={fps}
          />
        );

      case "cta":
        return (
          <CTASection
            data={ctaData}
            frame={relativeFrame}
            fps={fps}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        opacity,
        pointerEvents: "none",
      }}
    >
      {renderContent()}
    </div>
  );
};

export default ViewerInteraction;
