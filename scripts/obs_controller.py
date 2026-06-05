"""
OBS WebSocket コントローラー

obsws-python を使って OBS Studio を制御:
- ブラウザソース設定（aituber-kit URL）
- ストリームキー設定
- 配信開始/停止

Prerequisites:
    pip install obsws-python>=1.7.0
    OBS Studio で WebSocket Server を有効化（ツール > WebSocket Server Settings）
"""

import logging
import time

import obsws_python as obs

logger = logging.getLogger(__name__)

DEFAULT_OBS_HOST = "localhost"
DEFAULT_OBS_PORT = 4455
DEFAULT_OBS_PASSWORD = ""

BROWSER_SOURCE_NAME = "aituber-kit"
AITUBER_KIT_URL = "http://localhost:3000"


class OBSController:
    """OBS Studio をWebSocket経由で制御"""

    def __init__(
        self,
        host: str = DEFAULT_OBS_HOST,
        port: int = DEFAULT_OBS_PORT,
        password: str = DEFAULT_OBS_PASSWORD,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.client = None

    def connect(self, retries: int = 3, retry_delay: float = 5.0):
        """OBS WebSocket に接続（リトライ付き）"""
        last_error = None
        for attempt in range(retries):
            try:
                self.client = obs.ReqClient(
                    host=self.host,
                    port=self.port,
                    password=self.password if self.password else None,
                )
                version = self.client.get_version()
                logger.info(
                    f"Connected to OBS {version.obs_version} "
                    f"(WebSocket {version.obs_web_socket_version})"
                )
                return self
            except Exception as e:
                last_error = e
                self.client = None
                if attempt < retries - 1:
                    logger.warning(
                        f"OBS connection failed (attempt {attempt + 1}/{retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
        raise ConnectionError(f"Failed to connect to OBS after {retries} attempts: {last_error}")

    def reconnect(self):
        """再接続を試行"""
        logger.info("Attempting OBS reconnection...")
        self.client = None
        return self.connect()

    def disconnect(self):
        """切断"""
        if self.client:
            self.client = None
            logger.info("Disconnected from OBS")

    def _ensure_connected(self):
        if not self.client:
            raise RuntimeError("Not connected to OBS. Call connect() first.")
        # 接続が切れていないか確認し、切れていたら再接続
        try:
            self.client.get_version()
        except Exception:
            logger.warning("OBS connection lost, attempting reconnection...")
            self.reconnect()

    # ------------------------------------------------------------------
    # ブラウザソース管理
    # ------------------------------------------------------------------

    def setup_browser_source(
        self,
        url: str = AITUBER_KIT_URL,
        width: int = 1920,
        height: int = 1080,
        scene_name: str | None = None,
        source_name: str = BROWSER_SOURCE_NAME,
    ):
        """
        ブラウザソースを設定（既存なら更新、なければ作成）
        """
        self._ensure_connected()

        # 対象シーンを取得（指定なければ現在のシーン）
        if scene_name is None:
            current = self.client.get_current_program_scene()
            scene_name = current.scene_name

        # ソースが存在するか確認
        try:
            self.client.get_input_settings(source_name)
            # 存在する → 設定を更新
            self.client.set_input_settings(
                name=source_name,
                settings={"url": url, "width": width, "height": height},
                overlay=True,
            )
            logger.info(f"Updated browser source '{source_name}' → {url}")
        except Exception:
            # 存在しない → 新規作成
            self.client.create_input(
                scene_name=scene_name,
                input_name=source_name,
                input_kind="browser_source",
                input_settings={
                    "url": url,
                    "width": width,
                    "height": height,
                    "reroute_audio": True,
                },
                scene_item_enabled=True,
            )
            logger.info(f"Created browser source '{source_name}' → {url}")

    # ------------------------------------------------------------------
    # ストリーム設定
    # ------------------------------------------------------------------

    def set_stream_settings(
        self,
        server: str = "rtmp://a.rtmp.youtube.com/live2",
        stream_key: str = "",
    ):
        """RTMP ストリーム設定"""
        self._ensure_connected()

        self.client.set_stream_service_settings(
            ss_type="rtmp_custom",
            ss_settings={
                "server": server,
                "key": stream_key,
            },
        )
        logger.info(f"Stream settings configured (server: {server})")

    def set_youtube_stream_key(self, stream_key: str):
        """YouTube Live 用のストリームキーを設定"""
        self.set_stream_settings(
            server="rtmp://a.rtmp.youtube.com/live2",
            stream_key=stream_key,
        )

    # ------------------------------------------------------------------
    # 配信制御
    # ------------------------------------------------------------------

    def start_streaming(self):
        """配信を開始"""
        self._ensure_connected()
        self.client.start_stream()
        logger.info("OBS streaming started")

    def stop_streaming(self):
        """配信を停止"""
        self._ensure_connected()
        self.client.stop_stream()
        logger.info("OBS streaming stopped")

    def is_streaming(self) -> bool:
        """配信中かどうか"""
        self._ensure_connected()
        status = self.client.get_stream_status()
        return status.output_active

    def start_recording(self):
        """録画を開始"""
        self._ensure_connected()
        self.client.start_record()
        logger.info("OBS recording started")

    def stop_recording(self):
        """録画を停止"""
        self._ensure_connected()
        self.client.stop_record()
        logger.info("OBS recording stopped")

    # ------------------------------------------------------------------
    # エンドツーエンド
    # ------------------------------------------------------------------

    def setup_and_start(
        self,
        stream_key: str,
        aituber_url: str = AITUBER_KIT_URL,
    ):
        """
        ブラウザソース設定 → ストリームキー設定 → 配信開始

        Args:
            stream_key: YouTube Live ストリームキー
            aituber_url: aituber-kit の URL
        """
        self.setup_browser_source(url=aituber_url)
        self.set_youtube_stream_key(stream_key)

        # ブラウザソースの読み込みを待つ
        logger.info("Waiting for browser source to load...")
        time.sleep(5)

        self.start_streaming()
        logger.info("OBS setup complete and streaming")

    def teardown(self):
        """配信停止 + 切断"""
        try:
            if self.is_streaming():
                self.stop_streaming()
        except Exception as e:
            logger.warning(f"Error stopping stream: {e}")
        self.disconnect()
